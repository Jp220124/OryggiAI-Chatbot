"""
Pydantic Models for Reports API
Request and response models for report generation
"""

from typing import Optional
from pydantic import BaseModel, Field


class ReportGenerateRequest(BaseModel):
    """
    Request model for report generation endpoint
    """
    question: str = Field(..., description="User's natural language question", min_length=1)
    format: str = Field(default="pdf", description="Report format: 'pdf' or 'excel'")
    tenant_id: str = Field(default="default", description="Tenant identifier")
    user_id: str = Field(default="system", description="User identifier")
    user_role: str = Field(default="VIEWER", description="User role for RBAC (ADMIN, HR_MANAGER, HR_STAFF, VIEWER)")
    filename: Optional[str] = Field(None, description="Custom filename for the report (optional)")
    max_rows: Optional[int] = Field(None, description="Maximum rows to include in report (optional)")
    department: Optional[str] = Field(None, description="Department filter for HR_MANAGER role (optional)")
    email_to: Optional[str] = Field(None, description="Email address to send report (Phase 4 - Email Integration)")


class ReportGenerateResponse(BaseModel):
    """
    Response model for report generation endpoint
    """
    success: bool = Field(..., description="Whether report generation succeeded")
    report_path: Optional[str] = Field(None, description="Path to generated report file")
    format: Optional[str] = Field(None, description="Report format (pdf or excel)")
    rows_count: Optional[int] = Field(None, description="Number of rows in report")
    execution_time_ms: Optional[float] = Field(None, description="Execution time in milliseconds")
    question: Optional[str] = Field(None, description="Original question")
    sql_query: Optional[str] = Field(None, description="SQL query executed")
    truncated: Optional[bool] = Field(None, description="Whether report was truncated")
    max_rows: Optional[int] = Field(None, description="Maximum rows limit applied")
    error: Optional[str] = Field(None, description="Error message if failed")
    # Phase 4: Email Integration fields
    email_sent: Optional[bool] = Field(None, description="Whether report was emailed successfully")
    email_to: Optional[str] = Field(None, description="Email address where report was sent")
    email_error: Optional[str] = Field(None, description="Email sending error (if any)")
