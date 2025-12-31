"""Test WebSocket locally on VM"""
import asyncio
import json
import websockets
from datetime import datetime

async def test():
    ws_url = "ws://localhost:5005/api/gateway/ws"
    print(f"Connecting to {ws_url}...")
    try:
        async with websockets.connect(ws_url, close_timeout=10) as ws:
            print("Connected!")
            auth = {
                "type": "AUTH_REQUEST",
                "gateway_token": "gw_test_invalid_12345",
                "agent_version": "1.0.0",
                "agent_hostname": "test",
                "agent_os": "Windows",
                "timestamp": datetime.utcnow().isoformat()
            }
            await ws.send(json.dumps(auth))
            print("Sent auth request")
            resp = await asyncio.wait_for(ws.recv(), timeout=10)
            print(f"Response: {resp}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test())
