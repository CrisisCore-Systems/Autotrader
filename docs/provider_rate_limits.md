# External Provider Rate Limits & Budgets

This reference captures the enforced request budgets for the ingestion layer as
implemented by the shared `RateAwareRequester` and persistent ingestion queue.
The limits are intentionally conservative to protect against upstream bans and
can be tuned via configuration.

| Provider | Hostname | Budget | Notes |
| --- | --- | --- | --- |
| CoinGecko | `api.coingecko.com` | 30 requests / minute | Cached responses for 5 minutes to minimise duplicate fetches. |
| DefiLlama | `api.llama.fi` | 60 requests / minute | Protocol snapshots cached for 10 minutes. |
| Etherscan | `api.etherscan.io` | 5 requests / second | Contract lookups cached for 1 hour. |
| GitHub API | `api.github.com` | 4,500 requests / hour | Repository event polling cached for 2 minutes. |
| Generic feeds | `*` | 120 requests / minute | Applies to data sources without an explicit budget. |

## Queue Backoff Policies

The SQLite-backed ingestion queue enforces exponential-style backoff windows to
spread retries across runs:

- News feeds: 5-minute delay after failures before the next lease.
- Social streams: 2-minute delay after failures.
- GitHub repositories: 3-minute delay after failures.
- Tokenomics endpoints: 5-minute delay after failures.

Jobs marked as completed are not re-leased until they are re-enqueued with
updated payloads, ensuring noise from bursty feeds is smoothed across polling
cycles.
