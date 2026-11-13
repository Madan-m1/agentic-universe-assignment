from solution.ingestion.schema_loader import (
    load_schema,
    build_header_mapping,
)


def test_load_motor_renewal_schema():
    schema = load_schema("motor_renewal")

    assert schema["workflow_id"] == "motor_renewal"
    assert len(schema["fields"]) == 6


def test_load_policy_feedback_schema():
    schema = load_schema("policy_feedback")

    assert schema["workflow_id"] == "policy_feedback"
    assert len(schema["fields"]) == 6


def test_motor_header_alias_mapping():
    schema = load_schema("motor_renewal")

    headers = [
        "Customer_Name",
        "Mobile No",
        "Policy No",
        "Expiry Date",
        "Premium",
        "Language",
        "Unknown Column",
    ]

    mapping = build_header_mapping(schema, headers)

    assert mapping == {
        0: "customer_name",
        1: "phone",
        2: "policy_number",
        3: "policy_expiry",
        4: "premium_amount",
        5: "preferred_language",
    }


def test_policy_feedback_header_alias_mapping():
    schema = load_schema("policy_feedback")

    headers = [
        "Name",
        "Phone Number",
        "Order ID",
        "Item",
        "Purchase Date",
    ]

    mapping = build_header_mapping(schema, headers)

    assert mapping == {
        0: "customer_name",
        1: "phone",
        2: "order_id",
        3: "product",
        4: "order_date",
    }


def test_unknown_headers_are_ignored():
    schema = load_schema("motor_renewal")

    mapping = build_header_mapping(
        schema,
        ["Random Column", "Customer Name"],
    )

    assert mapping == {1: "customer_name"}