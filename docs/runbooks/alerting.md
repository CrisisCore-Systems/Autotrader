# Alerting Runbook

This runbook documents how the GemScore alerting stack is operated in production and how the idempotent outbox-based delivery flow behaves.

## Architecture Recap

1. `APScheduler` (or Cloud Scheduler) invokes the `/jobs/score-scan` endpoint on the API service.
2. The API enqueues a Celery task that performs `scan → score → apply rules`.
3. Matching candidates are persisted in the `alerts_outbox` table (see `src/alerts/repo.py`).
4. A dedicated dispatcher worker drains the outbox, sending notifications through Telegram, Slack, and email transports with exponential backoff.

## Idempotency & Cool-offs

* Each payload is keyed as `{symbol}:{window_start}:{rule_id}:v{rule.version}` which is enforced with a unique constraint in the storage layer.
* Before enqueuing, the engine checks `seen_recently` for the configured rule cool-off to avoid duplicate notifications.
* When the dispatcher retries, the same key is reused and the audit trail is updated with timestamps and attempt counters.

## Operational Commands

```bash
# Copy the environment template and fill in credentials
cp .env.template .env

# Evaluate rules against a JSON payload of candidates (example snippet)
python - <<'PY'
from datetime import datetime, timezone
import json
from pathlib import Path
from src.alerts.engine import AlertCandidate, evaluate_and_enqueue
from src.alerts.repo import InMemoryAlertOutbox

payload = json.loads(Path("artifacts/candidates.json").read_text())
outbox = InMemoryAlertOutbox()
candidates = [AlertCandidate(**item) for item in payload["candidates"]]
entries = evaluate_and_enqueue(candidates, now=datetime.now(timezone.utc), outbox=outbox)
print(f"Queued {len(entries)} alerts")
for entry in entries:
    print(entry.key, entry.payload)
PY

# Start the Celery worker and dispatcher (example supervisord excerpt)
celery -A src.alerts.worker worker -Q alerts --loglevel=INFO
python -m src.alerts.worker --dispatch
```

## Dead-letter Queue

* Entries that exhaust the retry budget land in the DLQ with `status="failed"`.
* Query `alerts_outbox` for failed entries (or call `outbox.list_dead_letters()` when using the repository abstraction).
* To replay a specific key, update the row back to `status='queued'`, clear the error field, and reset `next_attempt_at` to `NOW()`.

## Observability

* The dispatcher publishes Prometheus counters (`alerts_sent_total`, `alerts_retry_total`, `alerts_failed_total`).
* Structured logs include the idempotency key, attempts, and transport errors.
* Connect the logs to the incident channel to triage transport outages quickly.
