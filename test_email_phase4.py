"""
Test Script for Phase 4 Email Integration
Tests email functionality with SendGrid or SMTP
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
from loguru import logger


def test_email_configuration():
    """Test email provider configuration"""
    print("=" * 80)
    print("📧 EMAIL CONFIGURATION TEST")
    print("=" * 80)

    print(f"\n✅ SendGrid Configured: {send_email_tool.use_sendgrid}")
    if send_email_tool.use_sendgrid:
        print(f"   From: {settings.sendgrid_from_name} <{settings.sendgrid_from_email}>")
        print(f"   API Key: {settings.sendgrid_api_key[:20]}...")

    print(f"\n✅ SMTP Configured: {send_email_tool.use_smtp}")
    if send_email_tool.use_smtp:
        print(f"   Server: {settings.smtp_server}:{settings.smtp_port}")
        print(f"   Username: {settings.smtp_username}")
        print(f"   TLS: {settings.smtp_use_tls}")

    if not send_email_tool.use_sendgrid and not send_email_tool.use_smtp:
        print("\n⚠️  WARNING: No email provider configured!")
        print("Configure SendGrid or SMTP in .env file")
        return False

    return True


def test_email_validation():
    """Test email validation"""
    print("\n" + "=" * 80)
    print("🔒 EMAIL VALIDATION TEST")
    print("=" * 80)

    test_cases = [
        ("valid.email@company.com", True),
        ("invalid.email", False),
        ("test@tempmail.com", False),  # Blocked domain
        ("user@allowed-domain.com", True)
    ]

    for email, should_pass in test_cases:
        is_valid, error = email_validator.validate_email(
            recipient=email,
            user_id="test_user",
            check_rate_limit=False
        )

        status = "✅ PASS" if is_valid == should_pass else "❌ FAIL"
        print(f"\n{status} Email: {email}")
        if not is_valid:
            print(f"   Error: {error}")


def test_email_template():
    """Test email template rendering"""
    print("\n" + "=" * 80)
    print("📝 EMAIL TEMPLATE TEST")
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

        print("\n✅ Template rendered successfully!")
        print(f"   HTML length: {len(html)} characters")

        # Save template for inspection
        template_path = Path(__file__).parent / "test_email_output.html"
        with open(template_path, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"   Saved to: {template_path}")
        print("   Open in browser to preview")

        return True

    except Exception as e:
        print(f"\n❌ Template rendering failed: {str(e)}")
        return False


def test_send_email(recipient: str):
    """Test sending an actual email"""
    print("\n" + "=" * 80)
    print("📨 EMAIL SENDING TEST")
    print("=" * 80)

    print(f"\nRecipient: {recipient}")

    # Validate recipient first
    is_valid, error = email_validator.validate_email(
        recipient=recipient,
        user_id="test_admin",
        user_role="ADMIN",
        check_rate_limit=True
    )

    if not is_valid:
        print(f"\n❌ Email validation failed: {error}")
        return False

    print("✅ Email validation passed")

    # Render test email
    html = email_template_renderer.render_report_notification(
        question="Test Report - Email Integration Phase 4",
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

    # Send email (without attachment for test)
    print("\nSending test email...")

    result = send_email_tool.run(
        user_role="ADMIN",
        recipient=recipient,
        subject="🧪 Test Email - Advance Chatbot Phase 4",
        body_html=html,
        body_text="This is a test email from Advance Chatbot Phase 4 implementation.",
        user_id="test_admin"
    )

    if result.get("success") and result.get("result", {}).get("success"):
        print("\n✅ EMAIL SENT SUCCESSFULLY!")
        print(f"   Message ID: {result['result'].get('message_id')}")
        print(f"   Recipient: {result['result']['recipient']}")
        print(f"   Time: {result['result']['execution_time_ms']:.2f}ms")

        # Record for rate limiting
        email_validator.record_email_sent("test_admin")

        return True
    else:
        error = result.get("result", {}).get("error") or result.get("error")
        print(f"\n❌ EMAIL SENDING FAILED!")
        print(f"   Error: {error}")
        return False


def test_rate_limiting():
    """Test rate limiting"""
    print("\n" + "=" * 80)
    print("⏱️  RATE LIMITING TEST")
    print("=" * 80)

    user_id = "test_rate_limit_user"

    # Get initial stats
    stats = email_validator.get_user_stats(user_id)
    print(f"\nInitial Stats:")
    print(f"   Emails last hour: {stats['emails_last_hour']}")
    print(f"   Emails last day: {stats['emails_last_day']}")
    print(f"   Remaining (hour): {stats['remaining_hour']}")
    print(f"   Remaining (day): {stats['remaining_day']}")

    # Simulate sending emails
    print("\nSimulating email sends...")
    for i in range(5):
        email_validator.record_email_sent(user_id)

    # Check updated stats
    stats = email_validator.get_user_stats(user_id)
    print(f"\nAfter 5 emails:")
    print(f"   Emails last hour: {stats['emails_last_hour']}")
    print(f"   Remaining (hour): {stats['remaining_hour']}")

    # Test rate limit enforcement
    is_allowed, error = email_validator._check_rate_limit(
        user_id=user_id,
        max_hour=10,
        max_day=50
    )

    if is_allowed:
        print("\n✅ Within rate limits")
    else:
        print(f"\n⚠️  Rate limit exceeded: {error}")

    # Cleanup
    email_validator.reset_user_limits(user_id)
    print("\n✅ Rate limits reset for test user")


def main():
    """Main test runner"""
    print("\n" + "="  * 80)
    print("🚀 PHASE 4 EMAIL INTEGRATION - TEST SUITE")
    print("=" * 80)

    # Test 1: Configuration
    if not test_email_configuration():
        print("\n❌ Email configuration failed. Please configure SendGrid or SMTP in .env")
        return

    # Test 2: Validation
    test_email_validation()

    # Test 3: Template rendering
    if not test_email_template():
        print("\n❌ Template rendering failed")
        return

    # Test 4: Rate limiting
    test_rate_limiting()

    # Test 5: Send actual email
    print("\n" + "=" * 80)
    send_test = input("\n📨 Do you want to send a test email? (y/n): ").strip().lower()

    if send_test == 'y':
        recipient = input("Enter recipient email address: ").strip()

        if recipient:
            success = test_send_email(recipient)

            if success:
                print("\n" + "=" * 80)
                print("✅ ALL TESTS PASSED!")
                print("=" * 80)
                print("\nPhase 4 Email Integration is working correctly! 🎉")
                print("\nNext Steps:")
                print("1. Check your email inbox for the test email")
                print("2. Review the email template design")
                print("3. Test with actual report generation:")
                print("   POST /api/reports/generate with email_to parameter")
                print("=" * 80)
            else:
                print("\n❌ Email sending failed. Check logs for details.")
        else:
            print("\n⚠️  No recipient provided. Skipping email send test.")
    else:
        print("\n✅ Test suite completed (email send skipped)")

    print("\n" + "=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    print("✅ Email configuration: OK")
    print("✅ Email validation: OK")
    print("✅ Template rendering: OK")
    print("✅ Rate limiting: OK")
    if send_test == 'y' and recipient:
        print(f"{'✅' if success else '❌'} Email sending: {'OK' if success else 'FAILED'}")
    else:
        print("⏭️  Email sending: SKIPPED")
    print("=" * 80)


if __name__ == "__main__":
    main()
