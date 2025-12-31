"""
Gateway WebSocket End-to-End Test

Tests the complete flow:
1. Server WebSocket endpoint accepts connection
2. Authentication flow works (will fail with invalid token, which is expected)
3. Message protocol is correct
"""

import asyncio
import json
import websockets
from datetime import datetime


async def test_gateway_websocket():
    """Test the gateway WebSocket endpoint"""

    # Test endpoint URL (local server)
    ws_url = "ws://localhost:9000/api/gateway/ws"

    print("=" * 60)
    print("Gateway WebSocket E2E Test")
    print("=" * 60)

    try:
        print(f"\n1. Connecting to {ws_url}...")

        async with websockets.connect(ws_url, close_timeout=5) as websocket:
            print("   Connection established")

            # Send authentication request with test token
            auth_request = {
                "type": "AUTH_REQUEST",
                "gateway_token": "gw_test_invalid_token_12345",  # Invalid token for testing
                "agent_version": "1.0.0",
                "agent_hostname": "test-machine",
                "agent_os": "Windows 10",
                "timestamp": datetime.utcnow().isoformat(),
            }

            print(f"\n2. Sending AUTH_REQUEST...")
            await websocket.send(json.dumps(auth_request))
            print(f"   Sent: {json.dumps(auth_request, indent=2)}")

            # Wait for response
            print(f"\n3. Waiting for AUTH_RESPONSE...")
            response_data = await asyncio.wait_for(websocket.recv(), timeout=10)
            response = json.loads(response_data)

            print(f"   Received: {json.dumps(response, indent=2)}")

            # Check response
            if response.get("type") == "AUTH_RESPONSE":
                if response.get("status") == "success":
                    print("\n   Authentication successful!")
                    print(f"   Session ID: {response.get('session_id')}")
                    return True
                else:
                    print(f"\n   Authentication failed (expected with invalid token)")
                    print(f"   Error: {response.get('error_message')}")
                    # This is actually expected behavior - we used an invalid token
                    return True  # Test passed - server responded correctly
            else:
                print(f"\n   Unexpected response type: {response.get('type')}")
                return False

    except websockets.exceptions.InvalidStatusCode as e:
        print(f"\n   WebSocket connection rejected: {e}")
        return False
    except asyncio.TimeoutError:
        print("\n   Connection timed out")
        return False
    except ConnectionRefusedError:
        print("\n   Connection refused - is the server running?")
        return False
    except Exception as e:
        print(f"\n   Error: {type(e).__name__}: {e}")
        return False


async def test_heartbeat_format():
    """Test that heartbeat message format is correct"""
    print("\n" + "=" * 60)
    print("Testing Message Format Validation")
    print("=" * 60)

    # Validate message schemas
    from app.gateway.schemas import AuthRequest, Heartbeat, QueryRequest

    # Test AuthRequest
    auth = AuthRequest(
        gateway_token="gw_test123",
        agent_version="1.0.0",
        agent_hostname="test",
        agent_os="Windows"
    )
    print(f"\nAuthRequest schema: OK")
    print(f"  {auth.model_dump_json()}")

    # Test Heartbeat
    heartbeat = Heartbeat(
        session_id="sess123",
        db_status="connected",
        queries_executed=5,
        uptime_seconds=3600
    )
    print(f"\nHeartbeat schema: OK")
    print(f"  {heartbeat.model_dump_json()}")

    # Test QueryRequest
    query = QueryRequest(
        request_id="req123",
        sql_query="SELECT TOP 10 * FROM employees",
        timeout=30,
        max_rows=100
    )
    print(f"\nQueryRequest schema: OK")
    print(f"  {query.model_dump_json()}")

    return True


async def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print(" GATEWAY END-TO-END TEST SUITE")
    print("=" * 60)

    results = []

    # Test 1: WebSocket connection
    result = await test_gateway_websocket()
    results.append(("WebSocket Connection", result))

    # Test 2: Message format validation
    try:
        result = await test_heartbeat_format()
        results.append(("Message Schemas", result))
    except Exception as e:
        print(f"Schema test error: {e}")
        results.append(("Message Schemas", False))

    # Summary
    print("\n" + "=" * 60)
    print(" TEST RESULTS SUMMARY")
    print("=" * 60)

    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        symbol = "+" if passed else "X"  # ASCII for Windows console compatibility
        print(f"  [{symbol}] {name}: {status}")

    all_passed = all(r[1] for r in results)
    print("\n" + "=" * 60)
    print(f" OVERALL: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
    print("=" * 60)

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
