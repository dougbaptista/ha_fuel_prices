import pandas as pd
import requests
from bs4 import BeautifulSoup
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

DOMAIN = "precos_combustiveis_anp"
BASE_URL = "https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/levantamento-de-precos-de-combustiveis-ultimas-semanas-pesquisadas"

SENSOR_TYPES = [
    "Etanol Hidratado",
    "Gasolina Aditivada",
    "Gasolina Comum",
    "GLP",
    "GNV",
    "Óleo Diesel",
    "Óleo Diesel S10",
]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Configura os sensores."""
    data = await hass.async_add_executor_job(fetch_latest_data)
    sensors = [
        FuelPriceSensor(data, fuel_type)
        for fuel_type in SENSOR_TYPES
    ]
    async_add_entities(sensors, True)

def fetch_latest_data():
    """Busca o último arquivo de preços de combustíveis no site da ANP e retorna os dados processados."""
    try:
        # Acessa a página da ANP
        response = requests.get(BASE_URL)
        response.raise_for_status()

        # Analisa o HTML para encontrar o link mais recente
        soup = BeautifulSoup(response.text, "html.parser")
        links = soup.find_all("a", string=lambda text: "Preços médios semanais" in text)
        if not links:
            raise ValueError("Nenhum link encontrado para os preços médios semanais.")

        # Pega o último link disponível
        latest_link = links[0]["href"]
        file_url = latest_link if latest_link.startswith("http") else f"https://www.gov.br{latest_link}"

        # Baixa o arquivo Excel
        excel_response = requests.get(file_url)
        excel_response.raise_for_status()

        # Lê o arquivo Excel
        df = pd.read_excel(excel_response.content)

        # Filtra os dados para Santa Catarina e retorna os preços médios
        sc_data = df[df["MUNICÍPIO"] == "SANTA CATARINA"]
        prices = {row["PRODUTO"]: row["PREÇO MÉDIO REVENDA"] for _, row in sc_data.iterrows()}
        return prices
    except Exception as e:
        # Retorna dados vazios em caso de erro
        return {fuel: None for fuel in SENSOR_TYPES}

class FuelPriceSensor(SensorEntity):
    """Sensor para preços de combustíveis."""

    def __init__(self, data, fuel_type):
        """Inicializa o sensor."""
        self._fuel_type = fuel_type
        self._data = data

    @property
    def name(self):
        """Nome do sensor."""
        return f"Preço {self._fuel_type} (SC)"

    @property
    def state(self):
        """Retorna o preço do combustível."""
        return self._data.get(self._fuel_type)

    @property
    def unit_of_measurement(self):
        """Unidade de medida do preço."""
        return "R$/L"
