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
    """Baixa o arquivo XLS e retorna um dicionário com os preços médios do estado de SC na aba MUNICIPIOS."""
    temp_path = "/tmp/fuel_prices_sc.xlsx"

    # Download do arquivo XLS
    async with aiohttp.ClientSession() as session:
        async with session.get(xls_url) as response:
            if response.status != 200:
                raise ValueError(f"Falha ao baixar o arquivo XLS: {response.status}")
            content = await response.read()
            with open(temp_path, "wb") as f:
                f.write(content)

    # Processamento da planilha
    try:
        # Lê o arquivo e seleciona a aba "MUNICIPIOS"
        df = pd.read_excel(temp_path, sheet_name="MUNICIPIOS", engine="openpyxl", skiprows=10)

        # Identificar as colunas relevantes
        estado_col = next((col for col in df.columns if "estado" in col.lower()), None)
        municipio_col = next((col for col in df.columns if "município" in col.lower()), None)
        preco_col = next((col for col in df.columns if "preço médio" in col.lower()), None)
        produto_col = next((col for col in df.columns if "produto" in col.lower()), None)

        # Verificar se todas as colunas foram encontradas
        if not all([estado_col, municipio_col, preco_col, produto_col]):
            raise ValueError("Colunas necessárias não foram encontradas na planilha.")

        # Filtrar dados para o estado de SC
        df_sc = df[df[estado_col].str.upper() == "SANTA CATARINA"]

        # Agrupar os preços médios por tipo de combustível
        prices = (
            df_sc.groupby(produto_col)[preco_col]
            .mean()
            .to_dict()
        )
        return prices

    except Exception as e:
        raise ValueError(f"Erro ao processar a aba 'MUNICIPIOS': {e}")
