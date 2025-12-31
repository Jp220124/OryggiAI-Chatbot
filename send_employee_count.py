"""
Send Total Employee Count to Priyanshu Kumar
Queries the database and emails the employee count
"""

import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from datetime import datetime
import asyncio

sys.path.insert(0, str(Path(__file__).parent))

from app.tools.email_tools import send_email_tool
from app.middleware.email_validator import email_validator
from app.utils.email_templates import email_template_renderer
from app.config import settings


def get_total_employees():
    """Query database for total employee count"""
    print("\n" + "=" * 80)
    print("QUERYING DATABASE FOR TOTAL EMPLOYEE COUNT")
    print("=" * 80)

    try:
        # Create database connection
        print(f"\nConnecting to database: {settings.db_server}/{settings.db_name}")
        engine = create_engine(settings.database_url)

        # Query total employees
        with engine.connect() as conn:
            # Get total count of all employees
            result = conn.execute(text("SELECT COUNT(*) as total FROM dbo.EmployeeMaster"))
            total_count = result.fetchone()[0]

            # Get active employees count
            result = conn.execute(text("SELECT COUNT(*) as active FROM dbo.EmployeeMaster WHERE Active = 1"))
            active_count = result.fetchone()[0]

            # Get inactive employees count
            inactive_count = total_count - active_count

        print(f"[OK] Query successful")
        print(f"\nTotal Employees: {total_count}")
        print(f"  - Active: {active_count}")
        print(f"  - Inactive: {inactive_count}")

        return {
            'total': total_count,
            'active': active_count,
            'inactive': inactive_count
        }

    except Exception as e:
        print(f"[ERROR] Database query failed: {str(e)}")
        raise


async def send_employee_count_email(employee_data):
    """Send email with employee count to Priyanshu Kumar"""
    print("\n" + "=" * 80)
    print("SENDING EMPLOYEE COUNT EMAIL TO PRIYANSHU KUMAR")
    print("=" * 80)

    # Recipient
    recipient = "priyanshu.kumar@oryggitech.com"
    print(f"\nRecipient: {recipient}")
    print(f"From: {settings.sendgrid_from_name} <{settings.sendgrid_from_email}>")

    # Validate email
    print("\nValidating email address...")
    is_valid, error = email_validator.validate_email(
        recipient=recipient,
        user_id="admin",
        user_role="ADMIN",
        check_rate_limit=True
    )

    if not is_valid:
        print(f"[ERROR] Validation failed: {error}")
        return False

    print("[OK] Email validated successfully")

    # Create HTML email content
    current_date = datetime.now().strftime("%B %d, %Y at %I:%M %p")

    html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
            border-radius: 10px 10px 0 0;
        }}
        .header h1 {{
            margin: 0;
            font-size: 28px;
        }}
        .header p {{
            margin: 10px 0 0 0;
            font-size: 14px;
            opacity: 0.9;
        }}
        .content {{
            background: white;
            padding: 30px;
            border: 1px solid #e0e0e0;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
            margin: 30px 0;
        }}
        .stat-card {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
            border: 2px solid #e9ecef;
        }}
        .stat-card.total {{
            border-color: #667eea;
        }}
        .stat-card.active {{
            border-color: #51cf66;
        }}
        .stat-card.inactive {{
            border-color: #ff6b6b;
        }}
        .stat-number {{
            font-size: 36px;
            font-weight: bold;
            margin: 10px 0;
        }}
        .stat-card.total .stat-number {{
            color: #667eea;
        }}
        .stat-card.active .stat-number {{
            color: #51cf66;
        }}
        .stat-card.inactive .stat-number {{
            color: #ff6b6b;
        }}
        .stat-label {{
            font-size: 14px;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .metadata {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin-top: 30px;
            font-size: 13px;
            color: #666;
        }}
        .metadata p {{
            margin: 5px 0;
        }}
        .footer {{
            background: #f8f9fa;
            padding: 20px;
            text-align: center;
            border-radius: 0 0 10px 10px;
            border: 1px solid #e0e0e0;
            border-top: none;
        }}
        .footer p {{
            margin: 5px 0;
            color: #666;
            font-size: 13px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Employee Database Report</h1>
        <p>OryggiAI Database Assistant</p>
    </div>

    <div class="content">
        <h2>Total Employee Count</h2>
        <p>Here's the current employee data from the OryggiAI database:</p>

        <div class="stats-grid">
            <div class="stat-card total">
                <div class="stat-label">Total</div>
                <div class="stat-number">{employee_data['total']}</div>
                <div class="stat-label">Employees</div>
            </div>
            <div class="stat-card active">
                <div class="stat-label">Active</div>
                <div class="stat-number">{employee_data['active']}</div>
                <div class="stat-label">Employees</div>
            </div>
            <div class="stat-card inactive">
                <div class="stat-label">Inactive</div>
                <div class="stat-number">{employee_data['inactive']}</div>
                <div class="stat-label">Employees</div>
            </div>
        </div>

        <div class="metadata">
            <p><strong>Database:</strong> {settings.db_name}</p>
            <p><strong>Server:</strong> {settings.db_server}</p>
            <p><strong>Generated:</strong> {current_date}</p>
            <p><strong>Query:</strong> SELECT COUNT(*) FROM dbo.EmployeeMaster</p>
        </div>

        <p style="margin-top: 30px;">
            This data was automatically retrieved from the OryggiAI employee database.
            For more detailed reports or queries, please use the OryggiAI Database Assistant at
            <a href="http://localhost:9000">http://localhost:9000</a>.
        </p>
    </div>

    <div class="footer">
        <p><strong>OryggiAI Database Assistant</strong></p>
        <p>AI-Powered Business Intelligence</p>
        <p style="color: #999; font-size: 12px;">This is an automated report generated by OryggiAI</p>
    </div>
</body>
</html>
"""

    # Plain text version
    plain_text = f"""
OryggiAI Database Assistant - Employee Count Report
{'=' * 60}

Total Employee Count
{'=' * 60}

Total Employees:    {employee_data['total']}
Active Employees:   {employee_data['active']}
Inactive Employees: {employee_data['inactive']}

Database Information:
- Database: {settings.db_name}
- Server: {settings.db_server}
- Generated: {current_date}
- Query: SELECT COUNT(*) FROM dbo.EmployeeMaster

This data was automatically retrieved from the OryggiAI employee database.
For more detailed reports or queries, please use the OryggiAI Database Assistant.

---
OryggiAI Database Assistant
AI-Powered Business Intelligence
"""

    # Send email
    print("\nSending email...")
    print(f"Subject: Employee Count Report - {employee_data['total']} Total Employees")

    result = await send_email_tool.run(
        user_role="ADMIN",
        recipient=recipient,
        subject=f"Employee Count Report - {employee_data['total']} Total Employees",
        body_html=html_body,
        body_text=plain_text.strip(),
        user_id="admin"
    )

    # Check result
    if result.get("success") and result.get("result", {}).get("success"):
        print("\n" + "=" * 80)
        print("[SUCCESS] EMAIL SENT SUCCESSFULLY!")
        print("=" * 80)
        print(f"\nRecipient: {result['result']['recipient']}")
        print(f"Message ID: {result['result'].get('message_id')}")
        print(f"Execution Time: {result['result']['execution_time_ms']:.2f}ms")
        print(f"\nEmail Details:")
        print(f"  - Total Employees: {employee_data['total']}")
        print(f"  - Active: {employee_data['active']}")
        print(f"  - Inactive: {employee_data['inactive']}")
        print(f"  - Format: HTML + Plain Text")
        print(f"\nPriyanshu should receive this email at:")
        print(f"  priyanshu.kumar@oryggitech.com")
        print("=" * 80)

        # Record for rate limiting
        email_validator.record_email_sent("admin")

        return True
    else:
        error = result.get("result", {}).get("error") or result.get("error")
        print("\n" + "=" * 80)
        print("[ERROR] EMAIL SENDING FAILED!")
        print("=" * 80)
        print(f"\nError: {error}")
        print("\nPlease check:")
        print("  1. Email configuration in .env file")
        print("  2. Internet connection")
        print("  3. Email provider credentials")
        print("=" * 80)
        return False


async def main():
    """Main execution function"""
    print("\n")
    print("=" * 80)
    print("   EMPLOYEE COUNT REPORT EMAILER")
    print("   Querying Database & Sending to Priyanshu Kumar")
    print("=" * 80)

    try:
        # Step 1: Get employee data from database
        employee_data = get_total_employees()

        # Step 2: Send email with the data
        success = await send_employee_count_email(employee_data)

        if success:
            print("\n[DONE] Employee count successfully sent to Priyanshu Kumar!")
            print("\nNext steps:")
            print("  1. Priyanshu can check his email inbox")
            print("  2. Email contains:")
            print(f"     - Total: {employee_data['total']} employees")
            print(f"     - Active: {employee_data['active']} employees")
            print(f"     - Inactive: {employee_data['inactive']} employees")
            print("  3. Check logs: logs/audit.log for delivery confirmation")

        sys.exit(0 if success else 1)

    except Exception as e:
        print(f"\n[EXCEPTION] {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
