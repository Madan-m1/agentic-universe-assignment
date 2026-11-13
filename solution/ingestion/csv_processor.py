import csv
from pathlib import Path

from solution.ingestion.schema_loader import (
    load_schema,
    build_header_mapping,
)
from solution.ingestion.validator import validate_row


def process_csv_file(
    file_path: str | Path,
    workflow_id: str,
    batch_id: str,
) -> dict:
    """
    Read, map, and validate a single lead CSV file.

    Row numbers count nonblank data rows, excluding the header.
    """

    file_path = Path(file_path)
    schema = load_schema(workflow_id)

    accepted = []
    rejected = []
    row_warnings = []

    with file_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file)

        try:
            headers = next(reader)
        except StopIteration:
            raise ValueError(f"CSV file is empty: {file_path}")

        mapping = build_header_mapping(schema, headers)

        if not mapping:
            raise ValueError("CSV contains no recognized headers")

        row_number = 0

        for values in reader:
            # Ignore completely blank rows.
            if not any(str(value).strip() for value in values):
                continue

            row_number += 1

            raw_row = {}

            for index, field_name in mapping.items():
                raw_row[field_name] = (
                    values[index] if index < len(values) else ""
                )

            result = validate_row(schema, raw_row)

            if result["accepted"]:
                accepted.append({
                    "workflow_id": workflow_id,
                    "batch_id": batch_id,
                    "row_number": row_number,
                    "data": result["data"],
                })

                for field_name in result["warnings"]:
                    row_warnings.append({
                        "batch_id": batch_id,
                        "row_number": row_number,
                        "field": field_name,
                    })

            else:
                rejected.append({
                    "workflow_id": workflow_id,
                    "batch_id": batch_id,
                    "row_number": row_number,
                    "reason": result["rejection_reason"],
                })

    return {
        "accepted": accepted,
        "rejected": rejected,
        "warnings": row_warnings,
        "nonblank_rows": row_number,
    }