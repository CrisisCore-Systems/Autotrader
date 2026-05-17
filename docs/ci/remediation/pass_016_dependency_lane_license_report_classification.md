# Dependency Lane License Report Classification

## Source run

- Workflow: dependency-lane-license-report.yml
- Run ID: 25986806449
- Result: success

## Artifacts reviewed

- dependency-lane-license-report-runtime
- dependency-lane-license-report-broker
- dependency-lane-license-report-market-data
- dependency-lane-license-report-mlops

## Sensitive license findings

| Lane | Package | Version | License | Classification | Action |
|---|---|---:|---|---|---|
| broker | autotrader | 0.1.0 | UNKNOWN | Internal package metadata unknown | Add explicit license metadata in package metadata planning; no CI gate in this pass |
| broker | certifi | 2026.4.22 | Mozilla Public License 2.0 (MPL 2.0) | Weak copyleft (file-level) | Keep under observation; include in lane policy draft |
| market-data | autotrader | 0.1.0 | UNKNOWN | Internal package metadata unknown | Add explicit license metadata in package metadata planning; no CI gate in this pass |
| market-data | certifi | 2026.4.22 | Mozilla Public License 2.0 (MPL 2.0) | Weak copyleft (file-level) | Keep under observation; include in lane policy draft |
| market-data | frozendict | 2.4.7 | GNU Lesser General Public License v3 (LGPLv3) | Copyleft-sensitive | Track for legal review before any enforcement stage |
| market-data | peewee | 4.0.5 | UNKNOWN | Upstream metadata unresolved in report | Verify via supplemental source/license metadata before policy gates |
| mlops | asyncssh | 2.23.0 | EPL-2.0 OR GPL-2.0-or-later | Dual license including copyleft option | Capture preferred license interpretation in policy draft |
| mlops | autotrader | 0.1.0 | UNKNOWN | Internal package metadata unknown | Add explicit license metadata in package metadata planning; no CI gate in this pass |
| mlops | certifi | 2026.4.22 | Mozilla Public License 2.0 (MPL 2.0) | Weak copyleft (file-level) | Keep under observation; include in lane policy draft |
| mlops | dulwich | 1.2.1 | Apache-2.0 OR GPL-2.0-or-later | Dual license including copyleft option | Capture preferred license interpretation in policy draft |
| mlops | grandalf | 0.8 | GNU General Public License v2 (GPLv2) | Strong copyleft | Track for legal review before enforcement stage |
| mlops | orjson | 3.11.9 | MPL-2.0 AND (Apache-2.0 OR MIT) | Mixed permissive + weak copyleft | Keep under observation; verify obligations model |
| mlops | pathspec | 1.1.1 | Mozilla Public License 2.0 (MPL 2.0) | Weak copyleft (file-level) | Keep under observation; include in lane policy draft |
| mlops | pygit2 | 1.19.2 | GPLv2 with linking exception | Copyleft with exception | Track for legal review on exception applicability |
| mlops | tqdm | 4.67.3 | MPL-2.0 AND MIT | Mixed permissive + weak copyleft | Keep under observation; verify obligations model |
| mlops | zc.lockfile | 4.0 | Zope Public License | License-family review required | Classify in policy draft and confirm allow/deny handling |
| runtime | autotrader | 0.1.0 | UNKNOWN | Internal package metadata unknown | Add explicit license metadata in package metadata planning; no CI gate in this pass |
| runtime | certifi | 2026.4.22 | Mozilla Public License 2.0 (MPL 2.0) | Weak copyleft (file-level) | Keep under observation; include in lane policy draft |
| runtime | regex | 2026.5.9 | Apache-2.0 AND CNRI-Python | Multi-license, CNRI marker present | Classify CNRI handling in policy draft |
| runtime | tqdm | 4.67.3 | MPL-2.0 AND MIT | Mixed permissive + weak copyleft | Keep under observation; verify obligations model |

## Lane interpretation

### Runtime

Runtime lane completed successfully and includes mostly permissive licensing with flagged entries for UNKNOWN (internal package metadata), MPL variants, and CNRI-tagged dual licensing. No policy enforcement is applied in this phase.

### Broker

Broker lane completed successfully with a small sensitive set (UNKNOWN internal package metadata and MPL 2.0). Risk is currently observational and feeds future policy classification.

### Market data

Market-data lane completed successfully and includes LGPLv3 (frozendict) plus UNKNOWN metadata (autotrader and peewee in report output). This lane should be prioritized in policy drafting review before any gates are introduced.

### MLOps

MLOps lane completed successfully with the broadest sensitive profile, including GPL/LGPL-adjacent and MPL/Zope families plus dual-license packages. This lane requires the most detailed classification work prior to enforcement.

## Boundary

No requirements.txt changes.
No pyproject.toml changes.
No dependency movement.
No LGPLv3 allow-list patch.
No security-scan.yml replacement.
No runtime behavior changes.
No trading behavior changes.
No artifact JSON files committed.
