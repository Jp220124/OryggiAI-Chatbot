"""
Simple Email Test Script (Windows Compatible)
Tests Phase 4 email functionality without Unicode issues
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app.tools.email_tools import send_email_tool
from app.middleware.email_validator import email_validator
from app.utils.email_templates import email_template_renderer
from app.config import settings


def test_configuration():
    """Test email configuration"""
    print("=" * 80)
    print("EMAIL CONFIGURATION TEST")
    print("=" * 80)

    print(f"\nSendGrid Configured: {send_email_tool.use_sendgrid}")
    if send_email_tool.use_sendgrid:
        print(f"   API Key: {settings.sendgrid_api_key[:20]}...")

    print(f"\nSMTP Configured: {send_email_tool.use_smtp}")
    if send_email_tool.use_smtp:
        print(f"   Server: {settings.smtp_server}:{settings.smtp_port}")
        print(f"   Username: {settings.smtp_username}")
        print(f"   From: {settings.sendgrid_from_email}")
        print(f"   From Name: {settings.sendgrid_from_name}")
        print(f"   TLS: {settings.smtp_use_tls}")

    if not send_email_tool.use_sendgrid and not send_email_tool.use_smtp:
        print("\n[ERROR] No email provider configured!")
        return False

    print("\n[OK] Email provider configured successfully")
    return True


def test_validation():
    """Test email validation"""
    print("\n" + "=" * 80)
    print("EMAIL VALIDATION TEST")
    print("=" * 80)

    test_cases = [
        ("valid.email@company.com", True, "Valid email"),
        ("invalid.email", False, "Invalid format"),
        ("test@tempmail.com", False, "Blocked domain"),
    ]

    passed = 0
    failed = 0

    for email, should_pass, description in test_cases:
        is_valid, error = email_validator.validate_email(
            recipient=email,
            user_id="test_user",
            check_rate_limit=False
        )

        if is_valid == should_pass:
            print(f"\n[PASS] {description}: {email}")
            passed += 1
        else:
            print(f"\n[FAIL] {description}: {email}")
            if error:
                print(f"   Error: {error}")
            failed += 1

    print(f"\n\nValidation Tests: {passed} passed, {failed} failed")
    return failed == 0


def test_template():
    """Test email template rendering"""
    print("\n" + "=" * 80)
    print("EMAIL TEMPLATE RENDERING TEST")
    print("=" * 80)

    try:
        html = email_template_renderer.render_report_notification(
            question="Show me all employees in Engineering",
            rows_count=42,
            attachment_name="report_test.pdf",
            format="pdf",
            user_id="test_user",
            sql_query="SELECT * FROM Employees WHERE Department = 'Engineering'",
            show_sql=True,
            truncated=False,
            max_rows=10000,
            attachment_size="1.2 MB"
        )

        print("\n[OK] Template rendered successfully!")
        print(f"   HTML length: {len(html)} characters")

        # Save template
        output_path = Path(__file__).parent / "test_email_output.html"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"   Saved to: {output_path}")
        print("   You can open this file in your browser to preview")

        return True

    except Exception as e:
        print(f"\n[ERROR] Template rendering failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_send_email():
    """Test sending an actual email"""
    print("\n" + "=" * 80)
    print("EMAIL SENDING TEST")
    print("=" * 80)

    # Use the SMTP username as test recipient
    recipient = settings.smtp_username
    print(f"\nTest recipient: {recipient}")

    # Validate email
    is_valid, error = email_validator.validate_email(
        recipient=recipient,
        user_id="test_admin",
        user_role="ADMIN",
        check_rate_limit=True
    )

    if not is_valid:
        print(f"\n[ERROR] Email validation failed: {error}")
        return False

    print("[OK] Email validation passed")

    # Render test email
    html = email_template_renderer.render_report_notification(
        question="Test Report - Phase 4 Email Integration",
        rows_count=100,
        attachment_name="test_report.pdf",
        format="pdf",
        user_id="test_admin",
        sql_query="SELECT * FROM TestTable LIMIT 100",
        show_sql=True,
        truncated=False,
        max_rows=10000,
        attachment_size="500 KB"
    )

    # Send email
    print("\nSending test email...")

    result = send_email_tool.run(
        user_role="ADMIN",
        recipient=recipient,
        subject="Test Email - OryggiAI Chatbot Phase 4",
        body_html=html,
        body_text="This is a test email from OryggiAI Chatbot Phase 4 Email Integration.",
        user_id="test_admin"
    )

    if result.get("success") and result.get("result", {}).get("success"):
        print("\n[SUCCESS] EMAIL SENT SUCCESSFULLY!")
        print(f"   Message ID: {result['result'].get('message_id')}")
        print(f"   Recipient: {result['result']['recipient']}")
        print(f"   Time: {result['result']['execution_time_ms']:.2f}ms")

        # Record for rate limiting
        email_validator.record_email_sent("test_admin")

        return True
    else:
        error = result.get("result", {}).get("error") or result.get("error")
        print(f"\n[ERROR] EMAIL SENDING FAILED!")
        print(f"   Error: {error}")
        return False


def test_rate_limiting():
    """Test rate limiting"""
    print("\n" + "=" * 80)
    print("RATE LIMITING TEST")
    print("=" * 80)

    user_id = "test_rate_limit"

    # Get initial stats
    stats = email_validator.get_user_stats(user_id)
    print(f"\nInitial Stats:")
    print(f"   Emails last hour: {stats['emails_last_hour']}")
    print(f"   Remaining: {stats['remaining_hour']}/{stats['max_per_hour']}")

    # Simulate sending 5 emails
    print("\nSimulating 5 email sends...")
    for i in range(5):
        email_validator.record_email_sent(user_id)

    # Check updated stats
    stats = email_validator.get_user_stats(user_id)
    print(f"\nAfter 5 emails:")
    print(f"   Emails last hour: {stats['emails_last_hour']}")
    print(f"   Remaining: {stats['remaining_hour']}/{stats['max_per_hour']}")

    # Cleanup
    email_validator.reset_user_limits(user_id)
    print("\n[OK] Rate limiting test complete")

    return True


def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("PHASE 4 EMAIL INTEGRATION - TEST SUITE")
    print("OryggiAI Chatbot - Email Functionality Testing")
    print("=" * 80)

    results = {}

    # Test 1: Configuration
    print("\n\n[TEST 1/5] Email Configuration")
    results['configuration'] = test_configuration()
    if not results['configuration']:
        print("\n[ABORT] Cannot proceed without email configuration")
        return

    # Test 2: Validation
    print("\n\n[TEST 2/5] Email Validation")
    results['validation'] = test_validation()

    # Test 3: Template
    print("\n\n[TEST 3/5] Email Template Rendering")
    results['template'] = test_template()

    # Test 4: Rate Limiting
    print("\n\n[TEST 4/5] Rate Limiting")
    results['rate_limiting'] = test_rate_limiting()

    # Test 5: Send Email
    print("\n\n[TEST 5/5] Send Actual Email")
    confirm = input("\nDo you want to send a test email to yourself? (y/n): ").strip().lower()

    if confirm == 'y':
        results['send_email'] = test_send_email()
    else:
        print("\n[SKIPPED] Email sending test")
        results['send_email'] = None

    # Summary
    print("\n\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)

    for test_name, result in results.items():
        if result is True:
            status = "[PASS]"
        elif result is False:
            status = "[FAIL]"
        else:
            status = "[SKIP]"

        print(f"{status} {test_name.replace('_', ' ').title()}")

    # Final verdict
    passed = sum(1 for r in results.values() if r is True)
    failed = sum(1 for r in results.values() if r is False)
    skipped = sum(1 for r in results.values() if r is None)

    print("\n" + "=" * 80)
    print(f"Results: {passed} passed, {failed} failed, {skipped} skipped")
    print("=" * 80)

    if failed == 0:
        print("\n[SUCCESS] All tests passed!")
        print("\nPhase 4 Email Integration is working correctly!")
        print("\nNext steps:")
        print("1. Check your email inbox for the test email")
        print("2. Review test_email_output.html in your browser")
        print("3. Try the API endpoint:")
        print("   POST /api/reports/generate")
        print("   with 'email_to' parameter")
    else:
        print("\n[WARNING] Some tests failed. Check errors above.")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[ABORT] Test interrupted by user")
    except Exception as e:
        print(f"\n\n[ERROR] Test suite failed: {str(e)}")
        import traceback
        traceback.print_exc()
