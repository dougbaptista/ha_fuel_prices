import aiohttp
import pandas as pd
from bs4 import BeautifulSoup
import re
import asyncio
import logging
from aiofiles.tempfile import NamedTemporaryFile
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN

BASE_URL = "https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/levantamento-de-precos-de-combustiveis-ultimas-semanas-pesquisadas"

_LOGGER = logging.getLogger(__name__)

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
                raise ValueError("Não foi possível encontrar a URL XLS mais recente.")

            prices = await download_and_extract_sc_prices(xls_url)

            if not prices or self._fuel_type not in prices:
                self._state = None
            else:
                self._state = prices[self._fuel_type]
        except Exception as e:
            self._state = None
            _LOGGER.error(f"Erro ao atualizar {self._fuel_type}: {e}")


async def fetch_latest_xls_url():
    """Obtém a URL do último XLS disponível na página da ANP."""
    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL) as response:
            if response.status != 200:
                raise ValueError(f"Falha ao acessar página ANP: {response.status}")
            html = await response.text()

    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all("a", text=re.compile(r"Preços médios semanais: Brasil, regiões, estados e municípios"))
    if not links:
        return None
    latest_link = links[0]["href"]
    if latest_link.startswith("/"):
        latest_link = "https://www.gov.br" + latest_link
    return latest_link


async def download_and_extract_sc_prices(xls_url):
    """Baixa o arquivo XLS e retorna os preços médios de Santa Catarina."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(xls_url) as response:
                if response.status != 200:
                    raise ValueError(f"Falha ao baixar XLS: {response.status}")
                content = await response.read()

        # Salva em arquivo temporário
        async with NamedTemporaryFile(delete=False) as tmp_file:
            await tmp_file.write(content)
            tmp_file_path = tmp_file.name

        # Processa o arquivo usando pandas
        def process_excel():
            df = pd.read_excel(tmp_file_path, engine="openpyxl", skiprows=10)
            df.columns = [str(col).strip().lower() for col in df.columns]

            estado_col = next((col for col in df.columns if "estado" in col), None)
            produto_col = next((col for col in df.columns if "produto" in col), None)
            preco_col = next((col for col in df.columns if "preço médio" in col), None)

            if not estado_col or not produto_col or not preco_col:
                raise ValueError("Colunas necessárias não foram encontradas na planilha.")

            df_sc = df[df[estado_col].str.strip().str.upper() == "SANTA CATARINA"]
            if df_sc.empty:
                return {}

            prices = {}
            for _, row in df_sc.iterrows():
                product = str(row[produto_col]).strip()
                price = float(row[preco_col])
                prices[product] = price
            return prices

        # Chama o processamento de forma síncrona
        return await asyncio.get_event_loop().run_in_executor(None, process_excel)

    except Exception as e:
        raise ValueError(f"Erro ao processar planilha SC: {e}")
