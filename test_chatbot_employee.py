"""Test employee creation via chatbot"""
import asyncio
import sys
sys.path.insert(0, 'D:/OryggiAI_Service/Advance_Chatbot')

from app.integrations.access_control_extended import ExtendedAccessControlClient

async def test_enroll_employee():
    """Test enrolling an employee via the extended client"""
    client = ExtendedAccessControlClient()

    # Create a unique employee
    import time
    emp_code = f"CHATTEST{int(time.time()) % 10000}"

    print(f"\n{'='*60}")
    print(f"Testing employee enrollment via chatbot")
    print(f"Employee Code: {emp_code}")
    print(f"{'='*60}\n")

    from app.integrations.access_control_extended import EmployeeEnrollmentRequest

    request = EmployeeEnrollmentRequest(
        corp_emp_code=emp_code,
        emp_name="ChatBot Created User",
        department="IT",
        designation="Developer",
        email=f"{emp_code.lower()}@example.com",
        phone="8887776665",
        address="789 Chatbot Street",
        active=True
    )

    print(f"Request: {request}")

    try:
        result = await client.enroll_employee(request)
        print(f"\n{'='*60}")
        print(f"RESULT: {result}")
        print(f"{'='*60}")

        if result.get("success"):
            print(f"\n*** SUCCESS: Employee {emp_code} created with Ecode {result.get('ecode')} ***")
        else:
            print(f"\n*** FAILED: {result.get('error')} ***")

        return result
    except Exception as e:
        print(f"\n*** EXCEPTION: {e} ***")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    result = asyncio.run(test_enroll_employee())
