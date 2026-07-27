import sys
import types
import pytest

# Inject minimal fake 'homeassistant' package to allow importing the sensor module
ha = types.ModuleType("homeassistant")

# homeassistant.components.sensor.SensorEntity
components = types.ModuleType("homeassistant.components")
sensor_mod = types.ModuleType("homeassistant.components.sensor")
class _FakeSensorEntity:
    pass
sensor_mod.SensorEntity = _FakeSensorEntity
components.sensor = sensor_mod
ha.components = components

# homeassistant.config_entries.ConfigEntry
config_entries = types.ModuleType("homeassistant.config_entries")
class _FakeConfigEntry:
    pass
config_entries.ConfigEntry = _FakeConfigEntry
ha.config_entries = config_entries

# homeassistant.core.HomeAssistant
core = types.ModuleType("homeassistant.core")
class _FakeHomeAssistant:
    pass
core.HomeAssistant = _FakeHomeAssistant
ha.core = core

# homeassistant.helpers submodules
helpers = types.ModuleType("homeassistant.helpers")
# create a submodule typing
typing_mod = types.ModuleType("homeassistant.helpers.typing")
class ConfigType(dict):
    pass
typing_mod.ConfigType = ConfigType
helpers.typing = typing_mod
aiohttp_client = types.ModuleType("homeassistant.helpers.aiohttp_client")
def async_get_clientsession(hass):
    return None
aiohttp_client.async_get_clientsession = async_get_clientsession
helpers.aiohttp_client = aiohttp_client

entity_mod = types.ModuleType("homeassistant.helpers.entity")
class DeviceInfo:
    pass
entity_mod.DeviceInfo = DeviceInfo
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

from custom_components.ha_fuel_prices.sensor import (make_unique_id,
                                                     normalize_text)


@pytest.mark.parametrize(
    "input,expected",
    [
        ("SãO Paulo", "SAO PAULO"),
        ("tubarão", "TUBARAO"),
        (123, "123"),
    ],
)
def test_normalize_text(input, expected):
    assert normalize_text(input) == expected


def test_make_unique_id():
    uid = make_unique_id("GASOLINA COMUM", "med", "TUBARAO")
    assert "gasolina" in uid
    assert "med" in uid
    assert "tubarao" in uid
