import aiohttp
import pandas as pd
from bs4 import BeautifulSoup
import re
from aiofiles import open as aio_open
from concurrent.futures import ThreadPoolExecutor
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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
            xls_url = await fetch_latest_xls_url()
            if not xls_url:
                raise ValueError("Não foi possível encontrar a URL XLS mais recente.")
            
            # Chama a extração de preços em uma thread separada
            prices = await self.hass.async_add_executor_job(download_and_extract_sc_prices, xls_url)

            if not prices or self._fuel_type not in prices:
                self._state = None
            else:
                self._state = prices[self._fuel_type]
        except Exception as e:
            self._state = None
            self.hass.helpers.logging.getLogger(__name__).error(f"Erro ao atualizar {self._fuel_type}: {e}")


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


def download_and_extract_sc_prices(xls_url):
    """Baixa o arquivo XLS e retorna os preços médios de Santa Catarina."""
    temp_path = "/tmp/fuel_prices_sc.xlsx"

    # Baixar o arquivo
    with aiohttp.ClientSession() as session:
        response = session.get(xls_url)
        if response.status != 200:
            raise ValueError(f"Falha ao baixar XLS: {response.status}")
        content = response.content
        with open(temp_path, "wb") as f:
            f.write(content)

    try:
        df = pd.read_excel(temp_path, engine="openpyxl", skiprows=10)  # Pula as linhas antes do cabeçalho
        df.columns = [str(col).strip() for col in df.columns]  # Converte todos os nomes de coluna para string
        estado_col = next((col for col in df.columns if "estado" in col.lower()), None)
        produto_col = next((col for col in df.columns if "produto" in col.lower()), None)
        preco_col = next((col for col in df.columns if "preço médio" in col.lower()), None)

        if not estado_col or not produto_col or not preco_col:
            raise ValueError("Colunas necessárias não foram encontradas na planilha.")

        # Filtra apenas Santa Catarina
        df_sc = df[df[estado_col].astype(str).str.strip().str.upper() == "SANTA CATARINA"]

        if df_sc.empty:
            return {}

        # Extração dos preços médios por produto
        prices = {}
        for _, row in df_sc.iterrows():
            product = str(row[produto_col]).strip()
            price = float(row[preco_col])
            prices[product] = price

        return prices
    except Exception as e:
        raise ValueError(f"Erro ao processar planilha SC: {e}")
