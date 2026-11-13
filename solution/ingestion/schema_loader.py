import json
from pathlib import Path

from solution.ingestion.normalizers import normalize_header


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = PROJECT_ROOT / "assignment-a-data" / "schemas"


def load_schema(workflow_id: str) -> dict:
    schema_path = SCHEMA_DIR / f"{workflow_id}.json"

    if not schema_path.exists():
        raise FileNotFoundError(
            f"Schema not found for workflow: {workflow_id}"
        )

    with schema_path.open("r", encoding="utf-8") as file:
        schema = json.load(file)

    if schema.get("workflow_id") != workflow_id:
        raise ValueError("Workflow ID does not match schema filename")

    return schema


def build_header_mapping(schema: dict, csv_headers: list[str]) -> dict:
    """
    Map each CSV column index to its schema field name.
    Unknown columns are ignored.
    """
    aliases = {}

    for field in schema["fields"]:
        field_name = field["name"]
        names = [field_name] + field.get("aliases", [])

        for name in names:
            normalized = normalize_header(name)

            existing_field = aliases.get(normalized)

            if existing_field is not None and existing_field != field_name:
                raise ValueError(
                    f"Header alias conflict: '{name}' maps to "
                    f"both '{existing_field}' and '{field_name}'"
                )

            aliases[normalized] = field_name

    mapping = {}

    for index, header in enumerate(csv_headers):
        normalized = normalize_header(header)

        if normalized in aliases:
            if aliases[normalized] in mapping.values():
                raise ValueError(
                    f"Multiple CSV columns map to the same field: "
                    f"{aliases[normalized]}"
                )

            mapping[index] = aliases[normalized]

    return mapping