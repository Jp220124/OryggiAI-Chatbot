"""
Test Script for Platform Database Setup
Run this script to verify the platform database and models are working correctly.

Usage:
    cd D:\\OryggiAI_Service\\Advance_Chatbot
    python scripts/test_platform_db.py
"""

import sys
import os

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from loguru import logger

# Use ASCII-safe symbols for Windows compatibility
PASS = "[OK]"
FAIL = "[X]"


def test_imports():
    """Test that all modules can be imported"""
    print("\n" + "=" * 60)
    print("TEST 1: Import Verification")
    print("=" * 60)

    try:
        # Test config import
        from app.config import settings
        print(f"{PASS} Config imported - Platform DB: {settings.platform_db_name}")

        # Test model imports
        from app.models.platform import (
            PlatformBase,
            Tenant, TenantUser, RefreshToken,
            TenantDatabase, SchemaCache, FewShotExample,
            UsageMetrics, AuditLog, ApiKey
        )
        print(f"{PASS} All platform models imported successfully")

        # Test database connection import
        from app.database.platform_connection import (
            platform_db, get_platform_db,
            init_platform_database, close_platform_database
        )
        print(f"{PASS} Platform database connection module imported")

        return True

    except Exception as e:
        print(f"{FAIL} Import failed: {str(e)}")
        logger.exception("Import error")
        return False


def test_connection():
    """Test database connection"""
    print("\n" + "=" * 60)
    print("TEST 2: Database Connection")
    print("=" * 60)

    try:
        from app.database.platform_connection import platform_db
        from app.config import settings

        print(f"Connecting to: {settings.platform_db_server}/{settings.platform_db_name}")
        print(f"Using Windows Auth: {settings.platform_db_use_windows_auth}")

        # Initialize connection
        platform_db.initialize()
        print(f"{PASS} Connection pool initialized")

        # Test connection
        if platform_db.test_connection():
            print(f"{PASS} Connection test passed")
            return True
        else:
            print(f"{FAIL} Connection test failed")
            return False

    except Exception as e:
        print(f"{FAIL} Connection failed: {str(e)}")
        logger.exception("Connection error")
        return False


def test_tables_exist():
    """Check if platform tables exist"""
    print("\n" + "=" * 60)
    print("TEST 3: Table Existence Check")
    print("=" * 60)

    try:
        from app.database.platform_connection import platform_db

        tables = platform_db.check_tables_exist()

        all_exist = True
        for table, exists in tables.items():
            status = PASS if exists else FAIL
            print(f"  {status} {table}")
            if not exists:
                all_exist = False

        if all_exist:
            print(f"\n{PASS} All platform tables exist")
        else:
            print(f"\n{FAIL} Some tables are missing!")
            print("  Run the SQL migration script first:")
            print("  database/migrations/001_create_platform_database.sql")

        return all_exist

    except Exception as e:
        print(f"{FAIL} Table check failed: {str(e)}")
        logger.exception("Table check error")
        return False


def test_model_operations():
    """Test basic CRUD operations with models"""
    print("\n" + "=" * 60)
    print("TEST 4: Model Operations (CRUD)")
    print("=" * 60)

    try:
        from app.database.platform_connection import platform_db
        from app.models.platform import Tenant, TenantUser, TenantDatabase
        from app.models.platform.tenant import TenantStatus, TenantPlan
        from app.models.platform.user import UserRole
        import uuid

        with platform_db.session_scope() as session:
            # Test 1: Create a test tenant
            test_slug = f"test-tenant-{datetime.now().strftime('%Y%m%d%H%M%S')}"

            tenant = Tenant(
                name="Test Organization",
                slug=test_slug,
                admin_email="test@example.com",
                organization_type="Test",
                status=TenantStatus.ACTIVE.value,
                plan=TenantPlan.FREE.value
            )
            session.add(tenant)
            session.flush()  # Get the ID
            print(f"{PASS} Created tenant: {tenant.name} (ID: {tenant.id})")

            # Test 2: Create a test user
            user = TenantUser(
                tenant_id=tenant.id,
                email="admin@test.com",
                password_hash="$2b$12$placeholder_hash_for_testing",
                first_name="Test",
                last_name="Admin",
                role=UserRole.OWNER.value,
                is_active=True
            )
            session.add(user)
            session.flush()
            print(f"{PASS} Created user: {user.email} (ID: {user.id})")

            # Test 3: Query tenant
            found_tenant = session.query(Tenant).filter(
                Tenant.slug == test_slug
            ).first()
            assert found_tenant is not None
            assert found_tenant.name == "Test Organization"
            print(f"{PASS} Queried tenant: {found_tenant.name}")

            # Test 4: Test model properties
            assert found_tenant.is_active == True
            print(f"{PASS} Tenant is_active property: {found_tenant.is_active}")

            # Test 5: Test user properties
            assert user.full_name == "Test Admin"
            print(f"{PASS} User full_name property: {user.full_name}")

            # Test 6: Clean up - delete test data
            session.delete(user)
            session.delete(tenant)
            print(f"{PASS} Cleaned up test data")

        print(f"\n{PASS} All model operations passed")
        return True

    except Exception as e:
        print(f"{FAIL} Model operations failed: {str(e)}")
        logger.exception("Model operations error")
        return False


def test_to_dict():
    """Test model to_dict method"""
    print("\n" + "=" * 60)
    print("TEST 5: Model Serialization (to_dict)")
    print("=" * 60)

    try:
        from app.models.platform import Tenant
        from app.models.platform.tenant import TenantStatus, TenantPlan
        import uuid

        # Create in-memory tenant
        tenant = Tenant(
            id=uuid.uuid4(),
            name="Serialization Test",
            slug="serialization-test",
            admin_email="serialize@test.com",
            status=TenantStatus.ACTIVE.value,
            plan=TenantPlan.PROFESSIONAL.value
        )

        # Test to_dict
        data = tenant.to_dict()
        assert "id" in data
        assert data["name"] == "Serialization Test"
        assert data["slug"] == "serialization-test"
        print(f"{PASS} to_dict() works correctly")
        print(f"  Sample data: name={data['name']}, plan={data['plan']}")

        # Test to_dict with exclusion
        data_no_id = tenant.to_dict(exclude=["id", "created_at"])
        assert "id" not in data_no_id
        print(f"{PASS} to_dict(exclude=[...]) works correctly")

        return True

    except Exception as e:
        print(f"{FAIL} Serialization test failed: {str(e)}")
        logger.exception("Serialization error")
        return False


def cleanup():
    """Close database connections"""
    print("\n" + "=" * 60)
    print("CLEANUP")
    print("=" * 60)

    try:
        from app.database.platform_connection import platform_db
        platform_db.close()
        print(f"{PASS} Database connections closed")
    except Exception as e:
        print(f"[!] Cleanup warning: {str(e)}")


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("  PLATFORM DATABASE TEST SUITE")
    print("  OryggiAI Multi-Tenant SaaS Platform")
    print("=" * 60)

    results = {}

    # Run tests
    results["imports"] = test_imports()

    if results["imports"]:
        results["connection"] = test_connection()

        if results["connection"]:
            results["tables"] = test_tables_exist()

            if results["tables"]:
                results["crud"] = test_model_operations()
                results["serialization"] = test_to_dict()

    # Cleanup
    cleanup()

    # Summary
    print("\n" + "=" * 60)
    print("  TEST SUMMARY")
    print("=" * 60)

    all_passed = True
    for test_name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        icon = PASS if passed else FAIL
        print(f"  {icon} {test_name.upper()}: {status}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print(f"\n{PASS} ALL TESTS PASSED!")
        print("\nPlatform database is ready for use.")
        print("Next step: Run Step 2 - Security Module")
        return 0
    else:
        print(f"\n{FAIL} SOME TESTS FAILED!")
        print("\nPlease check the errors above and:")
        print("1. Ensure SQL Server is running")
        print("2. Run the migration script: database/migrations/001_create_platform_database.sql")
        print("3. Check connection settings in .env file")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
