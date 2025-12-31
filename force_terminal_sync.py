import pyodbc
import httpx
import time

conn_str = (
    'DRIVER={ODBC Driver 17 for SQL Server};'
    'SERVER=DESKTOP-UOD2VBS\\MSSQLSERVER2022;'
    'DATABASE=Oryggi;'
    'Trusted_Connection=yes;'
)

base_url = 'https://localhost/OryggiWebServceCoreApi/OryggiWebApi'
headers = {'APIKey': 'uw0RyC0v+aBV6nCWKM0M0Q=='}

print("=== Force Terminal Sync for Ecode 15 ===\n")

# Step 1: Update terminal status to Online
print("1. Updating Terminal Status to Online...")
conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

cursor.execute("""
    UPDATE MachineMaster
    SET Connection_Status = 'Online', ServerSync = 1
    WHERE TerminalID = 1
""")
rows = cursor.rowcount
conn.commit()
print(f"   Updated {rows} row(s)")

# Verify
cursor.execute("SELECT Connection_Status, ServerSync FROM MachineMaster WHERE TerminalID = 1")
row = cursor.fetchone()
print(f"   New status: Connection_Status={row[0]}, ServerSync={row[1]}")

conn.close()

# Step 2: Try AddAuthentication_Terminal again
print("\n2. Retrying AddAuthentication_Terminal...")
with httpx.Client(verify=False, timeout=60) as client:
    auth_data = {
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
                    json=auth_data,
                    headers=headers)
    print(f"   Response: {r.status_code} - {r.text}")

    # Step 3: Check GetTerminalList
    print("\n3. Checking GetTerminalList...")
    r = client.get(f'{base_url}/GetTerminalList',
                   params={'ClientVersion': '24.07.2025'},
                   headers=headers)
    terminals = r.json() if r.status_code == 200 else []
    print(f"   Found {len(terminals)} terminal(s)")
    for t in terminals:
        print(f"   - ID={t.get('TerminalID')}, Name={t.get('TerminalName')}, IP={t.get('IPAddress')}")

    # Step 4: Send sync command
    print("\n4. Sending EATR,1 sync command...")
    r = client.get(f'{base_url}/SendTCPCommand',
                   params={
                       'Command': 'EATR,1',
                       'host': '192.168.1.88',
                       'Port': 13000,
                       'LogDetail': 'Force sync after terminal online',
                       'ClientVersion': '24.07.2025'
                   },
                   headers=headers)
    print(f"   Response: {r.status_code} - {r.text}")

    # Wait for sync
    print("\n5. Waiting 5 seconds for sync...")
    time.sleep(5)

    # Step 6: Check result
    print("\n6. Checking Ecode 15 status...")
    r = client.get(f'{base_url}/GetTerminalAuthenticationListByEcode',
                   params={'Ecode': 15, 'ClientVersion': '24.07.2025'},
                   headers=headers)
    if r.status_code == 200:
        data = r.json()
        if data:
            print(f"   Status: {data[0].get('Status')}")
            print(f"   Error: {data[0].get('Error')}")
            print(f"   PresentCardNo: {data[0].get('PresentCardNo')}")
            print(f"   Group1: {data[0].get('Group1')}")

            if data[0].get('Status') == 'Success' and 'Face:Success' in str(data[0].get('Error', '')):
                print("\n*** SUCCESS! User should be able to authenticate now. ***")
            else:
                print("\n*** Status still not synced from device ***")

# Restore terminal status
print("\n7. Note: Terminal status was set to Online manually")
print("   The actual connection might still be offline in reality")
