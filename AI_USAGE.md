# AI Usage Disclosure

## Tools used

- ChatGPT (OpenAI)

## What I used them for

I used ChatGPT as a development assistant during the assignment for:

- Breaking down the assignment requirements into implementation steps.
- Discussing the database design, ingestion flow, event linking, and PII protection approach.
- Understanding Python implementation details and debugging errors.
- Reviewing edge cases in lead validation, duplicate merging, event deduplication, and orphan reconciliation.
- Designing and reviewing tests for important business rules.
- Reviewing generated reports and checking whether output totals matched database records.
- Preparing and reviewing the submission documentation.

Some implementation guidance, code suggestions, and test ideas were developed with AI assistance. I ran the commands, inspected the results, and iterated on the implementation based on observed behaviour.

## What I wrote or decided myself

I made and reviewed the implementation decisions for the assignment, including:

- Choosing Assignment A.
- Using SQLite for persistence.
- Organizing the solution into ingestion, database, security, and reporting modules.
- Following the specified lead identity and duplicate-merging rules.
- Using encrypted PII fields and deterministic HMAC phone hashes for matching.
- Keeping event records append-only and storing event-to-lead relationships separately.
- Running the supplied dataset through the pipeline and checking the resulting database and reports.
- Deciding which issues needed further investigation based on test and runtime output.

I am responsible for the final submitted code and for being able to explain the design and behaviour.

## Where the AI was wrong or unhelpful

During report verification, the AI initially interpreted a database query that checked for missing `event_links` rows as a count of orphan events. That query returned zero, but orphan events actually have an `event_links` row with `link_status = 'orphan'` and a null lead ID.

After inspecting the schema, repository code, and actual link-status counts, I corrected the interpretation. The final report's orphan count of 462 was correct.

This reinforced the importance of checking the actual data model and SQL semantics instead of accepting an explanation without verification.

## How I verified AI-generated code

- Ran the complete automated test suite using `python -m pytest -q`.
- Final test result: **117 passed**.
- Generated and ingested the supplied synthetic dataset.
- Queried the SQLite database to verify lead, event, link, and orphan counts.
- Checked that the five required report files were generated with the expected headers and row counts.
- Checked that phone numbers in the lead report were masked.
- Inspected the rejection report and data-quality JSON.
- Reviewed implementation and test output while debugging issues.

AI assistance was used as a development aid; runtime results and final checks were performed against the actual implementation.