import pyodbc

conn_str = (
    'DRIVER={ODBC Driver 17 for SQL Server};'
    'SERVER=DESKTOP-UOD2VBS\\MSSQLSERVER2022;'
    'DATABASE=Oryggi;'
    'Trusted_Connection=yes;'
)

conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

# Check EmpTerminalRelation
print("=== EmpTerminalRelation columns ===")
cursor.execute("""
    SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'EmpTerminalRelation'
""")
for row in cursor.fetchall():
    print(f"  - {row[0]}")

print("\n=== EmpTerminalRelation for Ecode 14 ===")
cursor.execute("SELECT * FROM EmpTerminalRelation WHERE Ecode = 14")
row = cursor.fetchone()
if row:
    cols = [d[0] for d in cursor.description]
    for col, val in zip(cols, row):
        print(f"  {col}: {val}")
else:
    print("  No record found!")

print("\n=== EmpTerminalRelation for Ecode 15 ===")
cursor.execute("SELECT * FROM EmpTerminalRelation WHERE Ecode = 15")
row = cursor.fetchone()
if row:
    cols = [d[0] for d in cursor.description]
    for col, val in zip(cols, row):
        print(f"  {col}: {val}")
else:
    print("  No record found!")

# Check if there's a card master table
print("\n=== CardMaster for Ecode 14 ===")
try:
    cursor.execute("SELECT * FROM CardMaster WHERE Ecode = 14")
    row = cursor.fetchone()
    if row:
        cols = [d[0] for d in cursor.description]
        for col, val in zip(cols, row):
            print(f"  {col}: {val}")
    else:
        print("  No record found!")
except Exception as e:
    print(f"  Error: {e}")

print("\n=== CardMaster for Ecode 15 ===")
try:
    cursor.execute("SELECT * FROM CardMaster WHERE Ecode = 15")
    row = cursor.fetchone()
    if row:
        cols = [d[0] for d in cursor.description]
        for col, val in zip(cols, row):
            print(f"  {col}: {val}")
    else:
        print("  No record found!")
except Exception as e:
    print(f"  Error: {e}")

# Check Employee_Card_Relation
print("\n=== Employee_Card_Relation for Ecode 14 ===")
try:
    cursor.execute("SELECT * FROM Employee_Card_Relation WHERE Ecode = 14")
    row = cursor.fetchone()
    if row:
        cols = [d[0] for d in cursor.description]
        for col, val in zip(cols, row):
            print(f"  {col}: {val}")
    else:
        print("  No record found!")
except Exception as e:
    print(f"  Error: {e}")

print("\n=== Employee_Card_Relation for Ecode 15 ===")
try:
    cursor.execute("SELECT * FROM Employee_Card_Relation WHERE Ecode = 15")
    row = cursor.fetchone()
    if row:
        cols = [d[0] for d in cursor.description]
        for col, val in zip(cols, row):
            print(f"  {col}: {val}")
    else:
        print("  No record found!")
except Exception as e:
    print(f"  Error: {e}")

conn.close()
