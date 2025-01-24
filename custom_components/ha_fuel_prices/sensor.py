import aiohttp
import pandas as pd
from homeassistant.components.sensor import SensorEntity
from .const import DOMAIN

BASE_URL = "https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/levantamento-de-precos-de-combustiveis-ultimas-semanas-pesquisadas"

async def async_setup_entry(hass, entry, async_add_entities):
    config = entry.data
    entities = [
        FuelPriceSensor(config, "Etanol Hidratado"),
        FuelPriceSensor(config, "Gasolina Comum"),
        FuelPriceSensor(config, "Gasolina Aditivada"),
        FuelPriceSensor(config, "GLP"),
        FuelPriceSensor(config, "GNV"),
        FuelPriceSensor(config, "Óleo Diesel"),
        FuelPriceSensor(config, "Óleo Diesel S10"),
    ]
    async_add_entities(entities)

class FuelPriceSensor(SensorEntity):
    def __init__(self, config, fuel_type):
        self._fuel_type = fuel_type
        self._state = None
        self._state_config = config
        self._attr_name = f"Preço {fuel_type}"
        self._attr_unique_id = f"{DOMAIN}_{fuel_type.lower().replace(' ', '_')}"
        self._attr_unit_of_measurement = "BRL/L"

    @property
    def native_value(self):
        return self._state

    async def async_update(self):
        """Atualiza os preços dos sensores com base nos dados da planilha."""
        try:
            xls_url = await fetch_latest_xls_url()
            if not xls_url:
                self._state = None
                return

            prices = await download_and_extract_prices(
                xls_url, self._state_config["state"], self._state_config["city"]
            )
            self._state = prices.get(self._fuel_type)
        except Exception as e:
            self._state = None
            self.hass.logger.error(f"Erro ao atualizar {self._fuel_type}: {e}")

async def fetch_latest_xls_url():
    """Encontra a URL mais recente do arquivo XLS no site da ANP."""
    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL) as response:
            if response.status != 200:
                raise ValueError(f"Falha ao acessar página ANP: {response.status}")
            html = await response.text()

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all("a", text="Preços médios semanais: Brasil, regiões, estados e municípios")
    if not links:
        return None

    latest_link = links[0]["href"]
    if latest_link.startswith("/"):
        latest_link = "https://www.gov.br" + latest_link
    return latest_link

async def download_and_extract_prices(xls_url, state, city):
    """Extrai os preços de combustível do arquivo XLS para o estado e cidade especificados."""
    temp_path = "/tmp/fuel_prices.xlsx"
    async with aiohttp.ClientSession() as session:
        async with session.get(xls_url) as response:
            if response.status != 200:
                raise ValueError(f"Falha ao baixar XLS: {response.status}")
            content = await response.read()
            with open(temp_path, "wb") as f:
                f.write(content)

    df = pd.read_excel(temp_path, engine="openpyxl", skiprows=9)
    df = df[(df["ESTADO"] == state) & (df["MUNICÍPIO"] == city)]
    prices = {row["PRODUTO"]: row["PREÇO MÉDIO REVENDA"] for _, row in df.iterrows()}
    return prices
