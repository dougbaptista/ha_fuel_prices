"""Testes da lógica pura de scraping e parsing."""

from __future__ import annotations

import pytest

from custom_components.fuel_prices.const import BASE_URL, FUEL_TYPES
from custom_components.fuel_prices.parser import (
    MunicipalityNotFoundError,
    SourceUnavailableError,
    coerce_date,
    coerce_price,
    find_xls_url,
    legacy_unique_ids,
    list_locations,
    make_unique_id,
    normalize_text,
    parse_workbook,
    translate_unit,
)

from .conftest import anp_row, build_workbook


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("SãO Paulo", "SAO PAULO"),
        ("tubarão", "TUBARAO"),
        ("  ÓLEO   DIESEL  S10 ", "OLEO DIESEL S10"),
        ("Criciúma\n", "CRICIUMA"),
    ],
)
def test_normalize_text(raw: str, expected: str) -> None:
    assert normalize_text(raw) == expected


def test_make_unique_id_is_stable_and_scoped_to_entry() -> None:
    uid = make_unique_id("abc123", "GASOLINA COMUM", "med")
    assert uid == "abc123_gasolina_comum_med"
    # Municípios homônimos em entradas distintas não colidem.
    assert uid != make_unique_id("def456", "GASOLINA COMUM", "med")


# Amostra retirada do core.entity_registry de uma instalação real (21
# entidades). A migração precisa reconhecer exatamente estes identificadores,
# senão o histórico dos sensores existentes é perdido.
REAL_LEGACY_IDS = [
    ("ETANOL HIDRATADO", "max", "fuel_prices_etanol_hidratado_max_tubarao"),
    ("GASOLINA ADITIVADA", "med", "fuel_prices_gasolina_aditivada_med_tubarao"),
    ("GASOLINA COMUM", "min", "fuel_prices_gasolina_comum_min_tubarao"),
    ("GLP", "med", "fuel_prices_glp_med_tubarao"),
    ("GNV", "max", "fuel_prices_gnv_max_tubarao"),
    ("OLEO DIESEL", "med", "fuel_prices_oleo_diesel_med_tubarao"),
    ("OLEO DIESEL S10", "min", "fuel_prices_oleo_diesel_s10_min_tubarao"),
]


@pytest.mark.parametrize(("fuel", "price_type", "expected"), REAL_LEGACY_IDS)
def test_legacy_ids_cover_real_installations(
    fuel: str, price_type: str, expected: str
) -> None:
    assert expected in legacy_unique_ids(fuel, price_type, "TUBARAO")


def test_legacy_ids_cover_both_historical_formats() -> None:
    ids = legacy_unique_ids("GASOLINA COMUM", "med", "TUBARAO")
    assert ids == (
        "fuel_prices_gasolina_comum_med_tubarao",  # v1.0.x, em produção
        "gasolina_comum_med_tubarao",  # v1.1.0, apenas no git
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (6.09, 6.09),
        ("6,09", 6.09),
        ("1.234,56", 1234.56),
        ("1234.56", 1234.56),
        (None, None),
        ("-", None),
        ("", None),
        ("n/d", None),
    ],
)
def test_coerce_price(raw: object, expected: float | None) -> None:
    assert coerce_price(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-07-25 00:00:00", "2026-07-25"),
        ("2026-07-25", "2026-07-25"),
        ("25/07/2026", "2026-07-25"),
        (None, None),
        ("qualquer coisa", None),
    ],
)
def test_coerce_date(raw: object, expected: str | None) -> None:
    assert coerce_date(raw) == expected


@pytest.mark.parametrize(
    ("raw", "product", "expected"),
    [
        ("R$/l", "GASOLINA COMUM", "BRL/L"),
        ("R$/13kg", "GLP", "BRL/13kg"),
        ("R$/m³", "GNV", "BRL/m³"),
        # Sem a coluna, cai no padrão correto por produto.
        (None, "GLP", "BRL/13kg"),
        (None, "GNV", "BRL/m³"),
        (None, "GASOLINA COMUM", "BRL/L"),
        ("unidade nova", "GLP", "BRL/13kg"),
    ],
)
def test_translate_unit(raw: object, product: str, expected: str) -> None:
    assert translate_unit(raw, product) == expected


class TestParseWorkbook:
    def test_extracts_prices_under_normalized_keys(self, anp_workbook: bytes) -> None:
        prices = parse_workbook(anp_workbook, "SANTA CATARINA", "TUBARAO")

        assert set(prices) <= set(FUEL_TYPES)
        gasoline = prices["GASOLINA COMUM"]
        assert (gasoline["min"], gasoline["med"], gasoline["max"]) == (
            6.26,
            6.30,
            6.66,
        )

    def test_normalizes_accented_products(self, anp_workbook: bytes) -> None:
        """A ANP publica sem acento hoje, mas não podemos depender disso."""
        prices = parse_workbook(anp_workbook, "SANTA CATARINA", "CRICIUMA")
        assert "OLEO DIESEL" in prices

    def test_matches_accented_input_from_the_user(self, anp_workbook: bytes) -> None:
        assert parse_workbook(anp_workbook, "Santa Catarina", "Tubarão")

    def test_filters_by_state_not_only_city(self, anp_workbook: bytes) -> None:
        prices = parse_workbook(anp_workbook, "SAO PAULO", "TUBARAO")
        assert prices["GASOLINA COMUM"]["med"] == 5.55

    def test_reads_unit_from_the_sheet(self, anp_workbook: bytes) -> None:
        """GLP é cotado por botijão de 13 kg e GNV por m³, não por litro."""
        prices = parse_workbook(anp_workbook, "SANTA CATARINA", "TUBARAO")
        assert prices["GLP"]["unit"] == "BRL/13kg"
        assert prices["GNV"]["unit"] == "BRL/m³"
        assert prices["GASOLINA COMUM"]["unit"] == "BRL/L"

    def test_exposes_reference_period_and_sample_size(
        self, anp_workbook: bytes
    ) -> None:
        glp = parse_workbook(anp_workbook, "SANTA CATARINA", "TUBARAO")["GLP"]
        assert glp["period_start"] == "2026-07-19"
        assert glp["period_end"] == "2026-07-25"
        assert glp["stations"] == 7

    def test_list_locations_groups_cities_by_state(self, anp_workbook: bytes) -> None:
        """Alimenta os seletores do fluxo de configuração."""
        locais = list_locations(anp_workbook)

        assert set(locais) == {"SANTA CATARINA", "SAO PAULO"}
        assert locais["SANTA CATARINA"] == ["CRICIUMA", "TUBARAO"]
        assert locais["SAO PAULO"] == ["TUBARAO"]

    def test_list_locations_normalizes_accents(self, anp_workbook: bytes) -> None:
        # A linha de Criciúma está acentuada na planilha de teste.
        assert "CRICIUMA" in list_locations(anp_workbook)["SANTA CATARINA"]

    def test_unknown_municipality_raises(self, anp_workbook: bytes) -> None:
        with pytest.raises(MunicipalityNotFoundError):
            parse_workbook(anp_workbook, "SANTA CATARINA", "CIDADE INEXISTENTE")

    def test_header_position_is_detected_not_hardcoded(self) -> None:
        content = build_workbook(
            [anp_row("SANTA CATARINA", "TUBARAO", "GNV", 4.2, 4.0, 4.4)],
            header_offset=3,
        )
        prices = parse_workbook(content, "SANTA CATARINA", "TUBARAO")
        assert prices["GNV"]["med"] == 4.2

    def test_missing_sheet_raises_source_error(self) -> None:
        from io import BytesIO

        from openpyxl import Workbook

        workbook = Workbook()
        workbook.active.title = "OUTRA"
        buffer = BytesIO()
        workbook.save(buffer)

        with pytest.raises(SourceUnavailableError, match="MUNICIPIOS"):
            parse_workbook(buffer.getvalue(), "SANTA CATARINA", "TUBARAO")


class TestFindXlsUrl:
    def test_resolves_relative_href(self) -> None:
        html = """
          <a href="/anp/arquivos/precos-semanais-municipios.xlsx">
            <span>Preços médios semanais:</span> Brasil, regiões, estados e
            <strong>municípios</strong>
          </a>
        """
        # Regressão: find_all(string=...) não casava texto dentro de <span>.
        assert find_xls_url(html, BASE_URL) == (
            "https://www.gov.br/anp/arquivos/precos-semanais-municipios.xlsx"
        )

    def test_rejects_external_host(self) -> None:
        html = (
            '<a href="https://exemplo-malicioso.com/x.xlsx">'
            "Preços médios semanais: Brasil, regiões, estados e municípios</a>"
        )
        with pytest.raises(SourceUnavailableError, match="host inesperado"):
            find_xls_url(html, BASE_URL)

    def test_rejects_non_spreadsheet_link(self) -> None:
        html = (
            '<a href="/anp/pagina.html">Preços médios semanais: Brasil, '
            "regiões, estados e municípios</a>"
        )
        with pytest.raises(SourceUnavailableError):
            find_xls_url(html, BASE_URL)

    def test_missing_link_raises(self) -> None:
        with pytest.raises(SourceUnavailableError):
            find_xls_url("<a href='/x.xlsx'>Outro relatório</a>", BASE_URL)
