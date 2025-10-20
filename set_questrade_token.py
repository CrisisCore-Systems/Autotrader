"""Interactive Questrade token setter."""

import sys
import os

print("=" * 70)
print(" QUESTRADE TOKEN SETUP")
print("=" * 70)
print()
print("Instructions:")
print("1. Look at your Questrade popup window")
print("2. Click 'COPY TOKEN'")
print("3. Paste it below")
print()

token = input("Paste your Questrade refresh token here: ").strip()

if not token:
    print("\n❌ No token entered!")
    sys.exit(1)

# Remove any quotes if pasted
token = token.strip('"').strip("'")

print(f"\n✅ Token received ({len(token)} characters)")
print(f"   First 10: {token[:10]}...")
print(f"   Last 10: ...{token[-10:]}")
print()

# Set environment variable for this session
os.environ['QTRADE_REFRESH_TOKEN'] = token

print("Testing connection...")
print()

# Test it
try:
    sys.path.insert(0, 'src')
    from bouncehunter.questrade_client import QuestradeClient
    
    client = QuestradeClient()
    accounts = client.get('v1/accounts')
    
    print("🎉 SUCCESS! Connection working!")
    print()
    
    if 'accounts' in accounts:
        print(f"Found {len(accounts['accounts'])} account(s):")
        for acc in accounts['accounts']:
            print(f"  - Account #{acc['number']} ({acc['type']})")
    
    print()
    print("=" * 70)
    print(" IMPORTANT: Save this command for future use:")
    print("=" * 70)
    print()
    print(f'$env:QTRADE_REFRESH_TOKEN = "{token}"')
    print()
    print("Add to your PowerShell profile or .env file!")
    
except Exception as e:
    print(f"❌ Connection failed: {e}")
    print()
    print("The token might be invalid. Try generating a new one.")
    sys.exit(1)
