from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

DOMAIN = "fuel_prices"

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Configuração inicial da integração."""
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    return True

async def async_setup(hass: HomeAssistant, config: ConfigType):
    """Configuração inicial quando a integração é carregada."""
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Descarrega uma entrada de configuração."""
    await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    return True
