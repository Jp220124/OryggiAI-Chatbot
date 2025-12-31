"""Test API lookup to understand why it returns -1"""
import asyncio
import sys
sys.path.insert(0, 'D:/OryggiAI_Service/Advance_Chatbot')

import httpx

BASE_URL = "https://localhost/OryggiWebServceCoreApi/OryggiWebApi"
API_KEY = "uw0RyC0v+aBV6nCWKM0M0Q=="

HEADERS = {
    "apiKey": API_KEY,
    "Content-Type": "application/json"
}

async def test_api_lookup():
    """Test API lookup"""
    print(f"\n{'='*60}")
    print("Testing getEcodeByCorpEmpCode API")
    print(f"{'='*60}\n")

    # Disable SSL warnings
    import warnings
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    test_cases = [
        "TERMTEST2191",  # Exact match
        "10000001",      # First employee from dashboard (HIMMAT SINGH)
        "11002271",      # Second employee (Aviral)
        "termtest2191",  # lowercase
        "1016",          # Ecode as string
        "NEWTEST001",    # Another test employee
    ]

    async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
        for corp_code in test_cases:
            url = f"{BASE_URL}/getEcodeByCorpEmpCode"
            params = {"CorpEmpCode": corp_code, "ClientVersion": "24.07.2025"}

            print(f"Testing: {corp_code}")
            response = await client.get(url, params=params, headers=HEADERS)
            print(f"  Status: {response.status_code}")
            print(f"  Response: {response.text}")
            print()

if __name__ == "__main__":
    asyncio.run(test_api_lookup())
