from homeassistant.helpers.entity import Entity
from .const import DOMAIN

async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    sensors = []

    for fuel, price in coordinator.data.items():
        sensors.append(FuelPriceSensor(fuel, price, coordinator))

    async_add_entities(sensors)

class FuelPriceSensor(Entity):
    def __init__(self, name, price, coordinator):
        self._name = f"Preço {name}"
        self._state = price
        self._coordinator = coordinator

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def unit_of_measurement(self):
        return "R$"

    async def async_update(self):
        await self._coordinator.async_request_refresh()
