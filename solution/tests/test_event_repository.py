
import json
import sqlite3
from pathlib import Path

import pytest

from solution.ingestion.event_repository import (
    insert_event,
    reconcile_orphan_events,
)
from solution.security.pii import hash_phone


@pytest.fixture
def connection():
    """Create an isolated temporary database for each test."""
    from solution.database.connection import SCHEMA_PATH

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    yield conn
    conn.close()


def add_lead(connection, phone="+919876543210"):
    """Insert a minimal lead for repository tests."""
    phone_hash = hash_phone(phone)

    cursor = connection.execute(
        """
        INSERT INTO leads (
            workflow_id,
            phone_hash,
            encrypted_phone,
            encrypted_customer_name,
            external_ref,
            attributes_json,
            batch_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "motor_renewal",
            phone_hash,
            b"encrypted-phone",
            b"encrypted-name",
            "POLICY-001",
            "{}",
            "batch_001",
        ),
    )
    return cursor.lastrowid


def make_event(
    event_id="evt_001",
    event_type="call.initiated",
    phone="+919876543210",
    call_id="call_001",
    occurred_at="2026-10-01T05:00:00Z",
    payload=None,
):
    return {
        "event_id": event_id,
        "event_type": event_type,
        "workflow_id": "motor_renewal",
        "call_id": call_id,
        "occurred_at": occurred_at,
        "phone": phone,
        "payload": payload or {},
    }


def test_insert_event_links_existing_lead(connection):
    add_lead(connection)

    result = insert_event(
        connection,
        make_event(),
        "events.jsonl",
        1,
    )

    link = connection.execute(
        "SELECT * FROM event_links WHERE event_id = 'evt_001'"
    ).fetchone()

    assert result == "inserted"
    assert link["link_status"] == "linked"
    assert link["lead_id"] is not None


def test_duplicate_event_id_is_ignored(connection):
    add_lead(connection)
    event = make_event()

    assert insert_event(connection, event, "a.jsonl", 1) == "inserted"
    assert insert_event(connection, event, "b.jsonl", 1) == "duplicate"

    count = connection.execute(
        "SELECT COUNT(*) FROM events"
    ).fetchone()[0]

    assert count == 1


def test_phone_is_not_stored_in_event_payload(connection):
    add_lead(connection)

    insert_event(
        connection,
        make_event(),
        "events.jsonl",
        1,
    )

    row = connection.execute(
        "SELECT phone_hash, payload_json FROM events"
    ).fetchone()

    assert row["phone_hash"] == hash_phone("+919876543210")
    assert "+919876543210" not in row["payload_json"]


def test_orphan_links_when_lead_arrives_later(connection):
    result = insert_event(
        connection,
        make_event(),
        "events.jsonl",
        1,
    )

    assert result == "inserted"

    add_lead(connection)
    linked = reconcile_orphan_events(connection)

    link = connection.execute(
        "SELECT * FROM event_links WHERE event_id = 'evt_001'"
    ).fetchone()

    assert linked == 1
    assert link["link_status"] == "linked"


def test_override_links_through_call_id(connection):
    add_lead(connection)

    call_event = make_event(
        event_id="evt_call",
        event_type="call.initiated",
    )
    insert_event(connection, call_event, "events.jsonl", 1)

    override = make_event(
        event_id="evt_override",
        event_type="disposition.override",
        phone=None,
        payload={"disposition_code": "renewed"},
    )
    insert_event(connection, override, "events.jsonl", 2)

    link = connection.execute(
        """
        SELECT link_status
        FROM event_links
        WHERE event_id = 'evt_override'
        """
    ).fetchone()

    assert link["link_status"] == "linked"


def test_override_before_call_event_reconciles_after_lead_arrives(connection):
    override = make_event(
        event_id="evt_override",
        event_type="disposition.override",
        phone=None,
        occurred_at="2026-10-01T04:00:00Z",
        payload={"disposition_code": "renewed"},
    )

    call_event = make_event(
        event_id="evt_call",
        event_type="call.initiated",
        occurred_at="2026-10-01T05:00:00Z",
    )

    insert_event(connection, override, "events.jsonl", 1)
    insert_event(connection, call_event, "events.jsonl", 2)

    add_lead(connection)
    reconcile_orphan_events(connection)

    statuses = {
        row["event_id"]: row["link_status"]
        for row in connection.execute(
            "SELECT event_id, link_status FROM event_links"
        )
    }

    assert statuses["evt_override"] == "linked"
    assert statuses["evt_call"] == "linked"

def test_invalid_phone_is_retained_as_orphan(connection):
    event = make_event(
        event_id="evt_invalid_phone",
        phone="not-a-valid-phone",
    )

    result = insert_event(
        connection,
        event,
        "events.jsonl",
        1,
    )

    row = connection.execute(
        """
        SELECT phone_hash
        FROM events
        WHERE event_id = 'evt_invalid_phone'
        """
    ).fetchone()

    link = connection.execute(
        """
        SELECT link_status, lead_id
        FROM event_links
        WHERE event_id = 'evt_invalid_phone'
        """
    ).fetchone()

    assert result == "inserted"
    assert row["phone_hash"] is None
    assert link["link_status"] == "orphan"
    assert link["lead_id"] is None

