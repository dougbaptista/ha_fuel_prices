"""Sensores de preço de combustível."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    BASE_URL,
    DEFAULT_UNIT,
    DOMAIN,
    FUEL_ICONS,
    FUEL_TYPES,
    MAX_DATA_AGE,
    PRICE_TYPE_NAMES,
    PRICE_TYPES,
    UNIT_BY_FUEL,
)
from .coordinator import FuelPriceCoordinator
from .parser import make_unique_id


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Cria os sensores a partir do coordinator já inicializado."""
    coordinator: FuelPriceCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        FuelPriceSensor(coordinator, fuel, price_type)
        for fuel in FUEL_TYPES
        for price_type in PRICE_TYPES
    )


class FuelPriceSensor(CoordinatorEntity[FuelPriceCoordinator], SensorEntity):
    """Preço (mínimo, médio ou máximo) de um combustível no município."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 3

    def __init__(
        self,
        coordinator: FuelPriceCoordinator,
        fuel_type: str,
        price_type: str,
    ) -> None:
        super().__init__(coordinator)
        self._fuel_type = fuel_type
        self._price_type = price_type

        self._attr_unique_id = make_unique_id(
            coordinator.entry.entry_id, fuel_type, price_type
        )
        self._attr_native_unit_of_measurement = UNIT_BY_FUEL.get(
            fuel_type, DEFAULT_UNIT
        )
        self._attr_icon = FUEL_ICONS.get(fuel_type, "mdi:cash")
        self._attr_name = (
            f"Preço {fuel_type.title()} ({coordinator.city_name.title()})"
            f" - {PRICE_TYPE_NAMES[price_type]}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=f"Preços ANP — {coordinator.city_name.title()}",
            manufacturer="ANP",
            model="Levantamento semanal de preços",
            configuration_url=BASE_URL,
        )

    @property
    def _price_info(self) -> dict | None:
        """Bloco de preços do combustível no último dado coletado."""
        return (self.coordinator.data or {}).get(self._fuel_type)

    @property
    def _is_stale(self) -> bool:
        """Indica se o dado em cache é antigo demais para ser confiável.

        Os dados da ANP são semanais; passado ``MAX_DATA_AGE`` sem uma coleta
        bem-sucedida é melhor sinalizar indisponibilidade do que seguir
        publicando um preço desatualizado como se fosse atual.
        """
        last = self.coordinator.last_successful_update
        if last is None:
            return True
        return dt_util.utcnow() - last > MAX_DATA_AGE

    @property
    def available(self) -> bool:
        """Mantém o último valor válido durante falhas passageiras."""
        if self._price_info is None:
            return False
        return self.coordinator.last_update_success or not self._is_stale

    @property
    def native_value(self) -> float | None:
        """Preço correspondente ao tipo deste sensor."""
        price_info = self._price_info
        if price_info is None:
            return None
        return price_info.get(self._price_type)

    @property
    def extra_state_attributes(self) -> dict:
        """Expõe os três preços, a origem e a idade do dado."""
        price_info = self._price_info or {}
        last = self.coordinator.last_successful_update
        return {
            "min": price_info.get("min"),
            "med": price_info.get("med"),
            "max": price_info.get("max"),
            "state_name": self.coordinator.state_name,
            "city_name": self.coordinator.city_name,
            "last_successful_update": last.isoformat() if last else None,
            "stale": self._is_stale,
        }
