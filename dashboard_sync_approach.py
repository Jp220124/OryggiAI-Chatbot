import httpx
import json

base_url = 'https://localhost/OryggiWebServceCoreApi/OryggiWebApi'
headers = {'APIKey': 'uw0RyC0v+aBV6nCWKM0M0Q=='}

with httpx.Client(verify=False, timeout=60) as client:
    # Check terminal details first
    print("=== Terminal Configuration ===")
    r = client.get(f'{base_url}/GetTerminalList',
                   params={'ClientVersion': '24.07.2025'},
                   headers=headers)
    if r.status_code == 200:
        terminals = r.json()
        for t in terminals[:3]:  # Show first 3
            print(f"  Terminal {t.get('TerminalID')}: {t.get('TerminalName')} - IP: {t.get('IPAddress')} - Active: {t.get('Active')}")

    # Check GetTerminalByIP for our device
    print("\n=== V-22 Device Info ===")
    r = client.get(f'{base_url}/GetTerminalByIP',
                   params={'IP': '192.168.1.201', 'ClientVersion': '24.07.2025'},
                   headers=headers)
    print(f"Response: {r.status_code}")
    if r.status_code == 200:
        print(json.dumps(r.json(), indent=2))

    # Check what auth methods exist for this terminal
    print("\n=== Auth Methods for Terminal 1 ===")
    r = client.get(f'{base_url}/GetAuthenticationList',
                   params={'ClientVersion': '24.07.2025'},
                   headers=headers)
    if r.status_code == 200:
        auths = r.json()
        for a in auths[:5]:
            print(f"  ID {a.get('AuthenticationID')}: {a.get('AuthenticationName')}")

    # Try to check if there's a specific endpoint for syncing users to terminal
    print("\n=== Checking PushUserToTerminal ===")
    sync_endpoints = [
        ('PushUserToTerminal', {'Ecode': 15, 'TerminalID': 1}),
        ('SyncEmployeeData', {'Ecode': 15, 'TerminalID': 1}),
        ('UpdateTerminalUser', {'Ecode': 15, 'TerminalID': 1}),
        ('SyncUser', {'Ecode': 15, 'TerminalID': 1}),
    ]
    for endpoint, params in sync_endpoints:
        params['ClientVersion'] = '24.07.2025'
        r = client.get(f'{base_url}/{endpoint}', params=params, headers=headers)
        if r.status_code != 404:
            print(f"  {endpoint}: {r.status_code} - {r.text[:100]}")

    # Let's check Ecode 14's exact auth details to compare
    print("\n=== Ecode 14 Full Auth Details ===")
    r = client.get(f'{base_url}/GetTerminalAuthenticationListByEcode',
                   params={'Ecode': 14, 'ClientVersion': '24.07.2025'},
                   headers=headers)
    if r.status_code == 200:
        data = r.json()
        if data:
            print(json.dumps(data[0], indent=2))

    print("\n=== Ecode 15 Full Auth Details ===")
    r = client.get(f'{base_url}/GetTerminalAuthenticationListByEcode',
                   params={'Ecode': 15, 'ClientVersion': '24.07.2025'},
                   headers=headers)
    if r.status_code == 200:
        data = r.json()
        if data:
            print(json.dumps(data[0], indent=2))
