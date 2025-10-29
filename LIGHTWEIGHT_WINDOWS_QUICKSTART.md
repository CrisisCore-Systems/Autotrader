# Lightweight Local Quickstart (Windows PowerShell)

Follow these steps to run AutoTrader in Lightweight Local mode (no Docker, SQLite-backed) on Windows.

## Prerequisites
- Windows PowerShell 5.1 or PowerShell 7+
- Python 3.11+ (3.13 tested)
- A virtual environment created and activated (e.g., .venv-2)

## One-time setup
1. From the repo root, ensure your venv is active:
   ```powershell
   & .\.venv-2\Scripts\Activate.ps1
   ```
2. Copy lightweight env settings (or ensure overrides exist):
   - We appended overrides to `Autotrader/.env` so it runs in lightweight mode.
3. Initialize local SQLite databases (optional):
   ```powershell
   python scripts\db\init_dev_databases.py
   ```
4. Install minimal runtime deps (if not already):
   ```powershell
   pip install -U uvicorn fastapi numpy pandas httpx structlog python-json-logger pydantic slowapi pytest pytest-cov
   ```

## Start the API
Option A — use the helper script:
```powershell
scripts\windows\run_lightweight.ps1
```

Option B — run manually from repo root:
```powershell
Set-Location Autotrader
python -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000
```

## Verify health
```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -Method GET | ConvertTo-Json -Compress
```
Expected:
```json
{"status":"healthy","timestamp":"<iso8601>"}
```

## Run smoke tests (optional)
```powershell
pytest -q Autotrader\tests\test_smoke.py
```

## Notes
- The `Autotrader/.env` now contains a lightweight overrides block appended at the bottom. Those values take precedence and ensure SQLite + file-based MLflow are used, with heavy services disabled.
- Do not commit `.env`.
- If you switch back to Docker, remove or comment the overrides block and follow `DOCKER_LIGHTWEIGHT_GUIDE.md` for Compose profiles.

## Token Scanning Workflow

The API provides endpoints to trigger on-demand token analysis using free/public data sources (no API keys required).

### Trigger a scan
```powershell
$json = @'
{
  "symbol": "UNI",
  "coingecko_id": "uniswap",
  "contract_address": "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
  "narratives": ["DeFi", "DEX"],
  "unlocks": []
}
'@

Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/scan/run' -Method POST -ContentType 'application/json' -Body $json | ConvertTo-Json -Depth 5
```

Expected response:
```json
{
  "token": "UNI",
  "gem_score": 26.3,
  "confidence": 100.0,
  "flagged": false,
  "liquidity_ok": true,
  "created_at": "20251028T225054Z",
  "artifact_markdown_path": "artifacts\\scans\\UNI\\UNI_20251028T225054Z.md",
  "artifact_html_path": "artifacts\\scans\\UNI\\UNI_20251028T225054Z.html",
  "debug": {...}
}
```

### List recent scans
```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/scan/recent?limit=10' -Method GET | ConvertTo-Json -Depth 3
```

Returns a list of recent scans sorted by timestamp (newest first), with metadata and artifact paths.

### View scan artifact in browser
Open the HTML report directly:
```powershell
Start-Process "http://127.0.0.1:8000/api/scan/view/UNI/UNI_20251028T225054Z.html"
```

Or retrieve it programmatically:
```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/scan/view/UNI/UNI_20251028T225054Z.html' -Method GET
```

### Artifacts
Scan results are saved to:
- Markdown report: `artifacts/scans/{SYMBOL}/{SYMBOL}_{timestamp}.md`
- HTML report: `artifacts/scans/{SYMBOL}/{SYMBOL}_{timestamp}.html`

Both contain the full analysis including gem score, confidence, safety evaluation, feature extraction, and narrative alignment.

