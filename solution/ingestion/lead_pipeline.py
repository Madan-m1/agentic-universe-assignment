
from pathlib import Path

from solution.database.connection import get_connection
from solution.ingestion.csv_processor import process_csv_file
from solution.ingestion.defaults import apply_schema_defaults
from solution.ingestion.file_tracker import (
    calculate_checksum,
    get_file_status,
    record_processed_file,
)
from solution.ingestion.lead_merger import merge_lead_records
from solution.ingestion.lead_repository import save_leads
from solution.ingestion.schema_loader import load_schema


def ingest_lead_files(
    files: list[str | Path],
    workflow_id: str,
) -> dict:
    """
    Ingest CSV files in filename order.

    All database changes are committed in one transaction.
    Each file receives its own accurate statistics.
    """

    ordered_files = sorted(
        [Path(file) for file in files],
        key=lambda path: path.name.lower(),
    )

    schema = load_schema(workflow_id)

    pending_files = []
    file_results = []

    # Read and validate files before opening the write transaction.
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

        result = process_csv_file(
            file_path,
            workflow_id,
            file_path.stem,
        )

        pending_files.append({
            "path": file_path,
            "checksum": calculate_checksum(file_path),
            "batch_id": file_path.stem,
            "result": result,
        })

    if not pending_files:
        return {
            "status": "no_new_files",
            "files": file_results,
            "inserted_leads": 0,
            "duplicate_count": 0,
            "accepted_rows": 0,
            "rejected_rows": 0,
            "warning_count": 0,
        }

    totals = {
        "inserted_leads": 0,
        "duplicate_count": 0,
        "accepted_rows": 0,
        "rejected_rows": 0,
        "warning_count": 0,
    }

    connection = get_connection()

    try:
        with connection:
            for item in pending_files:
                result = item["result"]

                # Merge duplicates within this file.
                merge_result = merge_lead_records(
                    result["accepted"]
                )

                merged_leads = apply_schema_defaults(
                    merge_result["leads"],
                    schema,
                )

                inserted_count = save_leads(
                    connection,
                    merged_leads,
                )

                accepted_count = len(result["accepted"])

                # Includes duplicates within this file and
                # records matching leads from earlier files.
                duplicate_count = accepted_count - inserted_count

                # Persist rejected rows.
                for rejected in result["rejected"]:
                    connection.execute(
                        """
                        INSERT INTO rejections (
                            workflow_id,
                            batch_id,
                            row_number,
                            reason
                        )
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            rejected["workflow_id"],
                            rejected["batch_id"],
                            rejected["row_number"],
                            rejected["reason"],
                        ),
                    )

                # Record file processing in the same transaction.
                record_processed_file(
                    connection,
                    item["path"],
                    item["checksum"],
                )

                connection.execute(
                    """
                    INSERT INTO file_ingestion_stats (
                        file_path,
                        file_checksum,
                        workflow_id,
                        batch_id,
                        total_rows,
                        accepted_rows,
                        rejected_rows,
                        warning_count,
                        duplicate_count,
                        inserted_leads
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(item["path"].resolve()),
                        item["checksum"],
                        workflow_id,
                        item["batch_id"],
                        result["nonblank_rows"],
                        accepted_count,
                        len(result["rejected"]),
                        len(result["warnings"]),
                        duplicate_count,
                        inserted_count,
                    ),
                )

                totals["inserted_leads"] += inserted_count
                totals["duplicate_count"] += duplicate_count
                totals["accepted_rows"] += accepted_count
                totals["rejected_rows"] += len(result["rejected"])
                totals["warning_count"] += len(result["warnings"])

                file_results.append({
                    "file": str(item["path"]),
                    "status": "processed",
                    "inserted_leads": inserted_count,
                    "duplicate_count": duplicate_count,
                    "accepted_rows": accepted_count,
                    "rejected_rows": len(result["rejected"]),
                    "warning_count": len(result["warnings"]),
                })

        return {
            "status": "processed",
            "files": file_results,
            **totals,
        }

    finally:
        connection.close()
