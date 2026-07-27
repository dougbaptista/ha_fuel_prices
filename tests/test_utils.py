import pytest

from custom_components.ha_fuel_prices.sensor import normalize_text, make_unique_id


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
