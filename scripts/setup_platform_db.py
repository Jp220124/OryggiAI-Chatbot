"""
Setup Script for Platform Database
Creates the OryggiAI_Platform database and tables using SQLAlchemy.

Usage:
    cd D:\\OryggiAI_Service\\Advance_Chatbot
    python scripts/setup_platform_db.py
"""

import sys
import os

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pyodbc
from loguru import logger

# Use ASCII-safe symbols for Windows compatibility
PASS = "[OK]"
FAIL = "[X]"
INFO = "[i]"


def get_master_connection_string():
    """Get connection string to master database"""
    from app.config import settings

    server = settings.platform_db_server

    if settings.platform_db_use_windows_auth:
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={server};"
            f"DATABASE=master;"
            f"Trusted_Connection=yes;"
        )
    else:
        conn_str = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={server};"
            f"DATABASE=master;"
            f"UID={settings.platform_db_username};"
            f"PWD={settings.platform_db_password};"
        )

    return conn_str


def database_exists(cursor, db_name):
    """Check if database exists"""
    cursor.execute(
        "SELECT COUNT(*) FROM sys.databases WHERE name = ?",
        (db_name,)
    )
    return cursor.fetchone()[0] > 0


def create_database():
    """Create the OryggiAI_Platform database"""
    from app.config import settings

    print("\n" + "=" * 60)
    print("  PLATFORM DATABASE SETUP")
    print("  OryggiAI Multi-Tenant SaaS Platform")
    print("=" * 60)

    db_name = settings.platform_db_name
    server = settings.platform_db_server

    print(f"\n{INFO} Server: {server}")
    print(f"{INFO} Database: {db_name}")
    print(f"{INFO} Using Windows Auth: {settings.platform_db_use_windows_auth}")

    try:
        # Connect to master database
        print(f"\n{INFO} Connecting to SQL Server (master)...")
        conn_str = get_master_connection_string()
        conn = pyodbc.connect(conn_str, autocommit=True)
        cursor = conn.cursor()
        print(f"{PASS} Connected to SQL Server")

        # Check if database exists
        if database_exists(cursor, db_name):
            print(f"{INFO} Database '{db_name}' already exists")
            print(f"{INFO} Skipping database creation (use existing)")
        else:
            # Create database
            print(f"\n{INFO} Creating database '{db_name}'...")
            cursor.execute(f"CREATE DATABASE [{db_name}]")
            print(f"{PASS} Database '{db_name}' created successfully")

        cursor.close()
        conn.close()

        return True

    except Exception as e:
        print(f"{FAIL} Failed to create database: {str(e)}")
        logger.exception("Database creation error")
        return False


def create_tables_with_sqlalchemy():
    """Create tables using SQLAlchemy models"""
    print("\n" + "=" * 60)
    print("  CREATING TABLES WITH SQLALCHEMY")
    print("=" * 60)

    try:
        from app.database.platform_connection import platform_db
        from app.models.platform.base import PlatformBase

        # Import all models to register them with the base
        from app.models.platform import (
            Tenant, TenantUser, RefreshToken, TenantDatabase,
            SchemaCache, FewShotExample, UsageMetrics, AuditLog, ApiKey
        )

        print(f"\n{INFO} Initializing database connection...")
        platform_db.initialize()
        print(f"{PASS} Database connection initialized")

        print(f"\n{INFO} Creating tables from SQLAlchemy models...")

        # Get list of tables before creation
        tables_before = set(PlatformBase.metadata.tables.keys())
        print(f"{INFO} Models registered: {len(tables_before)} tables")

        for table_name in sorted(tables_before):
            print(f"  - {table_name}")

        # Create all tables
        PlatformBase.metadata.create_all(bind=platform_db.engine)

        print(f"\n{PASS} All tables created successfully!")

        # Verify tables exist
        print(f"\n{INFO} Verifying tables...")
        existing_tables = platform_db.check_tables_exist()

        all_exist = True
        for table_name, exists in existing_tables.items():
            status = PASS if exists else FAIL
            print(f"  {status} {table_name}")
            if not exists:
                all_exist = False

        if all_exist:
            print(f"\n{PASS} All tables verified successfully!")
        else:
            print(f"\n{FAIL} Some tables are missing!")

        # Close connection
        platform_db.close()

        return all_exist

    except Exception as e:
        print(f"{FAIL} Failed to create tables: {str(e)}")
        logger.exception("Table creation error")
        return False


def main():
    """Main setup function"""

    # Step 1: Create database
    if not create_database():
        print(f"\n{FAIL} Database creation failed!")
        return 1

    # Step 2: Create tables using SQLAlchemy
    if not create_tables_with_sqlalchemy():
        print(f"\n{FAIL} Table creation failed!")
        return 1

    print("\n" + "=" * 60)
    print(f"  {PASS} PLATFORM DATABASE SETUP COMPLETE")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Run: python scripts/test_platform_db.py")
    print("  2. Proceed to Step 2: Security Module")

    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
