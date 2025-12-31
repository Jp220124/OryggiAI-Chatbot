import pyodbc
import httpx

conn_str = (
    'DRIVER={ODBC Driver 17 for SQL Server};'
    'SERVER=DESKTOP-UOD2VBS\\MSSQLSERVER2022;'
    'DATABASE=Oryggi;'
    'Trusted_Connection=yes;'
)

base_url = 'https://localhost/OryggiWebServceCoreApi/OryggiWebApi'
headers = {'APIKey': 'uw0RyC0v+aBV6nCWKM0M0Q=='}

# Step 1: Update Employee_Terminal_Authentication_Relation to match Ecode 14
print("=== Step 1: Updating Auth Record for Ecode 15 ===")
conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

# Update all the missing fields to match Ecode 14
cursor.execute("""
    UPDATE Employee_Terminal_Authentication_Relation
    SET
        Expiry_date = '2030-12-31 00:00:00',
        Start_date = '2025-12-17 00:00:00',
        Group01 = 1,
        BypassTZLevel = 1,
        ExpireDateCheck = 0,
        ServerSync = 0
    WHERE Ecode = 15
""")
rows = cursor.rowcount
conn.commit()
print(f"Updated {rows} row(s)")

# Verify update
cursor.execute("SELECT Group01, Expiry_date, BypassTZLevel, ExpireDateCheck FROM Employee_Terminal_Authentication_Relation WHERE Ecode = 15")
row = cursor.fetchone()
print(f"Verified: Group01={row[0]}, Expiry_date={row[1]}, BypassTZLevel={row[2]}, ExpireDateCheck={row[3]}")

conn.close()

# Step 2: Sync to terminal
print("\n=== Step 2: Syncing to Terminal ===")
with httpx.Client(verify=False, timeout=30) as client:
    # Send sync command
    r = client.get(
        f'{base_url}/SendTCPCommand',
        params={
            'Command': 'EATR,1',
            'host': '192.168.1.88',
            'LogDetail': 'Sync Ecode 15 after fix',
            'Port': 13000
        },
        headers=headers
    )
    print(f"SendTCPCommand (EATR,1): {r.status_code} - {r.text}")

# Wait a moment for sync
import time
print("Waiting 3 seconds for sync...")
time.sleep(3)

# Step 3: Verify via API
print("\n=== Step 3: Verifying via API ===")
with httpx.Client(verify=False, timeout=30) as client:
    r = client.get(
        f'{base_url}/GetTerminalAuthenticationListByEcode',
        params={'Ecode': 15, 'ClientVersion': '24.07.2025'},
        headers=headers
    )
    import json
    data = r.json()
    if data:
        print(f"Status: {data[0].get('Status')}")
        print(f"Error: {data[0].get('Error')}")
        print(f"PresentCardNo: {data[0].get('PresentCardNo')}")
        print(f"Group1: {data[0].get('Group1')}")
        print(f"ExpiryDate: {data[0].get('ExpiryDate')}")

        if data[0].get('Status') == 'Success':
            print("\n*** SUCCESS! Ecode 15 should now work. Please test authentication at the device. ***")
        else:
            print("\n*** Still not synced. Checking DB status... ***")

# Step 4: Check DB status after sync
print("\n=== Step 4: DB Status Check ===")
conn = pyodbc.connect(conn_str)
cursor = conn.cursor()
cursor.execute("SELECT Status, Error, DataLocation FROM Employee_Terminal_Authentication_Relation WHERE Ecode = 15")
row = cursor.fetchone()
if row:
    print(f"Status: {row[0]}")
    print(f"Error: {row[1]}")
    print(f"DataLocation: {row[2]}")
conn.close()
