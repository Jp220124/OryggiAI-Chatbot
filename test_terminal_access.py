"""Test terminal access grant via chatbot API"""
import asyncio
import sys
sys.path.insert(0, 'D:/OryggiAI_Service/Advance_Chatbot')

from app.integrations.access_control_extended import ExtendedAccessControlClient

async def test_grant_terminal_access():
    """Test granting terminal access to an employee"""
    client = ExtendedAccessControlClient()

    print(f"\n{'='*60}")
    print(f"Testing Terminal Access Grant")
    print(f"{'='*60}\n")

    # First, get available terminals
    print("1. Getting available terminals...")
    terminals = await client.get_terminals()
    print(f"   Found {len(terminals)} terminals:")
    for t in terminals:
        tid = t.get("terminalID") or t.get("TerminalID")
        tname = t.get("terminalName") or t.get("TerminalName")
        tip = t.get("ipAddress") or t.get("IPAddress")
        print(f"   - ID: {tid}, Name: {tname}, IP: {tip}")

    # Test with employee NEWTEST001 (ecode 1014) - this employee already has a card
    ecode = 1014  # NEWTEST001

    print(f"\n2. Granting terminal access to ecode {ecode}...")

    # Grant access to BS3 terminal (ID 1)
    result = await client.grant_terminal_access(
        ecode=ecode,
        terminal_name="BS3",  # or terminal_id=1
        authentication_type=3,  # Card/Finger
        schedule_id=63  # All Access
    )

    print(f"\n{'='*60}")
    print(f"RESULT:")
    for key, value in result.items():
        print(f"  {key}: {value}")
    print(f"{'='*60}")

    if result.get("success"):
        print(f"\n*** SUCCESS: Terminal access granted! ***")
    else:
        print(f"\n*** FAILED: {result.get('error', 'Unknown error')} ***")

    return result


async def test_grant_all_terminals():
    """Test granting access to all terminals"""
    client = ExtendedAccessControlClient()

    print(f"\n{'='*60}")
    print(f"Testing Grant Access to ALL Terminals")
    print(f"{'='*60}\n")

    ecode = 1014  # NEWTEST001

    result = await client.grant_terminal_access(
        ecode=ecode,
        grant_all_terminals=True,
        authentication_type=3,  # Card/Finger
        schedule_id=63  # All Access
    )

    print(f"\n{'='*60}")
    print(f"RESULT:")
    for key, value in result.items():
        print(f"  {key}: {value}")
    print(f"{'='*60}")

    return result


if __name__ == "__main__":
    print("="*60)
    print("Terminal Access Grant Test")
    print("="*60)

    # Test single terminal
    result1 = asyncio.run(test_grant_terminal_access())

    print("\n" + "="*60)

    # Optionally test all terminals
    # result2 = asyncio.run(test_grant_all_terminals())
