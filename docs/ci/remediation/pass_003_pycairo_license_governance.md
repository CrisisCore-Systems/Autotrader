# CI Remediation Pass 003: pycairo License Governance

## Linked evidence

Pass 002 classified License Compliance failure as pycairo 1.29.0 reporting `LGPL-2.1-only OR MPL-1.1`.

## Package

- Name: pycairo
- Version: 1.29.0
- License expression: LGPL-2.1-only OR MPL-1.1
- Direct dependency: no
- Parent dependency if transitive: rlPyCairo (required by svglib)

## Governance decision

Decision: defer

## Rationale

pycairo is not a direct dependency and is present due to svglib → rlPyCairo → pycairo. svglib is not listed in project requirements, so its presence may be due to a development or system-level install. No change to the allow-list or dependency manifests will be made until the necessity of svglib is confirmed and a governance decision is made.

## CI policy action

- Add exact allowed license expression: (deferred)
- Remove dependency: (deferred)
- Replace parent package: (deferred)
- Defer with issue: Yes, pending governance review

## Boundary

No broker code, strategy code, execution behavior, order sizing, live ports, or trading automation changed.
