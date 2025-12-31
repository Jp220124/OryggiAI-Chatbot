"""
Test Script for Authentication Flow
Tests the complete authentication cycle: register, login, refresh, logout

Usage:
    cd D:\\OryggiAI_Service\\Advance_Chatbot
    python scripts/test_auth_flow.py
"""

import sys
import os
import uuid
import time

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


def test_auth_service():
    """Test authentication service functions directly"""
    print("\n" + "=" * 60)
    print("TEST 1: Authentication Service (Direct)")
    print("=" * 60)

    try:
        from app.database.platform_connection import get_platform_session
        from app.services.auth_service import (
            register_tenant,
            authenticate_user,
            refresh_access_token,
            logout_user,
            change_password,
            RegistrationError,
            AuthenticationError
        )
        from app.security.jwt_handler import verify_token, TokenType

        # Create a test session
        session = get_platform_session()

        # Generate unique test data
        test_id = str(uuid.uuid4())[:8]
        test_email = f"test_{test_id}@example.com"
        test_password = "TestPass123!"
        test_tenant_name = f"Test Tenant {test_id}"

        print(f"\n{INFO} Test data:")
        print(f"  Email: {test_email}")
        print(f"  Tenant: {test_tenant_name}")

        # Test 1: Register tenant
        print(f"\n{INFO} Test 1: Register new tenant...")
        tenant, user, access_token, refresh_token = register_tenant(
            db=session,
            tenant_name=test_tenant_name,
            email=test_email,
            password=test_password,
            full_name="Test User"
        )

        assert tenant is not None, "Tenant should be created"
        assert user is not None, "User should be created"
        assert access_token, "Access token should be generated"
        assert refresh_token, "Refresh token should be generated"
        print(f"{PASS} Tenant registered successfully")
        print(f"  Tenant ID: {tenant.id}")
        print(f"  User ID: {user.id}")
        print(f"  Role: {user.role}")

        # Test 2: Verify access token
        print(f"\n{INFO} Test 2: Verify access token...")
        payload = verify_token(access_token, TokenType.ACCESS)
        assert payload is not None, "Token should be valid"
        assert payload.email == test_email, "Email should match"
        assert payload.role == "owner", "Role should be owner"
        print(f"{PASS} Access token verified")
        print(f"  Subject: {payload.sub}")
        print(f"  Tenant: {payload.tenant_id}")

        # Test 3: Login with credentials
        print(f"\n{INFO} Test 3: Login with credentials...")
        logged_user, logged_tenant, new_access, new_refresh = authenticate_user(
            db=session,
            email=test_email,
            password=test_password
        )
        assert logged_user.id == user.id, "User ID should match"
        assert logged_tenant.id == tenant.id, "Tenant ID should match"
        print(f"{PASS} Login successful")
        print(f"  User: {logged_user.email}")
        print(f"  Last login updated: {logged_user.last_login_at}")

        # Test 4: Wrong password should fail
        print(f"\n{INFO} Test 4: Wrong password login...")
        try:
            authenticate_user(
                db=session,
                email=test_email,
                password="WrongPassword123!"
            )
            print(f"{FAIL} Should have raised AuthenticationError")
            return False
        except AuthenticationError as e:
            print(f"{PASS} Wrong password correctly rejected")
            print(f"  Error: {str(e)}")

        # Test 5: Refresh token
        print(f"\n{INFO} Test 5: Refresh access token...")
        refreshed_access, refreshed_refresh = refresh_access_token(
            db=session,
            refresh_token_str=new_refresh
        )
        assert refreshed_access, "New access token should be generated"
        assert refreshed_refresh, "New refresh token should be generated"
        print(f"{PASS} Token refresh successful")

        # Test 6: Old refresh token should be invalid (token rotation)
        print(f"\n{INFO} Test 6: Old refresh token should be invalid...")
        try:
            refresh_access_token(
                db=session,
                refresh_token_str=new_refresh  # Old token
            )
            print(f"{FAIL} Old refresh token should have been revoked")
            return False
        except AuthenticationError:
            print(f"{PASS} Old refresh token correctly rejected")

        # Test 7: Change password
        print(f"\n{INFO} Test 7: Change password...")
        new_password = "NewTestPass456!"
        success = change_password(
            db=session,
            user_id=user.id,
            current_password=test_password,
            new_password=new_password
        )
        assert success, "Password change should succeed"
        print(f"{PASS} Password changed successfully")

        # Test 8: Login with new password
        print(f"\n{INFO} Test 8: Login with new password...")
        _, _, _, _ = authenticate_user(
            db=session,
            email=test_email,
            password=new_password
        )
        print(f"{PASS} Login with new password successful")

        # Test 9: Old password should fail
        print(f"\n{INFO} Test 9: Old password should fail...")
        try:
            authenticate_user(
                db=session,
                email=test_email,
                password=test_password  # Old password
            )
            print(f"{FAIL} Old password should have been rejected")
            return False
        except AuthenticationError:
            print(f"{PASS} Old password correctly rejected")

        # Test 10: Logout
        print(f"\n{INFO} Test 10: Logout user...")
        success = logout_user(
            db=session,
            user_id=user.id
        )
        assert success, "Logout should succeed"
        print(f"{PASS} User logged out successfully")

        # Clean up: Delete test data
        print(f"\n{INFO} Cleaning up test data...")
        from app.models.platform import Tenant, TenantUser, RefreshToken
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
        print(f"{FAIL} Auth service test failed: {str(e)}")
        logger.exception("Auth service test error")
        return False


def test_duplicate_registration():
    """Test duplicate email registration prevention"""
    print("\n" + "=" * 60)
    print("TEST 2: Duplicate Registration Prevention")
    print("=" * 60)

    try:
        from app.database.platform_connection import get_platform_session
        from app.services.auth_service import (
            register_tenant,
            RegistrationError
        )
        from app.models.platform import Tenant, TenantUser, RefreshToken

        session = get_platform_session()

        # Generate unique test data
        test_id = str(uuid.uuid4())[:8]
        test_email = f"dup_{test_id}@example.com"

        # Register first tenant
        print(f"\n{INFO} Register first tenant...")
        tenant, user, _, _ = register_tenant(
            db=session,
            tenant_name=f"First Tenant {test_id}",
            email=test_email,
            password="TestPass123!",
            full_name="First User"
        )
        print(f"{PASS} First tenant registered")

        # Try to register with same email
        print(f"\n{INFO} Attempt duplicate registration...")
        try:
            register_tenant(
                db=session,
                tenant_name=f"Second Tenant {test_id}",
                email=test_email,  # Same email
                password="TestPass456!",
                full_name="Second User"
            )
            print(f"{FAIL} Should have raised RegistrationError")
            return False
        except RegistrationError as e:
            print(f"{PASS} Duplicate email correctly rejected")
            print(f"  Error: {str(e)}")

        # Clean up
        print(f"\n{INFO} Cleaning up...")
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
        print(f"{FAIL} Duplicate registration test failed: {str(e)}")
        logger.exception("Duplicate registration test error")
        return False


def test_token_validation():
    """Test JWT token validation scenarios"""
    print("\n" + "=" * 60)
    print("TEST 3: Token Validation Scenarios")
    print("=" * 60)

    try:
        from app.security.jwt_handler import (
            create_access_token,
            create_refresh_token,
            verify_token,
            decode_token,
            is_token_expired,
            TokenType
        )
        from datetime import timedelta

        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()

        # Test 1: Create and verify access token
        print(f"\n{INFO} Test 1: Valid access token...")
        access_token = create_access_token(
            user_id=user_id,
            tenant_id=tenant_id,
            email="test@example.com",
            role="admin"
        )
        payload = verify_token(access_token, TokenType.ACCESS)
        assert payload is not None, "Token should be valid"
        print(f"{PASS} Valid access token verified")

        # Test 2: Access token with wrong type should fail
        print(f"\n{INFO} Test 2: Access token with wrong type check...")
        payload = verify_token(access_token, TokenType.REFRESH)
        assert payload is None, "Should reject access token as refresh"
        print(f"{PASS} Type mismatch correctly rejected")

        # Test 3: Create expired token
        print(f"\n{INFO} Test 3: Expired token check...")
        expired_token = create_access_token(
            user_id=user_id,
            tenant_id=tenant_id,
            email="test@example.com",
            role="admin",
            expires_delta=timedelta(seconds=-10)  # Already expired
        )
        assert is_token_expired(expired_token), "Token should be expired"
        print(f"{PASS} Expired token correctly detected")

        # Test 4: Decode expired token without verification
        print(f"\n{INFO} Test 4: Decode expired token without verification...")
        payload = decode_token(expired_token, verify_exp=False)
        assert payload is not None, "Should decode expired token"
        assert payload["email"] == "test@example.com"
        print(f"{PASS} Expired token decoded without verification")

        # Test 5: Invalid token
        print(f"\n{INFO} Test 5: Invalid token...")
        assert is_token_expired("invalid.token.here"), "Invalid should be treated as expired"
        print(f"{PASS} Invalid token correctly rejected")

        # Test 6: Refresh token
        print(f"\n{INFO} Test 6: Refresh token creation...")
        refresh_token, token_hash, expires_at = create_refresh_token(
            user_id=user_id,
            tenant_id=tenant_id
        )
        assert refresh_token, "Refresh token should be created"
        assert len(token_hash) == 64, "Token hash should be SHA-256 (64 chars)"
        assert expires_at is not None, "Expiry should be set"
        print(f"{PASS} Refresh token created")
        print(f"  Hash length: {len(token_hash)}")

        return True

    except Exception as e:
        print(f"{FAIL} Token validation test failed: {str(e)}")
        logger.exception("Token validation test error")
        return False


def test_schema_validation():
    """Test Pydantic schema validation"""
    print("\n" + "=" * 60)
    print("TEST 4: Schema Validation")
    print("=" * 60)

    try:
        from app.schemas.auth import (
            TenantRegistrationRequest,
            LoginRequest,
            PasswordChangeRequest
        )
        from pydantic import ValidationError

        # Test 1: Valid registration request
        print(f"\n{INFO} Test 1: Valid registration request...")
        valid_request = TenantRegistrationRequest(
            tenant_name="Test Company",
            email="valid@example.com",
            password="SecurePass123!",
            full_name="John Doe"
        )
        print(f"{PASS} Valid registration accepted")

        # Test 2: Weak password should fail
        print(f"\n{INFO} Test 2: Weak password validation...")
        try:
            TenantRegistrationRequest(
                tenant_name="Test Company",
                email="valid@example.com",
                password="weak",  # Too weak
                full_name="John Doe"
            )
            print(f"{FAIL} Should have rejected weak password")
            return False
        except ValidationError as e:
            print(f"{PASS} Weak password correctly rejected")
            print(f"  Errors: {len(e.errors())}")

        # Test 3: Invalid email should fail
        print(f"\n{INFO} Test 3: Invalid email validation...")
        try:
            LoginRequest(
                email="not-an-email",
                password="SomePassword123!"
            )
            print(f"{FAIL} Should have rejected invalid email")
            return False
        except ValidationError:
            print(f"{PASS} Invalid email correctly rejected")

        # Test 4: Invalid slug format
        print(f"\n{INFO} Test 4: Invalid slug validation...")
        try:
            TenantRegistrationRequest(
                tenant_name="Test Company",
                tenant_slug="Invalid Slug!",  # Contains space and special char
                email="valid@example.com",
                password="SecurePass123!",
                full_name="John Doe"
            )
            print(f"{FAIL} Should have rejected invalid slug")
            return False
        except ValidationError:
            print(f"{PASS} Invalid slug correctly rejected")

        # Test 5: Valid slug
        print(f"\n{INFO} Test 5: Valid slug validation...")
        valid_slug_request = TenantRegistrationRequest(
            tenant_name="Test Company",
            tenant_slug="valid-slug-123",
            email="valid@example.com",
            password="SecurePass123!",
            full_name="John Doe"
        )
        assert valid_slug_request.tenant_slug == "valid-slug-123"
        print(f"{PASS} Valid slug accepted")

        return True

    except Exception as e:
        print(f"{FAIL} Schema validation test failed: {str(e)}")
        logger.exception("Schema validation test error")
        return False


def main():
    """Run all authentication tests"""
    print("\n" + "=" * 60)
    print("  AUTHENTICATION FLOW TEST SUITE")
    print("  OryggiAI Multi-Tenant SaaS Platform")
    print("=" * 60)

    results = {}

    # Run tests
    results["auth_service"] = test_auth_service()
    results["duplicate_check"] = test_duplicate_registration()
    results["token_validation"] = test_token_validation()
    results["schema_validation"] = test_schema_validation()

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
        print(f"\n{PASS} ALL AUTHENTICATION TESTS PASSED!")
        print("\nAuthentication system is ready.")
        print("Next step: Create tenant context middleware")
        return 0
    else:
        print(f"\n{FAIL} SOME TESTS FAILED!")
        print("\nPlease check the errors above.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
