# Submission

## Candidate

- **Name:** Madan Kumar M.
- **Assignment chosen:** A — Interaction Ledger & Reporting Pipeline (Data)
- **Time spent:** Approximately [5-6 Hours]

## How to run

The implementation uses Python 3.11+ and SQLite. Run commands from the repository root.

### 1. Set up the environment

```bash
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -r requirements.txt
```

### 2. Generate the supplied synthetic dataset

```bash
python assignment-a-data/tools/generate_data.py --seed 42 --scale small --out data
```

### 3. Initialize the database and ingest both drops

Set the database path before starting Python:

```bash
export AU_DB_PATH="$PWD/data/assignment_final.db"
```

Then run:

```bash
python - <<'PY'
from pathlib import Path
from solution.database.connection import initialize_database
from solution.ingestion.lead_pipeline import ingest_lead_files
from solution.ingestion.event_pipeline import ingest_event_files

initialize_database()

for drop in ("drop_1", "drop_2"):
    base = Path("data") / drop / "leads"

    for workflow_dir in sorted(base.iterdir()):
        if workflow_dir.is_dir():
            files = sorted(workflow_dir.glob("*.csv"))
            if files:
                print(ingest_lead_files(files, workflow_dir.name))

    event_files = sorted(
        (Path("data") / drop / "events").glob("*.jsonl")
    )
    if event_files:
        print(ingest_event_files(event_files))
PY
```

### 4. Generate reports

```bash
python - <<'PY'
from solution.database.connection import get_connection
from solution.reporting.report_generator import generate_reports

conn = get_connection()
try:
    print(generate_reports(conn, "reports"))
finally:
    conn.close()
PY
```

### 5. Run tests

```bash
python -m pytest -q
```

## Design

The solution separates ingestion, database access, PII protection, and reporting into modules under `solution/`.

**Lead ingestion:** Workflow-specific JSON schemas define the fields, aliases, types, required fields, and defaults. CSV headers are normalized and mapped to schema fields. Values are validated and normalized before persistence. Invalid required values cause a row rejection; invalid optional values become null and generate field warnings.

Lead identity is based on `(workflow_id, canonical phone)`. Duplicate rows merge into the existing lead, retaining its original batch ID and updating only non-null values from later rows. Defaults are applied after merging.

**Event ingestion:** JSONL events are validated and inserted into an append-only event ledger. Event IDs are tracked separately to prevent duplicates, including IDs belonging to ignored unknown-disposition events. Event-to-lead relationships are stored separately in `event_links`, allowing orphan events to be reconciled when matching leads arrive later without modifying the original event records.

**Database:** SQLite stores leads, events, event links, ingestion tracking, rejections, quality observations, and ingestion statistics. Unique constraints and foreign keys enforce important relationships. Database triggers prevent updates and deletions of ledger events.

**PII protection:** PII fields such as phone numbers and customer names are encrypted using AES-GCM. A keyed HMAC-SHA256 hash of the normalized phone is stored separately to support matching without storing the phone in plaintext. Reports expose masked phone numbers.

**Reporting:** Reporting logic derives lead buckets, call counts, connectivity, effective dispositions, success metrics, and data-quality statistics from the database. The five required output files are generated with fixed column ordering and deterministic sorting.

## Decisions & assumptions

## Decisions & assumptions

| Decision | Why | Alternative considered |
|---|---|---|
| SQLite for persistence | Simple local database with transactions, constraints, and no separate server requirement | PostgreSQL |
| AES-GCM for PII encryption | Authenticated encryption protects stored sensitive values | Plaintext storage or unauthenticated encryption |
| HMAC-SHA256 phone hashes | Enables deterministic phone matching without storing plaintext phone numbers | Hashing without a secret key |
| Separate `event_links` table | Supports late orphan reconciliation without modifying immutable event records | Storing lead IDs directly in event rows |
| Separate seen-event-ID registry | Deduplicates IDs even when an unknown-disposition event is not inserted into the ledger | Deduplicating only against stored events |
| First valid lead row retains its batch ID | Follows the specified duplicate-merging rule | Moving a lead to the latest batch |
| Optional invalid fields become null | Preserves valid leads while recording data-quality warnings | Rejecting the entire row |
| Naive timestamps are interpreted as IST | Follows the assignment specification | Treating naive timestamps as UTC |

## Failure modes considered

- Missing or renamed CSV headers are handled through schema aliases and normalized header matching.
- Blank CSV rows are skipped.
- Invalid required values cause rejection with a reason.
- Invalid optional values are stored as null and counted as warnings.
- Duplicate lead identities are merged according to ingestion order.
- Re-ingesting an already processed file is prevented through file tracking and checksums.
- Malformed JSON events are counted and skipped.
- Duplicate event IDs are counted and skipped.
- Events that cannot be linked are retained as orphans and excluded from lead-level reporting until reconciliation succeeds.
- Unknown disposition codes are counted and ignored according to the event-processing rules.
- Database transactions protect ingestion operations from partial writes.
- Ledger immutability is enforced through database triggers.

**Known limitations / areas for improvement:**

- The solution uses a local SQLite database and is not designed as a horizontally scalable multi-worker ingestion service.
- Large-scale performance was not benchmarked.
- Production-grade operational monitoring, alerting, backup, and key rotation are not implemented.
- Concurrent ingestion and recovery under process termination deserve additional stress testing.

## Testing

The test suite covers normalization, validation, lead merging, database repository behaviour, event processing, event deduplication, orphan handling, and reporting-related rules.

Final verification:

```text
117 passed in 0.60s
```

The supplied small synthetic dataset was also ingested and the five report files were generated. Their headers, row counts, key data-quality totals, and phone masking were checked.

## Results

Final run using seed 42 and the small dataset:

| Metric | Result |
|---|---:|
| Unique leads | 1,892 |
| Lead rows processed | 2,057 |
| Rejected lead rows | 108 |
| Duplicate lead rows merged | 57 |
| Optional-field warnings | 122 |
| Event lines processed | 8,745 |
| Events stored in ledger | 8,482 |
| Duplicate events dropped | 237 |
| Malformed events | 8 |
| Unknown-disposition events | 18 |
| Events linked to leads | 8,020 |
| Remaining orphan events | 462 |

All five required reports were generated:

- `batch_summary.csv`
- `daily_overview.csv`
- `lead_report.csv`
- `rejections.csv`
- `data_quality.json`

The final database contains 8,020 linked events and 462 remaining orphans. Orphan counts reflect the final state after reconciliation.

## If I had another day

1. Add more integration tests for re-ingestion, process interruption, and recovery.
2. Benchmark the large synthetic dataset and optimize ingestion/report generation.
3. Add a simple command-line interface for initialization, ingestion, and report generation.
4. Improve operational logging and error diagnostics.
5. Add production-oriented key management, backup, and monitoring.