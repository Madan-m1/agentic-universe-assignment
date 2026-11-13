
import json
import sqlite3

import pytest

from solution.database import connection as db_connection
from solution.ingestion.event_pipeline import ingest_event_files


@pytest.fixture
def isolated_database(tmp_path, monkeypatch):
    db_path = tmp_path / "event_pipeline_test.db"

    monkeypatch.setattr(db_connection, "DB_PATH", db_path)
    db_connection.initialize_database()

    return db_path


def create_event_file(tmp_path, event_id="evt_pipeline_001"):
    event = {
        "event_id": event_id,
        "event_type": "call.initiated",
        "workflow_id": "motor_renewal",
        "call_id": "call_pipeline_001",
        "occurred_at": "2026-10-01T10:56:10+05:30",
        "phone": "+919876543210",
        "payload": {},
    }

    path = tmp_path / "events.jsonl"
    path.write_text(json.dumps(event) + "\n", encoding="utf-8")
    return path


def test_ingests_new_event_file(isolated_database, tmp_path):
    path = create_event_file(tmp_path)

    result = ingest_event_files([path])

    assert result["status"] == "processed"
    assert result["inserted_events"] == 1
    assert result["total_lines"] == 1

    connection = sqlite3.connect(isolated_database)
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM events"
        ).fetchone()[0] == 1

        assert connection.execute(
            "SELECT COUNT(*) FROM event_ingestion_stats"
        ).fetchone()[0] == 1
    finally:
        connection.close()


def test_rerun_skips_unchanged_file(isolated_database, tmp_path):
    path = create_event_file(tmp_path)

    first = ingest_event_files([path])
    second = ingest_event_files([path])

    assert first["inserted_events"] == 1
    assert second["status"] == "no_new_files"
    assert second["files"][0]["status"] == "skipped"

    connection = sqlite3.connect(isolated_database)
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM events"
        ).fetchone()[0] == 1

        assert connection.execute(
            "SELECT COUNT(*) FROM event_ingestion_stats"
        ).fetchone()[0] == 1
    finally:
        connection.close()


def test_changed_processed_file_is_rejected(
    isolated_database, tmp_path
):
    path = create_event_file(tmp_path)
    ingest_event_files([path])

    path.write_text(
        json.dumps({
            "event_id": "evt_changed",
            "event_type": "call.initiated",
            "workflow_id": "motor_renewal",
            "call_id": "call_changed",
            "occurred_at": "2026-10-02T10:00:00Z",
            "phone": "+919876543210",
            "payload": {},
        }) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Previously processed file has changed"):
        ingest_event_files([path])
