from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Configuração inicial do sensor."""
    sensors = [
        FuelPriceSensor(entry.data, "Etanol Hidratado"),
        FuelPriceSensor(entry.data, "Gasolina Comum"),
        FuelPriceSensor(entry.data, "Gasolina Aditivada"),
        FuelPriceSensor(entry.data, "GLP"),
        FuelPriceSensor(entry.data, "GNV"),
        FuelPriceSensor(entry.data, "Óleo Diesel"),
        FuelPriceSensor(entry.data, "Óleo Diesel S10"),
    ]
    async_add_entities(sensors)

class FuelPriceSensor(SensorEntity):
    """Representação de um sensor de preço de combustível."""

    def __init__(self, config, fuel_type):
        self._fuel_type = fuel_type
        self._state = None
        self._attr_name = f"Preço {fuel_type}"
        self._attr_unique_id = f"{DOMAIN}_{fuel_type.lower().replace(' ', '_')}"

    async def async_update(self):
        """Atualizar o estado do sensor."""
        # Lógica para atualizar o preço médio do combustível aqui
        # Exemplo fictício:
        self._state = 5.67  # Substituir com o valor correto
