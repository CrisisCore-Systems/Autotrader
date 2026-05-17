# CI Remediation Pass 004: greenlet License Governance

## Linked verification

CI Remediation Verification Pass 001 showed that Prompt Contract Validation and Python Dependency Audit moved past prior failures.

Remaining License Compliance failure:

- Package: greenlet
- Version: 3.5.0
- License expression: MIT AND PSF-2.0

## Dependency source

- Direct dependency: no
- Parent dependency if transitive: SQLAlchemy
- Project file declaring parent: (not found in requirements.txt, requirements-dev.txt, pyproject.toml, or setup.cfg)

## Governance decision

Decision: accept exact composite expression `MIT AND PSF-2.0`

## Rationale

Both MIT and PSF-2.0 are already accepted license families in the current policy. The failure is caused by the compliance tool reporting the combined SPDX-style expression as a distinct value. The policy should accept the exact composite expression without broadly expanding license families.

## CI policy action

Add exact allow-list entry:

`MIT AND PSF-2.0`

## Boundary

No broker code, strategy code, execution behavior, order sizing, live ports, or trading automation changed.
