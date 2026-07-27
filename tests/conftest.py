"""Configuração dos testes.

O módulo ``parser`` não depende do Home Assistant, então a maior parte da
suíte roda sem stubs. Os stubs abaixo só são instalados se o pacote
``homeassistant`` não estiver disponível, permitindo importar ``sensor`` e
``coordinator`` num ambiente enxuto sem impedir o uso do HA de verdade (e do
``pytest-homeassistant-custom-component``) quando ele estiver instalado.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from io import BytesIO

import pytest
from openpyxl import Workbook


def _install_homeassistant_stubs() -> None:
    """Cria um pacote ``homeassistant`` mínimo em ``sys.modules``."""
    modules: dict[str, types.ModuleType] = {}

    def stub_class(name: str, *bases: type) -> type:
        """Classe substituta tolerante às formas usadas pelo HA.

        Aceita subscrição genérica (``Foo[dict]``) e argumentos de classe
        (``class Bar(ConfigFlow, domain="x")``).
        """
        return type(
            name,
            bases or (),
            {
                "__class_getitem__": classmethod(lambda cls, item: cls),
                "__init_subclass__": classmethod(lambda cls, **kwargs: None),
            },
        )

    def module(name: str, **attrs: object) -> types.ModuleType:
        mod = types.ModuleType(name)
        for key, value in attrs.items():
            setattr(mod, key, value)
        modules[name] = mod
        return mod

    module("homeassistant")
    module("homeassistant.components")
    module(
        "homeassistant.components.sensor",
        SensorEntity=stub_class("SensorEntity"),
        SensorStateClass=types.SimpleNamespace(
            MEASUREMENT="measurement",
            TOTAL="total",
            TOTAL_INCREASING="total_increasing",
        ),
    )
    module(
        "homeassistant.config_entries",
        ConfigEntry=stub_class("ConfigEntry"),
        ConfigFlow=stub_class("ConfigFlow"),
        ConfigFlowResult=dict,
        OptionsFlow=stub_class("OptionsFlow"),
    )
    module("homeassistant.core", HomeAssistant=stub_class("HomeAssistant"))
    module("homeassistant.helpers")
    module(
        "homeassistant.helpers.aiohttp_client",
        async_get_clientsession=lambda hass: None,
    )
    module("homeassistant.helpers.device_registry", DeviceInfo=dict)
    module("homeassistant.helpers.entity_platform", AddEntitiesCallback=object)
    module("homeassistant.helpers.entity_registry", async_get=lambda hass: None)
    module("homeassistant.helpers.typing", ConfigType=dict)
    module(
        "homeassistant.helpers.update_coordinator",
        DataUpdateCoordinator=stub_class("DataUpdateCoordinator"),
        CoordinatorEntity=stub_class("CoordinatorEntity"),
        UpdateFailed=stub_class("UpdateFailed", Exception),
    )
    module("homeassistant.util")
    module("homeassistant.util.dt", utcnow=lambda: None)

    # Liga os submódulos aos pais para que "import a.b" resolva atributos.
    for name, mod in modules.items():
        parent, _, child = name.rpartition(".")
        if parent:
            setattr(modules[parent], child, mod)

    sys.modules.update(modules)


if importlib.util.find_spec("homeassistant") is None:  # pragma: no cover
    _install_homeassistant_stubs()


HEADER = [
    "ESTADO",
    "MUNICÍPIO",
    "PRODUTO",
    "PREÇO MÉDIO REVENDA",
    "PREÇO MÍNIMO REVENDA",
    "PREÇO MÁXIMO REVENDA",
]


def build_workbook(rows: list[list], *, header_offset: int = 9) -> bytes:
    """Gera um XLSX no formato da ANP (cabeçalho após linhas de metadados)."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "MUNICIPIOS"

    for _ in range(header_offset):
        sheet.append(["LEVANTAMENTO DE PREÇOS"])
    sheet.append(HEADER)
    for row in rows:
        sheet.append(row)

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


@pytest.fixture
def anp_workbook() -> bytes:
    """Planilha de exemplo com acentuação real nos nomes de produto."""
    return build_workbook(
        [
            ["SANTA CATARINA", "TUBARÃO", "GASOLINA COMUM", 6.09, 5.89, 6.39],
            ["SANTA CATARINA", "TUBARÃO", "ÓLEO DIESEL S10", 6.21, 5.99, 6.49],
            ["SANTA CATARINA", "TUBARÃO", "ETANOL HIDRATADO", 4.55, 4.29, 4.79],
            ["SANTA CATARINA", "TUBARÃO", "GLP", 102.5, 95.0, 110.0],
            ["SÃO PAULO", "TUBARÃO", "GASOLINA COMUM", 5.55, 5.19, 5.99],
            ["SANTA CATARINA", "CRICIÚMA", "GASOLINA COMUM", 6.11, 5.95, 6.45],
        ]
    )
