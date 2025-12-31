"""
Test Script for Tenant Context Middleware
Tests tenant isolation and context management

Usage:
    cd D:\\OryggiAI_Service\\Advance_Chatbot
    python scripts/test_tenant_context.py
"""

import sys
import os
import uuid
import asyncio

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


def test_tenant_context_basic():
    """Test basic tenant context operations"""
    print("\n" + "=" * 60)
    print("TEST 1: Basic Tenant Context Operations")
    print("=" * 60)

    try:
        from app.middleware.tenant_context import TenantContext

        # Generate test IDs
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()

        # Test 1: Context should not be set initially
        print(f"\n{INFO} Test 1: Initial context state...")
        assert TenantContext.get_tenant_id() is None, "Tenant ID should be None initially"
        assert TenantContext.get_user_id() is None, "User ID should be None initially"
        assert not TenantContext.is_set(), "Context should not be set"
        print(f"{PASS} Initial context is empty")

        # Test 2: Set context
        print(f"\n{INFO} Test 2: Set tenant context...")
        TenantContext.set_current(tenant_id, user_id)
        assert TenantContext.get_tenant_id() == tenant_id, "Tenant ID should match"
        assert TenantContext.get_user_id() == user_id, "User ID should match"
        assert TenantContext.is_set(), "Context should be set"
        print(f"{PASS} Tenant context set correctly")
        print(f"  Tenant ID: {tenant_id}")
        print(f"  User ID: {user_id}")

        # Test 3: Require methods
        print(f"\n{INFO} Test 3: Require methods...")
        assert TenantContext.require_tenant_id() == tenant_id
        assert TenantContext.require_user_id() == user_id
        print(f"{PASS} Require methods work correctly")

        # Test 4: Clear context
        print(f"\n{INFO} Test 4: Clear context...")
        TenantContext.clear()
        assert TenantContext.get_tenant_id() is None, "Tenant ID should be None after clear"
        assert TenantContext.get_user_id() is None, "User ID should be None after clear"
        assert not TenantContext.is_set(), "Context should not be set after clear"
        print(f"{PASS} Context cleared successfully")

        # Test 5: Require methods should raise error when not set
        print(f"\n{INFO} Test 5: Require methods without context...")
        try:
            TenantContext.require_tenant_id()
            print(f"{FAIL} Should have raised RuntimeError")
            return False
        except RuntimeError as e:
            print(f"{PASS} Correctly raised RuntimeError: {str(e)}")

        return True

    except Exception as e:
        print(f"{FAIL} Basic context test failed: {str(e)}")
        logger.exception("Basic context test error")
        return False


def test_tenant_scoped_query():
    """Test tenant-scoped query helper"""
    print("\n" + "=" * 60)
    print("TEST 2: Tenant-Scoped Query Helper")
    print("=" * 60)

    try:
        from app.middleware.tenant_context import TenantContext, tenant_scoped_query
        from app.database.platform_connection import get_platform_session
        from app.models.platform import TenantUser

        # Set context
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        TenantContext.set_current(tenant_id, user_id)

        # Create session
        session = get_platform_session()

        # Test tenant-scoped query
        print(f"\n{INFO} Test 1: Create tenant-scoped query...")
        try:
            query = tenant_scoped_query(
                session.query(TenantUser),
                TenantUser
            )
            # Execute to check it works (may return no results, that's ok)
            results = query.all()
            print(f"{PASS} Tenant-scoped query executed successfully")
            print(f"  Results: {len(results)} users for tenant {tenant_id}")
        except Exception as e:
            print(f"{FAIL} Query failed: {str(e)}")
            return False

        # Test without context
        print(f"\n{INFO} Test 2: Query without tenant context...")
        TenantContext.clear()
        try:
            query = tenant_scoped_query(
                session.query(TenantUser),
                TenantUser
            )
            print(f"{FAIL} Should have raised RuntimeError")
            return False
        except RuntimeError as e:
            print(f"{PASS} Correctly raised RuntimeError: {str(e)}")

        session.close()
        return True

    except Exception as e:
        print(f"{FAIL} Tenant-scoped query test failed: {str(e)}")
        logger.exception("Tenant-scoped query test error")
        return False


def test_tenant_access_validation():
    """Test tenant access validation"""
    print("\n" + "=" * 60)
    print("TEST 3: Tenant Access Validation")
    print("=" * 60)

    try:
        from app.middleware.tenant_context import TenantContext, validate_tenant_access

        # Set up context
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        TenantContext.set_current(tenant_id, user_id)

        # Test 1: Access own resource
        print(f"\n{INFO} Test 1: Access own tenant's resource...")
        try:
            result = validate_tenant_access(tenant_id)
            assert result == True, "Should return True for own resource"
            print(f"{PASS} Access to own resource allowed")
        except PermissionError:
            print(f"{FAIL} Should have allowed access")
            return False

        # Test 2: Access another tenant's resource
        print(f"\n{INFO} Test 2: Access another tenant's resource...")
        other_tenant_id = uuid.uuid4()
        try:
            validate_tenant_access(other_tenant_id)
            print(f"{FAIL} Should have raised PermissionError")
            return False
        except PermissionError as e:
            print(f"{PASS} Correctly denied access: {str(e)}")

        # Test 3: Access without context
        print(f"\n{INFO} Test 3: Access validation without context...")
        TenantContext.clear()
        try:
            validate_tenant_access(tenant_id)
            print(f"{FAIL} Should have raised RuntimeError")
            return False
        except RuntimeError as e:
            print(f"{PASS} Correctly raised RuntimeError: {str(e)}")

        return True

    except Exception as e:
        print(f"{FAIL} Access validation test failed: {str(e)}")
        logger.exception("Access validation test error")
        return False


def test_tenant_database_resolver():
    """Test tenant database resolver"""
    print("\n" + "=" * 60)
    print("TEST 4: Tenant Database Resolver")
    print("=" * 60)

    try:
        from app.middleware.tenant_context import TenantContext, TenantDatabaseResolver
        from app.database.platform_connection import get_platform_session
        from app.services.auth_service import register_tenant
        from app.models.platform import Tenant, TenantUser, RefreshToken, TenantDatabase

        # Create test tenant
        session = get_platform_session()
        test_id = str(uuid.uuid4())[:8]
        test_email = f"resolver_{test_id}@example.com"

        print(f"\n{INFO} Creating test tenant...")
        tenant, user, _, _ = register_tenant(
            db=session,
            tenant_name=f"Resolver Test {test_id}",
            email=test_email,
            password="TestPass123!",
            full_name="Test User"
        )
        print(f"{PASS} Test tenant created: {tenant.id}")

        # Set context to this tenant
        TenantContext.set_current(tenant.id, user.id, tenant)

        # Create resolver
        resolver = TenantDatabaseResolver(session)

        # Test 1: Get tenant databases (should be empty initially)
        print(f"\n{INFO} Test 1: Get tenant databases...")
        databases = resolver.get_tenant_databases()
        print(f"{PASS} Got {len(databases)} databases for tenant")

        # Test 2: Get default database (should be None initially)
        print(f"\n{INFO} Test 2: Get default database...")
        default_db = resolver.get_default_database()
        if default_db is None:
            print(f"{PASS} No default database configured (expected)")
        else:
            print(f"{PASS} Default database: {default_db.name}")

        # Test 3: Get database by name (should be None)
        print(f"\n{INFO} Test 3: Get database by name...")
        db_by_name = resolver.get_database_by_name("test_db")
        if db_by_name is None:
            print(f"{PASS} No database named 'test_db' found (expected)")
        else:
            print(f"{PASS} Found database: {db_by_name.name}")

        # Clean up
        print(f"\n{INFO} Cleaning up test data...")
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
        TenantContext.clear()

        return True

    except Exception as e:
        print(f"{FAIL} Database resolver test failed: {str(e)}")
        logger.exception("Database resolver test error")
        return False


def test_tenant_audit_logger():
    """Test tenant audit logger"""
    print("\n" + "=" * 60)
    print("TEST 5: Tenant Audit Logger")
    print("=" * 60)

    try:
        from app.middleware.tenant_context import TenantContext, TenantAuditLogger

        # Set context
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        TenantContext.set_current(tenant_id, user_id)

        # Test logging with context
        print(f"\n{INFO} Test 1: Log audit event with context...")
        TenantAuditLogger.log(
            action="create",
            resource_type="test_resource",
            resource_id="test-123",
            details={"test_key": "test_value"}
        )
        print(f"{PASS} Audit event logged with context")

        # Test logging without context
        print(f"\n{INFO} Test 2: Log audit event without context...")
        TenantContext.clear()
        TenantAuditLogger.log(
            action="anonymous_action",
            resource_type="test_resource",
            resource_id="test-456"
        )
        print(f"{PASS} Audit event logged without context")

        return True

    except Exception as e:
        print(f"{FAIL} Audit logger test failed: {str(e)}")
        logger.exception("Audit logger test error")
        return False


def test_context_isolation():
    """Test context isolation between operations"""
    print("\n" + "=" * 60)
    print("TEST 6: Context Isolation")
    print("=" * 60)

    try:
        from app.middleware.tenant_context import TenantContext

        # Test multiple context switches
        print(f"\n{INFO} Test 1: Multiple context switches...")

        tenant1 = uuid.uuid4()
        user1 = uuid.uuid4()
        tenant2 = uuid.uuid4()
        user2 = uuid.uuid4()

        # Set first context
        TenantContext.set_current(tenant1, user1)
        assert TenantContext.get_tenant_id() == tenant1
        print(f"  Set context 1: tenant={tenant1}")

        # Switch to second context
        TenantContext.set_current(tenant2, user2)
        assert TenantContext.get_tenant_id() == tenant2
        assert TenantContext.get_user_id() == user2
        print(f"  Set context 2: tenant={tenant2}")

        # Verify first context is overwritten
        assert TenantContext.get_tenant_id() != tenant1
        print(f"{PASS} Context properly switches between tenants")

        # Clear and verify
        TenantContext.clear()
        assert TenantContext.get_tenant_id() is None
        print(f"{PASS} Context properly cleared")

        return True

    except Exception as e:
        print(f"{FAIL} Context isolation test failed: {str(e)}")
        logger.exception("Context isolation test error")
        return False


def main():
    """Run all tenant context tests"""
    print("\n" + "=" * 60)
    print("  TENANT CONTEXT MIDDLEWARE TEST SUITE")
    print("  OryggiAI Multi-Tenant SaaS Platform")
    print("=" * 60)

    # Ensure context is clear at start
    from app.middleware.tenant_context import TenantContext
    TenantContext.clear()

    results = {}

    # Run tests
    results["basic_context"] = test_tenant_context_basic()
    results["scoped_query"] = test_tenant_scoped_query()
    results["access_validation"] = test_tenant_access_validation()
    results["database_resolver"] = test_tenant_database_resolver()
    results["audit_logger"] = test_tenant_audit_logger()
    results["context_isolation"] = test_context_isolation()

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
        print(f"\n{PASS} ALL TENANT CONTEXT TESTS PASSED!")
        print("\nTenant context middleware is ready.")
        print("Next step: Create tenant management API")
        return 0
    else:
        print(f"\n{FAIL} SOME TESTS FAILED!")
        print("\nPlease check the errors above.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
