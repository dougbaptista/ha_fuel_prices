import aiohttp
import pandas as pd
import zipfile
from bs4 import BeautifulSoup
import re
import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN

BASE_URL = "https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/levantamento-de-precos-de-combustiveis-ultimas-semanas-pesquisadas"
logger = logging.getLogger(__name__)

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
                logger.error("Não foi possível encontrar a URL XLS mais recente.")
                return

            # Baixar e processar o arquivo, extraindo preços para o município de TUBARÃO (SC)
            prices = await download_and_extract_sc_prices(xls_url)

            if not prices:
                self._state = None
                return

            # Atualiza o estado com o preço para o tipo de combustível atual
            self._state = prices.get(self._fuel_type)
        except Exception as e:
            self._state = None
            logger.error(f"Erro ao atualizar {self._fuel_type}: {e}")

async def fetch_latest_xls_url():
    """Encontra a URL do último XLS cujo link contenha 'Preços médios semanais: Brasil, regiões, estados e municípios'."""
    async with aiohttp.ClientSession() as session:
        async with session.get(BASE_URL) as response:
            if response.status != 200:
                raise ValueError(f"Falha ao acessar a página da ANP: {response.status}")
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
    """
    Baixa o arquivo XLSX e retorna um dicionário com os preços médios
    para o município de TUBARÃO, no estado SANTA CATARINA,
    a partir da aba "MUNICIPIOS".
    """
    temp_path = "/tmp/fuel_prices_sc.xlsx"

    async with aiohttp.ClientSession() as session:
        async with session.get(xls_url) as response:
            if response.status != 200:
                raise ValueError(f"Falha ao baixar o arquivo XLS: {response.status}")
            content = await response.read()
            # Salva o arquivo XLSX localmente
            with open(temp_path, "wb") as f:
                f.write(content)

    # Verifica se o arquivo XLSX baixado é um arquivo ZIP válido
    if not zipfile.is_zipfile(temp_path):
        logger.error("O arquivo XLSX baixado está corrompido ou incompleto (ZIP inválido).")
        return {}

    try:
        # Lê a aba "MUNICIPIOS" do arquivo XLSX, pulando as primeiras 10 linhas
        # (Essa chamada é bloqueante; para evitar o warning, você poderia usar: await hass.async_add_executor_job(pd.read_excel, ...)
        df = pd.read_excel(temp_path, sheet_name="MUNICIPIOS", engine="openpyxl", skiprows=10)
        
        # Converte os nomes das colunas para string, uppercase e sem espaços para padronização
        df.columns = df.columns.astype(str).str.strip().str.upper()
        logger.debug("Cabeçalhos do XLSX: " + ", ".join(df.columns))
        
        # Normaliza as colunas de filtro (usando nomes em uppercase)
        df["ESTADO"] = df["ESTADO"].astype(str).str.strip().str.upper()
        df["MUNICÍPIO"] = df["MUNICÍPIO"].astype(str).str.strip().str.upper()

        # Filtra para registros onde ESTADO seja "SANTA CATARINA" e MUNICÍPIO seja "TUBARÃO"
        df_sc = df[(df["ESTADO"] == "SANTA CATARINA") & (df["MUNICÍPIO"] == "TUBARÃO")]
        logger.debug("Registros filtrados:\n" + df_sc.head().to_string())
        if df_sc.empty:
            logger.error("Nenhum registro encontrado para SANTA CATARINA / TUBARÃO na aba MUNICIPIOS.")
            return {}

        prices = {}
        # Itera pelos registros filtrados e extrai os preços
        for _, row in df_sc.iterrows():
            product = str(row["PRODUTO"]).strip()
            try:
                # Converte o valor, substituindo a vírgula decimal por ponto
                price = float(str(row["PREÇO MÉDIO REVENDA"]).replace(",", "."))
            except Exception as e:
                logger.error(f"Erro ao converter o preço para o produto {product}: {e}")
                price = None
            logger.debug(f"Produto: {product}, Preço: {price}")
            prices[product] = price

        return prices
    except Exception as e:
        raise ValueError(f"Erro ao processar a aba 'MUNICIPIOS': {e}")
