"""Debug Questrade token and connection issues."""

import sys
from pathlib import Path
import yaml

def debug_questrade():
    """Debug Questrade configuration and connection."""
    print("=" * 70)
    print(" QUESTRADE DEBUGGING TOOL")
    print("=" * 70)
    print()
    
    # Step 1: Check credentials file
    print("Step 1: Checking credentials file...")
    creds_path = Path("configs/broker_credentials.yaml")
    
    if not creds_path.exists():
        print("❌ ERROR: Credentials file not found!")
        print(f"   Expected: {creds_path.absolute()}")
        return False
    
    print(f"✅ Found: {creds_path.absolute()}")
    print()
    
    # Step 2: Load and validate YAML
    print("Step 2: Loading credentials...")
    try:
        with open(creds_path) as f:
            creds = yaml.safe_load(f)
        print("✅ YAML parsed successfully")
    except Exception as e:
        print(f"❌ ERROR: Failed to parse YAML: {e}")
        return False
    print()
    
    # Step 3: Check Questrade section
    print("Step 3: Checking Questrade configuration...")
    if "questrade" not in creds:
        print("❌ ERROR: 'questrade' section not found in credentials")
        print(f"   Available sections: {list(creds.keys())}")
        return False
    
    qt_config = creds["questrade"]
    print("✅ Questrade section found")
    print()
    
    # Step 4: Validate token
    print("Step 4: Validating refresh token...")
    token = qt_config.get("refresh_token", "")
    
    if not token:
        print("❌ ERROR: refresh_token is empty!")
        return False
    
    print(f"✅ Token found")
    print(f"   Length: {len(token)} characters")
    print(f"   First 10 chars: {token[:10]}...")
    print(f"   Last 10 chars: ...{token[-10:]}")
    
    # Check for common issues
    issues = []
    if " " in token:
        issues.append("Token contains spaces (should be removed)")
    if "\n" in token:
        issues.append("Token contains newlines (should be removed)")
    if token.startswith('"') or token.endswith('"'):
        issues.append("Token has extra quotes (YAML handles this)")
    
    if issues:
        print("⚠️  WARNING: Potential token issues detected:")
        for issue in issues:
            print(f"   - {issue}")
    else:
        print("✅ Token format looks good")
    print()
    
    # Step 5: Test questrade-api library
    print("Step 5: Testing questrade-api library...")
    try:
        from questrade_api import Questrade
        print("✅ questrade-api library imported successfully")
    except ImportError as e:
        print(f"❌ ERROR: Failed to import questrade-api: {e}")
        print("   Install with: pip install questrade-api")
        return False
    print()
    
    # Step 6: Attempt connection
    print("Step 6: Testing Questrade API connection...")
    print("(This will attempt to authenticate with your token)")
    print()
    
    try:
        # Create Questrade instance
        print("   Creating Questrade instance...")
        qt = Questrade(refresh_token=token.strip())
        
        print("   ✅ Instance created")
        print()
        
        # Try to get accounts
        print("   Fetching account list...")
        accounts = qt.accounts
        
        if accounts and "accounts" in accounts:
            print(f"   ✅ SUCCESS! Found {len(accounts['accounts'])} account(s):")
            for acc in accounts["accounts"]:
                print(f"      - Account #{acc['number']}")
                print(f"        Type: {acc['type']}")
                print(f"        Status: {acc['status']}")
            print()
            
            # Show the new refresh token
            if hasattr(qt, 'refresh_token') and qt.refresh_token != token:
                print("   📝 NEW REFRESH TOKEN RECEIVED:")
                print(f"      {qt.refresh_token}")
                print()
                print("   ⚠️  IMPORTANT: Save this new token to broker_credentials.yaml!")
                print()
            
            return True
        else:
            print("   ⚠️  WARNING: No accounts returned")
            print(f"   Response: {accounts}")
            return False
            
    except Exception as e:
        print(f"   ❌ CONNECTION FAILED")
        print(f"   Error Type: {type(e).__name__}")
        print(f"   Error Message: {e}")
        print()
        
        # Provide specific guidance
        error_msg = str(e).lower()
        
        if "403" in error_msg or "forbidden" in error_msg:
            print("   📋 DIAGNOSIS: 403 Forbidden Error")
            print("   This typically means:")
            print("   1. The refresh token is invalid or expired")
            print("   2. API access is not enabled in your Questrade account")
            print("   3. The token was copied incorrectly")
            print()
            print("   🔧 SOLUTIONS:")
            print("   1. Generate a NEW refresh token:")
            print("      - Log into Questrade")
            print("      - Go to Account Management > Manage API Access")
            print("      - Create a new token (BounceHunter Agent)")
            print("      - Copy the ENTIRE token carefully")
            print("   2. Ensure API access is enabled in your account")
            print("   3. Check token has no extra spaces or line breaks")
            
        elif "401" in error_msg or "unauthorized" in error_msg:
            print("   📋 DIAGNOSIS: 401 Unauthorized")
            print("   The token format is incorrect or has expired")
            print("   Generate a fresh token from Questrade")
            
        elif "timeout" in error_msg or "connection" in error_msg:
            print("   📋 DIAGNOSIS: Network Issue")
            print("   Check your internet connection")
            print("   Try accessing https://www.questrade.com in browser")
            
        print()
        return False
    
    print("=" * 70)

if __name__ == "__main__":
    print()
    success = debug_questrade()
    print()
    
    if success:
        print("🎉 All checks passed! Your Questrade integration is ready.")
        print()
        print("Next steps:")
        print("  • Run: python test_questrade.py")
        print("  • Or start trading: python src/bouncehunter/agentic_cli.py --broker questrade")
    else:
        print("❌ Setup incomplete. Please fix the issues above.")
        print()
        print("Need help? Check:")
        print("  • QUESTRADE_SETUP.md")
        print("  • docs/CANADIAN_BROKERS.md")
    
    print()
    sys.exit(0 if success else 1)
