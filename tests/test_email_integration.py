"""
Test Email Integration for Report Generation
Quick test to verify email sending works end-to-end
"""

import requests
import json

# Test configuration
API_URL = "http://localhost:9000/api/reports/generate"

# Test 1: Generate PDF report and send to email
print("=" * 80)
print("TEST: Generate PDF Report + Send Email")
print("=" * 80)

request_data = {
    "question": "Show me top 5 employees",
    "format": "pdf",
    "user_id": "test_user",
    "user_role": "ADMIN",
    "email_to": "recipient@example.com"  # CHANGE THIS TO YOUR EMAIL
}

print(f"\nRequest Data:")
print(json.dumps(request_data, indent=2))
print("\nSending request...")

try:
    response = requests.post(API_URL, json=request_data)

    print(f"\nStatus Code: {response.status_code}")
    print(f"\nResponse:")
    print(json.dumps(response.json(), indent=2))

    result = response.json()

    if result.get("success"):
        print("\n✅ Report generated successfully!")
        print(f"Report Path: {result.get('report_path')}")
        print(f"Rows Count: {result.get('rows_count')}")

        # Check email status
        if result.get("email_sent"):
            print(f"\n✅ Email sent successfully to: {result.get('email_to')}")
        else:
            print(f"\n❌ Email failed: {result.get('email_error')}")
    else:
        print(f"\n❌ Report generation failed: {result.get('error')}")

except Exception as e:
    print(f"\n❌ Error: {str(e)}")

print("\n" + "=" * 80)
