"""Test card enrollment APIs using ExtendedAccessControlClient"""
import asyncio
import sys
sys.path.insert(0, 'D:/OryggiAI_Service/Advance_Chatbot')

from app.integrations.access_control_extended import ExtendedAccessControlClient


async def test_check_duplicate_card():
    """Test check_duplicate_card method"""
    print(f"\n{'='*60}")
    print("Testing check_duplicate_card()")
    print(f"{'='*60}\n")

    client = ExtendedAccessControlClient()

    # Test with a new card number
    result = await client.check_duplicate_card("99999999")
    print(f"Check for card 99999999 (should be not duplicate):")
    for key, value in result.items():
        print(f"  {key}: {value}")

    # Test with potentially existing card
    result2 = await client.check_duplicate_card("12345678")
    print(f"\nCheck for card 12345678:")
    for key, value in result2.items():
        print(f"  {key}: {value}")

    return result


async def test_get_employee_cards():
    """Test get_employee_cards method"""
    print(f"\n{'='*60}")
    print("Testing get_employee_cards()")
    print(f"{'='*60}\n")

    client = ExtendedAccessControlClient()

    # Test with TERMTEST2191 (ecode 1016)
    result = await client.get_employee_cards(1016)
    print(f"Cards for ecode 1016 (TERMTEST2191):")
    for key, value in result.items():
        print(f"  {key}: {value}")

    return result


async def test_enroll_card():
    """Test enroll_card method"""
    print(f"\n{'='*60}")
    print("Testing enroll_card()")
    print(f"{'='*60}\n")

    client = ExtendedAccessControlClient()

    # Enroll a card for TERMTEST2191 (ecode 1016)
    import time
    new_card = f"TEST{int(time.time()) % 100000:05d}"  # Unique card number

    print(f"Enrolling card {new_card} for ecode 1016...")
    result = await client.enroll_card(
        ecode=1016,
        card_number=new_card,
        card_type="permanent",
        sync_to_terminals=True
    )

    print(f"\nResult:")
    for key, value in result.items():
        print(f"  {key}: {value}")

    return result


async def test_enroll_card_by_corp_code():
    """Test enroll_card method using corp_emp_code"""
    print(f"\n{'='*60}")
    print("Testing enroll_card() by corp_emp_code")
    print(f"{'='*60}\n")

    client = ExtendedAccessControlClient()

    import time
    new_card = f"CORP{int(time.time()) % 100000:05d}"

    print(f"Enrolling card {new_card} for TERMTEST2191...")
    result = await client.enroll_card(
        corp_emp_code="TERMTEST2191",
        card_number=new_card,
        card_type="permanent"
    )

    print(f"\nResult:")
    for key, value in result.items():
        print(f"  {key}: {value}")

    return result


async def main():
    """Run all tests"""
    # 1. Check duplicate card
    await test_check_duplicate_card()

    # 2. Get employee cards
    await test_get_employee_cards()

    # 3. Enroll card by ecode
    await test_enroll_card()

    # 4. Verify card was enrolled
    await test_get_employee_cards()

    print(f"\n{'='*60}")
    print("Test Complete")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
