# CI Baseline Issue Index

## Purpose

Track each known CI failure bucket with a named GitHub issue, explicit owner slot, and cleanup path.

## Issue links

1. Dependency Review failure source
- Issue: https://github.com/CrisisCore-Systems/Autotrader/issues/124
- Scope: Identify root cause of security-scan/Dependency Review failure.
- Related to IBKR safety work: no
- Owner: TBD
- Priority: High

2. Security scan baseline failures
- Issue: https://github.com/CrisisCore-Systems/Autotrader/issues/129
- Scope: Classify security-scan failures (license/prompt/dependency-audit surface).
- Related to IBKR safety work: no
- Owner: TBD
- Priority: High

3. Test and lint workflow failures
- Issue: https://github.com/CrisisCore-Systems/Autotrader/issues/132
- Scope: Baseline test/lint failures across tests-and-coverage and CI Pipeline.
- Related to IBKR safety work: no
- Owner: TBD
- Priority: High

4. Unknown or stale failure log inspection
- Issue: https://github.com/CrisisCore-Systems/Autotrader/issues/133
- Scope: Reclassify unknown/stale failures after log inspection and reruns.
- Related to IBKR safety work: no
- Owner: TBD
- Priority: Medium

5. Policy gate for broker/trading PRs
- Issue: https://github.com/CrisisCore-Systems/Autotrader/issues/134
- Scope: Enforce non-green merge policy gate with issue-link requirements.
- Related to IBKR safety work: yes (governance)
- Owner: TBD
- Priority: High

## Policy boundary

No new trading capability should be added until these CI failure buckets are classified and linked to active remediation or accepted baseline decisions.

Hard boundary remains:
- No real strategy automation
- No larger order size
- No live ports
- No autonomous execution loop
