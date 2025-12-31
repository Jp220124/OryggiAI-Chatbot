import httpx
import json
import pyodbc

base_url = 'https://localhost/OryggiWebServceCoreApi/OryggiWebApi'
headers = {'APIKey': 'uw0RyC0v+aBV6nCWKM0M0Q=='}

conn_str = (
    'DRIVER={ODBC Driver 17 for SQL Server};'
    'SERVER=DESKTOP-UOD2VBS\\MSSQLSERVER2022;'
    'DATABASE=Oryggi;'
    'Trusted_Connection=yes;'
)

print("=== Investigating Terminal Sync Issue ===\n")

# Check terminal configuration in database
print("1. Terminal Configuration in Database:")
conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

# Find terminal table
cursor.execute("""
    SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_NAME LIKE '%Terminal%Master%' OR TABLE_NAME = 'TerminalMaster'
""")
terminal_tables = cursor.fetchall()
print(f"   Terminal tables found: {[t[0] for t in terminal_tables]}")

# Check TerminalMaster
try:
    cursor.execute("SELECT TOP 5 * FROM TerminalMaster")
    rows = cursor.fetchall()
    if rows:
        cols = [d[0] for d in cursor.description]
        print(f"\n   TerminalMaster columns: {cols}")
        for row in rows:
            terminal_dict = dict(zip(cols, row))
            print(f"   Terminal: ID={terminal_dict.get('TerminalID', terminal_dict.get('ID'))}, "
                  f"Name={terminal_dict.get('TerminalName', terminal_dict.get('Name'))}, "
                  f"IP={terminal_dict.get('IPAddress', terminal_dict.get('IP'))}, "
                  f"Active={terminal_dict.get('Active')}")
except Exception as e:
    print(f"   Error reading TerminalMaster: {e}")

conn.close()

# Check via API
print("\n2. Terminal List via API:")
with httpx.Client(verify=False, timeout=30) as client:
    r = client.get(f'{base_url}/GetTerminalList',
                   params={'ClientVersion': '24.07.2025'},
                   headers=headers)
    if r.status_code == 200:
        terminals = r.json()
        print(f"   Found {len(terminals)} terminals")
        for t in terminals[:5]:
            print(f"   Terminal: ID={t.get('TerminalID')}, Name={t.get('TerminalName')}, "
                  f"IP={t.get('IPAddress')}, Active={t.get('Active')}, "
                  f"DeviceType={t.get('DeviceType')}")
    else:
        print(f"   API returned: {r.status_code}")

    # Check terminal connectivity
    print("\n3. Terminal Connectivity Check:")
    r = client.get(f'{base_url}/GetTerminalStatus',
                   params={'ClientVersion': '24.07.2025'},
                   headers=headers)
    print(f"   GetTerminalStatus: {r.status_code} - {r.text[:200] if r.text else 'empty'}")

    # Try GetAllTerminalOnlineStatus
    r = client.get(f'{base_url}/GetAllTerminalOnlineStatus',
                   params={'ClientVersion': '24.07.2025'},
                   headers=headers)
    print(f"   GetAllTerminalOnlineStatus: {r.status_code} - {r.text[:200] if r.text else 'empty'}")

    # Check what AddAuthentication_Terminal expects
    print("\n4. Testing AddAuthentication_Terminal with Different Formats:")

    # Format 1: Single object with TerminalID array
    auth_data_1 = {
        "Ecode": 15,
        "TerminalID": [1],
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
                    json=auth_data_1,
                    headers=headers)
    print(f"   Format 1 (TerminalID as array): {r.status_code} - {r.text}")

    # Format 2: With TerminalIds string field
    auth_data_2 = {
        "Ecode": 15,
        "TerminalIds": "1",
        "AuthenticationID": 13,
        "ScheduleID": 63,
        "StartDate": "2025-12-17T00:00:00",
        "ExpiryDate": "2030-12-31T00:00:00",
        "Group1": 1
    }
    r = client.post(f'{base_url}/AddAuthentication_Terminal',
                    params={'IPAddress': 'localhost', 'OperatorEcode': 1, 'ClientVersion': '24.07.2025'},
                    json=auth_data_2,
                    headers=headers)
    print(f"   Format 2 (TerminalIds string): {r.status_code} - {r.text}")

    # Format 3: With terminalId (lowercase)
    auth_data_3 = {
        "ecode": 15,
        "terminalId": 1,
        "authenticationId": 13,
        "scheduleId": 63,
        "startDate": "2025-12-17T00:00:00",
        "expiryDate": "2030-12-31T00:00:00",
        "group1": 1
    }
    r = client.post(f'{base_url}/AddAuthentication_Terminal',
                    params={'IPAddress': 'localhost', 'OperatorEcode': 1, 'ClientVersion': '24.07.2025'},
                    json=auth_data_3,
                    headers=headers)
    print(f"   Format 3 (lowercase): {r.status_code} - {r.text}")

    # Check if we need UpdateTerminalAuthentication instead
    print("\n5. Checking Update API:")
    r = client.post(f'{base_url}/UpdateAuthentication_Terminal',
                    params={'IPAddress': 'localhost', 'OperatorEcode': 1, 'ClientVersion': '24.07.2025'},
                    json=auth_data_1,
                    headers=headers)
    print(f"   UpdateAuthentication_Terminal: {r.status_code} - {r.text[:200] if r.text else 'empty'}")

    # Check SyncTerminalAuthentication
    r = client.post(f'{base_url}/SyncTerminalAuthentication',
                    params={'TerminalID': 1, 'ClientVersion': '24.07.2025'},
                    json={'Ecode': 15},
                    headers=headers)
    print(f"   SyncTerminalAuthentication: {r.status_code} - {r.text[:200] if r.text else 'empty'}")
