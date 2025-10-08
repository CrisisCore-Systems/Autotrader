"""
Test Etherscan API V2 endpoints
"""
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

def test_etherscan_v2():
    api_key = os.getenv("ETHERSCAN_API_KEY")
    
    # Test contract addresses
    test_contracts = {
        "LINK": "0x514910771AF9Ca656af840dff83E8264EcF986CA",
        "UNI": "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
    }
    
    # V1 endpoint (deprecated)
    v1_base = "https://api.etherscan.io/api"
    
    # V2 endpoint (new)
    v2_base = "https://api.etherscan.io/v2/api"
    
    for name, address in test_contracts.items():
        print(f"\n{'='*70}")
        print(f"Testing {name} ({address})")
        print(f"{'='*70}")
        
        # Test V1 API
        print("\n[V1 API - Deprecated]")
        try:
            with httpx.Client(base_url=v1_base, timeout=15.0) as client:
                response = client.get(
                    "",
                    params={
                        "module": "contract",
                        "action": "getsourcecode",
                        "address": address,
                        "apikey": api_key,
                    },
                )
                data = response.json()
                print(f"Status: {response.status_code}")
                print(f"Response status: {data.get('status')}")
                print(f"Message: {data.get('message')}")
                print(f"Full response: {data}")
        except Exception as e:
            print(f"Error: {e}")
        
        # Test V2 API
        print("\n[V2 API - Current]")
        try:
            with httpx.Client(base_url=v2_base, timeout=15.0) as client:
                # Try both with and without API key
                for use_key in [True, False]:
                    key_label = "with key" if use_key else "without key"
                    print(f"\n  Attempt {key_label}:")
                    
                    params = {
                        "chainid": "1",  # Ethereum mainnet
                        "module": "contract",
                        "action": "getsourcecode",
                        "address": address,
                    }
                    if use_key:
                        params["apikey"] = api_key
                    
                    response = client.get("", params=params)
                    data = response.json()
                    print(f"  Status: {response.status_code}")
                    print(f"  Response status: {data.get('status')}")
                    print(f"  Message: {data.get('message')}")
                    
                    if data.get("status") == "1" and data.get("result"):
                        result = data["result"][0] if isinstance(data["result"], list) else data["result"]
                        print(f"  ✅ Contract Name: {result.get('ContractName', 'N/A')}")
                        print(f"  ✅ Compiler: {result.get('CompilerVersion', 'N/A')}")
                        print(f"  ✅ Verified: {result.get('Proxy', 'N/A')}")
                        break  # Success, no need to try without key
                    else:
                        print(f"  ❌ Result: {data.get('result', 'N/A')[:100]}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    print("Testing Etherscan API V1 vs V2 endpoints")
    test_etherscan_v2()
