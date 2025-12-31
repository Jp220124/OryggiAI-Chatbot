import pyodbc

conn_str = (
    'DRIVER={ODBC Driver 17 for SQL Server};'
    'SERVER=DESKTOP-UOD2VBS\\MSSQLSERVER2022;'
    'DATABASE=Oryggi;'
    'Trusted_Connection=yes;'
)

conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

# Check Employee_Terminal_Authentication_Relation for Ecode 14 and 15
print("=== Employee_Terminal_Authentication_Relation columns ===")
cursor.execute("""
    SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'Employee_Terminal_Authentication_Relation'
""")
for row in cursor.fetchall():
    print(f"  - {row[0]}")

print("\n=== Ecode 14 Authentication Record ===")
cursor.execute("SELECT * FROM Employee_Terminal_Authentication_Relation WHERE Ecode = 14")
row = cursor.fetchone()
if row:
    cols = [d[0] for d in cursor.description]
    for col, val in zip(cols, row):
        print(f"  {col}: {val}")

print("\n=== Ecode 15 Authentication Record ===")
cursor.execute("SELECT * FROM Employee_Terminal_Authentication_Relation WHERE Ecode = 15")
row = cursor.fetchone()
if row:
    cols = [d[0] for d in cursor.description]
    for col, val in zip(cols, row):
        print(f"  {col}: {val}")
else:
    print("  No record found!")

conn.close()
