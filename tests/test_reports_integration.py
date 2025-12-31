"""
Integration Tests for Phase 3: Report Generation
Tests tool registry, API integration, and core logic without PDF/Excel generation
"""

import sys
sys.path.insert(0, "D:\\OryggiAI_Service\\Advance_Chatbot")

import pytest
from unittest.mock import Mock, patch, MagicMock

# Test imports before WeasyPrint
from app.tools.base_tool import ChatbotTool
from app.models.reports import ReportGenerateRequest, ReportGenerateResponse


class TestReportToolRegistration:
    """Test report tool is registered in tool registry"""

    def test_generate_report_tool_registered(self):
        """Test generate_report_tool is auto-registered"""
        from app.tools import tool_registry

        tool = tool_registry.get_tool("generate_report")
        assert tool is not None
        assert tool.name == "generate_report"

    def test_generate_report_tool_metadata(self):
        """Test tool metadata is correct"""
        from app.tools import tool_registry

        tool = tool_registry.get_tool("generate_report")
        metadata = tool.get_metadata()

        assert metadata["name"] == "generate_report"
        assert metadata["destructive"] == False
        assert "ADMIN" in metadata["rbac_required"]
        assert "HR_MANAGER" in metadata["rbac_required"]
        assert "HR_STAFF" in metadata["rbac_required"]
        assert "VIEWER" not in metadata["rbac_required"]

    def test_tool_registry_count_includes_reports(self):
        """Test tool registry includes report tool"""
        from app.tools import tool_registry

        # Should have at least query_database_tool and generate_report_tool
        assert tool_registry.get_tool_count() >= 2

        # Verify both tools are registered
        assert tool_registry.get_tool("query_database") is not None
        assert tool_registry.get_tool("generate_report") is not None


class TestReportModels:
    """Test Pydantic models for reports"""

    def test_report_generate_request_defaults(self):
        """Test ReportGenerateRequest default values"""
        request = ReportGenerateRequest(question="Test query")

        assert request.question == "Test query"
        assert request.format == "pdf"
        assert request.tenant_id == "default"
        assert request.user_id == "system"
        assert request.user_role == "VIEWER"
        assert request.filename is None
        assert request.max_rows is None

    def test_report_generate_request_custom_values(self):
        """Test ReportGenerateRequest with custom values"""
        request = ReportGenerateRequest(
            question="List employees",
            format="excel",
            user_id="admin_001",
            user_role="ADMIN",
            filename="custom_report.xlsx",
            max_rows=500,
            department="IT"
        )

        assert request.question == "List employees"
        assert request.format == "excel"
        assert request.user_id == "admin_001"
        assert request.user_role == "ADMIN"
        assert request.filename == "custom_report.xlsx"
        assert request.max_rows == 500
        assert request.department == "IT"

    def test_report_generate_response_success(self):
        """Test ReportGenerateResponse for success case"""
        response = ReportGenerateResponse(
            success=True,
            report_path="/tmp/report.pdf",
            format="pdf",
            rows_count=10,
            execution_time_ms=1234.56,
            question="Test",
            sql_query="SELECT *",
            truncated=False,
            max_rows=1000
        )

        assert response.success == True
        assert response.report_path == "/tmp/report.pdf"
        assert response.error is None

    def test_report_generate_response_error(self):
        """Test ReportGenerateResponse for error case"""
        response = ReportGenerateResponse(
            success=False,
            error="Database connection failed"
        )

        assert response.success == False
        assert response.error == "Database connection failed"
        assert response.report_path is None


class TestGenerateReportToolLogic:
    """Test GenerateReportTool business logic without PDF generation"""

    @patch('app.tools.generate_report_tool.query_database_tool')
    @patch('app.tools.generate_report_tool.pdf_generator')
    @patch('app.tools.generate_report_tool.audit_logger')
    def test_tool_permission_enforcement(self, mock_audit, mock_pdf, mock_query):
        """Test RBAC permissions are enforced"""
        from app.tools.generate_report_tool import generate_report_tool

        # Test ADMIN allowed
        result = generate_report_tool.run(
            user_role="ADMIN",
            question="Test",
            user_id="admin",
            format="pdf"
        )
        # Will fail on query or PDF gen, but permission should pass
        # Check that it didn't fail with permission error
        if not result["success"]:
            assert "Permission denied" not in result.get("error", "")

        # Test VIEWER denied
        result = generate_report_tool.run(
            user_role="VIEWER",
            question="Test",
            user_id="viewer",
            format="pdf"
        )
        assert result["success"] == False
        assert "Permission denied" in result["error"]

    def test_format_validation(self):
        """Test invalid format is rejected"""
        from app.tools.generate_report_tool import generate_report_tool

        result = generate_report_tool._run(
            question="Test",
            user_id="admin",
            user_role="ADMIN",
            format="invalid_format"
        )

        assert result["success"] == False
        assert "Invalid format" in result["error"]
        assert "pdf" in result["error"].lower()
        assert "excel" in result["error"].lower()

    @patch('app.tools.generate_report_tool.query_database_tool')
    @patch('app.tools.generate_report_tool.audit_logger')
    def test_query_failure_handling(self, mock_audit, mock_query):
        """Test handling when query_database_tool fails"""
        from app.tools.generate_report_tool import generate_report_tool

        # Mock query failure
        mock_query.run.return_value = {
            "success": False,
            "error": "SQL syntax error"
        }

        result = generate_report_tool._run(
            question="Invalid SQL",
            user_id="admin",
            user_role="ADMIN",
            format="pdf"
        )

        assert result["success"] == False
        assert "SQL syntax error" in result["error"]
        assert result.get("query_error") == True

        # Verify audit logging was called
        assert mock_audit.log_tool_execution.called

    @patch('app.tools.generate_report_tool.query_database_tool')
    @patch('app.tools.generate_report_tool.audit_logger')
    def test_empty_results_handling(self, mock_audit, mock_query):
        """Test handling when query returns no data"""
        from app.tools.generate_report_tool import generate_report_tool

        # Mock empty results
        mock_query.run.return_value = {
            "success": True,
            "result": {
                "results": [],
                "sql_query": "SELECT * FROM NonExistent"
            }
        }

        result = generate_report_tool._run(
            question="Find nothing",
            user_id="admin",
            user_role="ADMIN",
            format="excel"
        )

        assert result["success"] == False
        assert "No data available" in result["error"]
        assert result.get("empty_results") == True


class TestReportsAPIIntegration:
    """Test Reports API router integration"""

    def test_reports_router_registered(self):
        """Test reports router is registered in main app"""
        from app.main import app

        # Check that /api/reports routes exist
        routes = [route.path for route in app.routes]

        # Should have reports endpoints
        report_routes = [r for r in routes if "/api/reports" in r]
        assert len(report_routes) > 0

    @pytest.mark.asyncio
    @patch('app.api.reports.generate_report_tool')
    async def test_generate_report_endpoint_success(self, mock_tool):
        """Test /api/reports/generate endpoint with mocked tool"""
        from app.api.reports import generate_report

        # Mock successful tool execution
        mock_tool.run.return_value = {
            "success": True,
            "result": {
                "report_path": "/tmp/report.pdf",
                "format": "pdf",
                "rows_count": 5,
                "execution_time_ms": 123.45,
                "question": "Test query",
                "sql_query": "SELECT *",
                "truncated": False,
                "max_rows": 1000
            }
        }

        request = ReportGenerateRequest(
            question="Test query",
            user_id="admin",
            user_role="ADMIN",
            format="pdf"
        )

        response = await generate_report(request)

        assert response.success == True
        assert response.report_path == "/tmp/report.pdf"
        assert response.format == "pdf"
        assert response.rows_count == 5

        # Verify tool was called with correct params
        call_kwargs = mock_tool.run.call_args[1]
        assert call_kwargs["user_role"] == "ADMIN"
        assert call_kwargs["question"] == "Test query"
        assert call_kwargs["format"] == "pdf"

    @pytest.mark.asyncio
    @patch('app.api.reports.generate_report_tool')
    async def test_generate_report_endpoint_error(self, mock_tool):
        """Test /api/reports/generate endpoint handles errors"""
        from app.api.reports import generate_report

        # Mock tool failure
        mock_tool.run.return_value = {
            "success": False,
            "error": "Permission denied"
        }

        request = ReportGenerateRequest(
            question="Test",
            user_id="viewer",
            user_role="VIEWER"
        )

        response = await generate_report(request)

        assert response.success == False
        assert "Permission denied" in response.error


class TestApplicationStartup:
    """Test application can start with reports module"""

    def test_app_imports_successfully(self):
        """Test main application imports without errors"""
        try:
            from app.main import app
            assert app is not None
        except ImportError as e:
            pytest.fail(f"Failed to import app.main: {e}")

    def test_reports_module_structure(self):
        """Test reports module is properly structured"""
        import os
        reports_dir = "D:\\OryggiAI_Service\\Advance_Chatbot\\app\\reports"

        assert os.path.exists(reports_dir)
        assert os.path.exists(os.path.join(reports_dir, "__init__.py"))
        assert os.path.exists(os.path.join(reports_dir, "templates"))

    def test_config_has_reports_settings(self):
        """Test config includes report settings"""
        from app.config import settings

        assert hasattr(settings, "reports_output_dir")
        assert hasattr(settings, "reports_max_rows")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
