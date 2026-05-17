# CI Remediation Pass 007: aiohttp License Governance

## Linked verification

After PR #144 cleared the `regex` composite license expression, the next License Compliance failure surfaced as a single exact expression.

Remaining License Compliance failure:

- Package: aiohttp
- Version: 3.13.5
- License expression: Apache-2.0 AND MIT

## Dependency source

- Direct dependency: `aiohttp>=3.8.0`
- Parent dependency if transitive: none (direct dependency)
- Project file declaring parent: `requirements.txt`, `pyproject.toml`

## Governance decision

Decision: accept exact composite expression `Apache-2.0 AND MIT`

## Rationale

Both Apache-2.0 and MIT are already accepted by the current policy. The failure is caused by the compliance tool reporting the combined SPDX-style expression as a distinct value. This remediation accepts only the exact composite expression reported by the tool and does not broadly expand license families.

## CI policy action

Add exact allow-list entry:

`Apache-2.0 AND MIT`

## Boundary

No broker code, strategy code, execution behavior, order sizing, live ports, or trading automation changed.
