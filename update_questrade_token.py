"""Update Questrade refresh token in credentials file."""

import sys
from pathlib import Path
import yaml

def update_token():
    """Interactively update the Questrade refresh token."""
    print("=" * 70)
    print(" QUESTRADE TOKEN UPDATER")
    print("=" * 70)
    print()
    print("This tool will help you update your Questrade refresh token.")
    print()
    
    # Load current config
    creds_path = Path("configs/broker_credentials.yaml")
    if not creds_path.exists():
        print(f"❌ ERROR: {creds_path} not found!")
        return False
    
    with open(creds_path) as f:
        creds = yaml.safe_load(f)
    
    # Show current token (masked)
    current_token = creds["questrade"]["refresh_token"]
    print(f"Current token: {current_token[:10]}...{current_token[-10:]} ({len(current_token)} chars)")
    print()
    
    # Get new token
    print("Instructions:")
    print("1. Log into Questrade web platform")
    print("2. Go to: Account Management > Manage API Access")
    print("3. Create a new token (name it 'BounceHunter Agent')")
    print("4. Copy the ENTIRE token (should be 50-60 characters)")
    print("5. Paste it below")
    print()
    
    new_token = input("Enter your NEW Questrade refresh token: ").strip()
    
    if not new_token:
        print("❌ No token entered. Cancelled.")
        return False
    
    # Remove any quotes if user pasted them
    new_token = new_token.strip('"').strip("'")
    
    print()
    print(f"New token: {new_token[:10]}...{new_token[-10:]} ({len(new_token)} chars)")
    
    # Confirm
    confirm = input("\nUpdate token? (yes/no): ").strip().lower()
    if confirm not in ["yes", "y"]:
        print("Cancelled.")
        return False
    
    # Update config
    creds["questrade"]["refresh_token"] = new_token
    creds["questrade"]["last_updated"] = "2025-10-17"
    
    # Save
    with open(creds_path, "w") as f:
        yaml.dump(creds, f, default_flow_style=False, sort_keys=False)
    
    print()
    print("✅ Token updated successfully!")
    print()
    print("Next step: Run the debug tool to test the connection")
    print("  python debug_questrade.py")
    print()
    
    return True

if __name__ == "__main__":
    try:
        update_token()
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        sys.exit(1)
