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
from datetime import datetime
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
    module(
        "homeassistant.helpers.selector",
        SelectSelector=stub_class("SelectSelector"),
        SelectSelectorConfig=stub_class("SelectSelectorConfig"),
        SelectSelectorMode=types.SimpleNamespace(DROPDOWN="dropdown", LIST="list"),
    )
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


# Colunas exatamente como na planilha publicada pela ANP (verificado contra
# resumo_semanal_lpc_2026-07-19_2026-07-25.xlsx).
HEADER = [
    "DATA INICIAL",
    "DATA FINAL",
    "ESTADO",
    "MUNICÍPIO",
    "PRODUTO",
    "NÚMERO DE POSTOS PESQUISADOS",
    "UNIDADE DE MEDIDA",
    "PREÇO MÉDIO REVENDA",
    "DESVIO PADRÃO REVENDA",
    "PREÇO MÍNIMO REVENDA",
    "PREÇO MÁXIMO REVENDA",
    "COEF DE VARIAÇÃO REVENDA",
]

PERIOD_START = datetime(2026, 7, 19)
PERIOD_END = datetime(2026, 7, 25)


def anp_row(
    state: str,
    city: str,
    product: str,
    med: float,
    minimum: float,
    maximum: float,
    *,
    unit: str = "R$/l",
    stations: int = 8,
    period_end: datetime = PERIOD_END,
) -> list:
    """Monta uma linha no layout real da planilha da ANP."""
    return [
        PERIOD_START,
        period_end,
        state,
        city,
        product,
        stations,
        unit,
        med,
        0.1,
        minimum,
        maximum,
        0.02,
    ]


def build_workbook(rows: list[list], *, header_offset: int = 9) -> bytes:
    """Gera um XLSX no formato da ANP (cabeçalho após linhas de metadados)."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "MUNICIPIOS"

    for _ in range(header_offset):
        sheet.append(["LEVANTAMENTO DE PREÇOS DE COMBUSTÍVEIS"])
    sheet.append(HEADER)
    for row in rows:
        sheet.append(row)

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


@pytest.fixture
def anp_workbook() -> bytes:
    """Planilha de exemplo no layout real, com as unidades por produto.

    Os nomes vêm sem acento, como a ANP realmente publica, mas há uma linha
    acentuada para provar que a normalização cobre os dois casos.
    """
    return build_workbook(
        [
            anp_row("SANTA CATARINA", "TUBARAO", "GASOLINA COMUM", 6.30, 6.26, 6.66),
            anp_row("SANTA CATARINA", "TUBARAO", "OLEO DIESEL S10", 6.28, 6.28, 6.29),
            anp_row("SANTA CATARINA", "TUBARAO", "ETANOL HIDRATADO", 4.58, 4.58, 4.59),
            anp_row(
                "SANTA CATARINA",
                "TUBARAO",
                "GLP",
                112.14,
                100.0,
                120.0,
                unit="R$/13kg",
                stations=7,
            ),
            anp_row(
                "SANTA CATARINA",
                "TUBARAO",
                "GNV",
                4.94,
                4.89,
                4.96,
                unit="R$/m³",
                stations=6,
            ),
            anp_row("SAO PAULO", "TUBARAO", "GASOLINA COMUM", 5.55, 5.19, 5.99),
            # Acentuada de propósito: a ANP publica sem acento hoje, mas a
            # normalização precisa cobrir uma eventual mudança.
            anp_row("SANTA CATARINA", "CRICIÚMA", "ÓLEO DIESEL", 6.02, 5.99, 6.19),
        ]
    )
