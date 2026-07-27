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


    @staticmethod
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Fluxo de opções para editar estado/município após a criação."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="options", data=user_input)

        schema = vol.Schema({
            vol.Required("state", default=self.config_entry.data.get("state", "SANTA CATARINA")): str,
            vol.Required("city", default=self.config_entry.data.get("city", "TUBARAO")): str,
        })

        return self.async_show_form(step_id="init", data_schema=schema)
