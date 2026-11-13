def merge_lead_records(records: list[dict]) -> dict:
    """
    Merge accepted lead records in their ingestion order.

    Identity: (workflow_id, canonical phone)

    First valid record:
        Creates the lead and preserves its batch_id.

    Subsequent records:
        Count as duplicates.
        Update only non-null fields.
    """

    merged = {}
    duplicate_count = 0

    for record in records:
        data = record["data"]

        identity = (
            record["workflow_id"],
            data["phone"],
        )

        if identity not in merged:
            merged[identity] = {
                "workflow_id": record["workflow_id"],
                "batch_id": record["batch_id"],
                "data": data.copy(),
            }
            continue

        duplicate_count += 1

        existing = merged[identity]

        for field_name, value in data.items():
            if value is not None:
                existing["data"][field_name] = value

    # Apply schema defaults only after all records are merged.
    return {
        "leads": list(merged.values()),
        "duplicate_count": duplicate_count,
    }