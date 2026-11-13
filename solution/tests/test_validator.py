from solution.ingestion.schema_loader import load_schema
from solution.ingestion.validator import validate_row


def motor_schema():
    return load_schema("motor_renewal")


def valid_motor_row():
    return {
        "customer_name": "Aarav Menon",
        "phone": "9932302346",
        "policy_number": "MOT/2026/100142",
        "policy_expiry": "21-11-2026",
        "premium_amount": "₹27,554",
        "preferred_language": "mr",
    }


def test_valid_motor_row():
    result = validate_row(motor_schema(), valid_motor_row())

    assert result["accepted"] is True
    assert result["data"]["phone"] == "+919932302346"
    assert result["data"]["policy_expiry"] == "2026-11-21"
    assert result["data"]["premium_amount"] == "27554.00"
    assert result["rejection_reason"] is None
    assert result["warnings"] == []


def test_missing_required_field():
    row = valid_motor_row()
    row["policy_number"] = ""

    result = validate_row(motor_schema(), row)

    assert result["accepted"] is False
    assert result["rejection_reason"] == "missing_required:policy_number"


def test_invalid_phone_rejected():
    row = valid_motor_row()
    row["phone"] = "12345"

    result = validate_row(motor_schema(), row)

    assert result["accepted"] is False
    assert result["rejection_reason"] == "invalid_phone"


def test_invalid_optional_date_becomes_null():
    row = valid_motor_row()
    row["policy_expiry"] = "31/02/2026"

    result = validate_row(motor_schema(), row)

    assert result["accepted"] is True
    assert result["data"]["policy_expiry"] is None
    assert result["warnings"] == ["policy_expiry"]


def test_invalid_optional_enum_becomes_null():
    row = valid_motor_row()
    row["preferred_language"] = "Hindi"

    result = validate_row(motor_schema(), row)

    assert result["accepted"] is True
    assert result["data"]["preferred_language"] is None
    assert result["warnings"] == ["preferred_language"]


def test_blank_optional_fields_are_null_without_warning():
    row = valid_motor_row()
    row["premium_amount"] = ""
    row["policy_expiry"] = ""

    result = validate_row(motor_schema(), row)

    assert result["accepted"] is True
    assert result["data"]["premium_amount"] is None
    assert result["data"]["policy_expiry"] is None
    assert result["warnings"] == []


def test_missing_required_fields_follow_schema_order():
    row = valid_motor_row()
    row["customer_name"] = ""
    row["phone"] = ""
    row["policy_number"] = ""

    result = validate_row(motor_schema(), row)

    assert result["accepted"] is False
    assert result["rejection_reason"] == "missing_required:customer_name"


def test_policy_feedback_schema():
    schema = load_schema("policy_feedback")

    row = {
        "customer_name": "Rohan Sharma",
        "phone": "8880395512",
        "order_id": "ORD/2026/001",
        "product": "Phone protection",
        "order_date": "2026-10-21",
        "preferred_language": "en",
    }

    result = validate_row(schema, row)

    assert result["accepted"] is True
    assert result["data"]["phone"] == "+918880395512"
    assert result["data"]["order_date"] == "2026-10-21"