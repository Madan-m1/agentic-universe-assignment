
import pytest

from solution.ingestion.normalizers import (
    normalize_phone,
    normalize_header
)


@pytest.mark.parametrize(
    "input_phone, expected",
    [
        ("9932302346", "+919932302346"),
        ("+919932302346", "+919932302346"),
        ("+91 99323 02346", "+919932302346"),
        ("91-99323-02346", "+919932302346"),
        ("09932302346", "+919932302346"),
        ("99323-02346", "+919932302346"),
    ]
)
def test_valid_phone_numbers(input_phone, expected):
    assert normalize_phone(input_phone) == expected


@pytest.mark.parametrize(
    "input_phone",
    [
        "",
        "1234567890",
        "12345678901",
        "12345",
        "abcdefghij",
        "5555555555",
    ]
)
def test_invalid_phone_numbers(input_phone):
    with pytest.raises(ValueError):
        normalize_phone(input_phone)


def test_missing_phone():
    with pytest.raises(ValueError):
        normalize_phone(None)


@pytest.mark.parametrize(
    "input_header, expected",
    [
        ("Customer_Name", "customer name"),
        (" PHONE NUMBER ", "phone number"),
        ("Policy___Number", "policy number"),
        ("Preferred   Language", "preferred language"),
    ]
)
def test_header_normalization(input_header, expected):
    assert normalize_header(input_header) == expected
