"""Diagnose Questrade token issues with detailed debugging."""

import os
import requests

def diagnose_token():
    """Try to diagnose what's wrong with the Questrade token."""
    
    token = os.getenv("QTRADE_REFRESH_TOKEN")
    
    print("=" * 70)
    print(" QUESTRADE TOKEN DIAGNOSTICS")
    print("=" * 70)
    print()
    
    if not token:
        print("❌ ERROR: QTRADE_REFRESH_TOKEN not set")
        print()
        print("Set it with:")
        print('  $env:QTRADE_REFRESH_TOKEN = "your_token"')
        return
    
    print(f"✅ Token found: {token[:10]}...{token[-10:]} ({len(token)} chars)")
    print()
    
    # Try both endpoints
    endpoints = [
        ("Production", "https://login.questrade.com/oauth2/token"),
        ("Practice", "https://practicelogin.questrade.com/oauth2/token"),
    ]
    
    for name, base_url in endpoints:
        print(f"Testing {name} endpoint...")
        print(f"  URL: {base_url}")
        
        url = f"{base_url}?grant_type=refresh_token&refresh_token={token}"
        
        try:
            response = requests.get(url, timeout=15)
            
            print(f"  Status: {response.status_code}")
            
            if response.status_code == 200:
                print(f"  ✅ SUCCESS with {name} endpoint!")
                data = response.json()
                print()
                print("  Response:")
                print(f"    Access Token: {data.get('access_token', '')[:20]}...")
                print(f"    Token Type: {data.get('token_type', '')}")
                print(f"    Expires In: {data.get('expires_in', '')} seconds")
                print(f"    API Server: {data.get('api_server', '')}")
                print()
                
                # Try to fetch accounts
                api_server = data.get('api_server', '')
                access_token = data.get('access_token', '')
                
                if api_server and access_token:
                    print("  Testing account access...")
                    headers = {"Authorization": f"Bearer {access_token}"}
                    accounts_url = f"{api_server}v1/accounts"
                    
                    acc_response = requests.get(accounts_url, headers=headers, timeout=15)
                    
                    if acc_response.status_code == 200:
                        accounts = acc_response.json()
                        if 'accounts' in accounts:
                            print(f"  ✅ Found {len(accounts['accounts'])} account(s):")
                            for acc in accounts['accounts']:
                                print(f"     - #{acc['number']} ({acc['type']}) - {acc['status']}")
                    else:
                        print(f"  ⚠️  Account access failed: {acc_response.status_code}")
                
                print()
                print("=" * 70)
                print(f" SOLUTION: Use {name.upper()} endpoint")
                print("=" * 70)
                print()
                
                if name == "Practice":
                    print("Your token is for a PRACTICE (paper) account.")
                    print()
                    print("Update your code to use:")
                    print("  https://practicelogin.questrade.com/oauth2/token")
                else:
                    print("Your token is for a LIVE trading account.")
                    print()
                    print("The current endpoint is correct.")
                
                return True
                
            elif response.status_code == 400:
                print(f"  ❌ 400 Bad Request")
                print(f"  Response: {response.text}")
                
            elif response.status_code == 401:
                print(f"  ❌ 401 Unauthorized")
                print(f"  Response: {response.text}")
                
            elif response.status_code == 403:
                print(f"  ❌ 403 Forbidden")
                print(f"  Response: {response.text}")
                
            elif response.status_code == 500:
                print(f"  ❌ 500 Internal Server Error")
                print(f"  Response: {response.text}")
                
            else:
                print(f"  ❌ Unexpected error: {response.status_code}")
                print(f"  Response: {response.text}")
            
            print()
            
        except requests.exceptions.RequestException as e:
            print(f"  ❌ Network error: {e}")
            print()
    
    print("=" * 70)
    print(" ❌ FAILED WITH BOTH ENDPOINTS")
    print("=" * 70)
    print()
    print("Possible causes:")
    print("  1. Token has expired (check expiry date in popup)")
    print("  2. Token was already used (some are single-use)")
    print("  3. Questrade API is having issues (temporary)")
    print("  4. Account doesn't have API access enabled")
    print()
    print("Solutions:")
    print("  1. Generate a FRESH token from Questrade:")
    print("     https://my.questrade.com > App Hub > Generate new token")
    print("  2. Wait 5-10 minutes and try again (API might be down)")
    print("  3. Contact Questrade support: 1-888-783-7837")
    print("  4. Try paper broker instead: --broker paper")
    print()
    
    return False

if __name__ == "__main__":
    import sys
    success = diagnose_token()
    sys.exit(0 if success else 1)
