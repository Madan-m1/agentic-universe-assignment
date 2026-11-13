from solution.ingestion.lead_merger import merge_lead_records


def make_record(batch_id, name, phone, policy, language=None):
    return {
        "workflow_id": "motor_renewal",
        "batch_id": batch_id,
        "row_number": 1,
        "data": {
            "customer_name": name,
            "phone": phone,
            "policy_number": policy,
            "policy_expiry": None,
            "premium_amount": None,
            "preferred_language": language,
        },
    }


def test_duplicate_leads_merge():
    records = [
        make_record(
            "batch_001",
            "Aarav Menon",
            "+919932302346",
            "MOT/001",
        ),
        make_record(
            "batch_002",
            "Aarav Menon Updated",
            "+919932302346",
            "MOT/001",
            "hi",
        ),
    ]

    result = merge_lead_records(records)

    assert len(result["leads"]) == 1
    assert result["duplicate_count"] == 1

    lead = result["leads"][0]

    assert lead["batch_id"] == "batch_001"
    assert lead["data"]["customer_name"] == "Aarav Menon Updated"
    assert lead["data"]["preferred_language"] == "hi"


def test_null_values_do_not_overwrite_existing_values():
    records = [
        make_record(
            "batch_001",
            "Aarav Menon",
            "+919932302346",
            "MOT/001",
            "en",
        ),
        make_record(
            "batch_002",
            "Aarav Menon",
            "+919932302346",
            "MOT/001",
            None,
        ),
    ]

    result = merge_lead_records(records)

    assert result["leads"][0]["data"]["preferred_language"] == "en"


def test_first_batch_id_is_preserved():
    records = [
        make_record(
            "batch_001",
            "Aarav Menon",
            "+919932302346",
            "MOT/001",
        ),
        make_record(
            "batch_002",
            "Aarav Menon",
            "+919932302346",
            "MOT/002",
        ),
    ]

    result = merge_lead_records(records)

    assert result["leads"][0]["batch_id"] == "batch_001"
    assert result["leads"][0]["data"]["policy_number"] == "MOT/002"


def test_different_workflows_are_not_duplicates():
    first = make_record(
        "batch_001",
        "Aarav Menon",
        "+919932302346",
        "MOT/001",
    )

    second = make_record(
        "batch_001",
        "Aarav Menon",
        "+919932302346",
        "MOT/001",
    )
    second["workflow_id"] = "policy_feedback"
    second["data"]["order_id"] = "ORD/001"

    result = merge_lead_records([first, second])

    assert len(result["leads"]) == 2
    assert result["duplicate_count"] == 0