import aiohttp
import pandas as pd
import logging
from bs4 import BeautifulSoup
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_call_later

_LOGGER = logging.getLogger(__name__)
BASE_URL = "https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos"

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Configuração inicial do sensor."""
    sensors = [
        FuelPriceSensor(entry.data, "Etanol Hidratado"),
        FuelPriceSensor(entry.data, "Gasolina Comum"),
        FuelPriceSensor(entry.data, "Gasolina Aditivada"),
        FuelPriceSensor(entry.data, "GLP"),
        FuelPriceSensor(entry.data, "GNV"),
        FuelPriceSensor(entry.data, "Óleo Diesel"),
        FuelPriceSensor(entry.data, "Óleo Diesel S10"),
    ]
    async_add_entities(sensors)

class FuelPriceSensor(SensorEntity):
    """Representação de um sensor de preço de combustível."""

    def __init__(self, config, fuel_type):
        self._fuel_type = fuel_type
        self._state = None
        self._attr_name = f"Preço {fuel_type}"
        self._attr_unique_id = f"fuel_prices_{fuel_type.lower().replace(' ', '_')}"
        self._attr_unit_of_measurement = "BRL/L" if fuel_type != "GLP" else "BRL/kg"

    @property
    def native_value(self):
        """Retorna o valor atual do sensor."""
        return self._state

    async def async_update(self):
        """Atualiza o estado do sensor."""
        try:
            # Obtém a URL mais recente do arquivo XLS
            xls_url = await fetch_latest_xls_url()
            _LOGGER.debug(f"URL do arquivo XLS: {xls_url}")

            # Faz o download e processa os preços para SC
            prices = await download_and_extract_sc_prices(self.hass, xls_url)

            # Atualiza o estado para o preço do tipo de combustível atual
            self._state = prices.get(self._fuel_type, None)
            if self._state is None:
                _LOGGER.warning(f"Preço não encontrado para {self._fuel_type}")
        except Exception as e:
            _LOGGER.error(f"Erro ao atualizar {self._fuel_type}: {e}")

async def fetch_latest_xls_url():
    """Obtém a URL do arquivo XLS mais recente da página da ANP."""
    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL) as response:
            html = await response.text()

    soup = BeautifulSoup(html, "html.parser")
    link = soup.find("a", text="Preços médios semanais: Brasil, regiões, estados e municípios")
    if link and link["href"]:
        return f"https://www.gov.br{link['href']}"
    raise ValueError("Não foi possível localizar o link para download do arquivo.")

async def download_and_extract_sc_prices(hass: HomeAssistant, xls_url):
    """Faz o download e processa os preços médios do estado de SC."""
    temp_path = "/tmp/fuel_prices_sc.xlsx"
    async with aiohttp.ClientSession() as session:
        async with session.get(xls_url) as response:
            content = await response.read()
            await hass.async_add_executor_job(write_file, temp_path, content)
    return await hass.async_add_executor_job(read_xls_and_extract_prices, temp_path)

def write_file(path, content):
    """Escreve o conteúdo em um arquivo local."""
    with open(path, "wb") as f:
        f.write(content)

def read_xls_and_extract_prices(path):
    """Lê o arquivo XLS e extrai os preços médios de SC."""
    df = pd.read_excel(path, sheet_name="MUNICIPIOS", engine="openpyxl", skiprows=10)
    if "Estado" not in df.columns or "Produto" not in df.columns or "Preço Médio de Revenda" not in df.columns:
        raise ValueError("Colunas necessárias não foram encontradas na planilha.")
    df_sc = df[df["Estado"].str.strip().str.upper() == "SANTA CATARINA"]
    prices = df_sc.groupby("Produto")["Preço Médio de Revenda"].mean().to_dict()
    return prices
