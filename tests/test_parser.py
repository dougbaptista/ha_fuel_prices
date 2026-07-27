"""Testes da lógica pura de scraping e parsing."""

from __future__ import annotations

import pytest

from custom_components.fuel_prices.const import BASE_URL, FUEL_TYPES
from custom_components.fuel_prices.parser import (
    MunicipalityNotFoundError,
    SourceUnavailableError,
    coerce_price,
    find_xls_url,
    legacy_unique_id,
    make_unique_id,
    normalize_text,
    parse_workbook,
)

from .conftest import build_workbook


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


def test_legacy_unique_id_matches_v1_1_0_format() -> None:
    assert legacy_unique_id("GASOLINA COMUM", "med", "TUBARAO") == (
        "gasolina_comum_med_tubarao"
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


class TestParseWorkbook:
    def test_extracts_accented_products_under_normalized_keys(
        self, anp_workbook: bytes
    ) -> None:
        prices = parse_workbook(anp_workbook, "SANTA CATARINA", "TUBARAO")

        # Regressão: até a v1.1.0 a chave era gravada crua ("ÓLEO DIESEL S10"),
        # nunca casando com a lista normalizada de combustíveis.
        assert "OLEO DIESEL S10" in prices
        assert set(prices) <= set(FUEL_TYPES)
        assert prices["GASOLINA COMUM"] == {"min": 5.89, "med": 6.09, "max": 6.39}

    def test_matches_accented_input_from_the_user(self, anp_workbook: bytes) -> None:
        assert parse_workbook(anp_workbook, "Santa Catarina", "Tubarão")

    def test_filters_by_state_not_only_city(self, anp_workbook: bytes) -> None:
        prices = parse_workbook(anp_workbook, "SAO PAULO", "TUBARAO")
        assert prices["GASOLINA COMUM"]["med"] == 5.55

    def test_unknown_municipality_raises(self, anp_workbook: bytes) -> None:
        with pytest.raises(MunicipalityNotFoundError):
            parse_workbook(anp_workbook, "SANTA CATARINA", "CIDADE INEXISTENTE")

    def test_header_position_is_detected_not_hardcoded(self) -> None:
        content = build_workbook(
            [["SANTA CATARINA", "TUBARÃO", "GNV", 4.2, 4.0, 4.4]],
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
