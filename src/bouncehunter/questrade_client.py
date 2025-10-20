"""Questrade API client with auto-refresh logic."""

import os
import time
from typing import Dict, Optional

import requests


class QuestradeClient:
    """Questrade API client with automatic token refresh.
    
    Usage:
        # Set environment variable
        os.environ['QTRADE_REFRESH_TOKEN'] = 'your_token_here'
        
        # Create client
        client = QuestradeClient()
        
        # Make API calls (auto-refreshes when needed)
        accounts = client.get('v1/accounts')
        balances = client.get(f'v1/accounts/{account_id}/balances')
    """
    
    def __init__(self, refresh_env: str = "QTRADE_REFRESH_TOKEN"):
        """Initialize Questrade client.
        
        Args:
            refresh_env: Environment variable name containing refresh token
            
        Raises:
            RuntimeError: If refresh token environment variable not set
        """
        tok = os.getenv(refresh_env)
        if not tok:
            raise RuntimeError(
                f"{refresh_env} not set. "
                f"Set it with: $env:{refresh_env}='your_token_here'"
            )
        
        self.refresh_token = tok
        self.access_token: Optional[str] = None
        self.api_server: Optional[str] = None
        self.expiry_ts: float = 0
        
        # Do initial refresh to get access token
        self._refresh()
    
    def _refresh(self):
        """Exchange refresh token for access token and API server URL.
        
        Raises:
            RuntimeError: If refresh fails
        """
        url = (
            "https://login.questrade.com/oauth2/token"
            f"?grant_type=refresh_token&refresh_token={self.refresh_token}"
        )
        
        try:
            r = requests.get(url, timeout=15)
            
            if r.status_code != 200:
                raise RuntimeError(
                    f"Questrade refresh failed {r.status_code}: {r.text}\n\n"
                    f"Common causes:\n"
                    f"  - Refresh token expired (check expiry date)\n"
                    f"  - Token already used (single-use in some cases)\n"
                    f"  - API access not enabled\n\n"
                    f"Solution: Generate NEW token from Questrade portal:\n"
                    f"  1. Log into https://my.questrade.com\n"
                    f"  2. Go to: App Hub > BounceHunter Agent\n"
                    f"  3. Click 'Generate new token'\n"
                    f"  4. Update: $env:QTRADE_REFRESH_TOKEN='new_token'"
                )
            
            j = r.json()
            self.access_token = j["access_token"]
            self.api_server = j["api_server"]
            
            # Set expiry 30 seconds before actual expiry (safety buffer)
            expires_in = int(j.get("expires_in", 1800))
            self.expiry_ts = time.time() + expires_in - 30
            
            print(f"✅ Questrade token refreshed (expires in {expires_in}s)")
            print(f"   API Server: {self.api_server}")
            
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Network error during refresh: {e}")
    
    def _hdr(self) -> Dict[str, str]:
        """Get authorization headers, refreshing token if needed.
        
        Returns:
            Dict with Authorization header
        """
        # Refresh if token expired or not yet obtained
        if time.time() > self.expiry_ts or not self.access_token:
            self._refresh()
        
        return {"Authorization": f"Bearer {self.access_token}"}
    
    def get(self, path: str) -> Dict:
        """Make GET request to Questrade API.
        
        Args:
            path: API endpoint path (e.g., 'v1/accounts')
            
        Returns:
            JSON response as dictionary
            
        Raises:
            RuntimeError: If API call fails
        """
        if not self.api_server:
            self._refresh()
        
        url = self.api_server + path.lstrip("/")
        
        try:
            r = requests.get(url, headers=self._hdr(), timeout=15)
            
            if r.status_code != 200:
                raise RuntimeError(
                    f"Questrade API error {r.status_code} for {path}: {r.text}"
                )
            
            return r.json()
            
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Network error calling {path}: {e}")
    
    def post(self, path: str, data: Dict) -> Dict:
        """Make POST request to Questrade API.
        
        Args:
            path: API endpoint path
            data: JSON payload
            
        Returns:
            JSON response as dictionary
            
        Raises:
            RuntimeError: If API call fails
        """
        if not self.api_server:
            self._refresh()
        
        url = self.api_server + path.lstrip("/")
        
        try:
            r = requests.post(url, headers=self._hdr(), json=data, timeout=15)
            
            if r.status_code not in [200, 201]:
                raise RuntimeError(
                    f"Questrade API error {r.status_code} for {path}: {r.text}"
                )
            
            return r.json()
            
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Network error calling {path}: {e}")


# Smoke test
if __name__ == "__main__":
    print("=" * 70)
    print(" QUESTRADE CLIENT SMOKE TEST")
    print("=" * 70)
    print()
    
    try:
        # Create client (reads QTRADE_REFRESH_TOKEN from environment)
        print("1. Initializing Questrade client...")
        client = QuestradeClient()
        print()
        
        # Test: Get accounts
        print("2. Fetching accounts...")
        accounts = client.get("v1/accounts")
        
        if "accounts" in accounts:
            print(f"   ✅ Found {len(accounts['accounts'])} account(s):")
            for acc in accounts["accounts"]:
                print(f"      - Account #{acc['number']}")
                print(f"        Type: {acc['type']}")
                print(f"        Status: {acc['status']}")
            
            # Test: Get first account balances
            if accounts["accounts"]:
                account_id = accounts["accounts"][0]["number"]
                print()
                print(f"3. Fetching balances for account #{account_id}...")
                balances = client.get(f"v1/accounts/{account_id}/balances")
                
                if "perCurrencyBalances" in balances:
                    print("   ✅ Balances:")
                    for bal in balances["perCurrencyBalances"]:
                        currency = bal["currency"]
                        cash = bal.get("cash", 0)
                        equity = bal.get("totalEquity", 0)
                        print(f"      - {currency}: Cash=${cash:,.2f}, Equity=${equity:,.2f}")
        
        print()
        print("=" * 70)
        print(" ✅ ALL TESTS PASSED!")
        print("=" * 70)
        print()
        print("Your Questrade API connection is working perfectly!")
        
    except RuntimeError as e:
        print(f"❌ ERROR: {e}")
        print()
        print("Troubleshooting:")
        print("  1. Check your refresh token is set:")
        print("     $env:QTRADE_REFRESH_TOKEN")
        print("  2. Generate fresh token if expired:")
        print("     https://my.questrade.com > App Hub > Generate new token")
        print("  3. Ensure API access enabled in your account")
    
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {type(e).__name__}: {e}")
