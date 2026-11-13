import json
import pytest
from solution.database.connection import get_connection
from solution.ingestion.lead_repository import save_leads
from solution.security.pii import decrypt_text
from solution.database import connection as connection_module

@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    test_db = tmp_path / "test_leads.sqlite"

    monkeypatch.setattr(
        connection_module,
        "DB_PATH",
        test_db,
    )

    connection_module.initialize_database()


def make_lead(
    batch_id="batch_001",
    name="Aarav Menon",
    phone="+919932302346",
    policy="MOT/001",
    language="en",
):
    return {
        "workflow_id": "motor_renewal",
        "batch_id": batch_id,
        "data": {
            "customer_name": name,
            "phone": phone,
            "policy_number": policy,
            "policy_expiry": None,
            "premium_amount": None,
            "preferred_language": language,
        },
    }


def clear_leads():
    connection = get_connection()
    try:
        with connection:
            connection.execute("DELETE FROM leads")
    finally:
        connection.close()


def test_insert_lead_and_encrypt_pii():
    clear_leads()

    connection = get_connection()
    try:
        with connection:
            inserted = save_leads(connection, [make_lead()])
        assert inserted == 1

        row = connection.execute("SELECT * FROM leads").fetchone()
        assert row is not None
        assert row["encrypted_phone"] != b"+919932302346"
        assert row["encrypted_customer_name"] != b"Aarav Menon"
        assert decrypt_text(row["encrypted_phone"]) == "+919932302346"
        assert decrypt_text(row["encrypted_customer_name"]) == "Aarav Menon"

        attributes = json.loads(row["attributes_json"])
        assert attributes["preferred_language"] == "en"
    finally:
        connection.close()


def test_duplicate_lead_updates_existing_record():
    clear_leads()

    connection = get_connection()
    try:
        with connection:
            save_leads(connection, [make_lead()])

        updated = make_lead(
            batch_id="batch_002",
            name="Aarav Updated",
            language="hi",
        )

        with connection:
            inserted = save_leads(connection, [updated])
        assert inserted == 0

        rows = connection.execute("SELECT * FROM leads").fetchall()
        assert len(rows) == 1
        assert rows[0]["batch_id"] == "batch_001"
        assert decrypt_text(rows[0]["encrypted_customer_name"]) == "Aarav Updated"

        attributes = json.loads(rows[0]["attributes_json"])
        assert attributes["preferred_language"] == "hi"
    finally:
        connection.close()


def test_different_workflows_create_separate_leads():
    clear_leads()

    first = make_lead()
    second = {
        "workflow_id": "policy_feedback",
        "batch_id": "batch_001",
        "data": {
            "customer_name": "Aarav Menon",
            "phone": "+919932302346",
            "order_id": "ORD/001",
            "product": "Phone protection",
            "order_date": None,
            "preferred_language": "en",
        },
    }

    connection = get_connection()
    try:
        with connection:
            inserted = save_leads(connection, [first, second])
        assert inserted == 2

        count = connection.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        assert count == 2
    finally:
        connection.close()


def test_lead_insert_rolls_back_on_failure():
    clear_leads()

    connection = get_connection()
    try:
        try:
            with connection:
                save_leads(connection, [make_lead()])
                raise RuntimeError("Simulated ingestion failure")
        except RuntimeError:
            pass

        count = connection.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        assert count == 0
    finally:
        connection.close()
