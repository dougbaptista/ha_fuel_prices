from homeassistant import config_entries
from .const import DOMAIN

class FuelPricesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Flow para Preços de Combustíveis (ANP)."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Etapa de configuração inicial."""
        if user_input is not None:
            return self.async_create_entry(title="Preços de Combustíveis (ANP)", data=user_input)

        return self.async_show_form(step_id="user")
