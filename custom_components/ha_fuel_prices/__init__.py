import pandas as pd
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from datetime import timedelta
import logging

from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry):
    hass.data.setdefault(DOMAIN, {})

    async def fetch_data():
        # Substitua este caminho pela lógica para buscar e processar a planilha do site da ANP
        data = {}
        try:
            df = pd.read_excel("/mnt/data/resumo_semanal_lpc_2025-01-12_2025-01-18.xlsx")

            # Filtra apenas SC e processa os preços médios
            df_sc = df[df["MUNICÍPIO"] == "SANTA CATARINA"]
            for fuel_type in df_sc["PRODUTO"].unique():
                fuel_data = df_sc[df_sc["PRODUTO"] == fuel_type]
                data[fuel_type] = fuel_data["PREÇO MÉDIO REVENDA"].mean()

        except Exception as e:
            _LOGGER.error(f"Erro ao processar dados: {e}")

        return data

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Fuel Prices ANP",
        update_method=fetch_data,
        update_interval=timedelta(minutes=UPDATE_INTERVAL),
    )

    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    return True
