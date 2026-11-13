
import pytest

from solution.ingestion.event_normalizers import normalize_event_timestamp


def test_utc_timestamp():
    assert normalize_event_timestamp(
        "2026-10-01T05:26:10Z"
    ) == "2026-10-01T05:26:10Z"


def test_offset_timestamp():
    assert normalize_event_timestamp(
        "2026-10-01T10:56:10+05:30"
    ) == "2026-10-01T05:26:10Z"


def test_naive_timestamp_is_ist():
    assert normalize_event_timestamp(
        "2026-10-01T10:56:10"
    ) == "2026-10-01T05:26:10Z"


@pytest.mark.parametrize("value", ["", "   ", None])
def test_missing_timestamp_raises(value):
    with pytest.raises(ValueError):
        normalize_event_timestamp(value)


def test_invalid_timestamp_raises():
    with pytest.raises(ValueError):
        normalize_event_timestamp("not-a-timestamp")
