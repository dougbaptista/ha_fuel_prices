from homeassistant import config_entries
from homeassistant.core import callback
from .const import DOMAIN

class FuelPricesFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            return self.async_create_entry(title="Fuel Prices", data=user_input)

        return self.async_show_form(step_id="user", errors=errors)
