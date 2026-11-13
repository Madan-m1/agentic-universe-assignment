
import json
from pathlib import Path

from solution.ingestion.event_normalizers import normalize_event_timestamp
from solution.ingestion.event_repository import (
    insert_event,
    reconcile_orphan_events,
    find_lead_by_phone,
    find_lead_by_call_id,
    register_event_id,
)
from solution.ingestion.normalizers import normalize_phone
from solution.security.pii import hash_phone


DISPOSITION_EVENT_TYPES = {
    "disposition.set",
    "disposition.override",
}


def _is_linkable(connection, event):
    """
    Check whether an event can currently be linked to a lead.

    Invalid or missing phones do not make an otherwise valid
    event malformed. The event may still link through call_id.
    """
    workflow_id = event["workflow_id"]
    phone = event.get("phone")
    call_id = event.get("call_id")

    if phone:
        try:
            normalized_phone = normalize_phone(phone)
            phone_hash = hash_phone(normalized_phone)

            lead = find_lead_by_phone(
                connection,
                workflow_id,
                phone_hash,
            )

            if lead:
                return True

        except (ValueError, TypeError, AttributeError):
            pass

    if call_id:
        lead = find_lead_by_call_id(
            connection,
            workflow_id,
            call_id,
        )

        if lead:
            return True

    return False


def process_event_file(connection, file_path, dispositions):
    """
    Process one JSONL event file.

    Processing order:
    1. Malformed JSON or missing event ID.
    2. Duplicate event ID.
    3. Orphan detection and retention.
    4. Unknown disposition detection for linkable events.

    The caller owns the database transaction.
    """
    file_path = Path(file_path)

    stats = {
        "total_lines": 0,
        "inserted_events": 0,
        "duplicate_events": 0,
        "malformed_events": 0,
        "unknown_dispositions": 0,
        "linked_events": 0,
    }

    with file_path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue

            stats["total_lines"] += 1

            # 1. Parse JSON.
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                stats["malformed_events"] += 1
                continue

            if not isinstance(event, dict):
                stats["malformed_events"] += 1
                continue

            event_id = event.get("event_id")

            if not isinstance(event_id, str) or not event_id.strip():
                stats["malformed_events"] += 1
                continue

            # 2. Check duplicate IDs before other event validation.
            # Reserve the ID, including IDs of ignored unknown dispositions.
            # This prevents the same event from being accepted in a later file.
            # 2. Check whether this event ID has already been seen.
            existing = connection.execute(
                "SELECT 1 FROM seen_event_ids WHERE event_id = ?",
                (event_id,),
            ).fetchone()

            if existing:
                stats["duplicate_events"] += 1
                continue

            # Validate required event structure.
            event_type = event.get("event_type")
            workflow_id = event.get("workflow_id")

            if (
                not isinstance(event_type, str)
                or not event_type.strip()
                or not isinstance(workflow_id, str)
                or not workflow_id.strip()
            ):
                stats["malformed_events"] += 1
                continue

            payload = event.get("payload")

            if payload is None:
                payload = {}
            elif not isinstance(payload, dict):
                stats["malformed_events"] += 1
                continue

            normalized_event = dict(event)
            normalized_event["payload"] = payload

            try:
                normalized_event["occurred_at"] = (
                    normalize_event_timestamp(event.get("occurred_at"))
                )
            except (ValueError, TypeError, KeyError):
                stats["malformed_events"] += 1
                continue

            # 3. Determine whether the event is an orphan.
            linkable = _is_linkable(connection, normalized_event)
            # Reserve the ID only after structural and timestamp validation.
            # This also reserves IDs for valid unknown-disposition events.
            if not register_event_id(connection, event_id):
                stats["duplicate_events"] += 1
                continue

            # 4. Unknown dispositions are ignored only after
            # orphan classification. Orphans are retained so
            # they can be reconciled when a lead arrives later.
            if linkable and event_type in DISPOSITION_EVENT_TYPES:
                disposition_code = payload.get("disposition_code")
                valid_codes = dispositions.get(workflow_id, {})

                if (
                    not isinstance(disposition_code, str)
                    or disposition_code.strip().lower() not in valid_codes
                ):
                    stats["unknown_dispositions"] += 1
                    continue

            try:
                result = insert_event(
                    connection,
                    normalized_event,
                    file_path,
                    line_number,
                )
            except (ValueError, TypeError, KeyError):
                stats["malformed_events"] += 1
                continue

            if result == "duplicate":
                stats["duplicate_events"] += 1
            else:
                stats["inserted_events"] += 1

    # Reconcile after processing the complete file.
    stats["linked_events"] = reconcile_orphan_events(connection)

    return stats
