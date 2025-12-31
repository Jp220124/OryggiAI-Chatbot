import pyodbc
import httpx
import json

conn_str = (
    'DRIVER={ODBC Driver 17 for SQL Server};'
    'SERVER=DESKTOP-UOD2VBS\\MSSQLSERVER2022;'
    'DATABASE=Oryggi;'
    'Trusted_Connection=yes;'
)

base_url = 'https://localhost/OryggiWebServceCoreApi/OryggiWebApi'
headers = {'APIKey': 'uw0RyC0v+aBV6nCWKM0M0Q=='}

conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

print("=== Understanding Terminal Sync Requirements ===\n")

# Check full MachineMaster data
print("1. MachineMaster Data:")
cursor.execute("""
    SELECT MachineID, TerminalID, IPAddress, DeviceType, Connection_Status,
           ServerSync, UserCount, UserCapacity
    FROM MachineMaster WHERE TerminalID > 0
""")
rows = cursor.fetchall()
cols = [d[0] for d in cursor.description]
for row in rows:
    print(f"   {dict(zip(cols, row))}")

conn.close()

# Check API endpoints that might work
print("\n2. Testing Different API Approaches:")
with httpx.Client(verify=False, timeout=60) as client:
    # Check GetTerminalList with different formats
    endpoints_to_try = [
        ('GetTerminalList', {}),
        ('GetMachineList', {}),
        ('GetTerminalDetails', {'TerminalID': 1}),
        ('GetMachineDetails', {'MachineID': 1}),
        ('GetTerminalById', {'TerminalID': 1}),
        ('GetTerminal', {'TerminalID': 1}),
    ]

    for endpoint, params in endpoints_to_try:
        params['ClientVersion'] = '24.07.2025'
        r = client.get(f'{base_url}/{endpoint}', params=params, headers=headers)
        if r.status_code == 200:
            try:
                data = r.json()
                print(f"   {endpoint}: {r.status_code} - {json.dumps(data)[:150]}...")
            except:
                print(f"   {endpoint}: {r.status_code} - {r.text[:150]}")
        else:
            print(f"   {endpoint}: {r.status_code}")

    # The key might be SyncTerminal endpoint that pushes data directly
    print("\n3. Checking Sync Endpoints:")
    sync_endpoints = [
        ('SyncTerminalData', {'TerminalID': 1}),
        ('PushDataToTerminal', {'TerminalID': 1, 'Ecode': 15}),
        ('SyncUserToTerminal', {'TerminalID': 1, 'Ecode': 15}),
        ('SyncEmployeeToTerminal', {'TerminalID': 1, 'Ecode': 15}),
        ('RefreshTerminal', {'TerminalID': 1}),
    ]

    for endpoint, params in sync_endpoints:
        params['ClientVersion'] = '24.07.2025'
        r = client.get(f'{base_url}/{endpoint}', params=params, headers=headers)
        if r.status_code != 404:
            print(f"   {endpoint}: {r.status_code} - {r.text[:100]}")

    # Try using the TCP command approach to manually push user
    print("\n4. TCP Commands for User Sync:")

    # Get the controller IP from database
    print("   Sending EATU (Update single user) command...")
    r = client.get(f'{base_url}/SendTCPCommand',
                   params={
                       'Command': 'EATU,15',  # EATU = Update user with Ecode 15
                       'host': '192.168.1.88',
                       'Port': 13000,
                       'LogDetail': 'Update Ecode 15',
                       'ClientVersion': '24.07.2025'
                   },
                   headers=headers)
    print(f"   EATU,15: {r.status_code} - {r.text}")

    # Try EAAD (Add user)
    r = client.get(f'{base_url}/SendTCPCommand',
                   params={
                       'Command': 'EAAD,15',  # EAAD = Add user with Ecode 15
                       'host': '192.168.1.88',
                       'Port': 13000,
                       'LogDetail': 'Add Ecode 15',
                       'ClientVersion': '24.07.2025'
                   },
                   headers=headers)
    print(f"   EAAD,15: {r.status_code} - {r.text}")

    # Try direct communication with the V-22 device
    print("\n5. Direct Device Communication:")
    # Try to ping the device
    r = client.get(f'{base_url}/CheckTerminalConnection',
                   params={'IPAddress': '192.168.1.201', 'ClientVersion': '24.07.2025'},
                   headers=headers)
    print(f"   CheckTerminalConnection: {r.status_code} - {r.text[:100] if r.text else 'empty'}")

    # GetDeviceStatus
    r = client.get(f'{base_url}/GetDeviceStatus',
                   params={'IPAddress': '192.168.1.201', 'ClientVersion': '24.07.2025'},
                   headers=headers)
    print(f"   GetDeviceStatus: {r.status_code} - {r.text[:100] if r.text else 'empty'}")
