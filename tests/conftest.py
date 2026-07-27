import sys
import types

# Create minimal fake 'homeassistant' package for unit tests
ha = types.ModuleType("homeassistant")

components = types.ModuleType("homeassistant.components")
sensor_mod = types.ModuleType("homeassistant.components.sensor")
class _FakeSensorEntity:
    pass
sensor_mod.SensorEntity = _FakeSensorEntity
components.sensor = sensor_mod
ha.components = components

config_entries = types.ModuleType("homeassistant.config_entries")
config_entries.ConfigEntry = type("ConfigEntry", (), {})
ha.config_entries = config_entries

core = types.ModuleType("homeassistant.core")
core.HomeAssistant = type("HomeAssistant", (), {})
ha.core = core

helpers = types.ModuleType("homeassistant.helpers")
typing_mod = types.ModuleType("homeassistant.helpers.typing")
typing_mod.ConfigType = dict
helpers.typing = typing_mod

aiohttp_client = types.ModuleType("homeassistant.helpers.aiohttp_client")
def async_get_clientsession(hass):
    return None
aiohttp_client.async_get_clientsession = async_get_clientsession
helpers.aiohttp_client = aiohttp_client

entity_mod = types.ModuleType("homeassistant.helpers.entity")
entity_mod.DeviceInfo = object
helpers.entity = entity_mod

update_coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")
class DataUpdateCoordinator:
    def __init__(self, hass, logger, name=None, update_interval=None):
        pass
class UpdateFailed(Exception):
    pass
class CoordinatorEntity:
    pass
update_coordinator.DataUpdateCoordinator = DataUpdateCoordinator
update_coordinator.UpdateFailed = UpdateFailed
update_coordinator.CoordinatorEntity = CoordinatorEntity
helpers.update_coordinator = update_coordinator

ha.helpers = helpers

sys.modules["homeassistant"] = ha
sys.modules["homeassistant.components"] = components
sys.modules["homeassistant.components.sensor"] = sensor_mod
sys.modules["homeassistant.config_entries"] = config_entries
sys.modules["homeassistant.core"] = core
sys.modules["homeassistant.helpers"] = helpers
sys.modules["homeassistant.helpers.aiohttp_client"] = aiohttp_client
sys.modules["homeassistant.helpers.entity"] = entity_mod
sys.modules["homeassistant.helpers.update_coordinator"] = update_coordinator
sys.modules["homeassistant.helpers.typing"] = typing_mod
