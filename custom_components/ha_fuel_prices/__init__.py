from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

async def async_setup(hass: HomeAssistant, config: dict):
    """Setup for integration via YAML (not used in this integration)."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Setup the integration using the UI."""
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload the integration."""
    await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    return True
