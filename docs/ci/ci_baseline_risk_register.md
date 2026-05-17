# CI Baseline Risk Register

## Current accepted-risk merges

### PR #120
Reason: Non-green checks accepted after confirming scoped IBKR harness diff.
Changed files:
- .gitignore
- docs/ibkr/pre_transmit_safety_checkpoint_v0.md
- scripts/run_ibkr_simulated_signal_paper_harness.py

### PR #121
Reason: Non-green checks accepted after confirming scoped batch-audit diff.
Changed files:
- .gitignore
- fixtures/ibkr/simulated_signal_batch_001.json
- scripts/run_ibkr_simulated_signal_batch_audit.py

## Merge policy going forward

Non-green merge is allowed only when:
- all failing checks are documented
- changed files are listed
- failure is proven unrelated to the PR scope
- no dependency manifests changed
- no runtime artifacts are included
- no node_modules are included
- no broker/live execution code is expanded without passing local safety validation

## Required cleanup

- Identify Dependency Review failure source
- Identify security-scan baseline failures
- Separate stale failures from active regressions
- Add issue links for each unresolved baseline failure
