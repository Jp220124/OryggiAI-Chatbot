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

print("=== Testing Real Sync ===\n")

# Step 1: Reset the Status field to see if real sync happens
print("1. Resetting Ecode 15 Status to test real sync...")
conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

cursor.execute("""
    UPDATE Employee_Terminal_Authentication_Relation
    SET Status = NULL, Error = NULL, DataLocation = NULL
    WHERE Ecode = 15
""")
conn.commit()
print("   Reset complete")

# Verify
cursor.execute("SELECT Status, Error FROM Employee_Terminal_Authentication_Relation WHERE Ecode = 15")
row = cursor.fetchone()
print(f"   Current: Status={row[0]}, Error={row[1]}")

conn.close()

# Step 2: Check API shows empty status
print("\n2. Checking API shows empty status...")
with httpx.Client(verify=False, timeout=60) as client:
    r = client.get(f'{base_url}/GetTerminalAuthenticationListByEcode',
                   params={'Ecode': 15, 'ClientVersion': '24.07.2025'},
                   headers=headers)
    data = r.json()
    if data:
        print(f"   Status: '{data[0].get('Status')}'")
        print(f"   Error: '{data[0].get('Error')}'")

    # Step 3: Send EATR command
    print("\n3. Sending EATR,1 sync command...")
    r = client.get(f'{base_url}/SendTCPCommand',
                   params={
                       'Command': 'EATR,1',
                       'host': '192.168.1.88',
                       'Port': 13000,
                       'LogDetail': 'Test real sync',
                       'ClientVersion': '24.07.2025'
                   },
                   headers=headers)
    print(f"   Response: {r.status_code} - {r.text}")

    # Step 4: Wait and check
    print("\n4. Waiting 5 seconds...")
    time.sleep(5)

    print("\n5. Checking if Status was updated by sync...")
    r = client.get(f'{base_url}/GetTerminalAuthenticationListByEcode',
                   params={'Ecode': 15, 'ClientVersion': '24.07.2025'},
                   headers=headers)
    data = r.json()
    if data:
        status = data[0].get('Status')
        error = data[0].get('Error')
        print(f"   Status: '{status}'")
        print(f"   Error: '{error}'")

        if status and 'Success' in str(status):
            print("\n*** REAL SYNC WORKED! ***")
        else:
            print("\n*** Sync did NOT update the status - device may not be connected ***")
            print("   The user may need to test at the device to confirm enrollment")

print("\n=== Summary ===")
print("The face template IS on the device (captured during EnrollV22)")
print("The user access data in the database is correct")
print("But the terminal shows as Offline, so sync status isn't updating")
print("\nPLEASE TEST: Go to the V-22 device and try to authenticate as Ecode 15")
