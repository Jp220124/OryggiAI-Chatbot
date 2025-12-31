"""Test employee lookup to verify the data"""
import asyncio
import sys
sys.path.insert(0, 'D:/OryggiAI_Service/Advance_Chatbot')

import pyodbc

def test_direct_db():
    """Test direct database lookup"""
    print(f"\n{'='*60}")
    print("Testing Direct Database Lookup")
    print(f"{'='*60}\n")

    conn_str = (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=DESKTOP-UOD2VBS\\MSSQLSERVER2022;"
        "DATABASE=Oryggi;"
        "Trusted_Connection=yes;"
    )

    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()

        # Look for TERMTEST2191
        print("Looking for TERMTEST2191...")
        cursor.execute("""
            SELECT TOP 1 Ecode, CorpEmpCode, FName, LName, PresentCardNo
            FROM EmployeeMaster
            WHERE CorpEmpCode = 'TERMTEST2191'
        """)
        row = cursor.fetchone()
        if row:
            print(f"  Found: Ecode={row[0]}, CorpEmpCode={row[1]}, Name={row[2]} {row[3]}, Card={row[4]}")
        else:
            print("  NOT FOUND!")

        # Look for similar patterns
        print("\nLooking for employees with 'TERM' or 'TEST' in CorpEmpCode...")
        cursor.execute("""
            SELECT TOP 10 Ecode, CorpEmpCode, FName, LName, PresentCardNo
            FROM EmployeeMaster
            WHERE CorpEmpCode LIKE '%TERM%' OR CorpEmpCode LIKE '%TEST%'
            ORDER BY Ecode DESC
        """)
        rows = cursor.fetchall()
        for row in rows:
            print(f"  Ecode={row[0]}, CorpEmpCode={row[1]}, Name={row[2]} {row[3]}, Card={row[4]}")

        # Check ecode 1016 which we were testing with
        print("\nLooking for ecode 1016...")
        cursor.execute("""
            SELECT Ecode, CorpEmpCode, FName, LName, PresentCardNo
            FROM EmployeeMaster
            WHERE Ecode = 1016
        """)
        row = cursor.fetchone()
        if row:
            print(f"  Found: Ecode={row[0]}, CorpEmpCode={row[1]}, Name={row[2]} {row[3]}, Card={row[4]}")
        else:
            print("  NOT FOUND!")

        # Get sample employees
        print("\nSample active employees...")
        cursor.execute("""
            SELECT TOP 5 Ecode, CorpEmpCode, FName, LName, PresentCardNo
            FROM EmployeeMaster
            WHERE Status = 1
            ORDER BY Ecode DESC
        """)
        rows = cursor.fetchall()
        for row in rows:
            print(f"  Ecode={row[0]}, CorpEmpCode={row[1]}, Name={row[2]} {row[3]}, Card={row[4]}")

        conn.close()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_direct_db()
