# CI Remediation Pass 011: frozendict License Governance

## Linked verification

After PR #148 cleared the `pygit2` linking-exception license expression, the next License Compliance failure surfaced as a single exact expression.

Remaining License Compliance failure:

- Package: frozendict
- Version: 2.4.7
- License expression: GNU Lesser General Public License v3 (LGPLv3)

## Dependency source

- Direct dependency: none
- Parent dependency if transitive: `yfinance` (requires `frozendict>=2.3.4`)
- Project file declaring parent: `requirements.txt` (`yfinance>=0.2.38`), `pyproject.toml` (`yfinance>=0.2.40`)

## Governance decision

Decision: defer

## Rationale

`GNU Lesser General Public License v3 (LGPLv3)` is a copyleft-family license expression. It should not be treated like permissive expressions such as MIT, Apache-2.0, BSD, or exact composite permissive values. The project must explicitly decide whether this package is acceptable, whether it is only present through tooling/dev dependencies, or whether the license scan should separate runtime dependencies from CI/dev tooling.

Evidence indicates `frozendict` is pulled through a runtime-declared dependency (`yfinance`) rather than only CI/dev tooling, so this should be reviewed as a runtime licensing decision rather than auto-allowing the token in CI.

## CI policy action

- Defer with governance issue

## Boundary

No broker code, strategy code, execution behavior, order sizing, live ports, dependency upgrades, or trading automation changed.
