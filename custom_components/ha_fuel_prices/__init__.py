import asyncio
from datetime import timedelta
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    hass.data.setdefault(DOMAIN, {})

    async def fetch_data():
        # Aqui vai a lógica para buscar e processar os dados da ANP
        return {"example_fuel": 5.45}

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Fuel Prices ANP",
        update_method=fetch_data,
        update_interval=timedelta(seconds=UPDATE_INTERVAL),
    )

    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][entry.entry_id] = coordinator
    hass.config_entries.async_setup_platforms(entry, ["sensor"])

    return True
