"""
Automatic Email Test - Sends test email without user interaction
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.tools.email_tools import send_email_tool
from app.middleware.email_validator import email_validator
from app.utils.email_templates import email_template_renderer
from app.config import settings


def send_test_email():
    """Send test email automatically"""
    print("=" * 80)
    print("SENDING TEST EMAIL")
    print("=" * 80)

    # Use SMTP username as recipient
    recipient = settings.smtp_username
    print(f"\nRecipient: {recipient}")
    print(f"From: {settings.sendgrid_from_name} <{settings.sendgrid_from_email}>")
    print(f"Provider: SMTP ({settings.smtp_server})")

    # Validate email
    is_valid, error = email_validator.validate_email(
        recipient=recipient,
        user_id="auto_test",
        user_role="ADMIN",
        check_rate_limit=True
    )

    if not is_valid:
        print(f"\n[ERROR] Validation failed: {error}")
        return False

    print("[OK] Email validated")

    # Render HTML email
    print("\nRendering email template...")
    html = email_template_renderer.render_report_notification(
        question="Test Report - OryggiAI Chatbot Phase 4 Email Integration",
        rows_count=150,
        attachment_name="sample_report.pdf",
        format="pdf",
        user_id="admin_user",
        sql_query="SELECT * FROM EmployeeMaster WHERE Department = 'Engineering' ORDER BY DateofJoin DESC",
        show_sql=True,
        truncated=False,
        max_rows=10000,
        attachment_size="1.5 MB"
    )
    print(f"[OK] Template rendered ({len(html)} chars)")

    # Send email
    print("\nSending email via SMTP...")
    result = send_email_tool.run(
        user_role="ADMIN",
        recipient=recipient,
        subject="[TEST] OryggiAI Chatbot - Phase 4 Email Integration Complete",
        body_html=html,
        body_text=(
            "This is a test email from OryggiAI Chatbot.\n\n"
            "Phase 4 Email Integration has been successfully implemented!\n\n"
            "Features:\n"
            "- SendGrid & SMTP support\n"
            "- Beautiful HTML templates\n"
            "- Email validation & rate limiting\n"
            "- Report delivery with attachments\n"
            "- Complete audit logging\n\n"
            "-- OryggiAI Chatbot"
        ),
        user_id="auto_test"
    )

    if result.get("success") and result.get("result", {}).get("success"):
        print("\n" + "=" * 80)
        print("[SUCCESS] EMAIL SENT SUCCESSFULLY!")
        print("=" * 80)
        print(f"\nMessage ID: {result['result'].get('message_id')}")
        print(f"Recipient: {result['result']['recipient']}")
        print(f"Execution Time: {result['result']['execution_time_ms']:.2f}ms")
        print(f"\nCheck your inbox: {recipient}")
        print("\nEmail Details:")
        print("  - Subject: [TEST] OryggiAI Chatbot - Phase 4 Email Integration Complete")
        print("  - Format: HTML + Plain Text")
        print("  - Template: Report Notification Template")
        print("=" * 80)

        # Record for rate limiting
        email_validator.record_email_sent("auto_test")

        return True
    else:
        error = result.get("result", {}).get("error") or result.get("error")
        print("\n" + "=" * 80)
        print("[ERROR] EMAIL SENDING FAILED!")
        print("=" * 80)
        print(f"\nError: {error}")
        print("\nTroubleshooting:")
        print("1. Check SMTP credentials in .env")
        print("2. Verify Gmail App Password is correct")
        print("3. Check logs: logs/advance_chatbot.log")
        print("=" * 80)
        return False


if __name__ == "__main__":
    print("\nOryggiAI Chatbot - Phase 4 Email Integration")
    print("Automatic Email Test\n")

    try:
        success = send_test_email()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[EXCEPTION] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
