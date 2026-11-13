
import csv
import json
from collections import OrderedDict
from pathlib import Path

from solution.ingestion.disposition_loader import load_dispositions
from solution.reporting.analytics import build_analytics


BATCH_COLUMNS = [
    "workflow_id",
    "batch_id",
    "total_leads",
    "yet_to_reach_out",
    "in_progress_telephony_failed",
    "in_progress_dialed",
    "completed",
]

DAILY_COLUMNS = [
    "workflow_id",
    "date",
    "total_calls",
    "connected_calls",
    "connectivity_rate",
    "success_leads",
]

LEAD_COLUMNS = [
    "workflow_id",
    "external_ref",
    "batch_id",
    "phone_masked",
    "bucket",
    "total_calls",
    "connected_calls",
    "last_call_at",
    "current_disposition",
    "ever_success",
]

REJECTION_COLUMNS = [
    "workflow_id",
    "batch_id",
    "row_number",
    "reason",
]


def write_csv(path: Path, columns: list[str], rows: list[dict]):
    """Write a CSV with a fixed header and deterministic line endings."""

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=columns,
            extrasaction="ignore",
            lineterminator="\n",
        )

        writer.writeheader()

        for row in rows:
            output_row = dict(row)

            # The contract requires lowercase true/false.
            if "ever_success" in output_row:
                output_row["ever_success"] = (
                    "true" if output_row["ever_success"] else "false"
                )

            writer.writerow(output_row)


def build_rejections(connection) -> list[dict]:
    """Return rejected rows in the exact required order."""

    rows = connection.execute("""
        SELECT
            workflow_id,
            batch_id,
            row_number,
            reason
        FROM rejections
        ORDER BY workflow_id, batch_id, row_number
    """).fetchall()

    return [dict(row) for row in rows]


def build_data_quality(connection) -> dict:
    """Calculate cumulative ingestion and final-state quality metrics."""

    lead_stats = connection.execute("""
        SELECT
            COALESCE(SUM(total_rows), 0) AS lead_rows_total,
            COALESCE(SUM(rejected_rows), 0) AS lead_rows_rejected,
            COALESCE(SUM(duplicate_count), 0)
                AS duplicate_lead_rows_merged,
            COALESCE(SUM(warning_count), 0) AS field_warnings
        FROM file_ingestion_stats
    """).fetchone()

    event_stats = connection.execute("""
        SELECT
            COALESCE(SUM(total_lines), 0) AS events_total,
            COALESCE(SUM(malformed_events), 0) AS malformed_events,
            COALESCE(SUM(duplicate_events), 0)
                AS duplicate_events_dropped,
            COALESCE(SUM(unknown_dispositions), 0)
                AS unknown_disposition_events
        FROM event_ingestion_stats
    """).fetchone()

    rejection_rows = connection.execute("""
        SELECT reason, COUNT(*) AS total
        FROM rejections
        GROUP BY reason
        ORDER BY reason
    """).fetchall()

    rejections_by_reason = OrderedDict(
        (row["reason"], row["total"])
        for row in rejection_rows
    )

    orphan_count = connection.execute("""
        SELECT COUNT(*) AS total
        FROM event_links
        WHERE link_status = 'orphan'
    """).fetchone()["total"]

    return {
        "lead_rows_total": lead_stats["lead_rows_total"],
        "lead_rows_rejected": lead_stats["lead_rows_rejected"],
        "rejections_by_reason": rejections_by_reason,
        "duplicate_lead_rows_merged":
            lead_stats["duplicate_lead_rows_merged"],
        "field_warnings": lead_stats["field_warnings"],
        "events_total": event_stats["events_total"],
        "malformed_events": event_stats["malformed_events"],
        "duplicate_events_dropped":
            event_stats["duplicate_events_dropped"],
        "orphan_events": orphan_count,
        "unknown_disposition_events":
            event_stats["unknown_disposition_events"],
    }


def generate_reports(connection, output_dir: str | Path) -> dict:
    """
    Generate all five assignment reports.

    The caller supplies an initialized database connection.
    The function reads the database and writes report files.
    """

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    dispositions = load_dispositions()
    analytics = build_analytics(connection, dispositions)

    # 1. Batch summary
    batch_path = output_path / "batch_summary.csv"

    write_csv(
        batch_path,
        BATCH_COLUMNS,
        analytics["batch_summary"],
    )

    # 2. Daily overview
    daily_path = output_path / "daily_overview.csv"

    write_csv(
        daily_path,
        DAILY_COLUMNS,
        analytics["daily_overview"],
    )

    # 3. Lead report
    lead_path = output_path / "lead_report.csv"

    write_csv(
        lead_path,
        LEAD_COLUMNS,
        analytics["lead_report"],
    )

    # 4. Rejections
    rejection_path = output_path / "rejections.csv"

    rejections = build_rejections(connection)

    write_csv(
        rejection_path,
        REJECTION_COLUMNS,
        rejections,
    )

    # 5. Data quality
    quality_path = output_path / "data_quality.json"

    quality = build_data_quality(connection)

    with quality_path.open("w", encoding="utf-8") as file:
        json.dump(
            quality,
            file,
            indent=2,
            ensure_ascii=False,
        )
        file.write("\n")

    return {
        "batch_summary": batch_path,
        "daily_overview": daily_path,
        "lead_report": lead_path,
        "rejections": rejection_path,
        "data_quality": quality_path,
    }
