import httpx
import json

base_url = 'https://localhost/OryggiWebServceCoreApi/OryggiWebApi'
headers = {'APIKey': 'uw0RyC0v+aBV6nCWKM0M0Q=='}

with httpx.Client(verify=False, timeout=60) as client:
    # First check face templates
    print("=== Face Template Check ===")
    r = client.get(f'{base_url}/GetFingerListByTemplate',
                   params={'Ecode': 15, 'TemplateType': 'FACE', 'ClientVersion': '24.07.2025'},
                   headers=headers)
    templates = r.json() if r.status_code == 200 else []
    print(f"Ecode 15 has {len(templates) if isinstance(templates, list) else 0} face template(s)")

    # Try AddAuthentication_Terminal with array format (like V2)
    print("\n=== Trying AddAuthentication_Terminal (array format) ===")
    auth_data = [{
        "Ecode": 15,
        "TerminalID": 1,
        "AuthenticationID": 13,
        "ScheduleID": 63,
        "StartDate": "2025-12-17T00:00:00",
        "ExpiryDate": "2030-12-31T00:00:00",
        "Group1": 1,
        "Group2": 0,
        "Group3": 0,
        "Group4": 0,
        "BypassTZLevel": 1,
        "WhiteList": False,
        "VIPlist": False
    }]
    r = client.post(f'{base_url}/AddAuthentication_Terminal',
                    params={'IPAddress': 'localhost', 'OperatorEcode': 1, 'ClientVersion': '24.07.2025'},
                    json=auth_data,
                    headers=headers)
    print(f"Response: {r.status_code} - {r.text}")

    # Try single object format
    print("\n=== Trying AddAuthentication_Terminal (single object) ===")
    auth_data_single = {
        "Ecode": 15,
        "TerminalID": 1,
        "AuthenticationID": 13,
        "ScheduleID": 63,
        "StartDate": "2025-12-17T00:00:00",
        "ExpiryDate": "2030-12-31T00:00:00",
        "Group1": 1,
        "Group2": 0,
        "Group3": 0,
        "Group4": 0,
        "BypassTZLevel": 1,
        "WhiteList": False,
        "VIPlist": False
    }
    r = client.post(f'{base_url}/AddAuthentication_Terminal',
                    params={'IPAddress': 'localhost', 'OperatorEcode': 1, 'ClientVersion': '24.07.2025'},
                    json=auth_data_single,
                    headers=headers)
    print(f"Response: {r.status_code} - {r.text}")

    # Try SyncDataToTerminals API
    print("\n=== Trying SyncDataToTerminals ===")
    r = client.get(f'{base_url}/SyncDataToTerminals',
                   params={'TerminalID': 1, 'ClientVersion': '24.07.2025'},
                   headers=headers)
    print(f"Response: {r.status_code} - {r.text[:200] if r.text else 'empty'}")

    # Try SyncAllDataToTerminal
    print("\n=== Trying SyncAllDataToTerminal ===")
    r = client.get(f'{base_url}/SyncAllDataToTerminal',
                   params={'TerminalID': 1, 'ClientVersion': '24.07.2025'},
                   headers=headers)
    print(f"Response: {r.status_code} - {r.text[:200] if r.text else 'empty'}")

    # Try EATR command with specific terminal
    print("\n=== Sync with EATR,1 ===")
    r = client.get(f'{base_url}/SendTCPCommand',
                   params={'Command': 'EATR,1', 'host': '192.168.1.88', 'Port': 13000,
                          'LogDetail': 'Sync terminal 1'},
                   headers=headers)
    print(f"Response: {r.status_code} - {r.text}")
