"""
Generate Report Tool
Creates PDF or Excel reports from database query results
"""

import time
from typing import Any, Dict, List, Optional
from loguru import logger

from app.tools.base_tool import ChatbotTool
from app.tools.query_database_tool import query_database_tool
from app.reports.generator_factory import report_generator_factory
from app.middleware.audit_logger import audit_logger
from app.middleware.email_validator import email_validator
from app.utils.email_templates import email_template_renderer
from app.config import settings


class GenerateReportTool(ChatbotTool):
    """
    Tool for generating Excel reports from database queries

    Follows ChatbotTool pattern with:
    - RBAC enforcement
    - Audit logging
    - Integration with query_database_tool
    - Excel format (.xlsx) reports
    """

    name = "generate_report"
    description = (
        "Generate an Excel report from a database query. "
        "Executes the query, formats results, and generates a downloadable .xlsx file. "
        "Supports data scoping based on user role (ADMIN, HR_MANAGER, HR_STAFF, VIEWER)."
    )
    rbac_required = ["ADMIN", "HR_MANAGER", "HR_STAFF"]
    destructive = False

    async def _run(
        self,
        question: str,
        user_id: str,
        user_role: Optional[str] = None,
        format: str = "excel",
        filename: Optional[str] = None,
        max_rows: Optional[int] = None,
        department: Optional[str] = None,
        email_to: Optional[str] = None,
        query_result: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Any:
        """
        Generate report from database query

        Args:
            question: Natural language question
            user_id: User identifier
            user_role: User role (ADMIN, HR_MANAGER, HR_STAFF, VIEWER)
            format: Report format ('excel' only)
            filename: Custom filename (optional)
            max_rows: Maximum rows to include (optional)
            department: Department filter for HR_MANAGER (optional)
            email_to: Email address to send report (optional)
            query_result: Pre-computed query result (optional - will execute query if not provided)
            **kwargs: Additional arguments

        Returns:
            Dictionary with report details
        """
        start_time = time.perf_counter()

        try:
            # Validate format (only Excel supported)
            format = format.lower()
            if format != "excel":
                error_msg = f"Invalid format '{format}'. Only 'excel' is supported."
                logger.error(error_msg)

                # Audit log
                audit_logger.log_tool_execution(
                    user_id=user_id,
                    user_role=user_role or "UNKNOWN",
                    tool_name=self.name,
                    success=False,
                    error=error_msg
                )

                return {
                    "success": False,
                    "error": error_msg
                }

            # Step 1: Use provided query results or execute query
            if query_result is not None:
                # Use pre-computed query results from orchestrator
                logger.info(f"[{self.name}] Using pre-computed query results")
            else:
                # Execute query using query_database_tool
                logger.info(f"[{self.name}] Executing query for user {user_id}")

                query_result = await query_database_tool.run(
                    user_role=user_role or "VIEWER",
                    question=question,
                    user_id=user_id,
                    department=department
                )

            # Check if query succeeded
            if not query_result.get("success"):
                error_msg = query_result.get("error", "Query execution failed")
                logger.error(f"[{self.name}] Query failed: {error_msg}")

                # Audit log
                audit_logger.log_tool_execution(
                    user_id=user_id,
                    user_role=user_role or "UNKNOWN",
                    tool_name=self.name,
                    success=False,
                    error=error_msg
                )

                return {
                    "success": False,
                    "error": error_msg,
                    "query_error": True
                }

            # Extract query results
            query_data = query_result.get("result", {})
            results = query_data.get("results", [])
            sql_query = query_data.get("sql_query", "")
            scoped_sql = query_data.get("scoped_sql_query", sql_query)

            logger.info(f"[{self.name}] Query returned {len(results)} rows")

            # Check if results are empty
            if not results:
                logger.warning(f"[{self.name}] No results to generate report")
                return {
                    "success": False,
                    "error": "No data available to generate report",
                    "empty_results": True
                }

            # Step 2: Get appropriate generator from factory
            logger.info(f"[{self.name}] Generating {format.upper()} report")

            try:
                # Get generator from factory (dependency injection)
                generator = report_generator_factory.get(format)
                logger.debug(f"[{self.name}] Using generator: {generator.__class__.__name__}")
            except ValueError as e:
                # Format not registered
                error_msg = str(e)
                logger.error(f"[{self.name}] {error_msg}")

                audit_logger.log_tool_execution(
                    user_id=user_id,
                    user_role=user_role or "UNKNOWN",
                    tool_name=self.name,
                    success=False,
                    error=error_msg
                )

                return {
                    "success": False,
                    "error": error_msg
                }

            # Set max rows
            max_rows = max_rows or settings.reports_max_rows

            # Generate report using factory-provided generator
            report_path = await generator.generate_table_report(
                query_results=results,
                title=question,
                user_id=user_id,
                user_role=user_role or "VIEWER",
                question=question,
                sql_query=scoped_sql,
                filename=filename,
                max_rows=max_rows
            )

            # Calculate execution time
            execution_time = (time.perf_counter() - start_time) * 1000  # milliseconds

            # Step 3: Send email if requested
            email_sent = False
            email_error = None

            if email_to:
                logger.info(f"[{self.name}] Sending report to {email_to}")

                try:
                    # Validate email
                    is_valid, validation_error = email_validator.validate_email(
                        recipient=email_to,
                        user_id=user_id,
                        user_role=user_role,
                        check_rate_limit=True
                    )

                    if not is_valid:
                        logger.warning(f"[{self.name}] Email validation failed: {validation_error}")
                        email_error = validation_error
                    else:
                        # Import email tool here to avoid circular imports
                        from app.tools.email_tools import send_email_tool

                        # Get file size
                        import os
                        file_size_bytes = os.path.getsize(report_path)
                        file_size = self._format_file_size(file_size_bytes)

                        # Render email template
                        email_html = email_template_renderer.render_report_notification(
                            question=question,
                            rows_count=len(results),
                            attachment_name=os.path.basename(report_path),
                            format=format,
                            user_id=user_id,
                            sql_query=scoped_sql,
                            show_sql=False,  # Don't show SQL in email by default
                            truncated=(len(results) > max_rows),
                            max_rows=max_rows,
                            attachment_size=file_size
                        )

                        # Send email
                        email_result = send_email_tool.run(
                            user_role=user_role or "VIEWER",
                            recipient=email_to,
                            subject=f"📊 Report: {question[:50]}{'...' if len(question) > 50 else ''}",
                            body_html=email_html,
                            attachment_path=report_path,
                            user_id=user_id
                        )

                        if email_result.get("success") and email_result.get("result", {}).get("success"):
                            email_sent = True
                            logger.success(f"[{self.name}] Report emailed to {email_to}")

                            # Record email sent for rate limiting
                            email_validator.record_email_sent(user_id)
                        else:
                            email_error = email_result.get("result", {}).get("error") or email_result.get("error")
                            logger.error(f"[{self.name}] Failed to send email: {email_error}")

                except Exception as e:
                    email_error = str(e)
                    logger.error(f"[{self.name}] Email sending exception: {str(e)}", exc_info=True)

            # Step 4: Audit logging
            audit_logger.log_tool_execution(
                user_id=user_id,
                user_role=user_role or "UNKNOWN",
                tool_name=self.name,
                success=True,
                execution_time_ms=execution_time,
                report_format=format,
                report_path=report_path,
                rows_count=len(results),
                truncated=(len(results) > max_rows),
                email_sent=email_sent,
                email_recipient=email_to if email_sent else None
            )

            logger.success(f"[{self.name}] Report generated: {report_path} ({execution_time:.2f}ms)")

            return {
                "success": True,
                "report_path": report_path,
                "format": format,
                "rows_count": len(results),
                "execution_time_ms": execution_time,
                "question": question,
                "sql_query": scoped_sql,
                "truncated": len(results) > max_rows,
                "max_rows": max_rows,
                "email_sent": email_sent,
                "email_to": email_to if email_sent else None,
                "email_error": email_error
            }

        except Exception as e:
            logger.error(f"[{self.name}] Report generation failed: {str(e)}", exc_info=True)

            # Audit log
            audit_logger.log_tool_execution(
                user_id=user_id,
                user_role=user_role or "UNKNOWN",
                tool_name=self.name,
                success=False,
                error=str(e)
            )

            return {
                "success": False,
                "error": f"Report generation failed: {str(e)}",
                "exception": type(e).__name__
            }

    def _format_file_size(self, size_bytes: int) -> str:
        """
        Format file size in human-readable format

        Args:
            size_bytes: File size in bytes

        Returns:
            Formatted string (e.g., "2.5 MB")
        """
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"


# Global instance
generate_report_tool = GenerateReportTool()
