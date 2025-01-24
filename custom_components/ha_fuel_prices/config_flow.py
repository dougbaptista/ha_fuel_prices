from homeassistant import config_entries
import voluptuous as vol

from .const import DOMAIN

class FuelPricesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configuração do fluxo de integração para preços de combustíveis."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Passo inicial da configuração do usuário."""
        if user_input is not None:
            return self.async_create_entry(title="Fuel Prices", data=user_input)

        # Esquema de configuração do usuário
        schema = vol.Schema({
            vol.Required("state", default="SANTA CATARINA"): str,
            vol.Required("city", default="TUBARAO"): str,
        })

        return self.async_show_form(step_id="user", data_schema=schema)
