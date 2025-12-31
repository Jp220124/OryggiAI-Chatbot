import httpx
import json

base_url = 'https://localhost/OryggiWebServceCoreApi/OryggiWebApi'
headers = {'APIKey': 'uw0RyC0v+aBV6nCWKM0M0Q=='}

with httpx.Client(verify=False, timeout=30) as client:
    # Check face templates for both users
    print("=== Face Templates for Ecode 14 ===")
    r = client.get(f'{base_url}/GetFingerListByTemplate',
                   params={'Ecode': 14, 'TemplateType': 'FACE', 'ClientVersion': '24.07.2025'},
                   headers=headers)
    templates14 = r.json() if r.status_code == 200 else []
    print(f"  Count: {len(templates14) if isinstance(templates14, list) else 0}")
    if templates14 and isinstance(templates14, list) and len(templates14) > 0:
        print(f"  First template keys: {list(templates14[0].keys()) if templates14[0] else 'N/A'}")

    print("\n=== Face Templates for Ecode 15 ===")
    r = client.get(f'{base_url}/GetFingerListByTemplate',
                   params={'Ecode': 15, 'TemplateType': 'FACE', 'ClientVersion': '24.07.2025'},
                   headers=headers)
    templates15 = r.json() if r.status_code == 200 else []
    print(f"  Count: {len(templates15) if isinstance(templates15, list) else 0}")
    if templates15 and isinstance(templates15, list) and len(templates15) > 0:
        print(f"  First template keys: {list(templates15[0].keys()) if templates15[0] else 'N/A'}")

    # Try different sync commands
    print("\n=== Trying Different Sync Commands ===")

    # Try SyncEmployeeToTerminal if it exists
    print("\n1. Trying SyncEmployeeToTerminal...")
    r = client.get(f'{base_url}/SyncEmployeeToTerminal',
                   params={'Ecode': 15, 'TerminalID': 1, 'ClientVersion': '24.07.2025'},
                   headers=headers)
    print(f"   Status: {r.status_code}, Response: {r.text[:200]}")

    # Try pushing with specific employee sync
    print("\n2. Trying EATU command (push single user)...")
    r = client.get(f'{base_url}/SendTCPCommand',
                   params={'Command': 'EATU,15', 'host': '192.168.1.88', 'Port': 13000,
                          'LogDetail': 'Push Ecode 15'},
                   headers=headers)
    print(f"   Status: {r.status_code}, Response: {r.text}")

    # Try EA command variations
    print("\n3. Trying EAAU command (add user)...")
    r = client.get(f'{base_url}/SendTCPCommand',
                   params={'Command': 'EAAU,15', 'host': '192.168.1.88', 'Port': 13000,
                          'LogDetail': 'Add user 15'},
                   headers=headers)
    print(f"   Status: {r.status_code}, Response: {r.text}")

    # List available APIs
    print("\n=== Checking Sync-related APIs ===")
    sync_apis = ['SyncTerminal', 'PushToTerminal', 'SyncEmployee', 'AddUserToTerminal',
                 'SyncUserToDevice', 'PushEmployee']
    for api in sync_apis:
        r = client.get(f'{base_url}/{api}',
                       params={'Ecode': 15, 'TerminalID': 1, 'ClientVersion': '24.07.2025'},
                       headers=headers)
        if r.status_code != 404:
            print(f"  {api}: {r.status_code} - {r.text[:100]}")
