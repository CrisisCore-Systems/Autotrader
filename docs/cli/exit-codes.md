# Exit Codes

AutoTrader CLI uses specific exit codes to indicate different failure modes.
This helps with scripting and automation.

## Exit Code Reference

| Code | Name | Description |
|------|------|-------------|
| `0` | `OK` | Success - operation completed successfully |
| `1` | `CONFIG` | Configuration error - invalid config file or settings |
| `2` | `INPUT` | Input error - invalid command-line arguments or data format |
| `10` | `RUNTIME` | Runtime error - execution failure, API error, or strategy error |
| `20` | `TIMEOUT` | Timeout - operation exceeded time limit |
| `21` | `LOCKED` | Lock error - another instance is running or lock acquisition failed |
| `30` | `VALIDATION` | Validation error - output failed schema or format validation |
| `130` | `INTERRUPTED` | Interrupted - user cancelled operation (Ctrl+C) |

## Using Exit Codes in Scripts

### Bash Example

```bash
autotrader-scan --config production.yaml
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "Scan completed successfully"
elif [ $EXIT_CODE -eq 1 ]; then
    echo "Configuration error - check your config file"
elif [ $EXIT_CODE -eq 21 ]; then
    echo "Another scan is running - please wait"
else
    echo "Scan failed with exit code $EXIT_CODE"
fi
```

### PowerShell Example

```powershell
autotrader-scan --config production.yaml
$exitCode = $LASTEXITCODE

switch ($exitCode) {
    0  { Write-Host "Scan completed successfully" }
    1  { Write-Host "Configuration error - check your config file" }
    21 { Write-Host "Another scan is running - please wait" }
    default { Write-Host "Scan failed with exit code $exitCode" }
}
```

## Deprecation Notice

Some exit code names have been deprecated in v2.0.0 and will be removed in v3.0.0:

| Deprecated | New Name | Removal Version |
|------------|----------|----------------|
| `SUCCESS` | `OK` | v3.0.0 |
| `CONFIG_ERROR` | `CONFIG` | v3.0.0 |
| `MISUSE` | `INPUT` | v3.0.0 |
| `RUNTIME_ERROR` | `RUNTIME` | v3.0.0 |
| `LOCK_ERROR` | `LOCKED` | v3.0.0 |
| `SIGINT` | `INTERRUPTED` | v3.0.0 |

Use `--print-deprecation-warnings` to see which deprecated names you're using.