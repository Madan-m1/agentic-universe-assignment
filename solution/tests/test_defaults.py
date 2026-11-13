from solution.ingestion.defaults import apply_schema_defaults
from solution.ingestion.schema_loader import load_schema


def test_default_language_is_applied():
    schema = load_schema("motor_renewal")

    leads = [{
        "workflow_id": "motor_renewal",
        "batch_id": "batch_001",
        "data": {
            "customer_name": "Aarav Menon",
            "phone": "+919932302346",
            "policy_number": "MOT/001",
            "policy_expiry": None,
            "premium_amount": None,
            "preferred_language": None,
        },
    }]

    result = apply_schema_defaults(leads, schema)

    assert result[0]["data"]["preferred_language"] == "en"


def test_existing_value_is_not_overwritten():
    schema = load_schema("motor_renewal")

    leads = [{
        "workflow_id": "motor_renewal",
        "batch_id": "batch_001",
        "data": {
            "preferred_language": "hi",
        },
    }]

    result = apply_schema_defaults(leads, schema)

    assert result[0]["data"]["preferred_language"] == "hi"


def test_defaults_are_applied_after_duplicate_merge():
    schema = load_schema("motor_renewal")

    leads = [{
        "workflow_id": "motor_renewal",
        "batch_id": "batch_001",
        "data": {
            "preferred_language": "ta",
        },
    }]

    result = apply_schema_defaults(leads, schema)

    assert result[0]["data"]["preferred_language"] == "ta"


def test_policy_feedback_default():
    schema = load_schema("policy_feedback")

    leads = [{
        "workflow_id": "policy_feedback",
        "batch_id": "batch_001",
        "data": {
            "preferred_language": None,
        },
    }]

    result = apply_schema_defaults(leads, schema)

    assert result[0]["data"]["preferred_language"] == "en"