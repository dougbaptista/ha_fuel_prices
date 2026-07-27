"""Constantes da integração Fuel Prices."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "fuel_prices"
PLATFORMS: Final = ["sensor"]

CONF_STATE: Final = "state"
CONF_CITY: Final = "city"

DEFAULT_STATE: Final = "SANTA CATARINA"
DEFAULT_CITY: Final = "TUBARAO"

BASE_URL: Final = (
    "https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/"
    "precos/levantamento-de-precos-de-combustiveis-ultimas-semanas-pesquisadas"
)

# Hosts aceitos ao seguir o link extraído da página da ANP.
ALLOWED_HOST_SUFFIX: Final = ".gov.br"

# Os dados da ANP são semanais; 6 horas é folgado para pegar a nova publicação.
UPDATE_INTERVAL: Final = timedelta(hours=6)

# Após esse período sem uma coleta bem-sucedida o valor em cache é considerado
# obsoleto e as entidades passam a reportar indisponibilidade.
MAX_DATA_AGE: Final = timedelta(days=14)

PAGE_TIMEOUT: Final = 30
DOWNLOAD_TIMEOUT: Final = 60

# Teto de download para evitar exaustão de memória (zip bomb / arquivo anômalo).
MAX_DOWNLOAD_BYTES: Final = 50 * 1024 * 1024
DOWNLOAD_CHUNK_SIZE: Final = 64 * 1024

# Nomes já normalizados (sem acento, maiúsculas) como aparecem após o parsing.
FUEL_TYPES: Final = (
    "ETANOL HIDRATADO",
    "GASOLINA COMUM",
    "GASOLINA ADITIVADA",
    "GLP",
    "GNV",
    "OLEO DIESEL",
    "OLEO DIESEL S10",
)

PRICE_TYPES: Final = ("min", "med", "max")

PRICE_TYPE_NAMES: Final = {"min": "Mínimo", "med": "Médio", "max": "Máximo"}

FUEL_ICONS: Final = {
    "ETANOL HIDRATADO": "mdi:gas-station",
    "GASOLINA COMUM": "mdi:gas-station",
    "GASOLINA ADITIVADA": "mdi:gas-station",
    "GLP": "mdi:gas-cylinder",
    "GNV": "mdi:gas-cylinder",
    "OLEO DIESEL": "mdi:fuel",
    "OLEO DIESEL S10": "mdi:fuel",
}

# GLP é vendido por quilo; os demais por litro.
UNIT_BY_FUEL: Final = {"GLP": "BRL/kg"}
DEFAULT_UNIT: Final = "BRL/L"
