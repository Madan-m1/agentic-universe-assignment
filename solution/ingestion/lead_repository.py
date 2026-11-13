import json

from solution.security.pii import encrypt_text, hash_phone


def save_leads(connection, leads: list[dict]) -> int:
    """
    Insert or update leads using the caller's transaction.

    Returns the number of newly inserted leads.
    """

    inserted_count = 0

    for lead in leads:
        data = lead["data"]

        workflow_id = lead["workflow_id"]
        canonical_phone = data["phone"]
        phone_hash = hash_phone(canonical_phone)

        existing = connection.execute(
            """
            SELECT id, attributes_json, external_ref
            FROM leads
            WHERE workflow_id = ? AND phone_hash = ?
            """,
            (workflow_id, phone_hash),
        ).fetchone()

        external_ref = (
            data.get("policy_number")
            or data.get("order_id")
        )

        attributes = {
            key: value
            for key, value in data.items()
            if key not in {
                "phone",
                "customer_name",
                "policy_number",
                "order_id",
            }
        }

        if existing is None:
            connection.execute(
                """
                INSERT INTO leads (
                    workflow_id,
                    phone_hash,
                    encrypted_phone,
                    encrypted_customer_name,
                    external_ref,
                    attributes_json,
                    batch_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    workflow_id,
                    phone_hash,
                    encrypt_text(canonical_phone),
                    encrypt_text(data["customer_name"]),
                    external_ref,
                    json.dumps(attributes),
                    lead["batch_id"],
                ),
            )

            inserted_count += 1

        else:
            existing_attributes = json.loads(
                existing["attributes_json"]
            )

            for key, value in attributes.items():
                if value is not None:
                    existing_attributes[key] = value

            updated_external_ref = (
                external_ref
                if external_ref is not None
                else existing["external_ref"]
            )

            connection.execute(
                """
                UPDATE leads
                SET
                    encrypted_phone = ?,
                    encrypted_customer_name = ?,
                    external_ref = ?,
                    attributes_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    encrypt_text(canonical_phone),
                    encrypt_text(data["customer_name"]),
                    updated_external_ref,
                    json.dumps(existing_attributes),
                    existing["id"],
                ),
            )

    return inserted_count