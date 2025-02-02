import aiohttp
import pandas as pd
import zipfile
import unicodedata
import os
import tempfile
from bs4 import BeautifulSoup
import re
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN  # O arquivo const.py deve estar na mesma pasta

BASE_URL = (
    "https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/"
    "precos/levantamento-de-precos-de-combustiveis-ultimas-semanas-pesquisadas"
)
logger = logging.getLogger(__name__)

def normalize_text(text):
    """Remove acentos, converte para ASCII, remove espaços e coloca em uppercase."""
    if not isinstance(text, str):
        text = str(text)
    normalized = unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode("utf-8")
    return normalized.upper().strip()

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Configuração inicial do sensor no Home Assistant."""
    # Lista dos combustíveis (deve coincidir com os produtos na planilha, em uppercase)
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
    # Cria três sensores para cada combustível
    for fuel in fuel_types:
        for pt in ["min", "med", "max"]:
            # O nome do sensor incluirá o combustível, a cidade (definida na configuração) e o tipo de preço
            city = entry.data.get("city", "TUBARAO").title()
            sensor_name = f"Preço {fuel.title()} ({city}) - {price_type_names[pt]}"
            sensors.append(FuelPriceSensor(entry.data, fuel, pt, sensor_name))
    async_add_entities(sensors)

class FuelPriceSensor(SensorEntity):
    """Sensor de preço de combustível para um tipo específico (mínimo, médio ou máximo)."""

    def __init__(self, config, fuel_type, price_type, sensor_name):
        """
        :param config: Dicionário de configuração com 'state' e 'city'
        :param fuel_type: Tipo de combustível (em uppercase, ex: "ETANOL HIDRATADO")
        :param price_type: "min", "med" ou "max"
        :param sensor_name: Nome do sensor (incluindo a cidade)
        """
        self._fuel_type = fuel_type
        self._price_type = price_type
        self._config = config
        self._state = None
        self._attr_name = sensor_name
        self._attr_unique_id = (
            f"{DOMAIN}_{fuel_type.lower().replace(' ', '_')}_"
            f"{price_type}_{config.get('city', '').lower().replace(' ', '_')}"
        )
        self._attr_unit_of_measurement = "BRL/L" if fuel_type != "GLP" else "BRL/kg"
        self._attr_extra_state_attributes = {}

    @property
    def native_value(self):
        return self._state

    async def async_update(self):
        """Atualiza o estado do sensor com o preço correspondente."""
        try:
            xls_url = await fetch_latest_xls_url()
            if not xls_url:
                logger.error("Não foi possível encontrar a URL XLS mais recente.")
                return

            # Use o executor para chamar a função bloqueante
            prices = await self.hass.async_add_executor_job(
                download_and_extract_sc_prices, xls_url, self._config
            )
            if not prices:
                self._state = None
                return

            price_info = prices.get(self._fuel_type)
            if price_info:
                self._state = price_info.get(self._price_type)
                self._attr_extra_state_attributes = {
                    "min": price_info.get("min"),
                    "médio": price_info.get("med"),
                    "máximo": price_info.get("max"),
                }
            else:
                self._state = None
        except Exception as e:
            self._state = None
            logger.error(f"Erro ao atualizar {self._fuel_type} ({self._price_type}): {e}")

async def fetch_latest_xls_url():
    """Busca a URL do último XLS cujo link contenha o texto esperado."""
    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL) as response:
            if response.status != 200:
                raise ValueError(f"Falha ao acessar a página da ANP: {response.status}")
            html = await response.text()
    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all("a", text=re.compile(r"Preços médios semanais: Brasil, regiões, estados e municípios"))
    if not links:
        return None
    latest_link = links[0]["href"]
    if latest_link.startswith("/"):
        latest_link = "https://www.gov.br" + latest_link
    return latest_link

def download_and_extract_sc_prices(xls_url, config):
    """
    Sincronamente (executado em um executor) baixa o arquivo XLSX e retorna um dicionário com os preços para cada combustível
    para o município e estado configurados (por exemplo, TUBARAO, SANTA CATARINA),
    a partir da aba "MUNICIPIOS". Cada produto terá um dicionário com as chaves: "min", "med" e "max".
    """
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, "fuel_prices_sc.xlsx")
    logger.debug(f"Arquivo XLSX será salvo em: {temp_path}")

    # Baixa o arquivo (bloco) – essa parte é executada dentro do executor, portanto é segura
    with aiohttp.ClientSession() as session:
        # Usamos requests síncronos aqui ou outra abordagem; para simplificar, usaremos aiohttp em modo síncrono
        # (Observação: se necessário, pode-se usar requests.get, mas certifique-se de que as dependências estejam disponíveis)
        import requests  # Usamos requests aqui para a operação síncrona
        r = requests.get(xls_url)
        if r.status_code != 200:
            raise ValueError(f"Falha ao baixar o arquivo XLS: {r.status_code}")
        with open(temp_path, "wb") as f:
            f.write(r.content)

    if not zipfile.is_zipfile(temp_path):
        logger.error("O arquivo XLSX baixado está corrompido ou incompleto (ZIP inválido).")
        return {}

    try:
        # Ajuste: usamos skiprows=9 para que a linha de cabeçalho correta seja lida
        df = pd.read_excel(temp_path, sheet_name="MUNICIPIOS", engine="openpyxl", skiprows=9)
        # Normaliza os nomes das colunas removendo acentos, espaços e convertendo para uppercase
        df.columns = [normalize_text(col) for col in df.columns]
        logger.debug("Cabeçalhos do XLSX: " + ", ".join(df.columns))
        if "ESTADO" not in df.columns or "MUNICIPIO" not in df.columns:
            raise ValueError("Colunas esperadas 'ESTADO' ou 'MUNICIPIO' não foram encontradas.")

        # Normaliza as colunas de filtro
        df["ESTADO"] = df["ESTADO"].astype(str).str.strip().str.upper()
        df["MUNICIPIO"] = df["MUNICIPIO"].astype(str).str.strip().str.upper()

        state_filter = config.get("state", "SANTA CATARINA").strip().upper()
        city_filter = config.get("city", "TUBARAO").strip().upper()

        df_sc = df[(df["ESTADO"] == state_filter) & (df["MUNICIPIO"] == city_filter)]
        logger.debug("Registros filtrados:\n" + df_sc.head().to_string())
        if df_sc.empty:
            logger.error(f"Nenhum registro encontrado para {state_filter} / {city_filter} na aba MUNICIPIOS.")
            return {}

        prices = {}
        for _, row in df_sc.iterrows():
            product = str(row["PRODUTO"]).strip()
            try:
                price_med = float(str(row["PRECO MEDIO REVENDA"]).replace(",", "."))
                price_min = float(str(row["PRECO MINIMO REVENDA"]).replace(",", "."))
                price_max = float(str(row["PRECO MAXIMO REVENDA"]).replace(",", "."))
            except Exception as e:
                logger.error(f"Erro ao converter os preços para o produto {product}: {e}")
                price_med = price_min = price_max = None
            logger.debug(f"Produto: {product}, min: {price_min}, med: {price_med}, max: {price_max}")
            prices[product] = {"min": price_min, "med": price_med, "max": price_max}

        return prices
    except Exception as e:
        raise ValueError(f"Erro ao processar a aba 'MUNICIPIOS': {e}")
