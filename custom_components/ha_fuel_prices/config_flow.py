from homeassistant import config_entries
from .const import DOMAIN

class FuelPricesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Flow para Preços de Combustíveis (ANP)."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """
        Etapa de configuração inicial.

        Apresenta um formulário ao usuário para coletar dados de configuração
        ou cria uma entrada de configuração se os dados forem fornecidos.
        """
        # Caso o usuário tenha submetido os dados
        if user_input is not None:
            # Cria a entrada no Home Assistant com os dados fornecidos
            return self.async_create_entry(
                title="Preços de Combustíveis (ANP)",
                data=user_input
            )

        # Mostra o formulário inicial (não há campos adicionais no momento)
        return self.async_show_form(step_id="user")
