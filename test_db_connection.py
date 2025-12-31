"""Test database connections to Oryggi database"""
import pyodbc

def test_oryggi_connection():
    """Test connection to Oryggi database with different methods"""

    # Method 1: Try with sa login
    print("=" * 60)
    print("Method 1: sa login with SQL Server authentication")
    print("=" * 60)

    conn_str_sa = (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=DESKTOP-UOD2VBS\\MSSQLSERVER2022;"
        "DATABASE=Oryggi;"
        "UID=sa;"
        "PWD=admin@123;"
    )

    try:
        conn = pyodbc.connect(conn_str_sa, timeout=10)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM EmployeeMaster")
        count = cursor.fetchone()[0]
        print(f"SUCCESS: EmployeeMaster has {count} records")
        conn.close()
        return "sa"
    except Exception as e:
        print(f"FAILED: {str(e)}")

    # Method 2: Try with Windows Authentication
    print("\n" + "=" * 60)
    print("Method 2: Windows Authentication (Trusted_Connection)")
    print("=" * 60)

    conn_str_win = (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=DESKTOP-UOD2VBS\\MSSQLSERVER2022;"
        "DATABASE=Oryggi;"
        "Trusted_Connection=yes;"
    )

    try:
        conn = pyodbc.connect(conn_str_win, timeout=10)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM EmployeeMaster")
        count = cursor.fetchone()[0]
        print(f"SUCCESS: EmployeeMaster has {count} records")
        conn.close()
        return "windows"
    except Exception as e:
        print(f"FAILED: {str(e)}")

    # Method 3: Connect to master and try to grant access
    print("\n" + "=" * 60)
    print("Method 3: Check sa login permissions via master database")
    print("=" * 60)

    conn_str_master = (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=DESKTOP-UOD2VBS\\MSSQLSERVER2022;"
        "DATABASE=master;"
        "UID=sa;"
        "PWD=admin@123;"
    )

    try:
        conn = pyodbc.connect(conn_str_master, timeout=10)
        cursor = conn.cursor()

        # Check sa's sysadmin status
        cursor.execute("""
            SELECT IS_SRVROLEMEMBER('sysadmin', 'sa')
        """)
        is_sysadmin = cursor.fetchone()[0]
        print(f"sa is sysadmin: {is_sysadmin}")

        # Check if Oryggi database is accessible
        cursor.execute("""
            SELECT state_desc, user_access_desc FROM sys.databases WHERE name = 'Oryggi'
        """)
        db_state = cursor.fetchone()
        if db_state:
            print(f"Oryggi database state: {db_state[0]}, access: {db_state[1]}")

        # Check if there's a user mapping for sa in Oryggi
        cursor.execute("""
            SELECT HAS_DBACCESS('Oryggi')
        """)
        has_access = cursor.fetchone()[0]
        print(f"sa HAS_DBACCESS('Oryggi'): {has_access}")

        # Try to switch to Oryggi database
        print("\nAttempting USE Oryggi...")
        try:
            cursor.execute("USE Oryggi")
            cursor.execute("SELECT COUNT(*) FROM EmployeeMaster")
            count = cursor.fetchone()[0]
            print(f"SUCCESS after USE Oryggi: EmployeeMaster has {count} records")
            conn.close()
            return "master_use"
        except Exception as use_err:
            print(f"USE Oryggi failed: {use_err}")

        conn.close()
    except Exception as e:
        print(f"FAILED: {str(e)}")

    return None

if __name__ == "__main__":
    result = test_oryggi_connection()
    if result:
        print(f"\n*** Working method: {result} ***")
    else:
        print("\n*** No working connection method found ***")
