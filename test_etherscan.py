"""Test Etherscan API directly"""
import requests

API_KEY = "9JPUSR4TSBYKYBGHMZU2PG93SW4J2VAA4C"
LINK_CONTRACT = "0x514910771AF9Ca656af840dff83E8264EcF986CA"

url = "https://api.etherscan.io/api"
params = {
    "module": "contract",
    "action": "getsourcecode",
    "address": LINK_CONTRACT,
    "apikey": API_KEY,
}

print(f"Testing Etherscan API...")
print(f"URL: {url}")
print(f"Contract: {LINK_CONTRACT}")
print(f"API Key: {API_KEY[:10]}...")

response = requests.get(url, params=params)
print(f"\nStatus Code: {response.status_code}")
print(f"\nResponse JSON:")
import json
print(json.dumps(response.json(), indent=2))
