"""Integração Fuel Prices — preços de combustíveis da ANP."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import CONF_CITY, DEFAULT_CITY, DOMAIN, FUEL_TYPES, PLATFORMS, PRICE_TYPES
from .coordinator import FuelPriceCoordinator
from .parser import legacy_unique_ids, make_unique_id

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configura uma entrada da integração."""
    _async_migrate_unique_ids(hass, entry)

    coordinator = FuelPriceCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Sem isto, editar estado/município pelo fluxo de opções não teria efeito.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Descarrega uma entrada da integração."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Recarrega a integração quando as opções mudam."""
    await hass.config_entries.async_reload(entry.entry_id)


def _async_migrate_unique_ids(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migra os unique_ids da v1.1.0 para o formato baseado em entry_id.

    O formato antigo (``combustivel_tipo_municipio``) colidia entre municípios
    homônimos e se perderia ao trocar de cidade pelas opções. Idempotente.
    """
    registry = er.async_get(hass)
    city = entry.data.get(CONF_CITY, DEFAULT_CITY)
    migrated = 0

    for fuel in FUEL_TYPES:
        for price_type in PRICE_TYPES:
            new_id = make_unique_id(entry.entry_id, fuel, price_type)
            if registry.async_get_entity_id("sensor", DOMAIN, new_id):
                continue  # já migrado

            for old_id in legacy_unique_ids(fuel, price_type, city):
                entity_id = registry.async_get_entity_id("sensor", DOMAIN, old_id)
                if entity_id is None:
                    continue
                _LOGGER.debug("Migrando unique_id %s -> %s", old_id, new_id)
                registry.async_update_entity(entity_id, new_unique_id=new_id)
                migrated += 1
                break

    if migrated:
        _LOGGER.info("Migradas %d entidades para o novo unique_id.", migrated)
