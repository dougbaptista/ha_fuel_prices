import aiohttp
import asyncio
import pandas as pd
from bs4 import BeautifulSoup
import re
import tempfile
from zipfile import BadZipFile

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.logging import getLogger
from .const import DOMAIN

BASE_URL = (
    "https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos"
)

_LOGGER = getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    sensors = [
        FuelPriceSensor(entry.data, fuel_type)
        for fuel_type in [
            "Etanol Hidratado",
            "Gasolina Comum",
            "Gasolina Aditivada",
            "GLP",
            "GNV",
            "Óleo Diesel",
            "Óleo Diesel S10",
        ]
    ]
    async_add_entities(sensors)


class FuelPriceSensor(SensorEntity):
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
        try:
            xls_url = await fetch_latest_xls_url()
            if not xls_url:
                raise ValueError("Não foi possível localizar o link para download do arquivo.")

            prices = await download_and_extract_sc_prices(xls_url)

            if not prices or self._fuel_type not in prices:
                self._state = None
                return

            self._state = prices[self._fuel_type]
        except Exception as e:
            _LOGGER.error(f"Erro ao atualizar {self._fuel_type}: {e}")
            self._state = None


async def fetch_latest_xls_url():
    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL) as response:
            if response.status != 200:
                raise ValueError(f"Falha ao acessar página ANP: {response.status}")
            html = await response.text()

    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all(
        "a", text=re.compile(r"Preços médios semanais: Brasil, regiões, estados e municípios")
    )
    if not links:
        return None

    latest_link = links[0]["href"]
    if latest_link.startswith("/"):
        latest_link = "https://www.gov.br" + latest_link

    return latest_link


async def download_and_extract_sc_prices(xls_url):
    async with aiohttp.ClientSession() as session:
        async with session.get(xls_url) as response:
            if response.status != 200:
                raise ValueError(f"Falha ao baixar o arquivo XLS: {response.status}")

            content = await response.read()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_file:
        tmp_file.write(content)
        tmp_file_path = tmp_file.name

    try:
        df = pd.read_excel(tmp_file_path, sheet_name="MUNICIPIOS", engine="openpyxl", skiprows=10)
        df = df[df["Estado"] == "SANTA CATARINA"]

        if df.empty:
            raise ValueError("Nenhum dado encontrado para o estado de SC.")

        prices = {}
        for _, row in df.iterrows():
            city, product, price = row["Municipio"], row["Produto"], row["Valor de Venda"]
            if product not in prices:
                prices[product] = price

        return prices
    except (KeyError, BadZipFile) as e:
        raise ValueError(f"Erro ao processar a aba 'MUNICIPIOS': {e}")
    finally:
        import os
        os.remove(tmp_file_path)
