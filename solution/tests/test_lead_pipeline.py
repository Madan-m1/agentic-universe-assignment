import csv

import pytest

from solution.database.connection import get_connection
from solution.ingestion.lead_pipeline import ingest_lead_files
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

def clear_pipeline_tables():
    connection = get_connection()

    try:
        with connection:
            connection.execute("DELETE FROM file_ingestion_stats")
            connection.execute("DELETE FROM ingested_files")
            connection.execute("DELETE FROM rejections")
            connection.execute("DELETE FROM leads")
    finally:
        connection.close()


def create_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow([
            "Customer Name",
            "Phone",
            "Policy",
            "Language",
        ])
        writer.writerows(rows)


def get_counts():
    connection = get_connection()

    try:
        return {
            "leads": connection.execute(
                "SELECT COUNT(*) FROM leads"
            ).fetchone()[0],
            "files": connection.execute(
                "SELECT COUNT(*) FROM ingested_files"
            ).fetchone()[0],
            "stats": connection.execute(
                "SELECT COUNT(*) FROM file_ingestion_stats"
            ).fetchone()[0],
        }
    finally:
        connection.close()


def test_pipeline_processes_csv_files(tmp_path):
    clear_pipeline_tables()

    path = tmp_path / "batch_001.csv"

    create_csv(path, [
        ["Aarav Menon", "9932302346", "MOT/001", "en"],
        ["Nikhil Nair", "8880395512", "MOT/002", "hi"],
    ])

    result = ingest_lead_files([path], "motor_renewal")

    assert result["status"] == "processed"
    assert result["inserted_leads"] == 2
    assert result["accepted_rows"] == 2

    assert get_counts() == {
        "leads": 2,
        "files": 1,
        "stats": 1,
    }


def test_rerunning_same_file_does_not_change_data(tmp_path):
    clear_pipeline_tables()

    path = tmp_path / "batch_001.csv"

    create_csv(path, [
        ["Aarav Menon", "9932302346", "MOT/001", "en"],
    ])

    first = ingest_lead_files([path], "motor_renewal")
    before = get_counts()

    second = ingest_lead_files([path], "motor_renewal")
    after = get_counts()

    assert first["inserted_leads"] == 1
    assert second["status"] == "no_new_files"
    assert before == after


def test_duplicate_leads_across_files(tmp_path):
    clear_pipeline_tables()

    first = tmp_path / "batch_001.csv"
    second = tmp_path / "batch_002.csv"

    create_csv(first, [
        ["Aarav Menon", "9932302346", "MOT/001", "en"],
    ])

    create_csv(second, [
        ["Aarav Updated", "9932302346", "MOT/001", "hi"],
    ])

    result = ingest_lead_files(
        [second, first],
        "motor_renewal",
    )

    assert result["accepted_rows"] == 2
    assert result["duplicate_count"] == 1
    assert result["inserted_leads"] == 1
    assert get_counts()["leads"] == 1

    connection = get_connection()

    try:
        stats = connection.execute(
            """
            SELECT batch_id, duplicate_count, inserted_leads
            FROM file_ingestion_stats
            ORDER BY batch_id
            """
        ).fetchall()

        assert stats[0]["batch_id"] == "batch_001"
        assert stats[0]["inserted_leads"] == 1
        assert stats[0]["duplicate_count"] == 0

        assert stats[1]["batch_id"] == "batch_002"
        assert stats[1]["inserted_leads"] == 0
        assert stats[1]["duplicate_count"] == 1

    finally:
        connection.close()


def test_changed_file_is_not_silently_reprocessed(tmp_path):
    clear_pipeline_tables()

    path = tmp_path / "batch_001.csv"

    create_csv(path, [
        ["Aarav Menon", "9932302346", "MOT/001", "en"],
    ])

    ingest_lead_files([path], "motor_renewal")

    create_csv(path, [
        ["Nikhil Nair", "8880395512", "MOT/002", "hi"],
    ])

    with pytest.raises(Exception):
        ingest_lead_files([path], "motor_renewal")

    assert get_counts() == {
        "leads": 1,
        "files": 1,
        "stats": 1,
    }

def test_changed_file_raises_clear_error(tmp_path):
    clear_pipeline_tables()

    path = tmp_path / "batch_001.csv"

    create_csv(path, [
        ["Aarav Menon", "9932302346", "MOT/001", "en"],
    ])

    ingest_lead_files([path], "motor_renewal")

    create_csv(path, [
        ["Nikhil Nair", "8880395512", "MOT/002", "hi"],
    ])

    with pytest.raises(ValueError, match="Previously processed file has changed"):
        ingest_lead_files([path], "motor_renewal")

