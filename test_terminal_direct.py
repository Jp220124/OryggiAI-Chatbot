"""Test terminal access APIs using ExtendedAccessControlClient"""
import asyncio
import sys
sys.path.insert(0, 'D:/OryggiAI_Service/Advance_Chatbot')

from app.integrations.access_control_extended import ExtendedAccessControlClient

async def test_get_terminals():
    """Test get_terminals method"""
    print(f"\n{'='*60}")
    print("Testing get_terminals()")
    print(f"{'='*60}\n")

    client = ExtendedAccessControlClient()

    terminals = await client.get_terminals()
    print(f"Found {len(terminals)} terminals:")
    for t in terminals:
        tid = t.get("terminalID") or t.get("TerminalID")
        tname = t.get("terminalName") or t.get("TerminalName")
        tip = t.get("ipAddress") or t.get("IPAddress")
        print(f"  - ID: {tid}, Name: {tname}, IP: {tip}")

    return terminals


async def test_grant_terminal_access():
    """Test grant_terminal_access method with NEWTEST001 (ecode 1014)"""
    print(f"\n{'='*60}")
    print("Testing grant_terminal_access()")
    print(f"Employee: NEWTEST001 (ecode=1014)")
    print(f"{'='*60}\n")

    client = ExtendedAccessControlClient()

    # NEWTEST001 has ecode 1014 and card "12345678" in CardMaster
    result = await client.grant_terminal_access(
        ecode=1014,
        terminal_name="BS3",  # or terminal_id=1
        authentication_type=3,  # Card/Finger
        schedule_id=63  # All Access
    )

    print(f"\nResult:")
    for key, value in result.items():
        print(f"  {key}: {value}")

    return result


async def test_grant_all_terminals():
    """Test granting access to all terminals"""
    print(f"\n{'='*60}")
    print("Testing grant_terminal_access(grant_all_terminals=True)")
    print(f"Employee: NEWTEST001 (ecode=1014)")
    print(f"{'='*60}\n")

    client = ExtendedAccessControlClient()

    result = await client.grant_terminal_access(
        ecode=1014,
        grant_all_terminals=True,
        authentication_type=3,  # Card/Finger
        schedule_id=63  # All Access
    )

    print(f"\nResult:")
    for key, value in result.items():
        print(f"  {key}: {value}")

    return result


async def test_check_api_health():
    """Test API health check"""
    print(f"\n{'='*60}")
    print("Testing API Health Check")
    print(f"{'='*60}\n")

    client = ExtendedAccessControlClient()
    health = await client.health_check()

    print(f"Health status:")
    for key, value in health.items():
        print(f"  {key}: {value}")

    return health


async def main():
    """Run all tests"""
    # 1. Check API health
    health = await test_check_api_health()

    if health.get("status") != "healthy":
        print(f"\n*** WARNING: API is not healthy. Tests may fail. ***")

    # 2. Get terminals
    terminals = await test_get_terminals()

    if not terminals:
        print("\n*** No terminals found. Cannot test terminal access. ***")
        return

    # 3. Test granting access to single terminal
    result = await test_grant_terminal_access()

    # 4. Optionally test granting to all terminals
    # result2 = await test_grant_all_terminals()

    print(f"\n{'='*60}")
    print("Test Complete")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
