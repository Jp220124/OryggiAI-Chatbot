"""
Test Script for Security Module
Run this script to verify password hashing, JWT, and encryption are working correctly.

Usage:
    cd D:\\OryggiAI_Service\\Advance_Chatbot
    python scripts/test_security.py
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


def test_password_hashing():
    """Test password hashing and verification"""
    print("\n" + "=" * 60)
    print("TEST 1: Password Hashing (bcrypt)")
    print("=" * 60)

    try:
        from app.security.password import (
            hash_password, verify_password,
            generate_random_password, check_password_strength
        )

        # Test 1: Hash a password
        password = "MySecurePassword123!"
        hashed = hash_password(password)

        assert hashed.startswith("$2b$"), "Hash should be bcrypt format"
        print(f"{PASS} Password hashed successfully")
        print(f"  Hash format: {hashed[:20]}...")

        # Test 2: Verify correct password
        assert verify_password(password, hashed), "Password verification should pass"
        print(f"{PASS} Password verification passed")

        # Test 3: Verify wrong password
        assert not verify_password("WrongPassword", hashed), "Wrong password should fail"
        print(f"{PASS} Wrong password correctly rejected")

        # Test 4: Generate random password
        random_pwd = generate_random_password(20, include_special=True)
        assert len(random_pwd) == 20, "Random password should be 20 characters"
        print(f"{PASS} Random password generated: {random_pwd[:10]}...")

        # Test 5: Password strength check
        strength = check_password_strength("weak")
        assert not strength["is_strong"], "Weak password should not be strong"
        print(f"{PASS} Password strength check works")
        print(f"  'weak' score: {strength['score']}/5")

        strength = check_password_strength("MyStr0ng!Pass")
        assert strength["is_strong"], "Strong password should be detected"
        print(f"  'MyStr0ng!Pass' score: {strength['score']}/5")

        return True

    except Exception as e:
        print(f"{FAIL} Password test failed: {str(e)}")
        logger.exception("Password test error")
        return False


def test_jwt_tokens():
    """Test JWT token creation and verification"""
    print("\n" + "=" * 60)
    print("TEST 2: JWT Token Management")
    print("=" * 60)

    try:
        from app.security.jwt_handler import (
            create_access_token, create_refresh_token,
            verify_token, decode_token,
            TokenType, is_token_expired,
            extract_user_id, extract_tenant_id
        )

        # Test data
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        email = "test@example.com"
        role = "admin"

        # Test 1: Create access token
        access_token = create_access_token(
            user_id=user_id,
            tenant_id=tenant_id,
            email=email,
            role=role
        )
        assert access_token, "Access token should be created"
        print(f"{PASS} Access token created")
        print(f"  Token: {access_token[:50]}...")

        # Test 2: Verify access token
        payload = verify_token(access_token, TokenType.ACCESS)
        assert payload is not None, "Token should be valid"
        assert payload.email == email, "Email should match"
        assert payload.role == role, "Role should match"
        print(f"{PASS} Access token verified")
        print(f"  User: {payload.email}, Role: {payload.role}")

        # Test 3: Extract user ID
        extracted_user_id = extract_user_id(access_token)
        assert extracted_user_id == user_id, "User ID should match"
        print(f"{PASS} User ID extracted correctly")

        # Test 4: Extract tenant ID
        extracted_tenant_id = extract_tenant_id(access_token)
        assert extracted_tenant_id == tenant_id, "Tenant ID should match"
        print(f"{PASS} Tenant ID extracted correctly")

        # Test 5: Create refresh token
        refresh_token, token_hash, expires_at = create_refresh_token(
            user_id=user_id,
            tenant_id=tenant_id
        )
        assert refresh_token, "Refresh token should be created"
        assert token_hash, "Token hash should be created"
        assert expires_at, "Expiry should be set"
        print(f"{PASS} Refresh token created")
        print(f"  Hash: {token_hash[:20]}...")
        print(f"  Expires: {expires_at}")

        # Test 6: Verify refresh token
        refresh_payload = verify_token(refresh_token, TokenType.REFRESH)
        assert refresh_payload is not None, "Refresh token should be valid"
        print(f"{PASS} Refresh token verified")

        # Test 7: Token expiry check
        assert not is_token_expired(access_token), "Token should not be expired"
        print(f"{PASS} Token expiry check works")

        # Test 8: Decode token without verification
        decoded = decode_token(access_token, verify_exp=False)
        assert decoded is not None, "Token should be decodable"
        assert decoded["email"] == email, "Decoded email should match"
        print(f"{PASS} Token decode (no verify) works")

        return True

    except Exception as e:
        print(f"{FAIL} JWT test failed: {str(e)}")
        logger.exception("JWT test error")
        return False


def test_encryption():
    """Test string encryption and decryption"""
    print("\n" + "=" * 60)
    print("TEST 3: Fernet Encryption")
    print("=" * 60)

    try:
        from app.security.encryption import (
            encrypt_string, decrypt_string,
            encrypt_dict_values, decrypt_dict_values,
            generate_fernet_key, is_encrypted
        )

        # Test 1: Encrypt a string
        plaintext = "MyDatabasePassword123!"
        encrypted = encrypt_string(plaintext)

        assert encrypted != plaintext, "Encrypted should differ from plaintext"
        print(f"{PASS} String encrypted")
        print(f"  Original: {plaintext}")
        print(f"  Encrypted: {encrypted[:40]}...")

        # Test 2: Decrypt the string
        decrypted = decrypt_string(encrypted)
        assert decrypted == plaintext, "Decrypted should match original"
        print(f"{PASS} String decrypted correctly")

        # Test 3: Is encrypted check
        assert is_encrypted(encrypted), "Encrypted string should be detected"
        assert not is_encrypted(plaintext), "Plaintext should not be detected as encrypted"
        print(f"{PASS} Encryption detection works")

        # Test 4: Encrypt dictionary values
        db_config = {
            "host": "localhost",
            "port": 1433,
            "username": "admin",
            "password": "secret123"
        }
        encrypted_config = encrypt_dict_values(db_config, ["password"])

        assert encrypted_config["host"] == "localhost", "Host should be unchanged"
        assert encrypted_config["password"] != "secret123", "Password should be encrypted"
        print(f"{PASS} Dictionary values encrypted")

        # Test 5: Decrypt dictionary values
        decrypted_config = decrypt_dict_values(encrypted_config, ["password"])
        assert decrypted_config["password"] == "secret123", "Password should be decrypted"
        print(f"{PASS} Dictionary values decrypted")

        # Test 6: Generate new Fernet key
        new_key = generate_fernet_key()
        assert len(new_key) == 44, "Fernet key should be 44 characters"
        print(f"{PASS} New Fernet key generated")
        print(f"  Key: {new_key[:20]}...")

        # Test 7: Empty string handling
        assert encrypt_string("") == "", "Empty string should return empty"
        assert decrypt_string("") == "", "Empty decrypt should return empty"
        print(f"{PASS} Empty string handling works")

        return True

    except Exception as e:
        print(f"{FAIL} Encryption test failed: {str(e)}")
        logger.exception("Encryption test error")
        return False


def main():
    """Run all security tests"""
    print("\n" + "=" * 60)
    print("  SECURITY MODULE TEST SUITE")
    print("  OryggiAI Multi-Tenant SaaS Platform")
    print("=" * 60)

    results = {}

    # Run tests
    results["password"] = test_password_hashing()
    results["jwt"] = test_jwt_tokens()
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
        print(f"\n{PASS} ALL SECURITY TESTS PASSED!")
        print("\nSecurity module is ready for use.")
        print("Next step: Create authentication API endpoints")
        return 0
    else:
        print(f"\n{FAIL} SOME TESTS FAILED!")
        print("\nPlease check the errors above.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
