def apply_schema_defaults(leads: list[dict], schema: dict) -> list[dict]:
    """
    Apply schema defaults to fields that remain None
    after all duplicate records have been merged.
    """

    defaults = {
        field["name"]: field["default"]
        for field in schema["fields"]
        if "default" in field
    }

    for lead in leads:
        for field_name, default_value in defaults.items():
            if lead["data"].get(field_name) is None:
                lead["data"][field_name] = default_value

    return leads