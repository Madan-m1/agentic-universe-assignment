
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def normalize_header(header: str) -> str:
    """
    Normalize CSV headers:
    lowercase, trim, and replace runs of
    underscores or whitespace with one space.
    """
    return re.sub(r"[_\s]+", " ", header.strip().lower())


def normalize_phone(value: str) -> str:
    """
    Normalize an Indian mobile number into +91XXXXXXXXXX.

    Raises ValueError if the number is invalid.
    """

    if value is None:
        raise ValueError("Phone number is missing")

    digits = re.sub(r"\D", "", str(value))

    # Remove Indian country code when present
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]

    # Remove leading zero when present
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]

    # Validate the resulting mobile number
    if len(digits) != 10 or digits[0] not in "6789":
        raise ValueError("Invalid Indian mobile number")

    return f"+91{digits}"


def normalize_date(value: str) -> str:
    if value is None or not str(value).strip():
        raise ValueError("Date is missing")

    value = str(value).strip()

    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d-%b-%Y",
    ]

    for date_format in formats:
        try:
            return datetime.strptime(value, date_format).date().isoformat()
        except ValueError:
            continue

    raise ValueError("Invalid date")


def normalize_decimal(value: str) -> str:
    if value is None or not str(value).strip():
        raise ValueError("Decimal is missing")

    cleaned = str(value).strip()

    # Remove supported currency prefixes.
    cleaned = re.sub(
        r"^(?:₹|rs\.?|inr)\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = cleaned.replace(",", "").strip()

    try:
        amount = Decimal(cleaned)
    except InvalidOperation as exc:
        raise ValueError("Invalid decimal") from exc

    if not amount.is_finite() or amount < 0:
        raise ValueError("Invalid decimal")

    return str(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def normalize_enum(value: str, allowed_values: list[str]) -> str:
    if value is None or not str(value).strip():
        raise ValueError("Enum value is missing")

    normalized = str(value).strip().casefold()
    allowed = {item.casefold(): item.lower() for item in allowed_values}

    if normalized not in allowed:
        raise ValueError("Invalid enum value")

    return allowed[normalized]
