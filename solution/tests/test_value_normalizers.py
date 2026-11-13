import pytest

from solution.ingestion.normalizers import (
    normalize_date,
    normalize_decimal,
    normalize_enum,
)


@pytest.mark.parametrize("value, expected", [
    ("2026-11-21", "2026-11-21"),
    ("21/11/2026", "2026-11-21"),
    ("21-11-2026", "2026-11-21"),
    ("21-Nov-2026", "2026-11-21"),
])
def test_valid_dates(value, expected):
    assert normalize_date(value) == expected


@pytest.mark.parametrize("value", [
    "31/02/2026",
    "2026-13-01",
    "not-a-date",
    "",
])
def test_invalid_dates(value):
    with pytest.raises(ValueError):
        normalize_date(value)


@pytest.mark.parametrize("value, expected", [
    ("27554", "27554.00"),
    ("₹27,554", "27554.00"),
    ("Rs. 6,850", "6850.00"),
    ("INR 25301.4", "25301.40"),
    ("12.345", "12.35"),
    ("0", "0.00"),
])
def test_valid_decimals(value, expected):
    assert normalize_decimal(value) == expected


@pytest.mark.parametrize("value", [
    "-100",
    "abc",
    "",
    "₹",
    "NaN",
    "Infinity",
])
def test_invalid_decimals(value):
    with pytest.raises(ValueError):
        normalize_decimal(value)


def test_valid_enum_case_insensitive():
    assert normalize_enum("HI", ["en", "hi", "ta"]) == "hi"


def test_valid_enum_trims_spaces():
    assert normalize_enum("  ta  ", ["en", "hi", "ta"]) == "ta"


def test_invalid_enum():
    with pytest.raises(ValueError):
        normalize_enum("Hindi", ["en", "hi", "ta"])


def test_missing_enum():
    with pytest.raises(ValueError):
        normalize_enum("", ["en", "hi", "ta"])