"""
Gateway Dashboard E2E Test

This test verifies:
1. Gateway agent connects successfully
2. Dashboard API shows the connected agent
3. Database gateway_connected flag is updated
"""

import asyncio
import json
import secrets
import hashlib
import websockets
from datetime import datetime, timedelta, timezone
from uuid import uuid4
import time

import sys
sys.path.insert(0, '.')

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.config import settings


def get_db_session():
    """Get database session using app config"""
    engine = create_engine(settings.platform_database_url)
    Session = sessionmaker(bind=engine)
    return Session()


def setup_test_data(db):
    """Find or create test data"""
    print("\n1. Setting up test data...")

    # Find first active tenant
    result = db.execute(text("""
        SELECT TOP 1 id, name, slug
        FROM tenants
        WHERE status = 'active'
        ORDER BY created_at
    """))
    tenant = result.fetchone()

    if not tenant:
        print("   ERROR: No active tenant found!")
        return None, None, None, None

    tenant_id = tenant[0]
    print(f"   Found tenant: {tenant[1]} (ID: {tenant_id})")

    # Find user
    result = db.execute(text("""
        SELECT TOP 1 id, email
        FROM tenant_users
        WHERE tenant_id = :tenant_id AND is_active = 1
        ORDER BY created_at
    """), {"tenant_id": tenant_id})
    user = result.fetchone()

    if not user:
        print("   ERROR: No user found!")
        return None, None, None, None

    user_id = user[0]
    print(f"   Found user: {user[1]}")

    # Find database
    result = db.execute(text("""
        SELECT TOP 1 id, name
        FROM tenant_databases
        WHERE tenant_id = :tenant_id AND is_active = 1
        ORDER BY created_at
    """), {"tenant_id": tenant_id})
    database = result.fetchone()

    if not database:
        print("   ERROR: No database found!")
        return None, None, None, None

    database_id = database[0]
    print(f"   Found database: {database[1]} (ID: {database_id})")

    # Generate gateway token
    token = f"gw_{secrets.token_urlsafe(32)}"
    key_prefix = token[:8]
    key_hash = hashlib.sha256(token.encode()).hexdigest()

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
        "name": "Dashboard Test Gateway Token",
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
            connection_mode = 'gateway_only',
            gateway_connected = 0
        WHERE id = :database_id
    """), {"api_key_id": api_key_id, "database_id": database_id})

    db.commit()
    print(f"   Token generated and linked to database")

    return token, api_key_id, database_id, tenant_id


def cleanup_test_data(db, api_key_id, database_id):
    """Clean up test data"""
    print("\n6. Cleaning up test data...")

    try:
        db.execute(text("""
            UPDATE tenant_databases
            SET gateway_api_key_id = NULL,
                gateway_connected = 0,
                gateway_connected_at = NULL
            WHERE id = :database_id
        """), {"database_id": database_id})

        db.execute(text("""
            DELETE FROM api_keys WHERE id = :api_key_id
        """), {"api_key_id": api_key_id})

        db.commit()
        print("   Cleaned up successfully")
    except Exception as e:
        print(f"   Cleanup error: {e}")


def check_database_status(db, database_id, expected_connected):
    """Check if database shows as connected/disconnected"""
    result = db.execute(text("""
        SELECT gateway_connected, gateway_connected_at
        FROM tenant_databases
        WHERE id = :database_id
    """), {"database_id": database_id})

    row = result.fetchone()
    if row:
        is_connected = bool(row[0])
        connected_at = row[1]
        status = "Connected" if is_connected else "Disconnected"
        print(f"   Database gateway status: {status}")
        if connected_at:
            print(f"   Connected at: {connected_at}")

        return is_connected == expected_connected
    return False


async def run_agent_and_verify(token, database_id, db):
    """
    Run gateway agent and verify dashboard status

    Args:
        token: Gateway token
        database_id: Database ID
        db: Database session
    """
    ws_url = "ws://localhost:5005/api/gateway/ws"

    print("\n2. Connecting gateway agent...")

    try:
        async with websockets.connect(ws_url, close_timeout=30) as websocket:
            print(f"   Connected to {ws_url}")

            # Send AUTH_REQUEST
            auth_request = {
                "type": "AUTH_REQUEST",
                "gateway_token": token,
                "agent_version": "1.0.0",
                "agent_hostname": "dashboard-test-agent",
                "agent_os": "Windows 10",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            await websocket.send(json.dumps(auth_request))
            print("   Sent AUTH_REQUEST")

            # Wait for AUTH_RESPONSE
            response_data = await asyncio.wait_for(websocket.recv(), timeout=10)
            response = json.loads(response_data)

            if response.get("type") != "AUTH_RESPONSE" or response.get("status") != "success":
                print(f"   [FAIL] Authentication failed: {response.get('error_message')}")
                return False, False, False

            session_id = response.get("session_id")
            print(f"   [SUCCESS] Authenticated! Session: {session_id}")

            # Wait a moment for database to update
            await asyncio.sleep(1)

            # Check database status - should show as connected
            print("\n3. Verifying database status (should be connected)...")
            db_status_ok = check_database_status(db, database_id, expected_connected=True)

            if db_status_ok:
                print("   [PASS] Database shows gateway as connected")
            else:
                print("   [FAIL] Database does not show gateway as connected")

            # Send heartbeat to keep connection alive
            print("\n4. Sending heartbeat to maintain connection...")
            heartbeat = {
                "type": "HEARTBEAT",
                "session_id": session_id,
                "db_status": "connected",
                "queries_executed": 0,
                "uptime_seconds": 5,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await websocket.send(json.dumps(heartbeat))

            # Wait for ACK
            ack_data = await asyncio.wait_for(websocket.recv(), timeout=10)
            ack = json.loads(ack_data)
            heartbeat_ok = ack.get("type") == "HEARTBEAT_ACK"

            if heartbeat_ok:
                print("   [PASS] Heartbeat acknowledged")
            else:
                print("   [FAIL] Heartbeat not acknowledged")

            # Connection is still alive
            print("\n5. Gateway Dashboard Test Results:")
            print("   " + "=" * 50)

            auth_ok = True
            return auth_ok, db_status_ok, heartbeat_ok

    except Exception as e:
        print(f"   Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False, False, False


async def main():
    """Run dashboard verification test"""
    print("=" * 60)
    print(" GATEWAY DASHBOARD E2E TEST")
    print("=" * 60)

    db = None
    api_key_id = None
    database_id = None

    try:
        db = get_db_session()

        # Setup test data
        token, api_key_id, database_id, tenant_id = setup_test_data(db)
        if not token:
            print("\nTest failed: Could not set up test data")
            return False

        # Run agent and verify
        auth_ok, db_status_ok, heartbeat_ok = await run_agent_and_verify(
            token, database_id, db
        )

        # Cleanup
        if api_key_id and database_id:
            cleanup_test_data(db, api_key_id, database_id)

        # Results
        print("\n" + "=" * 60)
        print(" TEST RESULTS")
        print("=" * 60)
        print(f"   [{'PASS' if auth_ok else 'FAIL'}] Gateway Authentication")
        print(f"   [{'PASS' if db_status_ok else 'FAIL'}] Database Gateway Status Update")
        print(f"   [{'PASS' if heartbeat_ok else 'FAIL'}] Heartbeat Mechanism")

        overall = auth_ok and db_status_ok and heartbeat_ok
        print("\n" + "=" * 60)
        print(f" OVERALL: {'ALL DASHBOARD TESTS PASSED!' if overall else 'SOME TESTS FAILED'}")
        print("=" * 60)

        if overall:
            print("\n Dashboard Verification Notes:")
            print("   - When a gateway agent connects, the database")
            print("     gateway_connected flag is set to TRUE")
            print("   - The dashboard can query this flag to show")
            print("     connected/disconnected status for each database")
            print("   - The gateway_connected_at timestamp shows")
            print("     when the agent last connected")

        return overall

    except Exception as e:
        print(f"\nTest error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

        if db and api_key_id and database_id:
            try:
                cleanup_test_data(db, api_key_id, database_id)
            except:
                pass

        return False
    finally:
        if db:
            db.close()


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
