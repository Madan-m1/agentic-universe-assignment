
from pathlib import Path

from solution.database.connection import get_connection
from solution.ingestion.disposition_loader import load_dispositions
from solution.ingestion.event_processor import process_event_file
from solution.ingestion.file_tracker import (
    calculate_checksum,
    get_file_status,
    record_processed_file,
)


def ingest_event_files(files: list[str | Path]) -> dict:
    """
    Ingest JSONL files in the order supplied.

    Each file is processed in its own database transaction.
    Previously processed unchanged files are skipped.
    Modified previously processed files are rejected.
    """

    ordered_files = [Path(file) for file in files]
    dispositions = load_dispositions()

    file_results = []

    totals = {
        "total_lines": 0,
        "inserted_events": 0,
        "duplicate_events": 0,
        "malformed_events": 0,
        "unknown_dispositions": 0,
        "linked_events": 0,
    }

    for file_path in ordered_files:
        status = get_file_status(file_path)

        if status == "unchanged":
            file_results.append({
                "file": str(file_path),
                "status": "skipped",
            })
            continue

        if status == "changed":
            raise ValueError(
                f"Previously processed file has changed: {file_path}"
            )

        checksum = calculate_checksum(file_path)
        connection = get_connection()

        try:
            with connection:
                stats = process_event_file(
                    connection,
                    file_path,
                    dispositions,
                )

                record_processed_file(
                    connection,
                    file_path,
                    checksum,
                )

                connection.execute(
                    """
                    INSERT INTO event_ingestion_stats (
                        file_path,
                        file_checksum,
                        total_lines,
                        inserted_events,
                        duplicate_events,
                        malformed_events,
                        unknown_dispositions
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(file_path.resolve()),
                        checksum,
                        stats["total_lines"],
                        stats["inserted_events"],
                        stats["duplicate_events"],
                        stats["malformed_events"],
                        stats["unknown_dispositions"],
                    ),
                )

            file_results.append({
                "file": str(file_path),
                "status": "processed",
                **stats,
            })

            for key in totals:
                totals[key] += stats[key]

        finally:
            connection.close()

    return {
        "status": "processed" if any(
            item["status"] == "processed" for item in file_results
        ) else "no_new_files",
        "files": file_results,
        **totals,
    }
