from solution.ingestion.normalizers import (
    normalize_phone,
    normalize_date,
    normalize_decimal,
    normalize_enum,
)


def validate_row(
    schema: dict,
    raw_row: dict,
) -> dict:
    """
    Validate and normalize one CSV row.

    Returns:
        {
            "accepted": bool,
            "data": normalized fields,
            "rejection_reason": str | None,
            "warnings": list[str]
        }
    """

    normalized_data = {}
    warnings = []

    for field in schema["fields"]:
        name = field["name"]
        field_type = field["type"]
        required = field.get("required", False)

        raw_value = raw_row.get(name)

        if raw_value is None or not str(raw_value).strip():
            if required:
                return {
                    "accepted": False,
                    "data": normalized_data,
                    "rejection_reason": f"missing_required:{name}",
                    "warnings": [],
                }

            normalized_data[name] = None
            continue

        value = str(raw_value).strip()

        try:
            if field_type == "string":
                normalized_value = value

            elif field_type == "phone":
                normalized_value = normalize_phone(value)

            elif field_type == "date":
                normalized_value = normalize_date(value)

            elif field_type == "decimal":
                normalized_value = normalize_decimal(value)

            elif field_type == "enum":
                normalized_value = normalize_enum(
                    value,
                    field["values"],
                )

            else:
                raise ValueError(f"Unsupported field type: {field_type}")

            normalized_data[name] = normalized_value

        except ValueError:
            if required:
                reason = (
                    "invalid_phone"
                    if field_type == "phone"
                    else f"invalid_{field_type}:{name}"
                )

                return {
                    "accepted": False,
                    "data": normalized_data,
                    "rejection_reason": reason,
                    "warnings": [],
                }

            normalized_data[name] = None
            warnings.append(name)

    return {
        "accepted": True,
        "data": normalized_data,
        "rejection_reason": None,
        "warnings": warnings,
    }