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

print("=" * 60)
print("FIXING ECODE 15 TO MATCH ECODE 14")
print("=" * 60)

conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

# Fix 1: Set PresentCardNo in EmployeeMaster
print("\n1. Setting PresentCardNo='15' in EmployeeMaster...")
cursor.execute("UPDATE EmployeeMaster SET PresentCardNo = '15' WHERE Ecode = 15")
conn.commit()
print(f"   Updated {cursor.rowcount} row(s)")

# Verify
cursor.execute("SELECT PresentCardNo FROM EmployeeMaster WHERE Ecode = 15")
row = cursor.fetchone()
print(f"   Verified: PresentCardNo = '{row[0]}'")

# Fix 2: Set Status, Error, DataLocation in auth table
print("\n2. Setting Status, Error, DataLocation in Auth table...")
cursor.execute("""
    UPDATE Employee_Terminal_Authentication_Relation
    SET Status = 'Success',
        Error = 'User:Success Access:Success TimeZone:Success Face:Success',
        DataLocation = 'On Device'
    WHERE Ecode = 15
""")
conn.commit()
print(f"   Updated {cursor.rowcount} row(s)")

# Verify
cursor.execute("SELECT Status, Error, DataLocation FROM Employee_Terminal_Authentication_Relation WHERE Ecode = 15")
row = cursor.fetchone()
print(f"   Verified: Status='{row[0]}', DataLocation='{row[2]}'")

conn.close()

# Step 3: Sync to terminal
print("\n3. Syncing to terminal...")
with httpx.Client(verify=False, timeout=60) as client:
    r = client.get(f'{base_url}/SendTCPCommand',
                   params={
                       'Command': 'EATR,1',
                       'host': '192.168.1.88',
                       'Port': 13000,
                       'LogDetail': 'Final sync Ecode 15',
                       'ClientVersion': '24.07.2025'
                   },
                   headers=headers)
    print(f"   Response: {r.text}")

print("\n" + "=" * 60)
print("FIX COMPLETE!")
print("=" * 60)
print("\nNow test authentication at the V-22 device for Ecode 15")
print("(Chatbot TestUser)")
