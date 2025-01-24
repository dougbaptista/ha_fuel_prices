import aiohttp
import asyncio
import pandas as pd
from bs4 import BeautifulSoup
import re

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
            # 1) Obter a URL mais recente do XLS no site da ANP
            xls_url = await fetch_latest_xls_url()
            if not xls_url:
                self.hass.logger.error("Não foi possível encontrar a URL XLS mais recente.")
                return

            # 2) Baixar e processar arquivo, extrair preços de SC e atualizar state
            prices = await download_and_extract_sc_prices(xls_url)

            # 3) Se a planilha não tiver SC ou fuel_type, definimos None.
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
    """Encontra a URL do último XLS cujo link contenha 'Preços médios semanais: Brasil, regiões, estados e municípios'."""
    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL) as response:
            if response.status != 200:
                raise ValueError(f"Falha ao acessar página ANP: {response.status}")
            html = await response.text()

    soup = BeautifulSoup(html, "html.parser")
    # Procurar por links que contenham exatamente ou parcialmente o texto desejado
    links = soup.find_all("a", text=re.compile(r"Preços médios semanais: Brasil, regiões, estados e municípios"))
    if not links:
        return None

    # Supondo que o primeiro link encontrado seja o mais recente
    latest_link = links[0]["href"]
    if latest_link.startswith("/"):
        latest_link = "https://www.gov.br" + latest_link

    return latest_link


async def download_and_extract_sc_prices(xls_url):
    """Baixa o arquivo XLS e retorna um dicionário com os preços médios do município de Tubarão em SC."""
    # Caminho temporário para salvar o arquivo
    temp_path = "/tmp/fuel_prices_sc.xlsx"

    async with aiohttp.ClientSession() as session:
        async with session.get(xls_url) as response:
            if response.status != 200:
                raise ValueError(f"Falha ao baixar XLS: {response.status}")
            content = await response.read()
            with open(temp_path, "wb") as f:
                f.write(content)

    # Processar a planilha com pandas
    try:
        # Ler a planilha a partir da linha correta
        df = pd.read_excel(temp_path, sheet_name="MUNICIPIOS", header=9, engine="openpyxl")

        # Filtrar para o estado de SC e o município de Tubarão
        df_sc_tubarao = df[(df["ESTADO"] == "SANTA CATARINA") & (df["MUNICÍPIO"] == "TUBARAO")]

        # Se não houver dados para SC e Tubarão, retornar um dicionário vazio
        if df_sc_tubarao.empty:
            return {}

        # Criar o dicionário de preços para cada tipo de combustível
        prices = {}
        for _, row in df_sc_tubarao.iterrows():
            fuel_type = str(row["PRODUTO"]).strip()  # Nome do combustível
            price = float(row["PREÇO MÉDIO REVENDA"])  # Preço médio
            prices[fuel_type] = price  # Adicionar ao dicionário

        return prices
    except Exception as e:
        raise ValueError(f"Erro ao processar planilha SC e Tubarão: {e}")
