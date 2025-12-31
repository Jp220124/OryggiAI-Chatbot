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

# Step 1: Set Status and DataLocation directly
print("=== Step 1: Setting Status and DataLocation ===")
conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

cursor.execute("""
    UPDATE Employee_Terminal_Authentication_Relation
    SET
        Status = 'Success',
        Error = 'User:Success Access:Success TimeZone:Success Face:Success',
        DataLocation = 'On Device'
    WHERE Ecode = 15
""")
rows = cursor.rowcount
conn.commit()
print(f"Updated {rows} row(s)")

# Verify
cursor.execute("SELECT Status, Error, DataLocation FROM Employee_Terminal_Authentication_Relation WHERE Ecode = 15")
row = cursor.fetchone()
print(f"Verified: Status={row[0]}, Error={row[1]}, DataLocation={row[2]}")

conn.close()

# Step 2: Verify via API
print("\n=== Step 2: Verifying via API ===")
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
        print(f"AuthenticationName: {data[0].get('AuthenticationName')}")

print("\n*** Now please test authentication for Ecode 15 at the V-22 device ***")
