
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


IST = ZoneInfo("Asia/Kolkata")


def normalize_event_timestamp(value: str) -> str:
    """
    Convert an event timestamp to UTC ISO 8601 format.

    Naive timestamps are interpreted as Asia/Kolkata time.
    Timestamps with an explicit timezone retain that timezone
    during conversion to UTC.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Event timestamp is missing")

    raw = value.strip()

    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid event timestamp") from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=IST)

    utc_value = parsed.astimezone(timezone.utc)

    return utc_value.isoformat(timespec="seconds").replace("+00:00", "Z")
