
import json

from solution.security.pii import hash_phone
from solution.ingestion.normalizers import normalize_phone


def find_lead_by_phone(connection, workflow_id, phone_hash):
    """Find a lead using its workflow and HMAC phone fingerprint."""
    return connection.execute(
        """
        SELECT id
        FROM leads
        WHERE workflow_id = ? AND phone_hash = ?
        """,
        (workflow_id, phone_hash),
    ).fetchone()


def find_lead_by_call_id(connection, workflow_id, call_id):
    """
    Find the lead associated with another event in the same call.
    Useful for disposition.override events without a phone number.
    """
    if not call_id:
        return None

    return connection.execute(
        """
        SELECT l.id
        FROM events e
        JOIN event_links el ON el.event_id = e.event_id
        JOIN leads l ON l.id = el.lead_id
        WHERE e.workflow_id = ?
          AND e.call_id = ?
          AND el.link_status = 'linked'
        LIMIT 1
        """,
        (workflow_id, call_id),
    ).fetchone()


def register_event_id(connection, event_id):
    """
    Register an event ID permanently.

    Returns True if this is the first occurrence,
    False if the ID has already been seen.
    """
    cursor = connection.execute(
        """
        INSERT OR IGNORE INTO seen_event_ids (event_id)
        VALUES (?)
        """,
        (event_id,),
    )

    return cursor.rowcount == 1


def insert_event(connection, event, source_file, source_line):
    """
    Insert one immutable event and its initial lead link.

    Returns:
        'inserted' for a new event.
        'duplicate' when its event_id already exists.

    Phone numbers are stored only as HMAC fingerprints.
    """
    event_id = event.get("event_id")

    if not isinstance(event_id, str) or not event_id.strip():
        raise ValueError("Event ID is missing")

    existing = connection.execute(
        "SELECT 1 FROM events WHERE event_id = ?",
        (event_id,),
    ).fetchone()

    if existing:
        return "duplicate"

    workflow_id = event["workflow_id"]
    call_id = event.get("call_id")
    phone = event.get("phone")

    phone_hash = None

    if phone:
        try:
            normalized_phone = normalize_phone(phone)
            phone_hash = hash_phone(normalized_phone)
        except (ValueError, TypeError, AttributeError):
            # The event may still be valid.
            # An unusable phone means it cannot be linked by phone,
            # but it may still be linked through call_id.
            phone_hash = None

    # Never persist the raw phone number in the JSON payload.
    safe_payload = dict(event.get("payload") or {})

    connection.execute(
        """
        INSERT INTO events (
            event_id,
            event_type,
            workflow_id,
            call_id,
            occurred_at,
            phone_hash,
            payload_json,
            source_file,
            source_line
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            event["event_type"],
            workflow_id,
            call_id,
            event["occurred_at"],
            phone_hash,
            json.dumps(safe_payload),
            str(source_file),
            source_line,
        ),
    )

    lead = None

    if phone_hash:
        lead = find_lead_by_phone(
            connection,
            workflow_id,
            phone_hash,
        )

    if lead is None and call_id:
        lead = find_lead_by_call_id(
            connection,
            workflow_id,
            call_id,
        )

    connection.execute(
        """
        INSERT INTO event_links (event_id, lead_id, link_status)
        VALUES (?, ?, ?)
        """,
        (
            event_id,
            lead["id"] if lead else None,
            "linked" if lead else "orphan",
        ),
    )

    return "inserted"



def reconcile_orphan_events(connection):
    """
    Reconcile orphan events in two passes.

    Pass 1: Link events by workflow_id + phone_hash.
    Pass 2: Link remaining events through an already-linked
            event belonging to the same workflow and call_id.

    Event records remain immutable. Only event_links are updated.
    """

    linked_count = 0

    # Pass 1: Direct phone-based matching.
    phone_orphans = connection.execute(
        """
        SELECT
            e.event_id,
            e.workflow_id,
            e.phone_hash
        FROM events e
        JOIN event_links el ON el.event_id = e.event_id
        WHERE el.link_status = 'orphan'
          AND e.phone_hash IS NOT NULL
        """
    ).fetchall()

    for event in phone_orphans:
        lead = find_lead_by_phone(
            connection,
            event["workflow_id"],
            event["phone_hash"],
        )

        if lead:
            connection.execute(
                """
                UPDATE event_links
                SET lead_id = ?, link_status = 'linked'
                WHERE event_id = ?
                """,
                (lead["id"], event["event_id"]),
            )
            linked_count += 1

    # Pass 2: Call-based matching after phone links are established.
    call_orphans = connection.execute(
        """
        SELECT
            e.event_id,
            e.workflow_id,
            e.call_id
        FROM events e
        JOIN event_links el ON el.event_id = e.event_id
        WHERE el.link_status = 'orphan'
          AND e.call_id IS NOT NULL
        """
    ).fetchall()

    for event in call_orphans:
        lead = find_lead_by_call_id(
            connection,
            event["workflow_id"],
            event["call_id"],
        )

        if lead:
            connection.execute(
                """
                UPDATE event_links
                SET lead_id = ?, link_status = 'linked'
                WHERE event_id = ?
                """,
                (lead["id"], event["event_id"]),
            )
            linked_count += 1

    return linked_count

