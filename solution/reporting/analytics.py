
import json
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from solution.security.pii import decrypt_text


IST = ZoneInfo("Asia/Kolkata")

BUCKETS = (
    "yet_to_reach_out",
    "in_progress_telephony_failed",
    "in_progress_dialed",
    "completed",
)


def to_ist(value: str) -> datetime:
    """Convert a normalized UTC timestamp into an IST datetime."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(IST)


def mask_phone(encrypted_phone: bytes) -> str:
    """Decrypt a phone in memory and return only its masked representation."""
    phone = decrypt_text(encrypted_phone)
    return "+91******" + phone[-4:]


def build_analytics(connection, dispositions: dict) -> dict:
    """
    Build report-ready analytics from linked leads and events.

    Orphan events are excluded from all calculations.
    The function does not modify the database.
    """

    # ---------------------------------------------------------
    # 1. Load leads
    # ---------------------------------------------------------

    lead_rows = connection.execute("""
        SELECT
            id,
            workflow_id,
            external_ref,
            batch_id,
            encrypted_phone,
            attributes_json
        FROM leads
        ORDER BY workflow_id, external_ref
    """).fetchall()

    leads = {}

    for row in lead_rows:
        lead_id = row["id"]

        leads[lead_id] = {
            "id": lead_id,
            "workflow_id": row["workflow_id"],
            "external_ref": row["external_ref"],
            "batch_id": row["batch_id"],
            "phone_masked": mask_phone(row["encrypted_phone"]),
            "attributes": json.loads(row["attributes_json"]),
            "calls": [],
        }

    # ---------------------------------------------------------
    # 2. Load only events linked to valid leads
    # ---------------------------------------------------------

    event_rows = connection.execute("""
        SELECT
            e.event_id,
            e.event_type,
            e.workflow_id,
            e.call_id,
            e.occurred_at,
            e.payload_json,
            el.lead_id
        FROM events e
        JOIN event_links el
          ON el.event_id = e.event_id
        WHERE el.link_status = 'linked'
          AND el.lead_id IS NOT NULL
        ORDER BY e.occurred_at, e.event_id
    """).fetchall()

    # Group events by lead and call.
    grouped_calls = defaultdict(list)

    for row in event_rows:
        lead_id = row["lead_id"]

        if lead_id not in leads:
            continue

        call_id = row["call_id"]

        if not call_id:
            continue

        key = (lead_id, call_id)

        grouped_calls[key].append({
            "event_type": row["event_type"],
            "occurred_at": row["occurred_at"],
            "payload": json.loads(row["payload_json"]),
        })

    # ---------------------------------------------------------
    # 3. Build calls and determine effective dispositions
    # ---------------------------------------------------------

    for (lead_id, call_id), events in grouped_calls.items():

        initiated_events = [
            event for event in events
            if event["event_type"] == "call.initiated"
        ]

        # A call exists only when call.initiated is present.
        if not initiated_events:
            continue

        # Use the earliest initiation if duplicate initiation
        # events exist for the same call.
        initiated = min(
            initiated_events,
            key=lambda event: event["occurred_at"],
        )

        connected = any(
            event["event_type"] == "call.connected"
            for event in events
        )

        telephony_failed = any(
            event["event_type"] == "call.telephony_failed"
            for event in events
        )

        overrides = [
            event for event in events
            if event["event_type"] == "disposition.override"
        ]

        disposition_sets = [
            event for event in events
            if event["event_type"] == "disposition.set"
        ]

        # A supervisor override takes precedence over every
        # original disposition.set event.
        if overrides:
            effective_event = max(
                overrides,
                key=lambda event: event["occurred_at"],
            )
        elif disposition_sets:
            effective_event = max(
                disposition_sets,
                key=lambda event: event["occurred_at"],
            )
        else:
            effective_event = None

        disposition_code = None
        is_terminal = False
        is_success = False

        if effective_event is not None:
            disposition_code = (
                effective_event["payload"].get("disposition_code")
            )

            catalog_entry = dispositions.get(
                leads[lead_id]["workflow_id"], {}
            ).get(disposition_code)

            if catalog_entry:
                is_terminal = catalog_entry["is_terminal"]
                is_success = catalog_entry["is_success"]

        call = {
            "call_id": call_id,
            "initiated_at": initiated["occurred_at"],
            "date": to_ist(initiated["occurred_at"]).date().isoformat(),
            "connected": connected,
            "telephony_failed": telephony_failed,
            "disposition": disposition_code,
            "is_terminal": is_terminal,
            "is_success": is_success,
        }

        leads[lead_id]["calls"].append(call)

    # ---------------------------------------------------------
    # 4. Calculate each lead's bucket and report fields
    # ---------------------------------------------------------

    lead_report = []
    batch_counts = defaultdict(
        lambda: {
            "total_leads": 0,
            **{bucket: 0 for bucket in BUCKETS},
        }
    )

    daily_calls = defaultdict(
        lambda: {
            "total_calls": 0,
            "connected_calls": 0,
            "success_leads": set(),
        }
    )

    for lead in leads.values():

        calls = sorted(
            lead["calls"],
            key=lambda call: call["initiated_at"],
        )

        total_calls = len(calls)

        connected_calls = sum(
            1 for call in calls if call["connected"]
        )

        # Bucket rules are evaluated in the specified order.
        if total_calls == 0:
            bucket = "yet_to_reach_out"

        elif any(call["is_terminal"] for call in calls):
            bucket = "completed"

        elif all(call["telephony_failed"] for call in calls):
            bucket = "in_progress_telephony_failed"

        else:
            bucket = "in_progress_dialed"

        # Most recent call with an effective disposition.
        calls_with_disposition = [
            call for call in calls
            if call["disposition"] is not None
        ]

        current_disposition = (
            calls_with_disposition[-1]["disposition"]
            if calls_with_disposition
            else ""
        )

        ever_success = any(
            call["is_success"] for call in calls
        )

        last_call_at = (
            to_ist(calls[-1]["initiated_at"]).isoformat()
            if calls
            else ""
        )

        lead_report.append({
            "workflow_id": lead["workflow_id"],
            "external_ref": lead["external_ref"],
            "batch_id": lead["batch_id"],
            "phone_masked": lead["phone_masked"],
            "bucket": bucket,
            "total_calls": total_calls,
            "connected_calls": connected_calls,
            "last_call_at": last_call_at,
            "current_disposition": current_disposition,
            "ever_success": ever_success,
        })

        # Batch summary.
        batch_key = (
            lead["workflow_id"],
            lead["batch_id"],
        )

        batch_counts[batch_key]["total_leads"] += 1
        batch_counts[batch_key][bucket] += 1

        # Daily overview.
        for call in calls:
            daily_key = (
                lead["workflow_id"],
                call["date"],
            )

            daily = daily_calls[daily_key]
            daily["total_calls"] += 1

            if call["connected"]:
                daily["connected_calls"] += 1

            if call["is_success"]:
                daily["success_leads"].add(lead["id"])

    # ---------------------------------------------------------
    # 5. Format batch summary
    # ---------------------------------------------------------

    batch_summary = []

    for (workflow_id, batch_id), counts in sorted(
        batch_counts.items()
    ):
        batch_summary.append({
            "workflow_id": workflow_id,
            "batch_id": batch_id,
            "total_leads": counts["total_leads"],
            "yet_to_reach_out": counts["yet_to_reach_out"],
            "in_progress_telephony_failed":
                counts["in_progress_telephony_failed"],
            "in_progress_dialed": counts["in_progress_dialed"],
            "completed": counts["completed"],
        })

    # ---------------------------------------------------------
    # 6. Format daily overview
    # ---------------------------------------------------------

    daily_overview = []

    for (workflow_id, date), counts in sorted(
        daily_calls.items()
    ):
        total_calls = counts["total_calls"]
        connected_calls = counts["connected_calls"]

        connectivity_rate = (
            connected_calls / total_calls
            if total_calls
            else 0
        )

        daily_overview.append({
            "workflow_id": workflow_id,
            "date": date,
            "total_calls": total_calls,
            "connected_calls": connected_calls,
            "connectivity_rate": f"{connectivity_rate:.4f}",
            "success_leads": len(counts["success_leads"]),
        })

    lead_report.sort(
        key=lambda row: (
            row["workflow_id"],
            row["external_ref"],
        )
    )

    return {
        "batch_summary": batch_summary,
        "daily_overview": daily_overview,
        "lead_report": lead_report,
    }
