
import json
import sqlite3
from pathlib import Path

import pytest

from solution.reporting.analytics import build_analytics
from solution.security.pii import encrypt_text, hash_phone


@pytest.fixture
def connection():
    schema_path = (
        Path(__file__).parents[1] / "database" / "schema.sql"
    )

    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(schema_path.read_text(encoding="utf-8"))

    phone = "+919876543210"

    db.execute(
        """
        INSERT INTO leads (
            workflow_id, phone_hash, encrypted_phone,
            encrypted_customer_name, external_ref,
            attributes_json, batch_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "motor_renewal",
            hash_phone(phone),
            encrypt_text(phone),
            encrypt_text("Test Customer"),
            "MOT/TEST/001",
            json.dumps({}),
            "batch_001",
        ),
    )

    db.commit()
    yield db
    db.close()


@pytest.fixture
def dispositions():
    return {
        "motor_renewal": {
            "renewed": {
                "is_terminal": True,
                "is_success": True,
            },
            "callback_requested": {
                "is_terminal": False,
                "is_success": False,
            },
            "not_interested": {
                "is_terminal": True,
                "is_success": False,
            },
        }
    }


def add_event(
    connection,
    event_id,
    event_type,
    call_id,
    occurred_at,
    payload=None,
    lead_id=1,
):
    connection.execute(
        """
        INSERT INTO events (
            event_id, event_type, workflow_id, call_id,
            occurred_at, phone_hash, payload_json,
            source_file, source_line
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            event_type,
            "motor_renewal",
            call_id,
            occurred_at,
            None,
            json.dumps(payload or {}),
            "test.jsonl",
            1,
        ),
    )

    connection.execute(
        """
        INSERT INTO event_links (event_id, lead_id, link_status)
        VALUES (?, ?, 'linked')
        """,
        (event_id, lead_id),
    )

    connection.commit()


def test_lead_without_calls_is_yet_to_reach_out(
    connection, dispositions
):
    result = build_analytics(connection, dispositions)

    lead = result["lead_report"][0]

    assert lead["bucket"] == "yet_to_reach_out"
    assert lead["total_calls"] == 0
    assert lead["last_call_at"] == ""
    assert lead["current_disposition"] == ""
    assert lead["ever_success"] is False


def test_telephony_failure_bucket(
    connection, dispositions
):
    add_event(
        connection, "evt1", "call.initiated",
        "call1", "2026-10-01T10:00:00Z",
    )
    add_event(
        connection, "evt2", "call.telephony_failed",
        "call1", "2026-10-01T10:00:10Z",
    )

    result = build_analytics(connection, dispositions)

    assert result["lead_report"][0]["bucket"] == (
        "in_progress_telephony_failed"
    )


def test_override_takes_precedence_over_disposition_set(
    connection, dispositions
):
    add_event(
        connection, "evt1", "call.initiated",
        "call1", "2026-10-01T10:00:00Z",
    )
    add_event(
        connection, "evt2", "disposition.override",
        "call1", "2026-10-01T10:05:00Z",
        {"disposition_code": "renewed"},
    )
    # Even a later disposition.set must not replace an override.
    add_event(
        connection, "evt3", "disposition.set",
        "call1", "2026-10-01T10:06:00Z",
        {"disposition_code": "callback_requested"},
    )

    result = build_analytics(connection, dispositions)

    lead = result["lead_report"][0]

    assert lead["current_disposition"] == "renewed"
    assert lead["bucket"] == "completed"
    assert lead["ever_success"] is True


def test_calls_without_initiated_are_not_counted(
    connection, dispositions
):
    add_event(
        connection, "evt1", "call.connected",
        "call1", "2026-10-01T10:00:00Z",
    )

    result = build_analytics(connection, dispositions)

    lead = result["lead_report"][0]

    assert lead["total_calls"] == 0
    assert result["daily_overview"] == []


def test_daily_date_and_last_call_time_use_ist(
    connection, dispositions
):
    add_event(
        connection, "evt1", "call.initiated",
        "call1", "2026-10-01T20:00:00Z",
    )
    add_event(
        connection, "evt2", "call.connected",
        "call1", "2026-10-01T20:00:10Z",
    )
    add_event(
        connection, "evt3", "disposition.set",
        "call1", "2026-10-01T20:01:00Z",
        {"disposition_code": "renewed"},
    )

    result = build_analytics(connection, dispositions)

    daily = result["daily_overview"][0]
    lead = result["lead_report"][0]

    assert daily["date"] == "2026-10-02"
    assert daily["total_calls"] == 1
    assert daily["connected_calls"] == 1
    assert daily["connectivity_rate"] == "1.0000"
    assert daily["success_leads"] == 1

    assert lead["last_call_at"] == (
        "2026-10-02T01:30:00+05:30"
    )
    assert lead["phone_masked"] == "+91******3210"
