from solution.database.connection import get_connection
from solution.ingestion.file_tracker import (
    calculate_checksum,
    is_file_processed,
    record_processed_file,
)


def clear_file_tracking():
    connection = get_connection()
    try:
        with connection:
            connection.execute("DELETE FROM ingested_files")
    finally:
        connection.close()


def test_checksum_is_deterministic(tmp_path):
    path = tmp_path / "sample.csv"
    path.write_text("name,phone\nAarav,9999999999\n", encoding="utf-8")

    assert calculate_checksum(path) == calculate_checksum(path)


def test_checksum_changes_when_content_changes(tmp_path):
    path = tmp_path / "sample.csv"
    path.write_text("first version", encoding="utf-8")
    first_checksum = calculate_checksum(path)

    path.write_text("second version", encoding="utf-8")
    second_checksum = calculate_checksum(path)

    assert first_checksum != second_checksum


def test_unprocessed_file_returns_false(tmp_path):
    clear_file_tracking()

    path = tmp_path / "sample.csv"
    path.write_text("name,phone\n", encoding="utf-8")

    assert is_file_processed(path) is False


def test_processed_file_returns_true(tmp_path):
    clear_file_tracking()

    path = tmp_path / "sample.csv"
    path.write_text("name,phone\n", encoding="utf-8")

    connection = get_connection()

    try:
        with connection:
            record_processed_file(
                connection,
                path,
                calculate_checksum(path),
            )
    finally:
        connection.close()

    assert is_file_processed(path) is True


def test_modified_file_is_not_treated_as_processed(tmp_path):
    clear_file_tracking()

    path = tmp_path / "sample.csv"
    path.write_text("version one", encoding="utf-8")

    connection = get_connection()

    try:
        with connection:
            record_processed_file(
                connection,
                path,
                calculate_checksum(path),
            )
    finally:
        connection.close()

    path.write_text("version two", encoding="utf-8")

    assert is_file_processed(path) is False