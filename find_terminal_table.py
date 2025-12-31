import pyodbc

conn_str = (
    'DRIVER={ODBC Driver 17 for SQL Server};'
    'SERVER=DESKTOP-UOD2VBS\\MSSQLSERVER2022;'
    'DATABASE=Oryggi;'
    'Trusted_Connection=yes;'
)

conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

print("=== Finding Terminal-Related Tables ===\n")

# Find ALL tables with "Terminal" in the name
cursor.execute("""
    SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
    WHERE TABLE_NAME LIKE '%Terminal%' OR TABLE_NAME LIKE '%Device%'
    ORDER BY TABLE_NAME
""")
tables = cursor.fetchall()
print("Tables found:")
for t in tables:
    print(f"  - {t[0]}")

# Check MasterTerminalHardwareTypeRelation which might have terminal info
print("\n=== Checking MasterTerminalHardwareTypeRelation ===")
try:
    cursor.execute("SELECT TOP 5 * FROM MasterTerminalHardwareTypeRelation")
    rows = cursor.fetchall()
    if rows:
        cols = [d[0] for d in cursor.description]
        print(f"Columns: {cols}")
        for row in rows:
            print(dict(zip(cols, row)))
except Exception as e:
    print(f"Error: {e}")

# The terminal data might be in a view
print("\n=== Finding Terminal Views ===")
cursor.execute("""
    SELECT TABLE_NAME FROM INFORMATION_SCHEMA.VIEWS
    WHERE TABLE_NAME LIKE '%Terminal%' OR TABLE_NAME LIKE '%Device%'
""")
views = cursor.fetchall()
for v in views:
    print(f"  - {v[0]}")

# Check Vw_TerminalDetail_VMS
print("\n=== Checking Vw_TerminalDetail_VMS ===")
try:
    cursor.execute("SELECT TOP 5 * FROM Vw_TerminalDetail_VMS")
    rows = cursor.fetchall()
    if rows:
        cols = [d[0] for d in cursor.description]
        print(f"Columns: {cols}")
        for row in rows:
            print(dict(zip(cols, row)))
    else:
        print("No data")
except Exception as e:
    print(f"Error: {e}")

# Let's search for any table that has IPAddress 192.168.1.201
print("\n=== Searching for 192.168.1.201 in database ===")
cursor.execute("""
    SELECT TABLE_NAME, COLUMN_NAME
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE COLUMN_NAME LIKE '%IP%' OR COLUMN_NAME LIKE '%Address%'
""")
ip_columns = cursor.fetchall()
print("Tables with IP columns:")
for table, col in ip_columns[:20]:
    print(f"  {table}.{col}")

# Check Employee_Terminal_Authentication_Relation for terminal info source
print("\n=== Checking what Terminal data exists in Auth Relation ===")
cursor.execute("""
    SELECT DISTINCT TerminalID FROM Employee_Terminal_Authentication_Relation
""")
terminal_ids = cursor.fetchall()
print(f"Terminal IDs in auth table: {[t[0] for t in terminal_ids]}")

# Check if there's Terminal_Master or similar
print("\n=== Checking Terminal_Master ===")
try:
    cursor.execute("SELECT TOP 5 * FROM Terminal_Master")
    rows = cursor.fetchall()
    if rows:
        cols = [d[0] for d in cursor.description]
        print(f"Columns: {cols}")
        for row in rows:
            print(dict(zip(cols, row)))
except Exception as e:
    print(f"Error: {e}")

# Check TerminalDetails or DeviceMaster
print("\n=== Checking All Tables for Terminal Config ===")
for table in ['TerminalDetails', 'DeviceMaster', 'DeviceDetails', 'Devices', 'Terminals']:
    try:
        cursor.execute(f"SELECT TOP 1 * FROM {table}")
        print(f"{table}: EXISTS")
    except:
        pass

conn.close()
