"""
Reports API Endpoints
Handles report generation (PDF and Excel) with RBAC enforcement
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from loguru import logger
import os

from app.models.reports import (
    ReportGenerateRequest,
    ReportGenerateResponse
)
from app.tools.generate_report_tool import generate_report_tool
from app.config import settings

# Create router
router = APIRouter()


@router.post("/generate", response_model=ReportGenerateResponse)
async def generate_report(request: ReportGenerateRequest):
    """
    Generate a PDF or Excel report from a natural language query

    **Phase 3 Feature:** Report Generation

    **Features:**
    - PDF and Excel report generation
    - RAG-enhanced SQL query generation
    - RBAC enforcement with data scoping
    - Automatic formatting and styling
    - Summary statistics (for numeric columns)

    **Example Request:**
    ```json
    {
        "question": "Show me all employees in Engineering department",
        "format": "pdf",
        "user_id": "admin",
        "user_role": "ADMIN"
    }
    ```

    **Example Response:**
    ```json
    {
        "success": true,
        "report_path": "./reports_output/report_20250117_143025.pdf",
        "format": "pdf",
        "rows_count": 45,
        "execution_time_ms": 1523.45,
        "question": "Show me all employees in Engineering department",
        "sql_query": "SELECT * FROM EmployeeMaster WHERE Department = 'Engineering'",
        "truncated": false,
        "max_rows": 10000
    }
    ```
    """
    logger.info(f"[{request.tenant_id}:{request.user_id}] Report generation request: {request.question} (format: {request.format})")

    try:
        # Call generate_report_tool (async)
        result = await generate_report_tool.run(
            user_role=request.user_role,
            question=request.question,
            user_id=request.user_id,
            format=request.format,
            filename=request.filename,
            max_rows=request.max_rows,
            department=request.department,
            email_to=request.email_to  # Phase 4: Email Integration
        )

        # Check if tool execution succeeded
        if not result.get("success"):
            error_msg = result.get("error", "Report generation failed")
            logger.error(f"[ERROR] Report generation failed: {error_msg}")

            return ReportGenerateResponse(
                success=False,
                error=error_msg
            )

        # Extract result data (tool returns data directly, not nested under "result" key)
        tool_result = result

        # Successful response
        return ReportGenerateResponse(
            success=True,
            report_path=tool_result.get("report_path"),
            format=tool_result.get("format"),
            rows_count=tool_result.get("rows_count"),
            execution_time_ms=tool_result.get("execution_time_ms"),
            question=tool_result.get("question"),
            sql_query=tool_result.get("sql_query"),
            truncated=tool_result.get("truncated"),
            max_rows=tool_result.get("max_rows"),
            # Phase 4: Email Integration
            email_sent=tool_result.get("email_sent"),
            email_to=tool_result.get("email_to"),
            email_error=tool_result.get("email_error")
        )

    except Exception as e:
        logger.error(f"[ERROR] Report generation exception: {str(e)}", exc_info=True)
        return ReportGenerateResponse(
            success=False,
            error=f"Internal server error: {str(e)}"
        )


@router.get("/download/{filename}")
async def download_report(filename: str):
    """
    Download a generated report file

    **Path Parameters:**
    - filename: Name of the report file to download

    **Returns:**
    FileResponse with the report file

    **Example:**
    ```
    GET /api/reports/download/report_20250117_143025.pdf
    ```

    **Security Note:**
    - Only files from the configured reports output directory can be downloaded
    - Prevents directory traversal attacks
    """
    try:
        # Sanitize filename (prevent directory traversal)
        filename = os.path.basename(filename)

        # Construct full path
        file_path = os.path.join(settings.reports_output_dir, filename)

        # Check if file exists
        if not os.path.exists(file_path):
            logger.warning(f"Report file not found: {file_path}")
            raise HTTPException(
                status_code=404,
                detail=f"Report file not found: {filename}"
            )

        # Determine media type based on extension
        if filename.endswith('.pdf'):
            media_type = "application/pdf"
        elif filename.endswith('.xlsx'):
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            media_type = "application/octet-stream"

        logger.info(f"Serving report file: {filename}")

        return FileResponse(
            path=file_path,
            media_type=media_type,
            filename=filename
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ERROR] Failed to serve report file: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to serve report file: {str(e)}"
        )


@router.get("/list")
async def list_reports():
    """
    List all generated reports in the output directory

    **Returns:**
    List of report filenames with metadata

    **Example Response:**
    ```json
    {
        "reports": [
            {
                "filename": "report_20250117_143025.pdf",
                "size_bytes": 125430,
                "created_at": "2025-01-17T14:30:25",
                "format": "pdf"
            },
            {
                "filename": "report_20250117_140512.xlsx",
                "size_bytes": 89234,
                "created_at": "2025-01-17T14:05:12",
                "format": "excel"
            }
        ],
        "total_reports": 2
    }
    ```
    """
    try:
        # Ensure output directory exists
        if not os.path.exists(settings.reports_output_dir):
            return {
                "reports": [],
                "total_reports": 0
            }

        # List all files in reports directory
        files = []
        for filename in os.listdir(settings.reports_output_dir):
            file_path = os.path.join(settings.reports_output_dir, filename)

            # Only include files (not directories)
            if os.path.isfile(file_path):
                # Get file stats
                stats = os.stat(file_path)

                # Determine format
                if filename.endswith('.pdf'):
                    format_type = "pdf"
                elif filename.endswith('.xlsx'):
                    format_type = "excel"
                else:
                    format_type = "unknown"

                files.append({
                    "filename": filename,
                    "size_bytes": stats.st_size,
                    "created_at": stats.st_ctime,
                    "format": format_type
                })

        # Sort by creation time (newest first)
        files.sort(key=lambda x: x["created_at"], reverse=True)

        logger.info(f"Listed {len(files)} reports")

        return {
            "reports": files,
            "total_reports": len(files)
        }

    except Exception as e:
        logger.error(f"[ERROR] Failed to list reports: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list reports: {str(e)}"
        )
