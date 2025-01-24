import aiohttp
import asyncio
import pandas as pd
from bs4 import BeautifulSoup
import re
from datetime import datetime

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN

BASE_URL = "https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/levantamento-de-precos-de-combustiveis-ultimas-semanas-pesquisadas"

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
            # Obter a URL mais recente do XLS no site da ANP
            xls_url = await fetch_latest_xls_url()
            if not xls_url:
                self.hass.logger.error("Não foi possível encontrar a URL XLS mais recente.")
                return

            # Baixar e processar o arquivo, extrair preços de SC e atualizar state
            prices = await download_and_extract_sc_prices(xls_url)

            if not prices:
                self._state = None
                return

            # Tenta obter o preço para o tipo de combustível atual
            if self._fuel_type in prices:
                self._state = prices[self._fuel_type]
            else:
                self._state = None
        except Exception as e:
            self._state = None
            self.hass.logger.error(f"Erro ao atualizar {self._fuel_type}: {e}")

async def fetch_latest_xls_url():
    """Encontra a URL do último XLS com base na data no nome do arquivo."""
    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL) as response:
            if response.status != 200:
                raise ValueError(f"Falha ao acessar página ANP: {response.status}")
            html = await response.text()

    soup = BeautifulSoup(html, "html.parser")
    links = soup.find_all("a", href=re.compile(r"resumo_semanal_lpc_\d{4}-\d{2}-\d{2}"))

    if not links:
        return None

    # Ordenar os links por data no nome do arquivo
    link_dates = []
    for link in links:
        href = link["href"]
        match = re.search(r"(\d{4}-\d{2}-\d{2})", href)
        if match:
            link_date = datetime.strptime(match.group(1), "%Y-%m-%d")
            link_dates.append((link_date, href))

    if not link_dates:
        return None

    # Pega o link com a data mais recente
    latest_date, latest_link = max(link_dates, key=lambda x: x[0])
    if latest_link.startswith("/"):
        latest_link = "https://www.gov.br" + latest_link

    return latest_link

async def download_and_extract_sc_prices(xls_url):
    """Baixa o arquivo XLS e retorna um dicionário com os preços médios do estado de SC."""
    temp_path = "/tmp/fuel_prices_sc.xlsx"

    async with aiohttp.ClientSession() as session:
        async with session.get(xls_url) as response:
            if response.status != 200:
                raise ValueError(f"Falha ao baixar XLS: {response.status}")
            content = await response.read()
            with open(temp_path, "wb") as f:
                f.write(content)

    try:
        df = pd.read_excel(temp_path, skiprows=10, engine="openpyxl")
        df_sc = df[(df["Estado"] == "SANTA CATARINA") & (df["Município"] == "TUBARÃO")]

        prices = {}
        for _, row in df_sc.iterrows():
            product = str(row["Produto"].strip())
            price = float(row["Preço Médio Revenda"])
            prices[product] = price

        return prices
    except Exception as e:
        raise ValueError(f"Erro ao processar planilha SC: {e}")
