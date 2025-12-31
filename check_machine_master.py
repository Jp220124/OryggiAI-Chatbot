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

conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

print("=== Checking Machine/Terminal Master Tables ===\n")

# Check VW_MachineMaster
print("1. VW_MachineMaster:")
cursor.execute("SELECT TerminalID, DeviceType, IPAddress, Connection_Status, DataLocation FROM VW_MachineMaster")
rows = cursor.fetchall()
cols = [d[0] for d in cursor.description]
for row in rows:
    print(f"   {dict(zip(cols, row))}")

# Find the actual base table for machines/terminals
print("\n2. Looking for base table:")
cursor.execute("""
    SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_NAME LIKE '%Machine%' AND TABLE_TYPE = 'BASE TABLE'
""")
tables = cursor.fetchall()
for t in tables:
    print(f"   - {t[0]}")

# Check MachineMaster
print("\n3. MachineMaster table:")
try:
    cursor.execute("SELECT TOP 5 * FROM MachineMaster")
    rows = cursor.fetchall()
    if rows:
        cols = [d[0] for d in cursor.description]
        print(f"   Columns: {cols}")
        for row in rows:
            d = dict(zip(cols, row))
            print(f"   ID={d.get('MachineID', d.get('ID'))}, Active={d.get('Active')}, "
                  f"IPAddress={d.get('IPAddress')}, TerminalID={d.get('TerminalID')}")
except Exception as e:
    print(f"   Error: {e}")

# Try to understand what GetTerminalList checks
print("\n4. Checking Active flags and conditions:")
cursor.execute("""
    SELECT m.MachineID, m.Active, m.IPAddress, m.TerminalID, m.DeviceType
    FROM VW_MachineMaster m
""")
rows = cursor.fetchall()
cols = [d[0] for d in cursor.description]
for row in rows:
    print(f"   {dict(zip(cols, row))}")

conn.close()

# Test API with different parameters
print("\n5. Testing GetTerminalList with different parameters:")
with httpx.Client(verify=False, timeout=30) as client:
    # Try without any params
    r = client.get(f'{base_url}/GetTerminalList', headers=headers)
    print(f"   No params: {r.status_code} - {len(r.json()) if r.status_code == 200 else r.text}")

    # Try with active filter
    r = client.get(f'{base_url}/GetTerminalList',
                   params={'Active': True, 'ClientVersion': '24.07.2025'},
                   headers=headers)
    print(f"   Active=True: {r.status_code} - {len(r.json()) if r.status_code == 200 else r.text}")

    # Try GetAllTerminals
    r = client.get(f'{base_url}/GetAllTerminals', headers=headers)
    print(f"   GetAllTerminals: {r.status_code} - {r.text[:200] if r.text else 'empty'}")

    # Try GetMachineList
    r = client.get(f'{base_url}/GetMachineList', headers=headers)
    print(f"   GetMachineList: {r.status_code} - {r.text[:200] if r.text else 'empty'}")

    # Try with BranchCode
    r = client.get(f'{base_url}/GetTerminalList',
                   params={'BranchCode': 1, 'ClientVersion': '24.07.2025'},
                   headers=headers)
    print(f"   BranchCode=1: {r.status_code} - {len(r.json()) if r.status_code == 200 else r.text}")
