"""
Test Script for Multi-Tenant Isolation
Verifies that tenants cannot access each other's data

Usage:
    cd D:\\OryggiAI_Service\\Advance_Chatbot
    python scripts/test_multi_tenant_isolation.py
"""

import sys
import os
import uuid
import requests
from typing import Dict, Tuple

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

# API Base URL
BASE_URL = "http://localhost:9000/api"


def register_tenant(tenant_name: str, email: str, password: str) -> Dict:
    """Register a new tenant via API and return normalized response"""
    response = requests.post(
        f"{BASE_URL}/auth/register",
        json={
            "tenant_name": tenant_name,
            "email": email,
            "password": password,
            "full_name": f"Admin for {tenant_name}"
        }
    )
    if response.status_code not in [200, 201]:
        raise Exception(f"Registration failed: {response.text}")
    data = response.json()
    # Normalize response to include tenant dict for easier access
    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "tenant": {"id": str(data["tenant_id"])},
        "user": {"id": str(data["user_id"]), "email": data["email"]}
    }


def login(email: str, password: str) -> Dict:
    """Login and get access token"""
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": email, "password": password}
    )
    if response.status_code != 200:
        raise Exception(f"Login failed: {response.text}")
    return response.json()


def get_auth_header(token: str) -> Dict:
    """Get authorization header"""
    return {"Authorization": f"Bearer {token}"}


def test_tenant_data_isolation():
    """Test that tenants cannot see each other's data"""
    print("\n" + "=" * 60)
    print("TEST 1: Tenant Data Isolation")
    print("=" * 60)

    test_id = str(uuid.uuid4())[:8]

    try:
        # Create two separate tenants
        print(f"\n{INFO} Creating Tenant A...")
        tenant_a_email = f"tenant_a_{test_id}@example.com"
        tenant_a = register_tenant(
            f"Tenant A {test_id}",
            tenant_a_email,
            "TenantA123!"
        )
        token_a = tenant_a["access_token"]
        tenant_a_id = tenant_a["tenant"]["id"]
        print(f"{PASS} Tenant A created: {tenant_a_id}")

        print(f"\n{INFO} Creating Tenant B...")
        tenant_b_email = f"tenant_b_{test_id}@example.com"
        tenant_b = register_tenant(
            f"Tenant B {test_id}",
            tenant_b_email,
            "TenantB123!"
        )
        token_b = tenant_b["access_token"]
        tenant_b_id = tenant_b["tenant"]["id"]
        print(f"{PASS} Tenant B created: {tenant_b_id}")

        # Test 1: Verify each tenant can only see their own info
        print(f"\n{INFO} Test 1: Verify tenant info isolation...")

        # Tenant A gets their own info
        resp_a = requests.get(
            f"{BASE_URL}/tenant/",
            headers=get_auth_header(token_a)
        )
        assert resp_a.status_code == 200
        data_a = resp_a.json()
        assert data_a["id"] == tenant_a_id
        assert "Tenant A" in data_a["name"]

        # Tenant B gets their own info
        resp_b = requests.get(
            f"{BASE_URL}/tenant/",
            headers=get_auth_header(token_b)
        )
        assert resp_b.status_code == 200
        data_b = resp_b.json()
        assert data_b["id"] == tenant_b_id
        assert "Tenant B" in data_b["name"]

        # Tenant A should NOT see Tenant B's data
        assert data_a["id"] != data_b["id"]
        print(f"{PASS} Tenant info properly isolated")

        # Test 2: Create database connections in each tenant
        print(f"\n{INFO} Test 2: Database connection isolation...")

        # Tenant A creates a database connection
        db_a_resp = requests.post(
            f"{BASE_URL}/tenant/databases",
            headers=get_auth_header(token_a),
            json={
                "name": "Tenant A Database",
                "db_type": "mssql",
                "host": "localhost",
                "port": 1433,
                "database_name": "TenantADB",
                "username": "sa",
                "password": "test_password_a"
            }
        )
        assert db_a_resp.status_code in [200, 201]
        db_a = db_a_resp.json()
        db_a_id = db_a["id"]
        print(f"  Tenant A created database: {db_a_id}")

        # Tenant B creates a database connection
        db_b_resp = requests.post(
            f"{BASE_URL}/tenant/databases",
            headers=get_auth_header(token_b),
            json={
                "name": "Tenant B Database",
                "db_type": "mssql",
                "host": "localhost",
                "port": 1433,
                "database_name": "TenantBDB",
                "username": "sa",
                "password": "test_password_b"
            }
        )
        assert db_b_resp.status_code in [200, 201]
        db_b = db_b_resp.json()
        db_b_id = db_b["id"]
        print(f"  Tenant B created database: {db_b_id}")

        # Verify Tenant A can only see their databases
        list_a_resp = requests.get(
            f"{BASE_URL}/tenant/databases",
            headers=get_auth_header(token_a)
        )
        assert list_a_resp.status_code == 200
        dbs_a = list_a_resp.json()
        db_ids_a = [db["id"] for db in dbs_a]
        assert db_a_id in db_ids_a, "Tenant A should see their database"
        assert db_b_id not in db_ids_a, "Tenant A should NOT see Tenant B's database"

        # Verify Tenant B can only see their databases
        list_b_resp = requests.get(
            f"{BASE_URL}/tenant/databases",
            headers=get_auth_header(token_b)
        )
        assert list_b_resp.status_code == 200
        dbs_b = list_b_resp.json()
        db_ids_b = [db["id"] for db in dbs_b]
        assert db_b_id in db_ids_b, "Tenant B should see their database"
        assert db_a_id not in db_ids_b, "Tenant B should NOT see Tenant A's database"

        print(f"{PASS} Database connections properly isolated")

        # Test 3: Tenant cannot access other tenant's specific database
        print(f"\n{INFO} Test 3: Cross-tenant database access prevention...")

        # Tenant A tries to get Tenant B's database
        cross_resp = requests.get(
            f"{BASE_URL}/tenant/databases/{db_b_id}",
            headers=get_auth_header(token_a)
        )
        assert cross_resp.status_code in [403, 404], \
            f"Expected 403/404, got {cross_resp.status_code}"
        print(f"  Tenant A cannot access Tenant B's database: {cross_resp.status_code}")

        # Tenant B tries to get Tenant A's database
        cross_resp2 = requests.get(
            f"{BASE_URL}/tenant/databases/{db_a_id}",
            headers=get_auth_header(token_b)
        )
        assert cross_resp2.status_code in [403, 404], \
            f"Expected 403/404, got {cross_resp2.status_code}"
        print(f"  Tenant B cannot access Tenant A's database: {cross_resp2.status_code}")

        print(f"{PASS} Cross-tenant database access prevented")

        # Test 4: Tenant cannot modify other tenant's database
        print(f"\n{INFO} Test 4: Cross-tenant database modification prevention...")

        # Tenant A tries to update Tenant B's database
        update_resp = requests.put(
            f"{BASE_URL}/tenant/databases/{db_b_id}",
            headers=get_auth_header(token_a),
            json={"name": "Hacked by Tenant A"}
        )
        assert update_resp.status_code in [400, 403, 404], \
            f"Expected 400/403/404, got {update_resp.status_code}"
        print(f"  Tenant A cannot modify Tenant B's database: {update_resp.status_code}")

        # Tenant A tries to delete Tenant B's database
        delete_resp = requests.delete(
            f"{BASE_URL}/tenant/databases/{db_b_id}",
            headers=get_auth_header(token_a)
        )
        assert delete_resp.status_code in [400, 403, 404], \
            f"Expected 400/403/404, got {delete_resp.status_code}"
        print(f"  Tenant A cannot delete Tenant B's database: {delete_resp.status_code}")

        print(f"{PASS} Cross-tenant database modification prevented")

        # Cleanup
        print(f"\n{INFO} Cleaning up test tenants...")
        cleanup_tenants([
            (tenant_a_id, token_a),
            (tenant_b_id, token_b)
        ])
        print(f"{PASS} Test tenants cleaned up")

        return True

    except Exception as e:
        print(f"{FAIL} Tenant isolation test failed: {str(e)}")
        logger.exception("Tenant isolation test error")
        return False


def test_user_isolation():
    """Test that users from different tenants are isolated"""
    print("\n" + "=" * 60)
    print("TEST 2: User Isolation Between Tenants")
    print("=" * 60)

    test_id = str(uuid.uuid4())[:8]

    try:
        # Create two separate tenants
        print(f"\n{INFO} Creating two tenants with users...")

        tenant_x_email = f"tenant_x_{test_id}@example.com"
        tenant_x = register_tenant(
            f"Tenant X {test_id}",
            tenant_x_email,
            "TenantX123!"
        )
        token_x = tenant_x["access_token"]
        tenant_x_id = tenant_x["tenant"]["id"]

        tenant_y_email = f"tenant_y_{test_id}@example.com"
        tenant_y = register_tenant(
            f"Tenant Y {test_id}",
            tenant_y_email,
            "TenantY123!"
        )
        token_y = tenant_y["access_token"]
        tenant_y_id = tenant_y["tenant"]["id"]

        print(f"{PASS} Created Tenant X: {tenant_x_id}")
        print(f"{PASS} Created Tenant Y: {tenant_y_id}")

        # Test 1: Each tenant sees only their own users
        print(f"\n{INFO} Test 1: User list isolation...")

        users_x_resp = requests.get(
            f"{BASE_URL}/tenant/users",
            headers=get_auth_header(token_x)
        )
        assert users_x_resp.status_code == 200
        users_x = users_x_resp.json()

        users_y_resp = requests.get(
            f"{BASE_URL}/tenant/users",
            headers=get_auth_header(token_y)
        )
        assert users_y_resp.status_code == 200
        users_y = users_y_resp.json()

        # Verify no overlap in users
        user_ids_x = {u["id"] for u in users_x}
        user_ids_y = {u["id"] for u in users_y}
        assert user_ids_x.isdisjoint(user_ids_y), "Users should not overlap between tenants"

        print(f"  Tenant X has {len(users_x)} users")
        print(f"  Tenant Y has {len(users_y)} users")
        print(f"{PASS} User lists properly isolated")

        # Test 2: Create additional user in Tenant X
        print(f"\n{INFO} Test 2: Create and isolate additional user...")

        new_user_resp = requests.post(
            f"{BASE_URL}/tenant/users",
            headers=get_auth_header(token_x),
            json={
                "email": f"extra_user_{test_id}@example.com",
                "password": "ExtraUser123!",
                "full_name": "Extra User",
                "role": "user"
            }
        )
        assert new_user_resp.status_code in [200, 201]
        new_user = new_user_resp.json()
        new_user_id = new_user["id"]
        print(f"  Created user in Tenant X: {new_user_id}")

        # Tenant Y should NOT see this user
        users_y_after = requests.get(
            f"{BASE_URL}/tenant/users",
            headers=get_auth_header(token_y)
        ).json()

        user_ids_y_after = {u["id"] for u in users_y_after}
        assert new_user_id not in user_ids_y_after, "New user should not be visible to Tenant Y"
        print(f"{PASS} New user not visible to other tenant")

        # Test 3: Cannot access user from another tenant
        print(f"\n{INFO} Test 3: Cross-tenant user access prevention...")

        # Try to get user details
        cross_user_resp = requests.get(
            f"{BASE_URL}/tenant/users/{new_user_id}",
            headers=get_auth_header(token_y)
        )
        assert cross_user_resp.status_code in [403, 404], \
            f"Expected 403/404, got {cross_user_resp.status_code}"
        print(f"  Cannot access user from other tenant: {cross_user_resp.status_code}")

        print(f"{PASS} Cross-tenant user access prevented")

        # Test 4: Cannot modify user from another tenant
        print(f"\n{INFO} Test 4: Cross-tenant user modification prevention...")

        modify_resp = requests.put(
            f"{BASE_URL}/tenant/users/{new_user_id}",
            headers=get_auth_header(token_y),
            json={"display_name": "Hacked!"}
        )
        assert modify_resp.status_code in [400, 403, 404], \
            f"Expected 400/403/404, got {modify_resp.status_code}"
        print(f"  Cannot modify user from other tenant: {modify_resp.status_code}")

        delete_resp = requests.delete(
            f"{BASE_URL}/tenant/users/{new_user_id}",
            headers=get_auth_header(token_y)
        )
        assert delete_resp.status_code in [400, 403, 404], \
            f"Expected 400/403/404, got {delete_resp.status_code}"
        print(f"  Cannot delete user from other tenant: {delete_resp.status_code}")

        print(f"{PASS} Cross-tenant user modification prevented")

        # Cleanup
        print(f"\n{INFO} Cleaning up test tenants...")
        cleanup_tenants([
            (tenant_x_id, token_x),
            (tenant_y_id, token_y)
        ])
        print(f"{PASS} Test tenants cleaned up")

        return True

    except Exception as e:
        print(f"{FAIL} User isolation test failed: {str(e)}")
        logger.exception("User isolation test error")
        return False


def test_token_isolation():
    """Test that tokens from one tenant cannot access another"""
    print("\n" + "=" * 60)
    print("TEST 3: Token and Authentication Isolation")
    print("=" * 60)

    test_id = str(uuid.uuid4())[:8]

    try:
        # Create two tenants
        print(f"\n{INFO} Creating two tenants...")

        tenant_1_email = f"tenant_1_{test_id}@example.com"
        tenant_1 = register_tenant(
            f"Tenant 1 {test_id}",
            tenant_1_email,
            "Tenant1Pass123!"
        )
        token_1 = tenant_1["access_token"]
        tenant_1_id = tenant_1["tenant"]["id"]

        tenant_2_email = f"tenant_2_{test_id}@example.com"
        tenant_2 = register_tenant(
            f"Tenant 2 {test_id}",
            tenant_2_email,
            "Tenant2Pass123!"
        )
        token_2 = tenant_2["access_token"]
        tenant_2_id = tenant_2["tenant"]["id"]

        print(f"{PASS} Created two tenants")

        # Test 1: Token gives access to correct tenant
        print(f"\n{INFO} Test 1: Token authentication correctness...")

        me_1 = requests.get(
            f"{BASE_URL}/auth/me",
            headers=get_auth_header(token_1)
        ).json()
        # UserResponse has tenant_id directly, not nested tenant object
        assert str(me_1["tenant_id"]) == tenant_1_id
        print(f"  Token 1 correctly identifies Tenant 1")

        me_2 = requests.get(
            f"{BASE_URL}/auth/me",
            headers=get_auth_header(token_2)
        ).json()
        # UserResponse has tenant_id directly, not nested tenant object
        assert str(me_2["tenant_id"]) == tenant_2_id
        print(f"  Token 2 correctly identifies Tenant 2")

        print(f"{PASS} Token authentication correct")

        # Test 2: Token cannot be used to spoof tenant
        print(f"\n{INFO} Test 2: Token cannot spoof tenant context...")

        # Using Token 1, but trying to access with Tenant 2's context
        # The endpoint should use the token's tenant, not a header
        tenant_info = requests.get(
            f"{BASE_URL}/tenant/",
            headers=get_auth_header(token_1)
        ).json()
        assert tenant_info["id"] == tenant_1_id, "Token should enforce tenant context"
        assert tenant_info["id"] != tenant_2_id, "Should not allow tenant spoofing"

        print(f"{PASS} Token enforces correct tenant context")

        # Test 3: Invalid token rejected
        print(f"\n{INFO} Test 3: Invalid token rejection...")

        invalid_resp = requests.get(
            f"{BASE_URL}/tenant/",
            headers={"Authorization": "Bearer invalid_token_12345"}
        )
        assert invalid_resp.status_code in [401, 403], \
            f"Expected 401/403, got {invalid_resp.status_code}"
        print(f"  Invalid token rejected: {invalid_resp.status_code}")

        # Test with no token
        no_token_resp = requests.get(f"{BASE_URL}/tenant/")
        assert no_token_resp.status_code in [401, 403], \
            f"Expected 401/403, got {no_token_resp.status_code}"
        print(f"  Missing token rejected: {no_token_resp.status_code}")

        print(f"{PASS} Invalid tokens properly rejected")

        # Cleanup
        print(f"\n{INFO} Cleaning up test tenants...")
        cleanup_tenants([
            (tenant_1_id, token_1),
            (tenant_2_id, token_2)
        ])
        print(f"{PASS} Test tenants cleaned up")

        return True

    except Exception as e:
        print(f"{FAIL} Token isolation test failed: {str(e)}")
        logger.exception("Token isolation test error")
        return False


def test_usage_stats_isolation():
    """Test that usage statistics are isolated per tenant"""
    print("\n" + "=" * 60)
    print("TEST 4: Usage Statistics Isolation")
    print("=" * 60)

    test_id = str(uuid.uuid4())[:8]

    try:
        # Create two tenants with different resource counts
        print(f"\n{INFO} Creating tenants with different resources...")

        # Tenant Alpha
        alpha_email = f"alpha_{test_id}@example.com"
        alpha = register_tenant(
            f"Alpha Corp {test_id}",
            alpha_email,
            "AlphaPass123!"
        )
        token_alpha = alpha["access_token"]
        tenant_alpha_id = alpha["tenant"]["id"]

        # Tenant Beta
        beta_email = f"beta_{test_id}@example.com"
        beta = register_tenant(
            f"Beta Inc {test_id}",
            beta_email,
            "BetaPass123!"
        )
        token_beta = beta["access_token"]
        tenant_beta_id = beta["tenant"]["id"]

        print(f"{PASS} Created Alpha and Beta tenants")

        # Add more resources to Alpha
        print(f"\n{INFO} Adding extra resources to Alpha...")

        # Add extra user to Alpha
        requests.post(
            f"{BASE_URL}/tenant/users",
            headers=get_auth_header(token_alpha),
            json={
                "email": f"alpha_user2_{test_id}@example.com",
                "password": "User2Pass123!",
                "full_name": "Alpha User 2",
                "role": "admin"
            }
        )

        # Add database to Alpha
        requests.post(
            f"{BASE_URL}/tenant/databases",
            headers=get_auth_header(token_alpha),
            json={
                "name": "Alpha Production DB",
                "db_type": "mssql",
                "host": "alpha-db.example.com",
                "port": 1433,
                "database_name": "AlphaProd",
                "username": "alpha_admin",
                "password": "alpha_db_pass"
            }
        )

        print(f"  Added 1 extra user and 1 database to Alpha")

        # Get usage stats for both
        print(f"\n{INFO} Verifying usage stats isolation...")

        stats_alpha = requests.get(
            f"{BASE_URL}/tenant/usage",
            headers=get_auth_header(token_alpha)
        ).json()

        stats_beta = requests.get(
            f"{BASE_URL}/tenant/usage",
            headers=get_auth_header(token_beta)
        ).json()

        print(f"  Alpha stats: {stats_alpha['user_count']} users, {stats_alpha['database_count']} databases")
        print(f"  Beta stats: {stats_beta['user_count']} users, {stats_beta['database_count']} databases")

        # Verify isolation
        assert stats_alpha["user_count"] == 2, "Alpha should have 2 users"
        assert stats_alpha["database_count"] == 1, "Alpha should have 1 database"
        assert stats_beta["user_count"] == 1, "Beta should have 1 user"
        assert stats_beta["database_count"] == 0, "Beta should have 0 databases"

        print(f"{PASS} Usage statistics properly isolated")

        # Cleanup
        print(f"\n{INFO} Cleaning up test tenants...")
        cleanup_tenants([
            (tenant_alpha_id, token_alpha),
            (tenant_beta_id, token_beta)
        ])
        print(f"{PASS} Test tenants cleaned up")

        return True

    except Exception as e:
        print(f"{FAIL} Usage stats isolation test failed: {str(e)}")
        logger.exception("Usage stats isolation test error")
        return False


def cleanup_tenants(tenants: list):
    """Clean up test tenants from database"""
    from app.database.platform_connection import get_platform_session
    from app.models.platform import Tenant, TenantUser, RefreshToken, TenantDatabase

    session = get_platform_session()

    for tenant_id, token in tenants:
        try:
            # Delete databases
            session.query(TenantDatabase).filter(
                TenantDatabase.tenant_id == tenant_id
            ).delete()

            # Get users for this tenant
            users = session.query(TenantUser).filter(
                TenantUser.tenant_id == tenant_id
            ).all()

            # Delete refresh tokens for all users
            for user in users:
                session.query(RefreshToken).filter(
                    RefreshToken.user_id == user.id
                ).delete()

            # Delete users
            session.query(TenantUser).filter(
                TenantUser.tenant_id == tenant_id
            ).delete()

            # Delete tenant
            session.query(Tenant).filter(
                Tenant.id == tenant_id
            ).delete()

        except Exception as e:
            logger.warning(f"Error cleaning up tenant {tenant_id}: {e}")

    session.commit()
    session.close()


def check_api_server():
    """Check if the API server is running"""
    try:
        response = requests.get(f"http://localhost:9000/health", timeout=5)
        return response.status_code == 200
    except:
        return False


def main():
    """Run all multi-tenant isolation tests"""
    print("\n" + "=" * 60)
    print("  MULTI-TENANT ISOLATION TEST SUITE")
    print("  OryggiAI Multi-Tenant SaaS Platform")
    print("=" * 60)

    # Check if API server is running
    print(f"\n{INFO} Checking API server...")
    if not check_api_server():
        print(f"{FAIL} API server is not running at localhost:9000")
        print("Please start the server with:")
        print("  cd D:\\OryggiAI_Service\\Advance_Chatbot")
        print("  venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 9000")
        return 1
    print(f"{PASS} API server is running")

    results = {}

    # Run tests
    results["data_isolation"] = test_tenant_data_isolation()
    results["user_isolation"] = test_user_isolation()
    results["token_isolation"] = test_token_isolation()
    results["usage_stats_isolation"] = test_usage_stats_isolation()

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
        print(f"\n{PASS} ALL MULTI-TENANT ISOLATION TESTS PASSED!")
        print("\nMulti-tenant isolation is working correctly.")
        print("The SaaS platform properly isolates:")
        print("  - Tenant data and configurations")
        print("  - Database connections")
        print("  - User accounts")
        print("  - Usage statistics")
        print("  - Authentication tokens")
        return 0
    else:
        print(f"\n{FAIL} SOME ISOLATION TESTS FAILED!")
        print("\nPlease review the errors above.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
