"""Fluxos de configuração e opções da integração Fuel Prices."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow

from .const import CONF_CITY, CONF_STATE, DEFAULT_CITY, DEFAULT_STATE, DOMAIN
from .parser import normalize_text


def _schema(state: str, city: str) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_STATE, default=state): str,
            vol.Required(CONF_CITY, default=city): str,
        }
    )


def _clean(user_input: dict[str, Any]) -> dict[str, str]:
    """Normaliza a entrada para casar com a planilha da ANP."""
    return {
        CONF_STATE: normalize_text(user_input[CONF_STATE]),
        CONF_CITY: normalize_text(user_input[CONF_CITY]),
    }


class FuelPricesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configuração inicial da integração."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pede estado e município."""
        errors: dict[str, str] = {}

        if user_input is not None:
            cleaned = _clean(user_input)
            if not cleaned[CONF_STATE] or not cleaned[CONF_CITY]:
                errors["base"] = "invalid_location"
            else:
                await self.async_set_unique_id(
                    f"{cleaned[CONF_STATE]}_{cleaned[CONF_CITY]}"
                )
                self._abort_if_unique_id_configured()
                title = f"{cleaned[CONF_CITY].title()} ({cleaned[CONF_STATE].title()})"
                return self.async_create_entry(title=title, data=cleaned)

        defaults = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=_schema(
                defaults.get(CONF_STATE, DEFAULT_STATE),
                defaults.get(CONF_CITY, DEFAULT_CITY),
            ),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry) -> OptionsFlowHandler:
        """Devolve o fluxo de opções."""
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlow):
    """Permite editar estado e município depois da instalação.

    Não define ``__init__``: atribuir ``self.config_entry`` manualmente está
    depreciado desde o HA 2024.11 e foi removido no 2025.12 — a classe base já
    fornece o atributo.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edita a localidade acompanhada."""
        errors: dict[str, str] = {}
        current = {**self.config_entry.data, **self.config_entry.options}

        if user_input is not None:
            cleaned = _clean(user_input)
            if not cleaned[CONF_STATE] or not cleaned[CONF_CITY]:
                errors["base"] = "invalid_location"
            else:
                return self.async_create_entry(data=cleaned)

        return self.async_show_form(
            step_id="init",
            data_schema=_schema(
                current.get(CONF_STATE, DEFAULT_STATE),
                current.get(CONF_CITY, DEFAULT_CITY),
            ),
            errors=errors,
        )
