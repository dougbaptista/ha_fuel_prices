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
    DEFAULT_PRECISION,
    DEFAULT_UNIT,
    DOMAIN,
    FALLBACK_UNITS,
    FUEL_ICONS,
    MAX_DATA_AGE,
    PRECISION_BY_UNIT,
    PRICE_TYPE_NAMES,
    PRICE_TYPES,
)
from .coordinator import FuelPriceCoordinator, selected_fuels
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
        for fuel in selected_fuels(entry)
        for price_type in PRICE_TYPES
    )


class FuelPriceSensor(CoordinatorEntity[FuelPriceCoordinator], SensorEntity):
    """Preço (mínimo, médio ou máximo) de um combustível no município."""

    _attr_state_class = SensorStateClass.MEASUREMENT

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
        # A unidade vem da própria planilha (GLP é por botijão de 13 kg, GNV
        # por m³). Fixada na construção para não variar durante a vida da
        # entidade, o que invalidaria as estatísticas de longo prazo.
        initial = (coordinator.data or {}).get(fuel_type) or {}
        unit = initial.get("unit") or FALLBACK_UNITS.get(fuel_type, DEFAULT_UNIT)
        self._attr_native_unit_of_measurement = unit
        self._attr_suggested_display_precision = PRECISION_BY_UNIT.get(
            unit, DEFAULT_PRECISION
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
        """Indica se o dado é antigo demais para ser confiável.

        Usa o fim do período de referência publicado na planilha, que é o que
        realmente data o preço; a hora da coleta é só o fallback. Os dados da
        ANP são semanais, então passado ``MAX_DATA_AGE`` é melhor sinalizar
        indisponibilidade do que publicar um preço velho como se fosse atual.
        """
        reference = (self._price_info or {}).get("period_end")
        if reference:
            parsed = dt_util.parse_date(reference)
            if parsed is not None:
                age = dt_util.utcnow().date() - parsed
                return age > MAX_DATA_AGE

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
            # Quantos postos a ANP pesquisou: amostra pequena significa preço
            # menos representativo.
            "surveyed_stations": price_info.get("stations"),
            "period_start": price_info.get("period_start"),
            "period_end": price_info.get("period_end"),
            "last_successful_update": last.isoformat() if last else None,
            "stale": self._is_stale,
        }
