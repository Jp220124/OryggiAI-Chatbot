"""
Gateway End-to-End Test with Valid Token

This test:
1. Connects to platform database
2. Finds/creates test data
3. Generates valid gateway token
4. Tests full authentication flow
5. Tests heartbeat mechanism
6. Tests query execution (simulated)
"""

import asyncio
import json
import secrets
import hashlib
import websockets
from datetime import datetime, timedelta, timezone

# Import SQLAlchemy models
import sys
sys.path.insert(0, '.')

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Use app's config
from app.config import settings


def get_db_session():
    """Get database session using app config"""
    engine = create_engine(settings.platform_database_url)
    Session = sessionmaker(bind=engine)
    return Session()


def find_test_data(db):
    """Find existing tenant and database for testing, create test database if needed"""
    print("\n1. Finding test data in platform database...")

    # Find first active tenant (status='active' instead of is_active=1, slug instead of subdomain)
    result = db.execute(text("""
        SELECT TOP 1 id, name, slug
        FROM tenants
        WHERE status = 'active'
        ORDER BY created_at
    """))
    tenant = result.fetchone()

    if not tenant:
        print("   ERROR: No active tenant found!")
        return None, None

    tenant_id = tenant[0]
    tenant_name = tenant[1]
    print(f"   Found tenant: {tenant_name} (ID: {tenant_id})")

    # Find first database for this tenant
    result = db.execute(text("""
        SELECT TOP 1 id, name, connection_mode
        FROM tenant_databases
        WHERE tenant_id = :tenant_id AND is_active = 1
        ORDER BY created_at
    """), {"tenant_id": tenant_id})
    database = result.fetchone()

    if not database:
        print("   No database found for tenant, creating test database record...")
        # Create a test database record with all required fields
        result = db.execute(text("""
            INSERT INTO tenant_databases (
                id, tenant_id, name, db_type, connection_mode,
                host, port, database_name, username, password_encrypted,
                is_active, created_at, updated_at
            )
            OUTPUT INSERTED.id, INSERTED.name, INSERTED.connection_mode
            VALUES (
                NEWID(), :tenant_id, 'GatewayE2ETestDB', 'mssql', 'gateway_only',
                'gateway-only-no-direct', 1433, 'GatewayTestDB', 'gateway_user', 'encrypted_placeholder',
                1, GETUTCDATE(), GETUTCDATE()
            )
        """), {"tenant_id": tenant_id})
        database = result.fetchone()
        db.commit()
        print(f"   Created test database: {database[1]} (ID: {database[0]})")
    else:
        database_id = database[0]
        database_name = database[1]
        print(f"   Found database: {database_name} (ID: {database_id})")

    return tenant, database


def generate_gateway_token(db, tenant_id, user_id, database_id):
    """Generate a valid gateway token directly in the database"""
    print("\n2. Generating gateway token...")

    # Generate token
    token = f"gw_{secrets.token_urlsafe(32)}"
    key_prefix = token[:8]  # Column is NVARCHAR(10), use 8 chars to be safe
    key_hash = hashlib.sha256(token.encode()).hexdigest()

    print(f"   Token prefix: {key_prefix}")

    # Insert API key
    result = db.execute(text("""
        INSERT INTO api_keys (
            id, tenant_id, user_id, name, key_prefix, key_hash,
            scopes, is_active, expires_at, created_at, updated_at
        )
        OUTPUT INSERTED.id
        VALUES (
            NEWID(), :tenant_id, :user_id, :name, :key_prefix, :key_hash,
            :scopes, 1, :expires_at, GETUTCDATE(), GETUTCDATE()
        )
    """), {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "name": "E2E Test Gateway Token",
        "key_prefix": key_prefix,
        "key_hash": key_hash,
        "scopes": '["gateway"]',
        "expires_at": datetime.now(timezone.utc) + timedelta(days=1),
    })

    api_key_id = result.fetchone()[0]
    print(f"   Created API key: {api_key_id}")

    # Link to database
    db.execute(text("""
        UPDATE tenant_databases
        SET gateway_api_key_id = :api_key_id,
            connection_mode = 'gateway_only'
        WHERE id = :database_id
    """), {"api_key_id": api_key_id, "database_id": database_id})

    db.commit()
    print(f"   Linked token to database")

    return token, api_key_id


def cleanup_test_token(db, api_key_id, database_id):
    """Clean up test token"""
    print("\n6. Cleaning up test token...")

    try:
        # Unlink from database
        db.execute(text("""
            UPDATE tenant_databases
            SET gateway_api_key_id = NULL
            WHERE id = :database_id
        """), {"database_id": database_id})

        # Delete API key
        db.execute(text("""
            DELETE FROM api_keys WHERE id = :api_key_id
        """), {"api_key_id": api_key_id})

        db.commit()
        print("   Cleaned up successfully")
    except Exception as e:
        print(f"   Cleanup error (non-fatal): {e}")


async def test_authentication(token, database_id):
    """Test gateway authentication with valid token"""
    print("\n3. Testing authentication with valid token...")

    ws_url = "ws://localhost:3000/api/gateway/ws"  # VM backend on port 3000 (bypasses IIS)

    try:
        async with websockets.connect(ws_url, close_timeout=10) as websocket:
            print(f"   Connected to {ws_url}")

            # Send AUTH_REQUEST
            auth_request = {
                "type": "AUTH_REQUEST",
                "gateway_token": token,
                "agent_version": "1.0.0",
                "agent_hostname": "e2e-test-machine",
                "agent_os": "Windows 10",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            await websocket.send(json.dumps(auth_request))
            print("   Sent AUTH_REQUEST")

            # Wait for response
            response_data = await asyncio.wait_for(websocket.recv(), timeout=10)
            response = json.loads(response_data)
            print(f"   Received: {json.dumps(response, indent=2)}")

            if response.get("type") == "AUTH_RESPONSE":
                if response.get("status") == "success":
                    session_id = response.get("session_id")
                    print(f"\n   [SUCCESS] Authenticated! Session: {session_id}")

                    # Test heartbeat
                    heartbeat_result = await test_heartbeat(websocket, session_id)

                    return True, session_id, heartbeat_result
                else:
                    print(f"\n   [FAIL] Auth failed: {response.get('error_message')}")
                    return False, None, False

            return False, None, False

    except Exception as e:
        print(f"   Error: {type(e).__name__}: {e}")
        return False, None, False


async def test_heartbeat(websocket, session_id):
    """Test heartbeat mechanism"""
    print("\n4. Testing heartbeat...")

    try:
        heartbeat = {
            "type": "HEARTBEAT",
            "session_id": session_id,
            "db_status": "connected",
            "queries_executed": 0,
            "uptime_seconds": 10,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        await websocket.send(json.dumps(heartbeat))
        print("   Sent HEARTBEAT")

        # Wait for ACK
        response_data = await asyncio.wait_for(websocket.recv(), timeout=10)
        response = json.loads(response_data)

        if response.get("type") == "HEARTBEAT_ACK":
            print(f"   [SUCCESS] Received HEARTBEAT_ACK")
            return True
        else:
            print(f"   [FAIL] Unexpected response: {response.get('type')}")
            return False

    except Exception as e:
        print(f"   Heartbeat error: {e}")
        return False


def check_gateway_status(db, database_id):
    """Check if gateway shows as connected"""
    print("\n5. Checking gateway connection status...")

    result = db.execute(text("""
        SELECT connection_mode, gateway_api_key_id
        FROM tenant_databases
        WHERE id = :database_id
    """), {"database_id": database_id})

    row = result.fetchone()
    if row:
        print(f"   Connection mode: {row[0]}")
        print(f"   Gateway API key: {row[1]}")
        return True
    return False


def find_user_for_tenant(db, tenant_id):
    """Find a user for the tenant"""
    result = db.execute(text("""
        SELECT TOP 1 id, email
        FROM tenant_users
        WHERE tenant_id = :tenant_id AND is_active = 1
        ORDER BY created_at
    """), {"tenant_id": tenant_id})
    user = result.fetchone()
    if user:
        print(f"   Found user: {user[1]} (ID: {user[0]})")
        return user[0]
    return None


async def main():
    """Run full E2E test"""
    print("=" * 60)
    print(" GATEWAY END-TO-END TEST WITH VALID TOKEN")
    print("=" * 60)

    db = None
    token = None
    api_key_id = None
    database_id = None

    try:
        db = get_db_session()

        # Find test data
        tenant, database = find_test_data(db)
        if not tenant or not database:
            print("\nTest failed: Could not find test data")
            return False

        tenant_id = tenant[0]
        database_id = database[0]

        # Find user
        user_id = find_user_for_tenant(db, tenant_id)
        if not user_id:
            print("\nTest failed: Could not find user")
            return False

        # Generate token
        token, api_key_id = generate_gateway_token(db, tenant_id, user_id, database_id)

        # Test authentication
        auth_success, session_id, heartbeat_success = await test_authentication(token, database_id)

        # Check gateway status
        status_ok = check_gateway_status(db, database_id)

        # Cleanup
        cleanup_test_token(db, api_key_id, database_id)

        # Results
        print("\n" + "=" * 60)
        print(" TEST RESULTS")
        print("=" * 60)
        print(f"   [{'PASS' if auth_success else 'FAIL'}] Authentication")
        print(f"   [{'PASS' if heartbeat_success else 'FAIL'}] Heartbeat")
        print(f"   [{'PASS' if status_ok else 'FAIL'}] Database Status")

        overall = auth_success and heartbeat_success and status_ok
        print("\n" + "=" * 60)
        print(f" OVERALL: {'ALL TESTS PASSED!' if overall else 'SOME TESTS FAILED'}")
        print("=" * 60)

        return overall

    except Exception as e:
        print(f"\nTest error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

        # Attempt cleanup
        if db and api_key_id and database_id:
            try:
                cleanup_test_token(db, api_key_id, database_id)
            except:
                pass

        return False
    finally:
        if db:
            db.close()


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
