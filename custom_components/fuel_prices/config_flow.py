"""Fluxos de configuração e opções da integração Fuel Prices."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_CITY, CONF_STATE, DEFAULT_CITY, DEFAULT_STATE, DOMAIN
from .coordinator import async_fetch_locations
from .parser import normalize_text

_LOGGER = logging.getLogger(__name__)


def _select(options: list[str], default: str | None) -> vol.Schema:
    """Seletor com busca, já que há 27 estados e centenas de municípios."""
    return SelectSelector(
        SelectSelectorConfig(
            options=options,
            mode=SelectSelectorMode.DROPDOWN,
            custom_value=False,
            sort=True,
        )
    )


def _text_schema(state: str, city: str) -> vol.Schema:
    """Fallback usado quando a lista da ANP não pôde ser obtida."""
    return vol.Schema(
        {
            vol.Required(CONF_STATE, default=state): str,
            vol.Required(CONF_CITY, default=city): str,
        }
    )


class LocationFlowMixin:
    """Passos compartilhados entre a configuração inicial e as opções."""

    _locations: dict[str, list[str]] | None = None
    _state: str | None = None

    async def _async_load_locations(self) -> str | None:
        """Baixa a lista de localidades. Devolve a chave do erro, se houver."""
        if self._locations is not None:
            return None
        try:
            self._locations = await async_fetch_locations(self.hass)
        except Exception:  # noqa: BLE001 - qualquer falha cai no modo texto
            _LOGGER.warning(
                "Não foi possível obter a lista de localidades da ANP; "
                "o formulário usará entrada livre.",
                exc_info=True,
            )
            return "cannot_connect"
        return None

    def _cities_for(self, state: str) -> list[str]:
        return (self._locations or {}).get(state, [])


class FuelPricesConfigFlow(LocationFlowMixin, ConfigFlow, domain=DOMAIN):
    """Configuração inicial da integração."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Escolhe o estado a partir da lista publicada pela ANP."""
        error = await self._async_load_locations()

        # Sem a lista, cai para o formulário livre de um passo só.
        if self._locations is None:
            return await self._async_step_manual(user_input, error)

        if user_input is not None:
            self._state = user_input[CONF_STATE]
            return await self.async_step_city()

        states = sorted(self._locations)
        default = DEFAULT_STATE if DEFAULT_STATE in states else states[0]
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_STATE, default=default): _select(states, default)}
            ),
        )

    async def async_step_city(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Escolhe o município entre os efetivamente pesquisados no estado."""
        assert self._state is not None
        cities = self._cities_for(self._state)

        if user_input is not None:
            return await self._async_create(self._state, user_input[CONF_CITY])

        default = DEFAULT_CITY if DEFAULT_CITY in cities else cities[0]
        return self.async_show_form(
            step_id="city",
            data_schema=vol.Schema(
                {vol.Required(CONF_CITY, default=default): _select(cities, default)}
            ),
            description_placeholders={"state": self._state},
        )

    async def _async_step_manual(
        self, user_input: dict[str, Any] | None, error: str | None
    ) -> ConfigFlowResult:
        """Entrada livre quando a planilha da ANP está inacessível."""
        errors: dict[str, str] = {}
        if user_input is not None:
            state = normalize_text(user_input[CONF_STATE])
            city = normalize_text(user_input[CONF_CITY])
            if not state or not city:
                errors["base"] = "invalid_location"
            else:
                return await self._async_create(state, city)
        elif error:
            errors["base"] = error

        defaults = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=_text_schema(
                defaults.get(CONF_STATE, DEFAULT_STATE),
                defaults.get(CONF_CITY, DEFAULT_CITY),
            ),
            errors=errors,
        )

    async def _async_create(self, state: str, city: str) -> ConfigFlowResult:
        await self.async_set_unique_id(f"{state}_{city}")
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"{city.title()} ({state.title()})",
            data={CONF_STATE: state, CONF_CITY: city},
        )

    @staticmethod
    def async_get_options_flow(config_entry) -> OptionsFlowHandler:
        """Devolve o fluxo de opções."""
        return OptionsFlowHandler()


class OptionsFlowHandler(LocationFlowMixin, OptionsFlow):
    """Permite editar estado e município depois da instalação.

    Não define ``__init__``: atribuir ``self.config_entry`` manualmente está
    depreciado desde o HA 2024.11 e foi removido no 2025.12 — a classe base já
    fornece o atributo.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Escolhe o estado."""
        error = await self._async_load_locations()
        current = {**self.config_entry.data, **self.config_entry.options}

        if self._locations is None:
            return await self._async_step_manual(user_input, error, current)

        if user_input is not None:
            self._state = user_input[CONF_STATE]
            return await self.async_step_city()

        states = sorted(self._locations)
        atual = current.get(CONF_STATE, DEFAULT_STATE)
        default = atual if atual in states else states[0]
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {vol.Required(CONF_STATE, default=default): _select(states, default)}
            ),
        )

    async def async_step_city(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Escolhe o município."""
        assert self._state is not None
        cities = self._cities_for(self._state)
        current = {**self.config_entry.data, **self.config_entry.options}

        if user_input is not None:
            return self.async_create_entry(
                data={CONF_STATE: self._state, CONF_CITY: user_input[CONF_CITY]}
            )

        atual = current.get(CONF_CITY, DEFAULT_CITY)
        default = atual if atual in cities else cities[0]
        return self.async_show_form(
            step_id="city",
            data_schema=vol.Schema(
                {vol.Required(CONF_CITY, default=default): _select(cities, default)}
            ),
            description_placeholders={"state": self._state},
        )

    async def _async_step_manual(
        self,
        user_input: dict[str, Any] | None,
        error: str | None,
        current: dict[str, Any],
    ) -> ConfigFlowResult:
        """Entrada livre quando a planilha da ANP está inacessível."""
        errors: dict[str, str] = {}
        if user_input is not None:
            state = normalize_text(user_input[CONF_STATE])
            city = normalize_text(user_input[CONF_CITY])
            if not state or not city:
                errors["base"] = "invalid_location"
            else:
                return self.async_create_entry(
                    data={CONF_STATE: state, CONF_CITY: city}
                )
        elif error:
            errors["base"] = error

        return self.async_show_form(
            step_id="init",
            data_schema=_text_schema(
                current.get(CONF_STATE, DEFAULT_STATE),
                current.get(CONF_CITY, DEFAULT_CITY),
            ),
            errors=errors,
        )
