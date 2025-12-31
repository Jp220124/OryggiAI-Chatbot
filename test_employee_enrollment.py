"""
Test script to verify employee enrollment via Oryggi REST API
This bypasses the chatbot and tests the API integration directly
"""
import asyncio
import sys
import os

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.integrations.access_control_extended import ExtendedAccessControlClient, EmployeeEnrollmentRequest

async def test_employee_enrollment():
    """Test employee enrollment through the extended API client"""

    print("=" * 60)
    print("Testing Employee Enrollment via Oryggi REST API")
    print("=" * 60)

    # Create API client
    client = ExtendedAccessControlClient()

    # Create test employee request
    request = EmployeeEnrollmentRequest(
        corp_emp_code="CHATBOT015",  # Unique test ID
        emp_name="Test ChatBot Employee",
        email="chatbot015@test.com",
        department_code="IT",
        designation_code="ENG",
        phone="1234567890",
        address="Test Address"
    )

    print(f"\nCreating employee:")
    print(f"  Corp Emp Code: {request.corp_emp_code}")
    print(f"  Name: {request.emp_name}")
    print(f"  Email: {request.email}")

    try:
        # Call enroll_employee directly
        result = await client.enroll_employee(request)

        print(f"\n{'=' * 60}")
        print("RESULT:")
        print(f"  Success: {result.success}")
        print(f"  Message: {result.message}")
        print(f"  Corp Emp Code: {result.corp_emp_code}")
        if result.ecode:
            print(f"  Ecode: {result.ecode}")
        if result.details:
            print(f"  Details: {result.details}")
        print("=" * 60)

        return result.success

    except Exception as e:
        print(f"\nERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_employee_enrollment())
    sys.exit(0 if success else 1)
