# CI Remediation Pass 009: certifi License Governance

## Linked verification

After PR #146 cleared the `zc.lockfile` license expression, the next License Compliance failure surfaced as a single exact expression.

Remaining License Compliance failure:

- Package: certifi
- Version: 2026.4.22
- License expression: Mozilla Public License 2.0 (MPL 2.0)

## Dependency source

- Direct dependency: none
- Parent dependency if transitive: `requests==2.33.0` and other HTTP clients in the stack resolve `certifi` transitively
- Project file declaring parent: `requirements.txt`, `pyproject.toml`

## Governance decision

Decision: accept exact expression `Mozilla Public License 2.0 (MPL 2.0)`

## Rationale

The current allow-list already contains `MPL-2.0`, but the compliance tool reports `certifi` using the expanded expression `Mozilla Public License 2.0 (MPL 2.0)`. This remediation accepts only the exact expression reported by the tool and does not broadly expand unrelated license families.

## CI policy action

Add exact allow-list entry:

`Mozilla Public License 2.0 (MPL 2.0)`

## Boundary

No broker code, strategy code, execution behavior, order sizing, live ports, dependency upgrades, or trading automation changed.
