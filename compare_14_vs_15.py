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

print("=" * 70)
print("COMPARING ECODE 14 (WORKS) vs ECODE 15 (NOT WORKING)")
print("=" * 70)

conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

# Compare EmployeeMaster
print("\n1. EmployeeMaster Comparison:")
cursor.execute("""
    SELECT Ecode, CorpEmpCode, FName, LName, PresentCardNo, Active,
           FP1_ID, FP2_ID, DFP_ID
    FROM EmployeeMaster
    WHERE Ecode IN (14, 15)
    ORDER BY Ecode
""")
rows = cursor.fetchall()
cols = [d[0] for d in cursor.description]
for row in rows:
    d = dict(zip(cols, row))
    print(f"\n   Ecode {d['Ecode']}:")
    for k, v in d.items():
        print(f"      {k}: {v}")

# Compare Terminal Authentication
print("\n" + "=" * 70)
print("2. Employee_Terminal_Authentication_Relation Comparison:")
cursor.execute("""
    SELECT * FROM Employee_Terminal_Authentication_Relation
    WHERE Ecode IN (14, 15)
    ORDER BY Ecode
""")
rows = cursor.fetchall()
cols = [d[0] for d in cursor.description]
for row in rows:
    d = dict(zip(cols, row))
    print(f"\n   Ecode {d['Ecode']}:")
    for k, v in d.items():
        if v is not None and v != '' and v != 0 and v != False:
            print(f"      {k}: {v}")

# Compare Face Templates
print("\n" + "=" * 70)
print("3. Face Templates (FingerMaster):")
cursor.execute("""
    SELECT Ecode, FingerID, TempleteType, Score, CheckedStatus
    FROM FingerMaster
    WHERE Ecode IN (14, 15) AND TempleteType = 'FACE'
    ORDER BY Ecode
""")
rows = cursor.fetchall()
cols = [d[0] for d in cursor.description]
for row in rows:
    d = dict(zip(cols, row))
    print(f"   Ecode {d['Ecode']}: FingerID={d['FingerID']}, Score={d['Score']}, CheckedStatus={d['CheckedStatus']}")

conn.close()

# Compare via API
print("\n" + "=" * 70)
print("4. API GetTerminalAuthenticationListByEcode:")
with httpx.Client(verify=False, timeout=30) as client:
    for ecode in [14, 15]:
        r = client.get(f'{base_url}/GetTerminalAuthenticationListByEcode',
                       params={'Ecode': ecode, 'ClientVersion': '24.07.2025'},
                       headers=headers)
        data = r.json() if r.status_code == 200 else []
        if data:
            print(f"\n   Ecode {ecode}:")
            important_fields = ['Status', 'Error', 'PresentCardNo', 'Group1', 'AuthenticationID',
                              'ScheduleID', 'ExpiryDate', 'BypassTZLevel']
            for f in important_fields:
                print(f"      {f}: {data[0].get(f)}")

print("\n" + "=" * 70)
print("KEY DIFFERENCES TO FIX:")
print("=" * 70)
