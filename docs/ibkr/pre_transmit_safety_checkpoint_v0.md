# IBKR Pre-Transmit Safety Checkpoint v0

Tag: ibkr-pre-transmit-safe-v0
Commit: 93fa9166

Validated constraints:
- IBKR mode requires --paper-only
- IBKR mode refuses port 7496
- IBKR mode refuses --transmit true
- Valid paper TWS port is 7497
- Intentional SNDL / STK / USD / SMART probe reaches placeOrder with transmit=false
- No fill occurs
- Runtime status artifact is isolated with skip-worktree

Hard boundary:
run_live_staging.py must remain non-transmitting.
Any future transmitted paper-order test must live in a separate script with explicit human-confirmation flags.

Post-merge repeatability checkpoint (main):
- Date: 2026-05-16
- Verified CLI entrypoint: `python scripts/run_ibkr_paper_transmit_probe.py --help`
- Verified one guarded paper probe on main (SNDL, STK, LMT, qty=1, max notional=5, localhost:7497, confirmation phrase exact match)
- Second safety marker preserved: ibkr-paper-transmit-probe-v0

Boundary reaffirmed:
- Do not connect strategy automation to IBKR order transmission yet.
- Next milestone is a paper trading harness with simulated strategy signals, not real strategy autonomy.
