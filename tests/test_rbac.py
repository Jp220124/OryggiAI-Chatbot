"""
Unit Tests for RBAC Middleware and Audit Logger
Tests role-based access control, data scoping, and audit logging
"""

import sys
sys.path.insert(0, "D:\\OryggiAI_Service\\Advance_Chatbot")

import pytest
from unittest.mock import Mock, patch, MagicMock
from app.middleware.rbac import RBACMiddleware
from app.middleware.audit_logger import AuditLogger
from app.tools.base_tool import ChatbotTool
from app.tools import ToolRegistry


# Mock Tool for Testing
class MockQueryTool(ChatbotTool):
    """Mock tool for RBAC testing"""
    name = "mock_query"
    description = "Mock database query tool"
    rbac_required = ["ADMIN", "HR_MANAGER", "HR_STAFF"]

    def _run(self, **kwargs):
        return {"status": "success"}


class TestRBACMiddleware:
    """Test suite for RBACMiddleware"""

    def test_role_hierarchy(self):
        """Test role hierarchy levels are correctly defined"""
        rbac = RBACMiddleware()

        assert rbac.get_role_level("ADMIN") == 100
        assert rbac.get_role_level("HR_MANAGER") == 50
        assert rbac.get_role_level("HR_STAFF") == 30
        assert rbac.get_role_level("VIEWER") == 10
        assert rbac.get_role_level("UNKNOWN") == 0

    def test_has_higher_role_admin(self):
        """Test ADMIN has access to all roles"""
        rbac = RBACMiddleware()

        assert rbac.has_higher_role("ADMIN", "ADMIN") == True
        assert rbac.has_higher_role("ADMIN", "HR_MANAGER") == True
        assert rbac.has_higher_role("ADMIN", "HR_STAFF") == True
        assert rbac.has_higher_role("ADMIN", "VIEWER") == True

    def test_has_higher_role_hr_manager(self):
        """Test HR_MANAGER role hierarchy"""
        rbac = RBACMiddleware()

        assert rbac.has_higher_role("HR_MANAGER", "ADMIN") == False
        assert rbac.has_higher_role("HR_MANAGER", "HR_MANAGER") == True
        assert rbac.has_higher_role("HR_MANAGER", "HR_STAFF") == True
        assert rbac.has_higher_role("HR_MANAGER", "VIEWER") == True

    def test_has_higher_role_hr_staff(self):
        """Test HR_STAFF role hierarchy"""
        rbac = RBACMiddleware()

        assert rbac.has_higher_role("HR_STAFF", "ADMIN") == False
        assert rbac.has_higher_role("HR_STAFF", "HR_MANAGER") == False
        assert rbac.has_higher_role("HR_STAFF", "HR_STAFF") == True
        assert rbac.has_higher_role("HR_STAFF", "VIEWER") == True

    def test_has_higher_role_viewer(self):
        """Test VIEWER role hierarchy"""
        rbac = RBACMiddleware()

        assert rbac.has_higher_role("VIEWER", "ADMIN") == False
        assert rbac.has_higher_role("VIEWER", "HR_MANAGER") == False
        assert rbac.has_higher_role("VIEWER", "HR_STAFF") == False
        assert rbac.has_higher_role("VIEWER", "VIEWER") == True

    @patch('pyodbc.connect')
    def test_get_user_role_found(self, mock_connect):
        """Test getting user role from database - user found"""
        # Mock database response
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("HR_MANAGER",)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        rbac = RBACMiddleware()
        role = rbac.get_user_role("emp_123")

        assert role == "HR_MANAGER"
        mock_cursor.execute.assert_called_once()

    @patch('pyodbc.connect')
    def test_get_user_role_not_found(self, mock_connect):
        """Test getting user role from database - user not found"""
        # Mock database response - no user found
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        rbac = RBACMiddleware()
        role = rbac.get_user_role("unknown_user")

        assert role == "VIEWER"  # Default role

    @patch('pyodbc.connect')
    def test_get_user_role_database_error(self, mock_connect):
        """Test getting user role when database error occurs"""
        # Mock database error
        mock_connect.side_effect = Exception("Database connection failed")

        rbac = RBACMiddleware()
        role = rbac.get_user_role("emp_123")

        assert role == "VIEWER"  # Default role on error

    def test_check_tool_permission_allowed(self):
        """Test tool permission check - allowed"""
        # Register mock tool
        registry = ToolRegistry()
        tool = MockQueryTool()
        registry.register(tool)

        # Mock the global registry
        with patch('app.middleware.rbac.tool_registry', registry):
            rbac = RBACMiddleware()
            allowed, error = rbac.check_tool_permission("ADMIN", "mock_query")

            assert allowed == True
            assert error is None

    def test_check_tool_permission_denied(self):
        """Test tool permission check - denied"""
        # Register mock tool
        registry = ToolRegistry()
        tool = MockQueryTool()
        registry.register(tool)

        # Mock the global registry
        with patch('app.middleware.rbac.tool_registry', registry):
            rbac = RBACMiddleware()
            allowed, error = rbac.check_tool_permission("VIEWER", "mock_query")

            assert allowed == False
            assert error is not None
            assert "Permission denied" in error

    def test_check_tool_permission_tool_not_found(self):
        """Test tool permission check - tool not found"""
        registry = ToolRegistry()

        # Mock the global registry
        with patch('app.middleware.rbac.tool_registry', registry):
            rbac = RBACMiddleware()
            allowed, error = rbac.check_tool_permission("ADMIN", "nonexistent_tool")

            assert allowed == False
            assert "not found" in error

    def test_apply_data_scoping_admin_no_filter(self):
        """Test data scoping for ADMIN - no filters applied"""
        rbac = RBACMiddleware()

        sql = "SELECT * FROM Employees"
        scoped_sql = rbac.apply_data_scoping(
            sql_query=sql,
            user_role="ADMIN"
        )

        assert scoped_sql == sql  # No changes for ADMIN

    def test_apply_data_scoping_hr_manager_department(self):
        """Test data scoping for HR_MANAGER - department filter"""
        rbac = RBACMiddleware()

        sql = "SELECT * FROM Employees"
        scoped_sql = rbac.apply_data_scoping(
            sql_query=sql,
            user_role="HR_MANAGER",
            department="IT"
        )

        assert "Department = 'IT'" in scoped_sql
        assert "WHERE" in scoped_sql

    def test_apply_data_scoping_hr_manager_with_existing_where(self):
        """Test data scoping for HR_MANAGER with existing WHERE clause"""
        rbac = RBACMiddleware()

        sql = "SELECT * FROM Employees WHERE Status = 'Active'"
        scoped_sql = rbac.apply_data_scoping(
            sql_query=sql,
            user_role="HR_MANAGER",
            department="IT"
        )

        assert "Department = 'IT'" in scoped_sql
        assert "AND" in scoped_sql
        assert "Status = 'Active'" in scoped_sql

    def test_apply_data_scoping_hr_staff_user_filter(self):
        """Test data scoping for HR_STAFF - user filter"""
        rbac = RBACMiddleware()

        sql = "SELECT * FROM Employees"
        scoped_sql = rbac.apply_data_scoping(
            sql_query=sql,
            user_role="HR_STAFF",
            user_id="emp_123"
        )

        assert "EmployeeId = 'emp_123'" in scoped_sql
        assert "WHERE" in scoped_sql

    def test_apply_data_scoping_viewer_user_filter(self):
        """Test data scoping for VIEWER - user filter"""
        rbac = RBACMiddleware()

        sql = "SELECT * FROM Employees"
        scoped_sql = rbac.apply_data_scoping(
            sql_query=sql,
            user_role="VIEWER",
            user_id="emp_456"
        )

        assert "EmployeeId = 'emp_456'" in scoped_sql
        assert "WHERE" in scoped_sql

    def test_apply_data_scoping_hr_staff_with_existing_where(self):
        """Test data scoping for HR_STAFF with existing WHERE clause"""
        rbac = RBACMiddleware()

        sql = "SELECT * FROM Employees WHERE Department = 'IT'"
        scoped_sql = rbac.apply_data_scoping(
            sql_query=sql,
            user_role="HR_STAFF",
            user_id="emp_123"
        )

        assert "EmployeeId = 'emp_123'" in scoped_sql
        assert "AND" in scoped_sql
        assert "Department = 'IT'" in scoped_sql

    def test_get_audit_context(self):
        """Test audit context generation"""
        rbac = RBACMiddleware()

        context = rbac.get_audit_context(
            user_id="emp_123",
            user_role="HR_MANAGER",
            action="query_database",
            tool_name="mock_query",
            question="How many employees?"
        )

        assert context["user_id"] == "emp_123"
        assert context["user_role"] == "HR_MANAGER"
        assert context["role_level"] == 50
        assert context["action"] == "query_database"
        assert context["tool_name"] == "mock_query"
        assert context["question"] == "How many employees?"


class TestAuditLogger:
    """Test suite for AuditLogger"""

    def test_initialization(self):
        """Test audit logger can be initialized"""
        audit = AuditLogger()
        assert audit is not None

    @patch('app.middleware.audit_logger.logger')
    def test_log_permission_check_granted(self, mock_logger):
        """Test logging permission check - granted"""
        audit = AuditLogger()

        audit.log_permission_check(
            user_id="emp_123",
            user_role="ADMIN",
            action="query_database",
            allowed=True
        )

        # Check that logger.info was called
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[0][0]
        assert "[AUDIT]" in call_args
        assert "Permission granted" in call_args
        assert "emp_123" in call_args

    @patch('app.middleware.audit_logger.logger')
    def test_log_permission_check_denied(self, mock_logger):
        """Test logging permission check - denied"""
        audit = AuditLogger()

        audit.log_permission_check(
            user_id="emp_123",
            user_role="VIEWER",
            action="delete_employee",
            allowed=False,
            reason="Insufficient permissions"
        )

        # Check that logger.warning was called
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args[0][0]
        assert "[AUDIT]" in call_args
        assert "Permission denied" in call_args
        assert "emp_123" in call_args

    @patch('app.middleware.audit_logger.logger')
    def test_log_tool_execution_success(self, mock_logger):
        """Test logging tool execution - success"""
        audit = AuditLogger()

        audit.log_tool_execution(
            user_id="emp_123",
            user_role="HR_MANAGER",
            tool_name="query_database",
            success=True,
            execution_time_ms=450
        )

        # Check that logger.info was called
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[0][0]
        assert "[AUDIT]" in call_args
        assert "Tool execution succeeded" in call_args
        assert "query_database" in call_args

    @patch('app.middleware.audit_logger.logger')
    def test_log_tool_execution_failure(self, mock_logger):
        """Test logging tool execution - failure"""
        audit = AuditLogger()

        audit.log_tool_execution(
            user_id="emp_123",
            user_role="HR_STAFF",
            tool_name="query_database",
            success=False,
            error="Database connection failed"
        )

        # Check that logger.error was called
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args[0][0]
        assert "[AUDIT]" in call_args
        assert "Tool execution failed" in call_args
        assert "Database connection failed" in call_args

    @patch('app.middleware.audit_logger.logger')
    def test_log_data_access(self, mock_logger):
        """Test logging data access"""
        audit = AuditLogger()

        audit.log_data_access(
            user_id="emp_123",
            user_role="HR_STAFF",
            query="SELECT * FROM Employees WHERE EmployeeId = 'emp_123'",
            rows_returned=1,
            data_scoped=True
        )

        # Check that logger.info was called
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[0][0]
        assert "[AUDIT]" in call_args
        assert "Data access" in call_args
        assert "emp_123" in call_args

    @patch('app.middleware.audit_logger.logger')
    def test_log_role_change(self, mock_logger):
        """Test logging role change"""
        audit = AuditLogger()

        audit.log_role_change(
            user_id="emp_123",
            old_role="HR_STAFF",
            new_role="HR_MANAGER",
            changed_by="admin_456"
        )

        # Check that logger.warning was called
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args[0][0]
        assert "[AUDIT]" in call_args
        assert "Role change" in call_args
        assert "emp_123" in call_args

    @patch('app.middleware.audit_logger.logger')
    def test_log_security_event_high_severity(self, mock_logger):
        """Test logging security event - high severity"""
        audit = AuditLogger()

        audit.log_security_event(
            event_type="UNAUTHORIZED_ACCESS_ATTEMPT",
            severity="HIGH",
            user_id="emp_123",
            description="Attempted to access admin-only tool"
        )

        # Check that logger.error was called for HIGH severity
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args[0][0]
        assert "[AUDIT]" in call_args
        assert "Security event" in call_args
        assert "HIGH" in call_args

    @patch('app.middleware.audit_logger.logger')
    def test_log_security_event_low_severity(self, mock_logger):
        """Test logging security event - low severity"""
        audit = AuditLogger()

        audit.log_security_event(
            event_type="RATE_LIMIT_WARNING",
            severity="LOW",
            user_id="emp_123",
            description="Approaching rate limit"
        )

        # Check that logger.info was called for LOW severity
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[0][0]
        assert "[AUDIT]" in call_args
        assert "Security event" in call_args

    @patch('app.middleware.audit_logger.logger')
    def test_log_login_attempt_success(self, mock_logger):
        """Test logging login attempt - success"""
        audit = AuditLogger()

        audit.log_login_attempt(
            user_id="emp_123",
            success=True,
            ip_address="192.168.1.100"
        )

        # Check that logger.info was called
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args[0][0]
        assert "[AUDIT]" in call_args
        assert "Login succeeded" in call_args

    @patch('app.middleware.audit_logger.logger')
    def test_log_login_attempt_failure(self, mock_logger):
        """Test logging login attempt - failure"""
        audit = AuditLogger()

        audit.log_login_attempt(
            user_id="emp_123",
            success=False,
            ip_address="192.168.1.100"
        )

        # Check that logger.warning was called
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args[0][0]
        assert "[AUDIT]" in call_args
        assert "Login failed" in call_args


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
