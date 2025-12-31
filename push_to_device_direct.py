import httpx
import time

base_url = 'https://localhost/OryggiWebServceCoreApi/OryggiWebApi'
headers = {'APIKey': 'uw0RyC0v+aBV6nCWKM0M0Q=='}

print("=" * 60)
print("ATTEMPTING DIRECT DEVICE PUSH FOR ECODE 15")
print("=" * 60)

with httpx.Client(verify=False, timeout=120) as client:
    # Try various push/sync endpoints
    print("\n1. Trying different sync approaches...")

    # Approach 1: SyncEmpToTerminal
    endpoints = [
        ('SyncEmpToTerminal', {'Ecode': 15, 'TerminalID': 1}),
        ('SyncEmployeeToDevice', {'Ecode': 15, 'DeviceIP': '192.168.1.201'}),
        ('PushUserToDevice', {'Ecode': 15, 'DeviceIP': '192.168.1.201'}),
        ('AddUserToDevice', {'Ecode': 15, 'DeviceIP': '192.168.1.201'}),
        ('SyncUser', {'Ecode': 15, 'TerminalID': 1}),
    ]

    for endpoint, params in endpoints:
        params['ClientVersion'] = '24.07.2025'
        r = client.get(f'{base_url}/{endpoint}', params=params, headers=headers)
        if r.status_code != 404:
            print(f"   {endpoint}: {r.status_code} - {r.text[:100]}")

    # Approach 2: Try AddAuthentication_TerminalV2 with correct format
    print("\n2. Trying AddAuthentication_TerminalV2...")
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
    r = client.post(f'{base_url}/AddAuthentication_TerminalV2',
                    params={'ClientVersion': '24.07.2025'},
                    json=auth_data,
                    headers=headers)
    print(f"   Response: {r.status_code} - {r.text}")

    # Approach 3: Try different TCP commands to the controller
    print("\n3. Trying TCP commands to controller (192.168.1.88)...")

    commands = [
        ('EAAU,15', 'Add user 15'),
        ('EAUU,15', 'Update user 15'),
        ('EASU,15', 'Sync user 15'),
        ('EASF,15', 'Sync face for user 15'),
        ('EATR,1', 'Sync terminal 1'),
        ('EAUR,1', 'Update all users on terminal 1'),
    ]

    for cmd, desc in commands:
        r = client.get(f'{base_url}/SendTCPCommand',
                       params={
                           'Command': cmd,
                           'host': '192.168.1.88',
                           'Port': 13000,
                           'LogDetail': desc,
                           'ClientVersion': '24.07.2025'
                       },
                       headers=headers)
        print(f"   {cmd}: {r.text}")

    # Approach 4: Try direct communication with V-22 device
    print("\n4. Trying direct V-22 device communication...")

    # SendCommandToDevice
    r = client.get(f'{base_url}/SendCommandToDevice',
                   params={
                       'DeviceIP': '192.168.1.201',
                       'Command': 'SyncUser',
                       'Ecode': 15,
                       'ClientVersion': '24.07.2025'
                   },
                   headers=headers)
    print(f"   SendCommandToDevice: {r.status_code} - {r.text[:100] if r.text else 'empty'}")

    # RefreshDevice
    r = client.get(f'{base_url}/RefreshDevice',
                   params={'DeviceIP': '192.168.1.201', 'ClientVersion': '24.07.2025'},
                   headers=headers)
    print(f"   RefreshDevice: {r.status_code} - {r.text[:100] if r.text else 'empty'}")

    # Approach 5: Re-enroll face to force device update
    print("\n5. Re-enrolling face to force device registration...")
    print("   Please present face to V-22 device NOW...")

    r = client.get(f'{base_url}/EnrollV22',
                   params={
                       'Ecode': 15,
                       'FingerID': 11,
                       'DeviceIP': '192.168.1.201',
                       'OperatorEcode': 1,
                       'ClientVersion': '24.07.2025'
                   },
                   headers=headers)
    print(f"   EnrollV22: {r.text}")

    if 'Success' in r.text:
        # Immediately try AddAuthentication_Terminal after enrollment
        print("\n6. Immediately adding terminal auth after enrollment...")
        auth_single = {
            "Ecode": 15,
            "TerminalID": 1,
            "AuthenticationID": 13,
            "ScheduleID": 63,
            "StartDate": "2025-12-17T00:00:00",
            "ExpiryDate": "2030-12-31T00:00:00",
            "Group1": 1
        }
        r = client.post(f'{base_url}/AddAuthentication_Terminal',
                        params={'IPAddress': 'localhost', 'OperatorEcode': 1, 'ClientVersion': '24.07.2025'},
                        json=auth_single,
                        headers=headers)
        print(f"   AddAuthentication_Terminal: {r.text}")

        # Sync
        r = client.get(f'{base_url}/SendTCPCommand',
                       params={
                           'Command': 'EATR,1',
                           'host': '192.168.1.88',
                           'Port': 13000,
                           'LogDetail': 'Sync after enrollment',
                           'ClientVersion': '24.07.2025'
                       },
                       headers=headers)
        print(f"   EATR,1: {r.text}")

print("\n" + "=" * 60)
print("Now test authentication at the V-22 device")
print("=" * 60)
