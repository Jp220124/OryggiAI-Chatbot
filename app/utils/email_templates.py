"""
Email Template Renderer
Renders HTML email templates using Jinja2
"""

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from loguru import logger

from app.config import settings


class EmailTemplateRenderer:
    """
    Renders email templates using Jinja2

    Templates location: templates/email/

    Available templates:
    - base_email.html (base template)
    - report_notification.html (report delivery notification)

    Example:
        renderer = EmailTemplateRenderer()
        html = renderer.render_report_notification(
            question="Show me sales data",
            rows_count=150,
            attachment_name="report.pdf"
        )
    """

    def __init__(self, templates_dir: Optional[str] = None):
        """
        Initialize template renderer

        Args:
            templates_dir: Path to templates directory (default: ./templates)
        """
        if templates_dir is None:
            # Default to ./templates relative to project root
            templates_dir = Path(__file__).parent.parent.parent / "templates"
        else:
            templates_dir = Path(templates_dir)

        if not templates_dir.exists():
            logger.warning(f"Templates directory not found: {templates_dir}")
            # Create directory if it doesn't exist
            templates_dir.mkdir(parents=True, exist_ok=True)

        # Initialize Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(['html', 'xml'])
        )

        logger.info(f"[EmailTemplateRenderer] Initialized with templates: {templates_dir}")

    def render_report_notification(
        self,
        question: str,
        rows_count: int,
        attachment_name: str,
        format: str,
        user_id: str,
        user_name: Optional[str] = None,
        sql_query: Optional[str] = None,
        show_sql: bool = False,
        truncated: bool = False,
        max_rows: Optional[int] = None,
        attachment_size: Optional[str] = None,
        dashboard_url: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Render report notification email template

        Args:
            question: User's query
            rows_count: Number of rows in report
            attachment_name: Name of attached file
            format: Report format (pdf/excel)
            user_id: User who requested report
            user_name: User's display name (optional)
            sql_query: SQL query executed (optional)
            show_sql: Show SQL query in email (default: False)
            truncated: Whether results were truncated
            max_rows: Max rows if truncated
            attachment_size: Human-readable file size (e.g., "2.5 MB")
            dashboard_url: Link to dashboard (optional)
            **kwargs: Additional template variables

        Returns:
            Rendered HTML string
        """
        try:
            template = self.env.get_template('email/report_notification.html')

            # Build template context
            context = {
                # Report details
                "question": question,
                "rows_count": rows_count,
                "attachment_name": attachment_name,
                "format": format,
                "sql_query": sql_query,
                "show_sql": show_sql,
                "truncated": truncated,
                "max_rows": max_rows,
                "attachment_size": attachment_size,

                # User details
                "user_id": user_id,
                "user_name": user_name,

                # URLs
                "dashboard_url": dashboard_url,

                # App details
                "app_name": settings.app_name,
                "app_tagline": "AI-Powered Business Intelligence",
                "support_email": settings.sendgrid_from_email,

                # Timestamp
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "current_year": datetime.now().year,

                # Custom variables
                **kwargs
            }

            html = template.render(**context)
            logger.debug("[EmailTemplateRenderer] Rendered report_notification template")
            return html

        except Exception as e:
            logger.error(f"[EmailTemplateRenderer] Template rendering failed: {str(e)}")
            # Fallback to simple HTML
            return self._fallback_report_email(
                question=question,
                rows_count=rows_count,
                attachment_name=attachment_name
            )

    def render_custom_template(
        self,
        template_name: str,
        **context
    ) -> str:
        """
        Render a custom email template

        Args:
            template_name: Name of template file (e.g., "email/custom.html")
            **context: Template variables

        Returns:
            Rendered HTML string
        """
        try:
            template = self.env.get_template(template_name)

            # Add default context variables
            default_context = {
                "app_name": settings.app_name,
                "current_year": datetime.now().year,
                "support_email": settings.sendgrid_from_email
            }

            # Merge with provided context
            full_context = {**default_context, **context}

            html = template.render(**full_context)
            logger.debug(f"[EmailTemplateRenderer] Rendered {template_name}")
            return html

        except Exception as e:
            logger.error(f"[EmailTemplateRenderer] Failed to render {template_name}: {str(e)}")
            raise

    def _fallback_report_email(
        self,
        question: str,
        rows_count: int,
        attachment_name: str
    ) -> str:
        """
        Fallback HTML email if template rendering fails

        Args:
            question: User query
            rows_count: Number of rows
            attachment_name: Attachment filename

        Returns:
            Simple HTML email
        """
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; padding: 20px; }}
                .container {{ max-width: 600px; margin: 0 auto; }}
                h1 {{ color: #333; }}
                p {{ color: #666; line-height: 1.6; }}
                .info {{ background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>📊 Your Report is Ready!</h1>
                <p>Your requested report has been generated and is attached to this email.</p>

                <div class="info">
                    <p><strong>Query:</strong> {question}</p>
                    <p><strong>Records:</strong> {rows_count}</p>
                    <p><strong>Attachment:</strong> {attachment_name}</p>
                </div>

                <p>Thank you for using {settings.app_name}!</p>
            </div>
        </body>
        </html>
        """


# Global template renderer instance
email_template_renderer = EmailTemplateRenderer()
