"""Direct Questrade API test without the questrade-api wrapper."""

import requests
import json

def test_questrade_direct():
    """Test Questrade API directly to diagnose authentication issues."""
    
    # Your refresh token
    refresh_token = "WRg3COlL51C3AYfu-DSpfhMjEMFGAm0G0vnguRAhWe7ztClm4hnpohBPCC6Y6IzBV0"
    
    print("=" * 70)
    print(" DIRECT QUESTRADE API TEST")
    print("=" * 70)
    print()
    
    # Step 1: Exchange refresh token for access token
    print("Step 1: Exchanging refresh token for access token...")
    print()
    
    auth_url = "https://login.questrade.com/oauth2/token"
    params = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    
    try:
        print(f"   POST {auth_url}")
        print(f"   Parameters: grant_type=refresh_token")
        print(f"   Token: {refresh_token[:15]}...{refresh_token[-15:]}")
        print()
        
        response = requests.get(auth_url, params=params)
        
        print(f"   Response Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("   ✅ SUCCESS!")
            print()
            print("   Response:")
            print(f"   - Access Token: {data.get('access_token', '')[:20]}...")
            print(f"   - Token Type: {data.get('token_type', '')}")
            print(f"   - Expires In: {data.get('expires_in', '')} seconds")
            print(f"   - Refresh Token: {data.get('refresh_token', '')[:20]}...")
            print(f"   - API Server: {data.get('api_server', '')}")
            print()
            
            # Save new refresh token
            new_refresh = data.get('refresh_token', '')
            if new_refresh and new_refresh != refresh_token:
                print("   📝 NEW REFRESH TOKEN RECEIVED!")
                print(f"   {new_refresh}")
                print()
                print("   ⚠️  IMPORTANT: Update this in broker_credentials.yaml")
                print()
            
            # Test API call with access token
            print("Step 2: Testing API call (fetching time)...")
            api_server = data.get('api_server', '')
            access_token = data.get('access_token', '')
            
            if api_server and access_token:
                time_url = f"{api_server}v1/time"
                headers = {"Authorization": f"Bearer {access_token}"}
                
                time_response = requests.get(time_url, headers=headers)
                print(f"   Response Status: {time_response.status_code}")
                
                if time_response.status_code == 200:
                    time_data = time_response.json()
                    print("   ✅ API Call Successful!")
                    print(f"   Server Time: {time_data.get('time', '')}")
                    print()
                    print("=" * 70)
                    print(" 🎉 CONNECTION SUCCESSFUL!")
                    print("=" * 70)
                    print()
                    print("Your Questrade API access is working perfectly!")
                    print("The questrade-api library might have issues.")
                    print("I'll create a custom implementation for you.")
                    return True
                else:
                    print(f"   ❌ API call failed: {time_response.text}")
            
        elif response.status_code == 400:
            print("   ❌ BAD REQUEST (400)")
            print(f"   Response: {response.text}")
            print()
            print("   Possible causes:")
            print("   - Token format is incorrect")
            print("   - Token has expired")
            print("   - Token has already been used (single-use issue)")
            
        elif response.status_code == 401:
            print("   ❌ UNAUTHORIZED (401)")
            print(f"   Response: {response.text}")
            print()
            print("   The token is invalid or has expired.")
            print("   Generate a fresh token from Questrade.")
            
        elif response.status_code == 403:
            print("   ❌ FORBIDDEN (403)")
            print(f"   Response: {response.text}")
            print()
            print("   Possible causes:")
            print("   - API access not enabled in your Questrade account")
            print("   - Token is for paper trading but using live endpoint (or vice versa)")
            print("   - Account doesn't have API permissions")
            print()
            print("   🔧 SOLUTIONS:")
            print("   1. Log into Questrade web platform")
            print("   2. Go to: My Account > Account Management")
            print("   3. Enable 'API Access' if not already enabled")
            print("   4. Generate a NEW token")
            print("   5. Make sure you're using the correct account type")
            
        else:
            print(f"   ❌ UNEXPECTED ERROR ({response.status_code})")
            print(f"   Response: {response.text}")
        
        print()
        return False
        
    except requests.exceptions.RequestException as e:
        print(f"   ❌ NETWORK ERROR")
        print(f"   {e}")
        print()
        print("   Check your internet connection.")
        return False
    
    except Exception as e:
        print(f"   ❌ UNEXPECTED ERROR")
        print(f"   {e}")
        return False

if __name__ == "__main__":
    import sys
    success = test_questrade_direct()
    sys.exit(0 if success else 1)
