import aiohttp
import pandas as pd
from io import BytesIO
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from bs4 import BeautifulSoup
import re
from .const import DOMAIN

BASE_URL = "https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/levantamento-de-precos-de-combustiveis-ultimas-semanas-pesquisadas"

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Configuração inicial do sensor."""
    sensors = [
        FuelPriceSensor(hass, entry.data, "Etanol Hidratado"),
        FuelPriceSensor(hass, entry.data, "Gasolina Comum"),
        FuelPriceSensor(hass, entry.data, "Gasolina Aditivada"),
        FuelPriceSensor(hass, entry.data, "GLP"),
        FuelPriceSensor(hass, entry.data, "GNV"),
        FuelPriceSensor(hass, entry.data, "Óleo Diesel"),
        FuelPriceSensor(hass, entry.data, "Óleo Diesel S10"),
    ]
    async_add_entities(sensors)

class FuelPriceSensor(SensorEntity):
    """Representação de um sensor de preço de combustível."""

    def __init__(self, hass, config, fuel_type):
        self.hass = hass
        self._fuel_type = fuel_type
        self._state = None
        self._attr_name = f"Preço {fuel_type}"
        self._attr_unique_id = f"{DOMAIN}_{fuel_type.lower().replace(' ', '_')}"
        self._attr_unit_of_measurement = "BRL/L" if fuel_type != "GLP" else "BRL/kg"

    @property
    def native_value(self):
        return self._state

    async def async_update(self):
        """Atualizar o estado do sensor."""
        try:
            # Obter a URL mais recente do XLS
            xls_url = await fetch_latest_xls_url()
            if not xls_url:
                raise ValueError("Não foi possível encontrar a URL do arquivo XLS mais recente.")

            # Processar o arquivo e obter preços
            prices = await self.hass.async_add_executor_job(download_and_extract_sc_prices, xls_url)

            # Atualizar o estado do sensor
            self._state = prices.get(self._fuel_type, None)

        except Exception as e:
            self._state = None
            self.hass.helpers.event.async_call_later(
                0, lambda _: self.hass.helpers.logging.getLogger(__name__).error(f"Erro ao atualizar {self._fuel_type}: {e}")
            )

async def fetch_latest_xls_url():
    """Encontra a URL do último XLS na página da ANP."""
    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL) as response:
            if response.status != 200:
                raise ValueError(f"Erro ao acessar a página da ANP: {response.status}")
            html = await response.text()

    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all("a", text=re.compile(r"Preços médios semanais: Brasil, regiões, estados e municípios"))
    if not links:
        return None
    latest_link = links[0]["href"]
    if latest_link.startswith("/"):
        latest_link = "https://www.gov.br" + latest_link
    return latest_link

def download_and_extract_sc_prices(xls_url):
    """Baixa o arquivo XLS e processa a aba MUNICIPIOS para retornar preços de SC."""
    try:
        response = requests.get(xls_url)
        if response.status_code != 200:
            raise ValueError(f"Erro ao baixar arquivo XLS: {response.status_code}")

        # Carregar o XLS em memória
        xls_file = BytesIO(response.content)
        df = pd.read_excel(xls_file, sheet_name="MUNICIPIOS", engine="openpyxl", skiprows=10)

        # Identificar as colunas necessárias
        def find_column(columns, keyword):
            for col in columns:
                if isinstance(col, str) and keyword.lower() in col.lower():
                    return col
            return None

        estado_col = find_column(df.columns, "estado")
        municipio_col = find_column(df.columns, "município")
        preco_col = find_column(df.columns, "preço médio")
        produto_col = find_column(df.columns, "produto")

        if not all([estado_col, municipio_col, preco_col, produto_col]):
            raise ValueError("Colunas necessárias não foram encontradas na planilha.")

        # Filtrar Santa Catarina
        df_sc = df[df[estado_col].str.strip().str.upper() == "SANTA CATARINA"]

        # Retornar preços médios por tipo de combustível
        return df_sc.groupby(produto_col)[preco_col].mean().to_dict()

    except Exception as e:
        raise ValueError(f"Erro ao processar a aba 'MUNICIPIOS': {e}")
