import aiohttp
import asyncio
import pandas as pd
from bs4 import BeautifulSoup
import re
import tempfile

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from .const import DOMAIN

BASE_URL = (
    "https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos"
)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Configuração inicial do sensor."""
    fuel_types = [
        "Etanol Hidratado",
        "Gasolina Comum",
        "Gasolina Aditivada",
        "GLP",
        "GNV",
        "Óleo Diesel",
        "Óleo Diesel S10",
    ]
    async_add_entities(
        [FuelPriceSensor(entry.data, fuel_type) for fuel_type in fuel_types]
    )

class FuelPriceSensor(SensorEntity):
    """Representação de um sensor de preço de combustível."""

    def __init__(self, config, fuel_type):
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
            xls_url = await fetch_latest_xls_url()
            if not xls_url:
                raise ValueError("Não foi possível localizar o link para download do arquivo.")

            prices = await download_and_extract_sc_prices(xls_url)
            self._state = prices.get(self._fuel_type)
        except Exception as e:
            self._state = None
            self.hass.helpers.logger.error(f"Erro ao atualizar {self._fuel_type}: {e}")

async def fetch_latest_xls_url():
    """Obtém a URL mais recente do arquivo XLS da página da ANP."""
    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL) as response:
            if response.status != 200:
                raise ValueError(f"Erro ao acessar a página: {response.status}")
            html = await response.text()

    soup = BeautifulSoup(html, "html.parser")
    link = soup.find("a", href=True, text=re.compile(r"Levantamento de Preços de Combustíveis"))
    if not link:
        return None

    href = link["href"]
    if href.startswith("/"):
        href = f"https://www.gov.br{href}"
    return href

async def download_and_extract_sc_prices(xls_url):
    """Baixa e processa o arquivo XLS, retornando os preços médios para SC."""
    async with aiohttp.ClientSession() as session:
        async with session.get(xls_url) as response:
            if response.status != 200:
                raise ValueError(f"Erro ao baixar o arquivo: {response.status}")
            content = await response.read()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_file:
        tmp_file.write(content)
        tmp_file_path = tmp_file.name

    try:
        df = pd.read_excel(tmp_file_path, sheet_name="MUNICIPIOS", engine="openpyxl", skiprows=10)
        df_sc = df[df["Estado"].str.upper() == "SANTA CATARINA"]
        prices = df_sc.groupby("Produto")["Valor de Venda"].mean().to_dict()
        return prices
    except Exception as e:
        raise ValueError(f"Erro ao processar a aba 'MUNICIPIOS': {e}")
