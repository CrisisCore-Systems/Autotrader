"""Detailed Questrade token diagnostic following official recommendations."""

import sys

TOKEN = "hv41CCrfeUhEUixeAH6l8ez-AZ0T3Yra0"

print("=" * 70)
print(" QUESTRADE TOKEN DIAGNOSTIC (Detailed)")
print("=" * 70)
print()
print(f"Token: {TOKEN[:10]}...{TOKEN[-10:]} ({len(TOKEN)} chars)")
print()

# Test both endpoints
endpoints = [
    ("Production", "https://login.questrade.com"),
    ("Practice", "https://practicelogin.questrade.com"),
]

for name, base in endpoints:
    print(f"Testing {name} endpoint...")
    print(f"  Base: {base}")
    
    # Use PowerShell Invoke-RestMethod
    ps_script = f"""
$TOKEN = '{TOKEN}'
$uri = "{base}/oauth2/token?grant_type=refresh_token&refresh_token=" + [uri]::EscapeDataString($TOKEN)
try {{
    $resp = Invoke-RestMethod -Method GET -Uri $uri -ErrorAction Stop
    Write-Output "SUCCESS"
    $resp | ConvertTo-Json -Compress
}} catch {{
    Write-Output "ERROR"
    Write-Output ("STATUS: " + $_.Exception.Response.StatusCode.value__)
    $sr = New-Object IO.StreamReader($_.Exception.Response.GetResponseStream())
    Write-Output ("BODY: " + $sr.ReadToEnd())
}}
"""
    
    import subprocess
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_script],
        capture_output=True,
        text=True
    )
    
    output = result.stdout.strip()
    
    if "SUCCESS" in output:
        print(f"  ✅ {name} endpoint WORKS!")
        print(f"  Response: {output.replace('SUCCESS', '').strip()}")
        print()
    else:
        print(f"  ❌ {name} endpoint failed")
        for line in output.split('\n'):
            if line.strip():
                print(f"     {line}")
        print()

print("=" * 70)
print(" RECOMMENDATIONS")
print("=" * 70)
print()
print("If BOTH failed with 500 or invalid_grant:")
print("  1. In Questrade App Hub, ensure Callback URL is set:")
print("     https://localhost:8080/redirect")
print("  2. Click SAVE on the app")
print("  3. Generate NEW token (+ New device → Copy Token)")
print("  4. Use the fresh token")
print()
print("If token is only 33 chars:")
print("  - Questrade tokens should be 40-70 characters")
print("  - You may have copied only part of it")
print("  - Try manually selecting the entire token before copying")
print()
print("Security Note:")
print("  ⚠️  Revoke this token after testing (shared in chat)")
print("  ⚠️  Generate fresh token from Questrade portal")
print()
