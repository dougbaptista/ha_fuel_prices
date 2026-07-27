"""Verificações estruturais que não exigem uma instância do Home Assistant."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from custom_components.fuel_prices import config_flow, coordinator, sensor
from custom_components.fuel_prices.const import (
    DOMAIN,
    FUEL_ICONS,
    FUEL_TYPES,
    PRICE_TYPE_NAMES,
    PRICE_TYPES,
)

COMPONENT_DIR = Path(__file__).resolve().parents[1] / "custom_components" / DOMAIN


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_directory_name_matches_manifest_domain() -> None:
    """O Home Assistant exige que a pasta tenha o mesmo nome do domínio."""
    manifest = _load(COMPONENT_DIR / "manifest.json")
    assert manifest["domain"] == COMPONENT_DIR.name == DOMAIN


def test_manifest_requirements_are_pinned_and_exclude_core_deps() -> None:
    manifest = _load(COMPONENT_DIR / "manifest.json")
    for requirement in manifest["requirements"]:
        assert "==" in requirement, f"{requirement} precisa de versão fixada"
        # aiohttp é do core: declará-lo aqui pode atualizar a rede do HA.
        assert not requirement.startswith("aiohttp")


@pytest.mark.parametrize("locale", ["en", "pt-BR"])
def test_translations_match_strings_keys(locale: str) -> None:
    def keys(node: dict, prefix: str = "") -> set[str]:
        found = set()
        for key, value in node.items():
            found.add(prefix + key)
            if isinstance(value, dict):
                found |= keys(value, f"{prefix}{key}.")
        return found

    strings = _load(COMPONENT_DIR / "strings.json")
    translation = _load(COMPONENT_DIR / "translations" / f"{locale}.json")
    assert keys(strings) == keys(translation)


def test_every_fuel_and_price_type_is_labelled() -> None:
    assert set(PRICE_TYPE_NAMES) == set(PRICE_TYPES)
    assert set(FUEL_ICONS) == set(FUEL_TYPES)


def test_options_flow_does_not_assign_config_entry() -> None:
    """Atribuir ``self.config_entry`` foi removido no HA 2025.12."""
    assert "__init__" not in vars(config_flow.OptionsFlowHandler)


def test_effective_config_lets_options_override_data() -> None:
    entry = type("Entry", (), {"data": {"city": "TUBARAO"}, "options": {}})()
    assert coordinator.entry_config(entry)["city"] == "TUBARAO"

    entry.options = {"city": "CRICIUMA"}
    assert coordinator.entry_config(entry)["city"] == "CRICIUMA"


def test_sensor_declares_long_term_statistics_support() -> None:
    """Sem state_class os preços não entram nas estatísticas históricas."""
    assert sensor.FuelPriceSensor._attr_state_class == "measurement"


@pytest.mark.parametrize(
    ("unit", "expected"),
    [
        ("BRL/L", 3),  # bombas exibem 3 casas: 6,299
        ("BRL/13kg", 2),  # 112,140 parecia 112 mil
        ("BRL/m³", 2),  # a ANP publica GNV com 2 casas
        ("unidade nova", 2),
    ],
)
def test_display_precision_follows_the_unit(unit: str, expected: int) -> None:
    from custom_components.fuel_prices.const import DEFAULT_PRECISION, PRECISION_BY_UNIT

    assert PRECISION_BY_UNIT.get(unit, DEFAULT_PRECISION) == expected


class TestSelectedFuels:
    """Escolha de combustíveis (v1.4.0)."""

    @staticmethod
    def _entry(data: dict, options: dict | None = None):
        return type(
            "Entry", (), {"data": data, "options": options or {}, "entry_id": "abc"}
        )()

    def test_missing_key_keeps_every_fuel(self) -> None:
        """Instalações anteriores à v1.4.0 não têm a chave.

        Se isto falhar, atualizar faria sensores desaparecerem sozinhos.
        """
        entry = self._entry({"city": "TUBARAO"})
        assert coordinator.selected_fuels(entry) == list(FUEL_TYPES)

    def test_empty_list_falls_back_to_every_fuel(self) -> None:
        entry = self._entry({"fuels": []})
        assert coordinator.selected_fuels(entry) == list(FUEL_TYPES)

    def test_respects_the_selection(self) -> None:
        entry = self._entry({"fuels": ["GASOLINA COMUM", "GLP"]})
        assert coordinator.selected_fuels(entry) == ["GASOLINA COMUM", "GLP"]

    def test_options_override_data(self) -> None:
        entry = self._entry({"fuels": list(FUEL_TYPES)}, {"fuels": ["GNV"]})
        assert coordinator.selected_fuels(entry) == ["GNV"]

    def test_keeps_canonical_order_regardless_of_input(self) -> None:
        entry = self._entry({"fuels": ["GLP", "ETANOL HIDRATADO", "GASOLINA COMUM"]})
        assert coordinator.selected_fuels(entry) == [
            "ETANOL HIDRATADO",
            "GASOLINA COMUM",
            "GLP",
        ]

    def test_ignores_unknown_fuel_names(self) -> None:
        entry = self._entry({"fuels": ["GASOLINA COMUM", "QUEROSENE"]})
        assert coordinator.selected_fuels(entry) == ["GASOLINA COMUM"]
