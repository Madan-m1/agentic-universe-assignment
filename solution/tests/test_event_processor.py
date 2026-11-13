
import json
import sqlite3

import pytest

from solution.database.connection import SCHEMA_PATH
from solution.ingestion.event_processor import process_event_file
from solution.security.pii import hash_phone


@pytest.fixture
def connection():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    yield conn
    conn.close()


@pytest.fixture
def dispositions():
    return {
        "motor_renewal": {
            "renewed": {
                "label": "Policy renewed",
                "is_terminal": True,
                "is_success": True,
            }
        }
    }


def make_event(event_id, event_type="call.initiated", **overrides):
    event = {
        "event_id": event_id,
        "event_type": event_type,
        "workflow_id": "motor_renewal",
        "call_id": "call_001",
        "occurred_at": "2026-10-01T10:56:10+05:30",
        "phone": "+919876543210",
        "payload": {},
    }
    event.update(overrides)
    return event


def write_jsonl(tmp_path, lines):
    path = tmp_path / "events.jsonl"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_counts_malformed_json(connection, dispositions, tmp_path):
    path = write_jsonl(
        tmp_path,
        [
            json.dumps(make_event("evt_001")),
            "{invalid json",
        ],
    )

    stats = process_event_file(connection, path, dispositions)

    assert stats["total_lines"] == 2
    assert stats["inserted_events"] == 1
    assert stats["malformed_events"] == 1


def test_counts_duplicate_event_ids(connection, dispositions, tmp_path):
    event = make_event("evt_001")
    path = write_jsonl(
        tmp_path,
        [json.dumps(event), json.dumps(event)],
    )

    stats = process_event_file(connection, path, dispositions)

    assert stats["inserted_events"] == 1
    assert stats["duplicate_events"] == 1



def test_ignores_unknown_disposition(connection, dispositions, tmp_path):
    # Create a matching lead so the event is linkable.
    phone_hash = hash_phone("+919876543210")

    connection.execute(
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

    event = make_event(
        "evt_001",
        event_type="disposition.set",
        payload={"disposition_code": "unknown_code"},
    )

    path = write_jsonl(tmp_path, [json.dumps(event)])
    stats = process_event_file(connection, path, dispositions)

    assert stats["unknown_dispositions"] == 1
    assert stats["inserted_events"] == 0

    event_count = connection.execute(
        "SELECT COUNT(*) FROM events"
    ).fetchone()[0]

    assert event_count == 0


def test_accepts_valid_disposition(connection, dispositions, tmp_path):
    event = make_event(
        "evt_001",
        event_type="disposition.set",
        payload={"disposition_code": "renewed"},
    )
    path = write_jsonl(tmp_path, [json.dumps(event)])

    stats = process_event_file(connection, path, dispositions)

    assert stats["inserted_events"] == 1
    assert stats["unknown_dispositions"] == 0


def test_normalizes_timestamp_and_hashes_phone(
    connection, dispositions, tmp_path
):
    event = make_event("evt_001")
    path = write_jsonl(tmp_path, [json.dumps(event)])

    process_event_file(connection, path, dispositions)

    row = connection.execute(
        "SELECT occurred_at, phone_hash, payload_json FROM events"
    ).fetchone()

    assert row["occurred_at"] == "2026-10-01T05:26:10Z"
    assert row["phone_hash"] == hash_phone("+919876543210")
    assert "+919876543210" not in row["payload_json"]


def test_counts_missing_event_id_as_malformed(
    connection, dispositions, tmp_path
):
    event = make_event("evt_001")
    del event["event_id"]

    path = write_jsonl(tmp_path, [json.dumps(event)])
    stats = process_event_file(connection, path, dispositions)

    assert stats["malformed_events"] == 1
    assert stats["inserted_events"] == 0


def test_invalid_phone_is_retained_as_orphan(
    connection, dispositions, tmp_path
):
    event = make_event("evt_invalid_phone", phone="invalid-phone")
    path = write_jsonl(tmp_path, [json.dumps(event)])

    stats = process_event_file(connection, path, dispositions)

    link = connection.execute(
        "SELECT link_status FROM event_links "
        "WHERE event_id = 'evt_invalid_phone'"
    ).fetchone()

    assert stats["inserted_events"] == 1
    assert stats["malformed_events"] == 0
    assert link["link_status"] == "orphan"


def test_non_object_json_is_malformed(
    connection, dispositions, tmp_path
):
    path = write_jsonl(tmp_path, ['"just a string"'])

    stats = process_event_file(connection, path, dispositions)

    assert stats["malformed_events"] == 1
    assert stats["inserted_events"] == 0


def test_duplicate_checked_before_timestamp_validation(
    connection, dispositions, tmp_path
):
    first = make_event("evt_duplicate")
    second = make_event(
        "evt_duplicate",
        occurred_at="not-a-valid-timestamp",
    )

    path = write_jsonl(
        tmp_path,
        [json.dumps(first), json.dumps(second)],
    )

    stats = process_event_file(connection, path, dispositions)

    assert stats["inserted_events"] == 1
    assert stats["duplicate_events"] == 1
    assert stats["malformed_events"] == 0



def test_unknown_disposition_event_id_is_deduplicated_across_files(
    connection, dispositions, tmp_path
):
    # Create a lead so the event is linkable.
    phone_hash = hash_phone("+919876543210")

    connection.execute(
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

    event = make_event(
        "evt_unknown_duplicate",
        event_type="disposition.set",
        payload={"disposition_code": "unknown_code"},
    )

    first_file = write_jsonl(
        tmp_path,
        [json.dumps(event)],
    )

    first_stats = process_event_file(
        connection,
        first_file,
        dispositions,
    )

    second_file = tmp_path / "second_events.jsonl"
    second_file.write_text(
        json.dumps(event) + "\n",
        encoding="utf-8",
    )

    second_stats = process_event_file(
        connection,
        second_file,
        dispositions,
    )

    assert first_stats["unknown_dispositions"] == 1
    assert first_stats["inserted_events"] == 0
    assert second_stats["duplicate_events"] == 1
    assert second_stats["inserted_events"] == 0

    registry_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM seen_event_ids
        WHERE event_id = 'evt_unknown_duplicate'
        """
    ).fetchone()[0]

    assert registry_count == 1

