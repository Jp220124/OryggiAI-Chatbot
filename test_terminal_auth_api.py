"""Test terminal authentication APIs to understand the exact format"""
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

async def test_get_terminal_authentication_list():
    """Get existing terminal authentication list for employee"""
    print(f"\n{'='*60}")
    print("Testing GetTerminalAuthenticationListByEcode")
    print(f"{'='*60}\n")

    ecode = 1014  # NEWTEST001

    async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
        url = f"{BASE_URL}/GetTerminalAuthenticationListByEcode"
        params = {
            "Ecode": ecode,
            "ClientVersion": "24.07.2025"
        }
        print(f"Calling: GET {url}")
        print(f"Params: {params}")

        response = await client.get(url, params=params, headers=HEADERS)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:2000]}")

        if response.status_code == 200:
            data = response.json()
            print(f"\nFound {len(data) if isinstance(data, list) else 'N/A'} authentication records")
            if isinstance(data, list) and len(data) > 0:
                print(f"\nFirst record structure:")
                for key, value in data[0].items():
                    print(f"  {key}: {value}")
        return response.json() if response.status_code == 200 else None


async def test_get_card_details(ecode=1014):
    """Get card details for employee"""
    print(f"\n{'='*60}")
    print(f"Testing getCardDetailsByEcode for Ecode={ecode}")
    print(f"{'='*60}\n")

    async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
        url = f"{BASE_URL}/getCardDetailsByEcode"
        params = {
            "Ecode": ecode,
            "ClientVersion": "24.07.2025"
        }
        print(f"Calling: GET {url}")
        print(f"Params: {params}")

        response = await client.get(url, params=params, headers=HEADERS)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")

        return response.json() if response.status_code == 200 else None


async def test_add_authentication_terminal():
    """Test AddAuthentication_Terminal API with correct format"""
    print(f"\n{'='*60}")
    print("Testing AddAuthentication_Terminal")
    print(f"{'='*60}\n")

    # Use a different employee without terminal access
    ecode = 1016  # TERMTEST2191

    payload = {
        "ecode": ecode,
        "terminalID": "1",
        "authenticationID": 3,  # Card/Finger
        "scheduleID": 63,  # All Access
        "expiry_date": "2030-12-31 00:00:00",
        "start_date": "2025-11-27 00:00:00",
        "group01": 1,
        "bypassTZLevel": 1,
        "isAntipassBack": 0,
        "OfflinePriority": 0,
        "UserType": 0,
        "iSDeleted": False
    }

    print(f"Payload: {payload}")

    async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
        url = f"{BASE_URL}/AddAuthentication_Terminal"
        params = {
            "IPAddress": "localhost",
            "OperatorEcode": 1,
            "ClientVersion": "24.07.2025"
        }
        print(f"\nCalling: POST {url}")
        print(f"Query Params: {params}")

        response = await client.post(url, params=params, json=payload, headers=HEADERS)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")

        return response.json() if response.status_code == 200 else None


async def test_get_employee_details():
    """Get employee details including card"""
    print(f"\n{'='*60}")
    print("Testing Get_Employee_Details_By_CorpEmpCode")
    print(f"{'='*60}\n")

    corp_emp_code = "NEWTEST001"

    async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
        url = f"{BASE_URL}/Get_Employee_Details_By_CorpEmpCode"
        params = {
            "CorpEmpCode": corp_emp_code,
            "ClientVersion": "24.07.2025"
        }
        print(f"Calling: GET {url}")
        print(f"Params: {params}")

        response = await client.get(url, params=params, headers=HEADERS)
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            # Print key fields
            if isinstance(data, list) and len(data) > 0:
                emp = data[0]
                print(f"\nEmployee Details:")
                print(f"  Ecode: {emp.get('Ecode')}")
                print(f"  CorpEmpCode: {emp.get('CorpEmpCode')}")
                print(f"  EmpName: {emp.get('EmpName')}")
                print(f"  PresentCardNo: {emp.get('PresentCardNo')}")

        return response.json() if response.status_code == 200 else None


async def test_get_terminals():
    """Get all terminals"""
    print(f"\n{'='*60}")
    print("Testing GetAllTerminal")
    print(f"{'='*60}\n")

    async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
        url = f"{BASE_URL}/GetAllTerminal"
        params = {
            "OperatorEcode": 1,
            "hardWareTypeID": 0,
            "ClientVersion": "24.07.2025"
        }
        print(f"Calling: GET {url}")

        response = await client.get(url, params=params, headers=HEADERS)
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            terminals = response.json()
            print(f"\nFound {len(terminals)} terminals:")
            for t in terminals:
                print(f"  - ID: {t.get('TerminalID')}, Name: {t.get('TerminalName')}, IP: {t.get('IPAddress')}")

        return response.json() if response.status_code == 200 else None


async def main():
    """Run all tests"""
    import warnings
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # 1. Get terminals
    await test_get_terminals()

    # 2. Get employee details
    await test_get_employee_details()

    # 3. Get card details for NEWTEST001 (works)
    await test_get_card_details(1014)

    # 3b. Get card details for TERMTEST2191 (failing employee)
    await test_get_card_details(1016)

    # 4. Get existing terminal authentication
    await test_get_terminal_authentication_list()

    # 5. Try adding terminal authentication
    await test_add_authentication_terminal()

    print(f"\n{'='*60}")
    print("Test Complete")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
