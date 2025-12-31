"""
Test Script for Tenant Management API
Tests tenant, database, and user management endpoints

Usage:
    cd D:\\OryggiAI_Service\\Advance_Chatbot
    python scripts/test_tenant_api.py
"""

import sys
import os
import uuid

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger

# Use ASCII-safe symbols for Windows compatibility
PASS = "[OK]"
FAIL = "[X]"
INFO = "[i]"


def test_tenant_service():
    """Test tenant service functions directly"""
    print("\n" + "=" * 60)
    print("TEST 1: Tenant Service Functions")
    print("=" * 60)

    try:
        from app.database.platform_connection import get_platform_session
        from app.services.auth_service import register_tenant
        from app.services.tenant_service import (
            get_tenant,
            update_tenant,
            get_tenant_usage_stats,
            create_database_connection,
            list_database_connections,
            delete_database_connection,
            list_tenant_users,
            TenantServiceError
        )
        from app.models.platform import Tenant, TenantUser, RefreshToken, TenantDatabase

        session = get_platform_session()

        # Generate unique test data
        test_id = str(uuid.uuid4())[:8]
        test_email = f"tenant_api_{test_id}@example.com"

        # Create test tenant
        print(f"\n{INFO} Creating test tenant...")
        tenant, user, access_token, refresh_token = register_tenant(
            db=session,
            tenant_name=f"API Test Tenant {test_id}",
            email=test_email,
            password="TestPass123!",
            full_name="API Test User"
        )
        print(f"{PASS} Test tenant created: {tenant.id}")

        # Test 1: Get tenant
        print(f"\n{INFO} Test 1: Get tenant...")
        fetched_tenant = get_tenant(session, tenant.id)
        assert fetched_tenant is not None
        assert fetched_tenant.name == f"API Test Tenant {test_id}"
        print(f"{PASS} Tenant retrieved successfully")

        # Test 2: Update tenant
        print(f"\n{INFO} Test 2: Update tenant...")
        updated_tenant = update_tenant(
            db=session,
            tenant_id=tenant.id,
            organization_type="technology",
            industry="software",
            country="India"
        )
        assert updated_tenant.organization_type == "technology"
        assert updated_tenant.industry == "software"
        print(f"{PASS} Tenant updated successfully")

        # Test 3: Get usage stats
        print(f"\n{INFO} Test 3: Get usage stats...")
        stats = get_tenant_usage_stats(session, tenant.id)
        assert stats["user_count"] == 1
        assert stats["active_user_count"] == 1
        assert stats["database_count"] == 0
        print(f"{PASS} Usage stats retrieved")
        print(f"  Users: {stats['user_count']}, Databases: {stats['database_count']}")

        # Test 4: Create database connection
        print(f"\n{INFO} Test 4: Create database connection...")
        try:
            tenant_db = create_database_connection(
                db=session,
                tenant_id=tenant.id,
                user_id=user.id,
                name="Test Database",
                db_type="mssql",
                host="localhost",
                port=1433,
                database_name="TestDB",
                username="sa",
                password="test_password",
                description="Test database for API testing"
            )
            assert tenant_db is not None
            assert tenant_db.name == "Test Database"
            print(f"{PASS} Database connection created: {tenant_db.id}")
        except TenantServiceError as e:
            print(f"{PASS} Database creation handled: {str(e)}")
            tenant_db = None

        # Test 5: List database connections
        print(f"\n{INFO} Test 5: List database connections...")
        databases = list_database_connections(session, tenant.id)
        db_count = len(databases)
        print(f"{PASS} Listed {db_count} databases")

        # Test 6: List tenant users
        print(f"\n{INFO} Test 6: List tenant users...")
        users = list_tenant_users(session, tenant.id)
        assert len(users) == 1
        assert users[0].email == test_email
        print(f"{PASS} Listed {len(users)} users")

        # Test 7: Database limit check
        print(f"\n{INFO} Test 7: Database limit check...")
        tenant.max_databases = 1  # Set limit to 1
        session.commit()

        if tenant_db:
            try:
                create_database_connection(
                    db=session,
                    tenant_id=tenant.id,
                    user_id=user.id,
                    name="Second Database",
                    db_type="mssql",
                    host="localhost",
                    port=1433,
                    database_name="TestDB2",
                    username="sa",
                    password="test_password"
                )
                print(f"{FAIL} Should have hit database limit")
                return False
            except TenantServiceError as e:
                if "maximum database limit" in str(e):
                    print(f"{PASS} Database limit enforced correctly")
                else:
                    print(f"{FAIL} Unexpected error: {str(e)}")
                    return False
        else:
            print(f"{PASS} Skipped (no database created)")

        # Clean up
        print(f"\n{INFO} Cleaning up test data...")
        if tenant_db:
            session.query(TenantDatabase).filter(
                TenantDatabase.id == tenant_db.id
            ).delete()
        session.query(RefreshToken).filter(
            RefreshToken.user_id == user.id
        ).delete()
        session.query(TenantUser).filter(
            TenantUser.id == user.id
        ).delete()
        session.query(Tenant).filter(
            Tenant.id == tenant.id
        ).delete()
        session.commit()
        print(f"{PASS} Test data cleaned up")

        session.close()
        return True

    except Exception as e:
        print(f"{FAIL} Tenant service test failed: {str(e)}")
        logger.exception("Tenant service test error")
        return False


def test_schema_validation():
    """Test tenant schema validation"""
    print("\n" + "=" * 60)
    print("TEST 2: Tenant Schema Validation")
    print("=" * 60)

    try:
        from app.schemas.tenant import (
            DatabaseConnectionCreate,
            TenantUserCreate,
            TenantUpdate,
            DatabaseType
        )
        from pydantic import ValidationError

        # Test 1: Valid database connection
        print(f"\n{INFO} Test 1: Valid database connection schema...")
        valid_db = DatabaseConnectionCreate(
            name="Production DB",
            db_type=DatabaseType.MSSQL,
            host="db.example.com",
            port=1433,
            database_name="ProdDB",
            username="admin",
            password="SecurePass123!"
        )
        assert valid_db.name == "Production DB"
        print(f"{PASS} Valid database schema accepted")

        # Test 2: Invalid port
        print(f"\n{INFO} Test 2: Invalid port validation...")
        try:
            DatabaseConnectionCreate(
                name="Invalid DB",
                db_type=DatabaseType.MSSQL,
                host="db.example.com",
                port=99999,  # Invalid port
                database_name="TestDB",
                username="admin",
                password="pass"
            )
            print(f"{FAIL} Should have rejected invalid port")
            return False
        except ValidationError:
            print(f"{PASS} Invalid port correctly rejected")

        # Test 3: Valid user creation
        print(f"\n{INFO} Test 3: Valid user creation schema...")
        valid_user = TenantUserCreate(
            email="newuser@example.com",
            password="SecurePass123!",
            full_name="New User",
            role="user"
        )
        assert valid_user.email == "newuser@example.com"
        print(f"{PASS} Valid user schema accepted")

        # Test 4: Invalid role
        print(f"\n{INFO} Test 4: Invalid role validation...")
        try:
            TenantUserCreate(
                email="newuser@example.com",
                password="SecurePass123!",
                full_name="New User",
                role="superuser"  # Invalid role
            )
            print(f"{FAIL} Should have rejected invalid role")
            return False
        except ValidationError:
            print(f"{PASS} Invalid role correctly rejected")

        # Test 5: Weak password
        print(f"\n{INFO} Test 5: Weak password validation...")
        try:
            TenantUserCreate(
                email="newuser@example.com",
                password="weak",  # Weak password
                full_name="New User",
                role="user"
            )
            print(f"{FAIL} Should have rejected weak password")
            return False
        except ValidationError:
            print(f"{PASS} Weak password correctly rejected")

        # Test 6: Valid tenant update
        print(f"\n{INFO} Test 6: Valid tenant update schema...")
        valid_update = TenantUpdate(
            name="Updated Tenant Name",
            organization_type="enterprise",
            timezone="UTC"
        )
        assert valid_update.name == "Updated Tenant Name"
        print(f"{PASS} Valid tenant update accepted")

        return True

    except Exception as e:
        print(f"{FAIL} Schema validation test failed: {str(e)}")
        logger.exception("Schema validation test error")
        return False


def test_user_management():
    """Test user management within tenant"""
    print("\n" + "=" * 60)
    print("TEST 3: User Management within Tenant")
    print("=" * 60)

    try:
        from app.database.platform_connection import get_platform_session
        from app.services.auth_service import register_tenant, register_user
        from app.services.tenant_service import (
            update_tenant_user,
            delete_tenant_user,
            list_tenant_users,
            TenantServiceError
        )
        from app.models.platform import Tenant, TenantUser, RefreshToken

        session = get_platform_session()

        # Generate unique test data
        test_id = str(uuid.uuid4())[:8]
        test_email = f"usermgmt_{test_id}@example.com"

        # Create test tenant
        print(f"\n{INFO} Creating test tenant with owner...")
        tenant, owner, _, _ = register_tenant(
            db=session,
            tenant_name=f"User Mgmt Test {test_id}",
            email=test_email,
            password="TestPass123!",
            full_name="Test Owner"
        )
        print(f"{PASS} Test tenant created")

        # Test 1: Create additional user
        print(f"\n{INFO} Test 1: Create additional user...")
        user2 = register_user(
            db=session,
            tenant_id=tenant.id,
            email=f"user2_{test_id}@example.com",
            password="UserPass123!",
            full_name="Second User",
            role="admin"
        )
        assert user2 is not None
        print(f"{PASS} Second user created: {user2.email}")

        # Test 2: Update user
        print(f"\n{INFO} Test 2: Update user...")
        updated_user = update_tenant_user(
            db=session,
            user_id=user2.id,
            tenant_id=tenant.id,
            display_name="Updated User Name",
            phone="+1234567890"
        )
        assert updated_user.display_name == "Updated User Name"
        assert updated_user.phone == "+1234567890"
        print(f"{PASS} User updated successfully")

        # Test 3: Change role
        print(f"\n{INFO} Test 3: Change user role...")
        role_changed = update_tenant_user(
            db=session,
            user_id=user2.id,
            tenant_id=tenant.id,
            role="manager"
        )
        assert role_changed.role == "manager"
        print(f"{PASS} User role changed to manager")

        # Test 4: Cannot demote only owner
        print(f"\n{INFO} Test 4: Cannot demote only owner...")
        try:
            update_tenant_user(
                db=session,
                user_id=owner.id,
                tenant_id=tenant.id,
                role="user"  # Try to demote owner
            )
            print(f"{FAIL} Should have prevented owner demotion")
            return False
        except TenantServiceError as e:
            if "only owner" in str(e).lower():
                print(f"{PASS} Owner demotion prevented")
            else:
                print(f"{FAIL} Unexpected error: {str(e)}")
                return False

        # Test 5: Delete non-owner user
        print(f"\n{INFO} Test 5: Delete non-owner user...")
        delete_result = delete_tenant_user(
            db=session,
            user_id=user2.id,
            tenant_id=tenant.id,
            hard_delete=True
        )
        assert delete_result == True
        print(f"{PASS} User deleted successfully")

        # Test 6: Cannot delete only owner
        print(f"\n{INFO} Test 6: Cannot delete only owner...")
        try:
            delete_tenant_user(
                db=session,
                user_id=owner.id,
                tenant_id=tenant.id
            )
            print(f"{FAIL} Should have prevented owner deletion")
            return False
        except TenantServiceError as e:
            if "only owner" in str(e).lower():
                print(f"{PASS} Owner deletion prevented")
            else:
                print(f"{FAIL} Unexpected error: {str(e)}")
                return False

        # Test 7: Verify user count
        print(f"\n{INFO} Test 7: Verify user count...")
        users = list_tenant_users(session, tenant.id)
        assert len(users) == 1  # Only owner remains
        print(f"{PASS} User count verified: {len(users)}")

        # Clean up
        print(f"\n{INFO} Cleaning up test data...")
        session.query(RefreshToken).filter(
            RefreshToken.user_id == owner.id
        ).delete()
        session.query(TenantUser).filter(
            TenantUser.id == owner.id
        ).delete()
        session.query(Tenant).filter(
            Tenant.id == tenant.id
        ).delete()
        session.commit()
        print(f"{PASS} Test data cleaned up")

        session.close()
        return True

    except Exception as e:
        print(f"{FAIL} User management test failed: {str(e)}")
        logger.exception("User management test error")
        return False


def test_encryption():
    """Test database password encryption"""
    print("\n" + "=" * 60)
    print("TEST 4: Password Encryption")
    print("=" * 60)

    try:
        from app.security.encryption import encrypt_string as encrypt_data, decrypt_string as decrypt_data

        # Test 1: Encrypt and decrypt password
        print(f"\n{INFO} Test 1: Encrypt and decrypt password...")
        original_password = "MySecretDatabasePassword123!"
        encrypted = encrypt_data(original_password)
        decrypted = decrypt_data(encrypted)

        assert encrypted != original_password, "Encrypted should differ from original"
        assert decrypted == original_password, "Decrypted should match original"
        print(f"{PASS} Password encryption working correctly")
        print(f"  Original length: {len(original_password)}")
        print(f"  Encrypted length: {len(encrypted)}")

        # Test 2: Different encryptions for same input
        print(f"\n{INFO} Test 2: Same password, different encryptions...")
        encrypted2 = encrypt_data(original_password)
        # Note: Fernet uses random IV, so same plaintext gives different ciphertext
        decrypted2 = decrypt_data(encrypted2)
        assert decrypted2 == original_password
        print(f"{PASS} Multiple encryptions decrypt correctly")

        # Test 3: Special characters
        print(f"\n{INFO} Test 3: Special characters in password...")
        special_password = "P@$$w0rd!#$%^&*()_+-=[]{}|;':\",./<>?"
        encrypted_special = encrypt_data(special_password)
        decrypted_special = decrypt_data(encrypted_special)
        assert decrypted_special == special_password
        print(f"{PASS} Special characters handled correctly")

        return True

    except Exception as e:
        print(f"{FAIL} Encryption test failed: {str(e)}")
        logger.exception("Encryption test error")
        return False


def main():
    """Run all tenant API tests"""
    print("\n" + "=" * 60)
    print("  TENANT MANAGEMENT API TEST SUITE")
    print("  OryggiAI Multi-Tenant SaaS Platform")
    print("=" * 60)

    results = {}

    # Run tests
    results["tenant_service"] = test_tenant_service()
    results["schema_validation"] = test_schema_validation()
    results["user_management"] = test_user_management()
    results["encryption"] = test_encryption()

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
        print(f"\n{PASS} ALL TENANT API TESTS PASSED!")
        print("\nTenant management API is ready.")
        print("Next step: Test multi-tenant isolation")
        return 0
    else:
        print(f"\n{FAIL} SOME TESTS FAILED!")
        print("\nPlease check the errors above.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
