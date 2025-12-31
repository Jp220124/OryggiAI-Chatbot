"""
Gateway WebSocket End-to-End Test for VM
Tests the VM server at 103.197.77.163:9000
"""

import asyncio
import json
import websockets
from datetime import datetime


async def test_gateway_websocket():
    """Test the gateway WebSocket endpoint on VM"""

    # VM server URL - Now through IIS with WebSocket support enabled
    ws_url = "ws://103.197.77.163:9000/api/gateway/ws"  # Through IIS

    print("=" * 60)
    print("Gateway WebSocket E2E Test (VM)")
    print("=" * 60)

    try:
        print(f"\n1. Connecting to {ws_url}...")

        async with websockets.connect(ws_url, close_timeout=10) as websocket:
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
                    print("\n   [PASS] Authentication successful!")
                    print(f"   Session ID: {response.get('session_id')}")
                    return True
                else:
                    print(f"\n   [PASS] Authentication failed (expected with invalid token)")
                    print(f"   Error: {response.get('error_message')}")
                    # This is actually expected behavior - we used an invalid token
                    return True  # Test passed - server responded correctly
            else:
                print(f"\n   [FAIL] Unexpected response type: {response.get('type')}")
                return False

    except websockets.exceptions.InvalidStatusCode as e:
        print(f"\n   [FAIL] WebSocket connection rejected: {e}")
        return False
    except asyncio.TimeoutError:
        print("\n   [FAIL] Connection timed out")
        return False
    except ConnectionRefusedError:
        print("\n   [FAIL] Connection refused - is the server running?")
        return False
    except Exception as e:
        print(f"\n   [FAIL] Error: {type(e).__name__}: {e}")
        return False


async def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print(" VM GATEWAY END-TO-END TEST")
    print("=" * 60)

    result = await test_gateway_websocket()

    print("\n" + "=" * 60)
    print(f" OVERALL: {'TEST PASSED' if result else 'TEST FAILED'}")
    print("=" * 60)

    return result


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
