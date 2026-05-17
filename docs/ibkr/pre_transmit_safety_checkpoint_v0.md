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
