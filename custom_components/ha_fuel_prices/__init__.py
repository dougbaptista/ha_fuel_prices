from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

async def async_setup(hass: HomeAssistant, config: dict):
    """Configuração da integração via configuração YAML (não utilizada aqui)."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Configuração da integração via UI."""
    hass.config_entries.async_setup_platforms(entry, ["sensor"])
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Descarregar uma entrada de configuração."""
    await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    return True
