# CI Remediation Pass 006: regex License Governance

## Linked verification

CI Remediation Verification Pass 002 showed that Python Dependency Audit, Prompt Contract Validation, Bandit, Trivy, Gitleaks, and TruffleHog pass.

Remaining License Compliance failure:

- Package: regex
- Version: 2026.5.9
- License expression: Apache-2.0 AND CNRI-Python

## Dependency source

- Direct dependency: no direct `regex` declaration in `requirements.txt`, `requirements-dev.txt`, or `pyproject.toml`
- Parent dependency if transitive: `nltk==3.9.4` (NLP dependency present in runtime requirements)
- Project file declaring parent: `requirements.txt`

## Governance decision

Decision: accept exact composite expression `Apache-2.0 AND CNRI-Python`

## Rationale

Apache-2.0 is already accepted by the current policy. CNRI-Python is a Python ecosystem license expression that must be evaluated explicitly. This remediation accepts only the exact composite expression reported by the license tool and does not broadly allow new license families.

## CI policy action

Add exact allow-list entry:

`Apache-2.0 AND CNRI-Python`

## Boundary

No broker code, strategy code, execution behavior, order sizing, live ports, or trading automation changed.
