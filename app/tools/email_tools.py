"""
Send Email Tool
Sends emails with optional attachments (reports) using SendGrid or SMTP
"""

from typing import Any, Dict, List, Optional
from pathlib import Path
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from loguru import logger
import os
import time

from app.tools.base_tool import ChatbotTool
from app.middleware.audit_logger import audit_logger
from app.config import settings


class SendEmailTool(ChatbotTool):
    """
    Tool for sending emails with optional file attachments

    Features:
    - SendGrid API support (primary)
    - SMTP fallback support
    - HTML email templates
    - File attachments (PDF/Excel reports)
    - RBAC enforcement
    - Rate limiting (via middleware)
    - Audit logging

    Example:
        result = send_email_tool.run(
            user_role="HR_MANAGER",
            recipient="manager@company.com",
            subject="Monthly Report",
            body_html="<h1>Report attached</h1>",
            attachment_path="./reports_output/report.pdf"
        )
    """

    name = "send_email"
    description = (
        "Send email with optional file attachment. "
        "Supports HTML content and PDF/Excel attachments. "
        "Available to ADMIN and HR_MANAGER roles."
    )
    rbac_required = ["ADMIN", "HR_MANAGER"]
    destructive = False

    def __init__(self):
        """Initialize email tool and validate configuration"""
        super().__init__()

        # Determine email provider
        self.use_sendgrid = bool(settings.sendgrid_api_key)
        self.use_smtp = bool(settings.smtp_server)

        if not self.use_sendgrid and not self.use_smtp:
            logger.warning(
                "[WARNING]  No email provider configured! "
                "Set SENDGRID_API_KEY or SMTP_* environment variables."
            )
        elif self.use_sendgrid:
            logger.info("📧 Email provider: SendGrid")
        else:
            logger.info("📧 Email provider: SMTP")

    def _run(
        self,
        recipient: str,
        subject: str,
        body_html: Optional[str] = None,
        body_text: Optional[str] = None,
        attachment_path: Optional[str] = None,
        attachment_name: Optional[str] = None,
        user_id: str = "system",
        user_role: Optional[str] = None,
        **kwargs
    ) -> Any:
        """
        Send email with optional attachment

        Args:
            recipient: Email address of recipient
            subject: Email subject line
            body_html: HTML body content (optional)
            body_text: Plain text body content (optional)
            attachment_path: Path to file attachment (optional)
            attachment_name: Custom attachment filename (optional)
            user_id: User sending the email
            user_role: User's role
            **kwargs: Additional arguments

        Returns:
            {
                "success": bool,
                "message_id": str (if SendGrid),
                "recipient": str,
                "subject": str
            }

        Raises:
            ValueError: If no email body provided or recipient invalid
            Exception: If email sending fails
        """
        start_time = time.time()

        try:
            # Validate inputs
            if not recipient:
                raise ValueError("Recipient email is required")

            if not body_html and not body_text:
                raise ValueError("Email body (HTML or text) is required")

            # Validate attachment if provided
            if attachment_path:
                attachment_path = Path(attachment_path)
                if not attachment_path.exists():
                    raise FileNotFoundError(f"Attachment not found: {attachment_path}")

                # Set attachment name
                if not attachment_name:
                    attachment_name = attachment_path.name

            logger.info(
                f"[{self.name}] Sending email to {recipient} "
                f"(attachment: {attachment_name or 'none'})"
            )

            # Send email using configured provider
            if self.use_sendgrid:
                result = self._send_via_sendgrid(
                    recipient=recipient,
                    subject=subject,
                    body_html=body_html,
                    body_text=body_text,
                    attachment_path=attachment_path,
                    attachment_name=attachment_name
                )
            elif self.use_smtp:
                result = self._send_via_smtp(
                    recipient=recipient,
                    subject=subject,
                    body_html=body_html,
                    body_text=body_text,
                    attachment_path=attachment_path,
                    attachment_name=attachment_name
                )
            else:
                raise Exception(
                    "No email provider configured. "
                    "Set SENDGRID_API_KEY or SMTP_* environment variables."
                )

            # Calculate execution time
            execution_time = (time.time() - start_time) * 1000  # ms

            # Audit log
            audit_logger.log_tool_execution(
                user_id=user_id,
                user_role=user_role or "UNKNOWN",
                tool_name=self.name,
                success=True,
                execution_time_ms=execution_time,
                recipient=recipient,
                subject=subject,
                has_attachment=bool(attachment_path),
                provider="sendgrid" if self.use_sendgrid else "smtp"
            )

            logger.success(
                f"[{self.name}] Email sent successfully to {recipient} "
                f"({execution_time:.2f}ms)"
            )

            return {
                "success": True,
                "recipient": recipient,
                "subject": subject,
                "message_id": result.get("message_id"),
                "has_attachment": bool(attachment_path),
                "execution_time_ms": execution_time
            }

        except Exception as e:
            logger.error(f"[{self.name}] Email sending failed: {str(e)}", exc_info=True)

            # Audit log failure
            audit_logger.log_tool_execution(
                user_id=user_id,
                user_role=user_role or "UNKNOWN",
                tool_name=self.name,
                success=False,
                error=str(e)
            )

            return {
                "success": False,
                "error": str(e),
                "recipient": recipient
            }

    def _send_via_sendgrid(
        self,
        recipient: str,
        subject: str,
        body_html: Optional[str],
        body_text: Optional[str],
        attachment_path: Optional[Path],
        attachment_name: Optional[str]
    ) -> Dict[str, Any]:
        """
        Send email using SendGrid API

        Args:
            recipient: Email address
            subject: Email subject
            body_html: HTML content
            body_text: Plain text content
            attachment_path: File to attach
            attachment_name: Attachment filename

        Returns:
            {"message_id": str}
        """
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import (
                Mail, Attachment, FileContent, FileName,
                FileType, Disposition
            )
            import base64

            logger.debug("[SendGrid] Preparing email message")

            # Create message
            message = Mail(
                from_email=(settings.sendgrid_from_email, settings.sendgrid_from_name),
                to_emails=recipient,
                subject=subject,
                html_content=body_html,
                plain_text_content=body_text
            )

            # Add attachment if provided
            if attachment_path:
                logger.debug(f"[SendGrid] Attaching file: {attachment_name}")

                with open(attachment_path, 'rb') as f:
                    file_data = f.read()

                # Encode file
                encoded = base64.b64encode(file_data).decode()

                # Determine MIME type
                if attachment_name.endswith('.pdf'):
                    file_type = 'application/pdf'
                elif attachment_name.endswith('.xlsx'):
                    file_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                else:
                    file_type = 'application/octet-stream'

                # Create attachment
                attachment = Attachment(
                    FileContent(encoded),
                    FileName(attachment_name),
                    FileType(file_type),
                    Disposition('attachment')
                )
                message.attachment = attachment

            # Send email
            logger.debug("[SendGrid] Sending email...")
            sg = SendGridAPIClient(settings.sendgrid_api_key)
            response = sg.send(message)

            logger.debug(f"[SendGrid] Response status: {response.status_code}")

            # Extract message ID from headers
            message_id = response.headers.get('X-Message-Id', 'unknown')

            return {
                "message_id": message_id,
                "status_code": response.status_code
            }

        except Exception as e:
            logger.error(f"[SendGrid] Failed to send email: {str(e)}")
            raise Exception(f"SendGrid error: {str(e)}")

    def _send_via_smtp(
        self,
        recipient: str,
        subject: str,
        body_html: Optional[str],
        body_text: Optional[str],
        attachment_path: Optional[Path],
        attachment_name: Optional[str]
    ) -> Dict[str, Any]:
        """
        Send email using SMTP

        Args:
            recipient: Email address
            subject: Email subject
            body_html: HTML content
            body_text: Plain text content
            attachment_path: File to attach
            attachment_name: Attachment filename

        Returns:
            {"message_id": str}
        """
        try:
            logger.info("=" * 80)
            logger.info("[SMTP] ENTERING SMTP EMAIL SEND METHOD")
            logger.info("=" * 80)
            logger.info(f"[SMTP] Recipient: {recipient}")
            logger.info(f"[SMTP] Subject: {subject}")
            logger.info(f"[SMTP] Has body_html: {bool(body_html)}")
            logger.info(f"[SMTP] Has body_text: {bool(body_text)}")
            logger.info(f"[SMTP] Attachment path: {attachment_path}")
            logger.info(f"[SMTP] Attachment name: {attachment_name}")

            logger.info("[SMTP] Preparing email message...")

            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{settings.sendgrid_from_name} <{settings.sendgrid_from_email}>"
            msg['To'] = recipient
            msg['Subject'] = subject

            logger.info(f"[SMTP] From: {msg['From']}")
            logger.info(f"[SMTP] To: {msg['To']}")

            # Add plain text body
            if body_text:
                logger.info(f"[SMTP] Adding plain text body ({len(body_text)} chars)")
                msg.attach(MIMEText(body_text, 'plain'))

            # Add HTML body
            if body_html:
                logger.info(f"[SMTP] Adding HTML body ({len(body_html)} chars)")
                msg.attach(MIMEText(body_html, 'html'))

            # Add attachment if provided
            if attachment_path:
                logger.info(f"[SMTP] Adding attachment: {attachment_name}")
                logger.info(f"[SMTP] Attachment exists: {attachment_path.exists()}")

                with open(attachment_path, 'rb') as f:
                    file_data = f.read()
                    logger.info(f"[SMTP] Attachment size: {len(file_data)} bytes")
                    attachment = MIMEApplication(file_data)

                attachment.add_header(
                    'Content-Disposition',
                    'attachment',
                    filename=attachment_name
                )
                msg.attach(attachment)
                logger.info("[SMTP] Attachment added successfully")

            # Connect to SMTP server
            logger.info(f"[SMTP] Connecting to SMTP server: {settings.smtp_server}:{settings.smtp_port}")
            logger.info(f"[SMTP] TLS enabled: {settings.smtp_use_tls}")
            logger.info(f"[SMTP] Username: {settings.smtp_username}")

            with smtplib.SMTP(settings.smtp_server, settings.smtp_port) as server:
                logger.info("[SMTP] Connected to SMTP server")

                if settings.smtp_use_tls:
                    logger.info("[SMTP] Starting TLS...")
                    server.starttls()
                    logger.info("[SMTP] TLS started successfully")

                # Login if credentials provided
                if settings.smtp_username and settings.smtp_password:
                    logger.info("[SMTP] Authenticating with credentials...")
                    server.login(settings.smtp_username, settings.smtp_password)
                    logger.info("[SMTP] Authentication successful")

                # Send email
                logger.info("[SMTP] Sending email message...")
                server.send_message(msg)
                logger.success("=" * 80)
                logger.success("[SMTP] EMAIL SENT SUCCESSFULLY VIA SMTP!")
                logger.success("=" * 80)

            return {
                "message_id": f"smtp_{recipient}_{subject}",
                "status_code": 200
            }

        except Exception as e:
            logger.error("=" * 80)
            logger.error(f"[SMTP] SMTP EMAIL SEND FAILED: {str(e)}")
            logger.error("=" * 80)
            logger.exception("[SMTP] Full exception traceback:")
            raise Exception(f"SMTP error: {str(e)}")


# Global instance
send_email_tool = SendEmailTool()
