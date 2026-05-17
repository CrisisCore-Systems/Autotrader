# CI Remediation Pass 008: zc.lockfile License Governance

## Linked verification

After PR #145 cleared the `aiohttp` composite license expression, the next License Compliance failure surfaced as a single exact expression.

Remaining License Compliance failure:

- Package: zc.lockfile
- Version: 4.0
- License expression: Zope Public License

## Dependency source

- Direct dependency: none
- Parent dependency if transitive: `dvc[s3]==3.51.0` (through DVC lock/utility dependency chain)
- Project file declaring parent: `requirements.txt`, `pyproject.toml`

## Governance decision

Decision: accept exact expression `Zope Public License`

## Rationale

The compliance tool reports `zc.lockfile` under the exact expression `Zope Public License`. This remediation accepts only the exact expression reported by the tool and does not broadly allow unrelated license families or aliases.

## CI policy action

Add exact allow-list entry:

`Zope Public License`

## Boundary

No broker code, strategy code, execution behavior, order sizing, live ports, dependency upgrades, or trading automation changed.
