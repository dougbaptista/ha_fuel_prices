import logging
import re
import unicodedata
from datetime import timedelta
from io import BytesIO

from bs4 import BeautifulSoup
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (CoordinatorEntity,
                                                      DataUpdateCoordinator,
                                                      UpdateFailed)
from openpyxl import load_workbook

from .const import DOMAIN

BASE_URL = (
    "https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/"
    "precos/levantamento-de-precos-de-combustiveis-ultimas-semanas-pesquisadas"
)
logger = logging.getLogger(__name__)

# Intervalo de atualização: dados da ANP são semanais, 6 horas é mais que suficiente
UPDATE_INTERVAL = timedelta(hours=6)


def normalize_text(text: str) -> str:
    """Remove acentos, converte para ASCII, remove espaços e coloca em uppercase."""
    if not isinstance(text, str):
        text = str(text)
    normalized = unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("utf-8")
    return normalized.upper().strip()


def make_unique_id(fuel_type: str, price_type: str, city: str) -> str:
    base = f"{fuel_type}_{price_type}_{city}"
    # Normalize to ascii lowercase and underscores
    return normalize_text(base).lower().replace(" ", "_")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Configuração inicial do sensor no Home Assistant."""

    coordinator = FuelPriceCoordinator(hass, entry.data)
    # Salva o coordinator para referência futura
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await coordinator.async_config_entry_first_refresh()

    fuel_types = [
        "ETANOL HIDRATADO",
        "GASOLINA COMUM",
        "GASOLINA ADITIVADA",
        "GLP",
        "GNV",
        "OLEO DIESEL",
        "OLEO DIESEL S10",
    ]
    sensors = []
    price_type_names = {"min": "Mínimo", "med": "Médio", "max": "Máximo"}

    for fuel in fuel_types:
        for pt in ["min", "med", "max"]:
            city = entry.data.get("city", "TUBARAO").title()
            sensor_name = f"Preço {fuel.title()} ({city}) - {price_type_names[pt]}"
            sensors.append(FuelPriceSensor(coordinator, entry.data, fuel, pt, sensor_name))

    async_add_entities(sensors)


class FuelPriceCoordinator(DataUpdateCoordinator):
    """Coordenador que busca os dados da ANP uma única vez e compartilha com todos os sensores."""

    def __init__(self, hass: HomeAssistant, config: dict):
        super().__init__(
            hass,
            logger,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self._config = config
        self.hass = hass

    async def _async_update_data(self) -> dict:
        """Busca os dados da ANP. Retorna dicionário de preços por combustível."""
        try:
            xls_url = await fetch_latest_xls_url(self.hass)
            if not xls_url:
                raise UpdateFailed("Não foi possível encontrar a URL XLS mais recente.")

            prices = await download_and_extract_sc_prices(xls_url, self._config, self.hass)
            if not prices:
                raise UpdateFailed(
                    f"Nenhum dado retornado para "
                    f"{self._config.get('state', '')} / {self._config.get('city', '')}"
                )
            return prices
        except UpdateFailed:
            raise
        except Exception as e:
            logger.exception("Erro ao atualizar dados da ANP")
            raise UpdateFailed(f"Erro ao buscar dados da ANP: {e}") from e


class FuelPriceSensor(CoordinatorEntity, SensorEntity):
    """Sensor de preço de combustível para um tipo específico de preço."""

    def __init__(self, coordinator: FuelPriceCoordinator, config: dict, fuel_type: str, price_type: str, sensor_name: str):
        super().__init__(coordinator)
        self.coordinator: FuelPriceCoordinator = coordinator
        self._fuel_type = fuel_type
        self._price_type = price_type
        self._config = config
        self._attr_name = sensor_name
        self._attr_unique_id = make_unique_id(fuel_type, price_type, config.get('city', ''))
        self._attr_unit_of_measurement = "BRL/L" if fuel_type != "GLP" else "BRL/kg"
        self._attr_extra_state_attributes = {}

        # Ícones por tipo de combustível
        icon_map = {
            "ETANOL HIDRATADO": "mdi:gas-station",
            "GASOLINA COMUM": "mdi:gas-station",
            "GASOLINA ADITIVADA": "mdi:gas-station",
            "GLP": "mdi:gas-cylinder",
            "GNV": "mdi:gas-cylinder",
            "OLEO DIESEL": "mdi:oil",
            "OLEO DIESEL S10": "mdi:oil",
        }
        self._attr_icon = icon_map.get(fuel_type, "mdi:cash")

    @property
    def available(self) -> bool:
        """Sensor disponível se o coordinator tiver dados."""
        return self.coordinator.last_update_success or bool(self.coordinator.data)

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        price_info = data.get(self._fuel_type)
        if price_info:
            value = price_info.get(self._price_type)
            # Atualiza atributos extras
            self._attr_extra_state_attributes = {
                "min": price_info.get("min"),
                "med": price_info.get("med"),
                "max": price_info.get("max"),
            }
            return value
        return None


async def fetch_latest_xls_url(hass: HomeAssistant):
    """Busca a URL do último XLS cujo link contenha o texto esperado."""
    session = async_get_clientsession(hass)
    try:
        async with session.get(BASE_URL, timeout=30) as response:
            if response.status != 200:
                raise ValueError(f"Falha ao acessar a página da ANP: {response.status}")
            html = await response.text()
    except Exception as e:
        logger.exception("Erro ao buscar página da ANP")
        raise

    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all("a", text=re.compile(
        r"Preços médios semanais: Brasil, regiões, estados e municípios"
    ))
    if not links:
        return None
    latest_link = links[0]["href"]
    if latest_link.startswith("/"):
        latest_link = "https://www.gov.br" + latest_link
    return latest_link


async def download_and_extract_sc_prices(xls_url: str, config: dict, hass: HomeAssistant) -> dict:
    """
    Baixa o arquivo XLSX e retorna um dicionário com os preços para cada combustível,
    para o município e estado configurados, a partir da aba "MUNICIPIOS".
    Usa openpyxl diretamente (sem pandas) em memória para menor consumo de disco.
    """
    session = async_get_clientsession(hass)
    try:
        async with session.get(xls_url, timeout=60) as response:
            if response.status != 200:
                raise ValueError(f"Falha ao baixar o arquivo XLS: {response.status}")
            content = await response.read()
    except Exception as e:
        logger.exception("Erro ao baixar XLSX")
        return {}

    try:
        wb = load_workbook(BytesIO(content), read_only=True, data_only=True)
        if "MUNICIPIOS" not in wb.sheetnames:
            raise ValueError("Aba 'MUNICIPIOS' não encontrada no arquivo.")
        ws = wb["MUNICIPIOS"]

        # Linha 10 (índice 10, pois skiprows=9) é o cabeçalho
        header_row = 10
        headers = []
        for cell in ws[header_row]:
            headers.append(normalize_text(str(cell.value)) if cell.value else "")

        logger.debug("Cabeçalhos do XLSX: " + ", ".join(headers))

        # Mapeia índices das colunas necessárias
        col_map = {}
        required_cols = ["ESTADO", "MUNICIPIO", "PRODUTO", "PRECO MEDIO REVENDA",
                         "PRECO MINIMO REVENDA", "PRECO MAXIMO REVENDA"]
        for col_name in required_cols:
            if col_name in headers:
                col_map[col_name] = headers.index(col_name)
            else:
                raise ValueError(f"Coluna esperada '{col_name}' não foi encontrada.")

        state_filter = normalize_text(config.get("state", "SANTA CATARINA"))
        city_filter = normalize_text(config.get("city", "TUBARAO"))

        prices = {}
        found_any = False

        for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
            estado = normalize_text(str(row[col_map["ESTADO"]])) if row[col_map["ESTADO"]] else ""
            municipio = normalize_text(str(row[col_map["MUNICIPIO"]])) if row[col_map["MUNICIPIO"]] else ""

            if estado != state_filter or municipio != city_filter:
                continue

            found_any = True
            product = str(row[col_map["PRODUTO"]]).strip() if row[col_map["PRODUTO"]] else ""

            try:
                raw_med = row[col_map["PRECO MEDIO REVENDA"]]
                raw_min = row[col_map["PRECO MINIMO REVENDA"]]
                raw_max = row[col_map["PRECO MAXIMO REVENDA"]]
                price_med = float(str(raw_med).replace(",", ".")) if raw_med is not None else None
                price_min = float(str(raw_min).replace(",", ".")) if raw_min is not None else None
                price_max = float(str(raw_max).replace(",", ".")) if raw_max is not None else None
            except Exception as e:
                logger.error(f"Erro ao converter os preços para o produto {product}: {e}")
                price_med = price_min = price_max = None

            logger.debug(f"Produto: {product}, min: {price_min}, med: {price_med}, max: {price_max}")
            prices[product] = {"min": price_min, "med": price_med, "max": price_max}

        wb.close()

        if not found_any:
            logger.error(
                f"Nenhum registro encontrado para {state_filter} / {city_filter} na aba MUNICIPIOS."
            )
            return {}

        return prices
    except Exception as e:
        logger.exception("Erro ao processar XLSX")
        return {}
