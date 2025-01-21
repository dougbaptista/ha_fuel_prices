from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

FUEL_TYPES = [
    "ETANOL HIDRATADO",
    "GASOLINA ADITIVADA",
    "GASOLINA COMUM",
    "GLP",
    "GNV",
    "OLEO DIESEL",
    "OLEO DIESEL S10",
]

async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    sensors = [
        FuelPriceSensor(coordinator, fuel_type)
        for fuel_type in FUEL_TYPES
    ]

    async_add_entities(sensors, update_before_add=True)

class FuelPriceSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, fuel_type):
        super().__init__(coordinator)
        self._fuel_type = fuel_type
        self._attr_name = f"Preço Médio {fuel_type}"
        self._attr_unique_id = f"fuel_price_{fuel_type.replace(' ', '_').lower()}"

    @property
    def native_value(self):
        """Return the current fuel price."""
        value = self.coordinator.data.get(self._fuel_type)
        if value is None:
            _LOGGER.debug(f"Dados para {self._fuel_type} não encontrados. Dados disponíveis: {self.coordinator.data}")
        return value
        

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "R$/L"

