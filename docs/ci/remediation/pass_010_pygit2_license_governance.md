# CI Remediation Pass 010: pygit2 License Governance

## Linked verification

After PR #147 cleared the `certifi` license expression, the next License Compliance failure surfaced as a single exact expression.

Remaining License Compliance failure:

- Package: pygit2
- Version: 1.19.2
- License expression: GPLv2 with linking exception

## Dependency source

- Direct dependency: none
- Parent dependency if transitive: `scmrepo<4,>=3.3.4` pulled by `dvc[s3]==3.51.0`, which resolves `pygit2>=1.14.0`
- Project file declaring parent: `requirements.txt` (dvc[s3]==3.51.0), `pyproject.toml` (dvc[s3]>=3.50.0)

## Governance decision

Decision: accept

## Rationale

`GPLv2 with linking exception` is a GPL-family expression and should not be treated the same as permissive composite expressions like `Apache-2.0 AND MIT`. The linking exception may reduce integration risk, but the project should explicitly decide whether this expression is acceptable for the CI license policy.

In this repository, `pygit2` is transitive from intentionally declared DVC dependencies used for data/versioning workflows. The allow-list already contains a GPLv2 variant (`GNU General Public License v2 (GPLv2)`), so accepting only this exact reported expression keeps policy matching strict without broadening to generic GPL patterns.

## CI policy action

- Accept exact expression only: `GPLv2 with linking exception`

## Boundary

No broker code, strategy code, execution behavior, order sizing, live ports, dependency upgrades, or trading automation changed.
