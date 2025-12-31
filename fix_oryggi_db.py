"""Try to recover the Oryggi database"""
import pyodbc

conn_str = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=DESKTOP-UOD2VBS\\MSSQLSERVER2022;"
    "DATABASE=master;"
    "UID=sa;"
    "PWD=admin@123;"
)
conn = pyodbc.connect(conn_str, timeout=30)
conn.autocommit = True
cursor = conn.cursor()

print("Attempting to recover Oryggi database...")

# Try method 1: Set to emergency mode and repair
try:
    print("\n1. Setting Oryggi to EMERGENCY mode...")
    cursor.execute("ALTER DATABASE Oryggi SET EMERGENCY")
    print("   SUCCESS")
except Exception as e:
    print(f"   FAILED: {e}")

# Check state
cursor.execute("SELECT state_desc FROM sys.databases WHERE name = 'Oryggi'")
state = cursor.fetchone()[0]
print(f"\n   Current state: {state}")

if state == 'EMERGENCY':
    # Try to bring online
    try:
        print("\n2. Setting Oryggi to SINGLE_USER mode...")
        cursor.execute("ALTER DATABASE Oryggi SET SINGLE_USER WITH ROLLBACK IMMEDIATE")
        print("   SUCCESS")
    except Exception as e:
        print(f"   FAILED: {e}")

    try:
        print("\n3. Running DBCC CHECKDB with repair...")
        cursor.execute("DBCC CHECKDB('Oryggi', REPAIR_ALLOW_DATA_LOSS)")
        print("   SUCCESS")
    except Exception as e:
        print(f"   FAILED: {e}")

    try:
        print("\n4. Setting Oryggi to MULTI_USER mode...")
        cursor.execute("ALTER DATABASE Oryggi SET MULTI_USER")
        print("   SUCCESS")
    except Exception as e:
        print(f"   FAILED: {e}")

    try:
        print("\n5. Setting Oryggi ONLINE...")
        cursor.execute("ALTER DATABASE Oryggi SET ONLINE")
        print("   SUCCESS")
    except Exception as e:
        print(f"   FAILED: {e}")

# Final state check
cursor.execute("SELECT state_desc, user_access_desc FROM sys.databases WHERE name = 'Oryggi'")
result = cursor.fetchone()
print(f"\n*** Final state: {result[0]}, access: {result[1]} ***")

# Test if we can access
cursor.execute("SELECT HAS_DBACCESS('Oryggi')")
has_access = cursor.fetchone()[0]
print(f"*** HAS_DBACCESS: {has_access} ***")

if has_access:
    try:
        cursor.execute("USE Oryggi")
        cursor.execute("SELECT COUNT(*) FROM EmployeeMaster")
        count = cursor.fetchone()[0]
        print(f"\n*** SUCCESS: EmployeeMaster has {count} records ***")
    except Exception as e:
        print(f"\n*** Still cannot access: {e} ***")

conn.close()
