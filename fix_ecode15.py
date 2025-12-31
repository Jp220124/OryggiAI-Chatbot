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

# Step 1: Update PresentCardNo in database
print("=== Step 1: Updating PresentCardNo for Ecode 15 ===")
conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

cursor.execute("UPDATE EmployeeMaster SET PresentCardNo = '15' WHERE Ecode = 15")
rows = cursor.rowcount
conn.commit()
print(f"Updated {rows} row(s)")

# Verify
cursor.execute("SELECT Ecode, PresentCardNo FROM EmployeeMaster WHERE Ecode = 15")
row = cursor.fetchone()
print(f"Verified: Ecode={row[0]}, PresentCardNo={row[1]}")

# Check what terminal auth tables exist
print("\n=== Checking Terminal Auth Tables ===")
cursor.execute("""
    SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_NAME LIKE '%Terminal%' OR TABLE_NAME LIKE '%Auth%'
""")
for row in cursor.fetchall():
    print(f"  - {row[0]}")

conn.close()

# Step 2: Sync to terminal using API
print("\n=== Step 2: Syncing to Terminal ===")
with httpx.Client(verify=False, timeout=30) as client:
    # Use AddAuthentication_Terminal (non-V2) with proper data
    auth_data = {
        "Ecode": 15,
        "TerminalID": 1,
        "AuthenticationID": 13,  # Fusion
        "ScheduleID": 63,  # All Access
        "StartDate": "2025-12-17T00:00:00",
        "ExpiryDate": "2030-12-31T00:00:00",
        "Group1": 1,
        "Group2": 0,
        "Group3": 0,
        "Group4": 0,
        "BypassTZLevel": 0,
        "WhiteList": False,
        "VIPlist": False
    }

    r = client.post(
        f'{base_url}/AddAuthentication_Terminal',
        params={'IPAddress': 'localhost', 'OperatorEcode': 1, 'ClientVersion': '24.07.2025'},
        json=auth_data,
        headers=headers
    )
    print(f"AddAuthentication_Terminal: {r.status_code} - {r.text}")

    # Sync command
    r = client.get(
        f'{base_url}/SendTCPCommand',
        params={
            'Command': 'EATR,1',
            'host': '192.168.1.88',
            'LogDetail': 'Sync Ecode 15',
            'Port': 13000
        },
        headers=headers
    )
    print(f"SendTCPCommand (EATR,1): {r.status_code} - {r.text}")

# Step 3: Verify
print("\n=== Step 3: Verifying ===")
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
        print(f"PresentCardNo: {data[0].get('PresentCardNo')}")
        print(f"Group1: {data[0].get('Group1')}")
        print(f"Error: {data[0].get('Error')}")
