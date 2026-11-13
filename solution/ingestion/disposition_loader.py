
import csv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DISPOSITION_FILE = (
    PROJECT_ROOT
    / "assignment-a-data"
    / "schemas"
    / "dispositions.csv"
)


def load_dispositions():
    """Load valid disposition codes grouped by workflow."""
    if not DISPOSITION_FILE.exists():
        raise FileNotFoundError(
            f"Disposition catalog not found: {DISPOSITION_FILE}"
        )

    dispositions = {}

    with DISPOSITION_FILE.open(
        encoding="utf-8-sig",
        newline="",
    ) as file:
        for row in csv.DictReader(file):
            workflow_id = row["workflow_id"].strip()
            code = row["code"].strip().lower()

            dispositions.setdefault(workflow_id, {})[code] = {
                "label": row["label"].strip(),
                "is_terminal": row["is_terminal"].strip().lower() == "true",
                "is_success": row["is_success"].strip().lower() == "true",
            }

    return dispositions
