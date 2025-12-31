"""
Check Database Tables
"""
import os
import pyodbc
from app.config import settings

def list_tables():
    print(f"Connecting to {settings.db_server}...")
    
    conn_str = (
        f"DRIVER={{{settings.db_driver}}};"
        f"SERVER={settings.db_server},{settings.db_port};"
        f"DATABASE={settings.db_name};"
    )
    
    if settings.db_use_windows_auth:
        conn_str += "Trusted_Connection=yes;"
    else:
        conn_str += f"UID={settings.db_username};PWD={settings.db_password};"
        
    try:
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        print("\nTables in database:")
        cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME")
        tables = cursor.fetchall()
        
        for table in tables:
            print(f"- {table[0]}")
            
        print(f"\nTotal tables: {len(tables)}")
        
        # Check for 'User' related tables
        print("\nUser related tables:")
        for table in tables:
            if 'user' in table[0].lower() or 'role' in table[0].lower():
                print(f"- {table[0]}")
                
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_tables()
