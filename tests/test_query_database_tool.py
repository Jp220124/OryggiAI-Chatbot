"""
Unit Tests for QueryDatabaseTool
Tests RBAC integration, data scoping, and audit logging
"""

import sys
sys.path.insert(0, "D:\\OryggiAI_Service\\Advance_Chatbot")

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from app.tools.query_database_tool import QueryDatabaseTool, query_database_tool


class TestQueryDatabaseToolInitialization:
    """Test suite for QueryDatabaseTool initialization"""

    def test_tool_metadata(self):
        """Test tool has correct metadata"""
        tool = QueryDatabaseTool()

        assert tool.name == "query_database"
        assert tool.description is not None
        assert "query" in tool.description.lower()
        assert tool.destructive == False
        assert tool.rbac_required == ["ADMIN", "HR_MANAGER", "HR_STAFF", "VIEWER"]

    def test_global_instance_exists(self):
        """Test global tool instance is available"""
        assert query_database_tool is not None
        assert isinstance(query_database_tool, QueryDatabaseTool)

    def test_tool_initialization(self):
        """Test tool initializes without errors"""
        tool = QueryDatabaseTool()
        assert tool is not None
        assert tool.name == "query_database"


class TestQueryDatabaseToolPermissions:
    """Test suite for permission checking"""

    def test_admin_has_permission(self):
        """Test ADMIN role has access"""
        tool = QueryDatabaseTool()
        allowed, error = tool.check_permission("ADMIN")

        assert allowed == True
        assert error is None

    def test_hr_manager_has_permission(self):
        """Test HR_MANAGER role has access"""
        tool = QueryDatabaseTool()
        allowed, error = tool.check_permission("HR_MANAGER")

        assert allowed == True
        assert error is None

    def test_hr_staff_has_permission(self):
        """Test HR_STAFF role has access"""
        tool = QueryDatabaseTool()
        allowed, error = tool.check_permission("HR_STAFF")

        assert allowed == True
        assert error is None

    def test_viewer_has_permission(self):
        """Test VIEWER role has access"""
        tool = QueryDatabaseTool()
        allowed, error = tool.check_permission("VIEWER")

        assert allowed == True
        assert error is None

    def test_unknown_role_denied(self):
        """Test unknown role is denied"""
        tool = QueryDatabaseTool()
        allowed, error = tool.check_permission("UNKNOWN_ROLE")

        assert allowed == False
        assert error is not None
        assert "Permission denied" in error


class TestQueryDatabaseToolDataScoping:
    """Test suite for data scoping functionality"""

    def test_admin_no_scoping(self):
        """Test ADMIN queries are not scoped"""
        tool = QueryDatabaseTool()

        sql = "SELECT * FROM Employees"
        scoped = tool._apply_data_scoping(
            sql_query=sql,
            user_role="ADMIN"
        )

        assert scoped == sql  # No modification for ADMIN

    def test_hr_manager_department_scoping(self):
        """Test HR_MANAGER queries are department-scoped"""
        tool = QueryDatabaseTool()

        sql = "SELECT * FROM Employees"
        scoped = tool._apply_data_scoping(
            sql_query=sql,
            user_role="HR_MANAGER",
            department="IT"
        )

        assert "Department = 'IT'" in scoped
        assert "WHERE" in scoped

    def test_hr_manager_scoping_with_existing_where(self):
        """Test HR_MANAGER scoping with existing WHERE clause"""
        tool = QueryDatabaseTool()

        sql = "SELECT * FROM Employees WHERE Status = 'Active'"
        scoped = tool._apply_data_scoping(
            sql_query=sql,
            user_role="HR_MANAGER",
            department="Finance"
        )

        assert "Department = 'Finance'" in scoped
        assert "AND" in scoped
        assert "Status = 'Active'" in scoped

    def test_hr_staff_user_scoping(self):
        """Test HR_STAFF queries are user-scoped"""
        tool = QueryDatabaseTool()

        sql = "SELECT * FROM Employees"
        scoped = tool._apply_data_scoping(
            sql_query=sql,
            user_role="HR_STAFF",
            user_id="staff_001"
        )

        assert "EmployeeId = 'staff_001'" in scoped
        assert "WHERE" in scoped

    def test_viewer_user_scoping(self):
        """Test VIEWER queries are user-scoped"""
        tool = QueryDatabaseTool()

        sql = "SELECT * FROM Employees"
        scoped = tool._apply_data_scoping(
            sql_query=sql,
            user_role="VIEWER",
            user_id="viewer_001"
        )

        assert "EmployeeId = 'viewer_001'" in scoped
        assert "WHERE" in scoped

    def test_hr_staff_scoping_with_existing_where(self):
        """Test HR_STAFF scoping with existing WHERE clause"""
        tool = QueryDatabaseTool()

        sql = "SELECT * FROM Employees WHERE Department = 'IT'"
        scoped = tool._apply_data_scoping(
            sql_query=sql,
            user_role="HR_STAFF",
            user_id="staff_001"
        )

        assert "EmployeeId = 'staff_001'" in scoped
        assert "AND" in scoped
        assert "Department = 'IT'" in scoped


class TestQueryDatabaseToolExecution:
    """Test suite for tool execution with mocking"""

    @patch('app.tools.query_database_tool.sql_agent')
    @patch('app.tools.query_database_tool.rbac_middleware')
    @patch('app.tools.query_database_tool.audit_logger')
    def test_successful_query_execution_admin(self, mock_audit, mock_rbac, mock_sql_agent):
        """Test successful query execution for ADMIN"""
        # Mock SQL agent response
        mock_sql_agent.generate_sql.return_value = {
            "sql_query": "SELECT COUNT(*) AS total FROM Employees",
            "tables_referenced": ["Employees"]
        }
        mock_sql_agent.execute_query.return_value = [{"total": 42}]
        mock_sql_agent._format_answer.return_value = "The answer is: 42"

        # Mock RBAC scoping - ADMIN should return same SQL (no scoping)
        mock_rbac.apply_data_scoping.return_value = "SELECT COUNT(*) AS total FROM Employees"

        # Execute query
        tool = QueryDatabaseTool()
        result = tool._run(
            question="How many employees?",
            user_id="admin_001",
            user_role="ADMIN"
        )

        # Verify result
        assert result["success"] == True
        assert result["sql_query"] == "SELECT COUNT(*) AS total FROM Employees"
        assert result["result_count"] == 1
        assert result["natural_answer"] == "The answer is: 42"
        assert result["data_scoped"] == False  # ADMIN not scoped
        assert result["user_role"] == "ADMIN"

        # Verify SQL agent was called
        mock_sql_agent.generate_sql.assert_called_once()
        mock_sql_agent.execute_query.assert_called_once()

        # Verify audit logging
        assert mock_audit.log_tool_execution.called
        assert mock_audit.log_data_access.called

    @patch('app.tools.query_database_tool.sql_agent')
    @patch('app.tools.query_database_tool.rbac_middleware')
    @patch('app.tools.query_database_tool.audit_logger')
    def test_successful_query_execution_hr_manager(self, mock_audit, mock_rbac, mock_sql_agent):
        """Test successful query execution for HR_MANAGER with department scoping"""
        # Mock SQL agent response
        mock_sql_agent.generate_sql.return_value = {
            "sql_query": "SELECT * FROM Employees",
            "tables_referenced": ["Employees"]
        }
        mock_sql_agent.execute_query.return_value = [
            {"EmployeeId": "emp_001", "Name": "John Doe", "Department": "IT"}
        ]
        mock_sql_agent._format_answer.return_value = "Found 1 result(s):\n\n1. EmployeeId: emp_001, Name: John Doe, Department: IT"

        # Mock RBAC scoping
        mock_rbac.apply_data_scoping.return_value = "SELECT * FROM Employees WHERE Department = 'IT'"

        # Execute query
        tool = QueryDatabaseTool()
        result = tool._run(
            question="List employees in my department",
            user_id="manager_001",
            user_role="HR_MANAGER",
            department="IT"
        )

        # Verify result
        assert result["success"] == True
        assert result["sql_query"] == "SELECT * FROM Employees"
        assert result["scoped_sql_query"] == "SELECT * FROM Employees WHERE Department = 'IT'"
        assert result["result_count"] == 1
        assert result["data_scoped"] == True  # HR_MANAGER is scoped
        assert result["user_role"] == "HR_MANAGER"

        # Verify RBAC was applied
        mock_rbac.apply_data_scoping.assert_called_once()

    @patch('app.tools.query_database_tool.sql_agent')
    @patch('app.tools.query_database_tool.rbac_middleware')
    @patch('app.tools.query_database_tool.audit_logger')
    def test_successful_query_execution_hr_staff(self, mock_audit, mock_rbac, mock_sql_agent):
        """Test successful query execution for HR_STAFF with user scoping"""
        # Mock SQL agent response
        mock_sql_agent.generate_sql.return_value = {
            "sql_query": "SELECT * FROM Employees",
            "tables_referenced": ["Employees"]
        }
        mock_sql_agent.execute_query.return_value = [
            {"EmployeeId": "staff_001", "Name": "Jane Smith"}
        ]
        mock_sql_agent._format_answer.return_value = "Found 1 result(s):\n\n1. EmployeeId: staff_001, Name: Jane Smith"

        # Mock RBAC scoping
        mock_rbac.apply_data_scoping.return_value = "SELECT * FROM Employees WHERE EmployeeId = 'staff_001'"

        # Execute query
        tool = QueryDatabaseTool()
        result = tool._run(
            question="Show my details",
            user_id="staff_001",
            user_role="HR_STAFF"
        )

        # Verify result
        assert result["success"] == True
        assert result["scoped_sql_query"] == "SELECT * FROM Employees WHERE EmployeeId = 'staff_001'"
        assert result["result_count"] == 1
        assert result["data_scoped"] == True  # HR_STAFF is scoped
        assert result["user_role"] == "HR_STAFF"

    @patch('app.tools.query_database_tool.sql_agent')
    @patch('app.tools.query_database_tool.rbac_middleware')
    @patch('app.tools.query_database_tool.audit_logger')
    def test_query_execution_with_role_fetching(self, mock_audit, mock_rbac, mock_sql_agent):
        """Test query execution fetches role from database if not provided"""
        # Mock role fetching
        mock_rbac.get_user_role.return_value = "HR_STAFF"

        # Mock SQL agent
        mock_sql_agent.generate_sql.return_value = {
            "sql_query": "SELECT * FROM Employees",
            "tables_referenced": ["Employees"]
        }
        mock_sql_agent.execute_query.return_value = []
        mock_sql_agent._format_answer.return_value = "No results found"

        # Mock RBAC scoping
        mock_rbac.apply_data_scoping.return_value = "SELECT * FROM Employees WHERE EmployeeId = 'staff_001'"

        # Execute query WITHOUT user_role (should fetch it)
        tool = QueryDatabaseTool()
        result = tool._run(
            question="Show my details",
            user_id="staff_001"
            # Note: user_role NOT provided
        )

        # Verify role was fetched
        mock_rbac.get_user_role.assert_called_once_with("staff_001")
        assert result["user_role"] == "HR_STAFF"

    @patch('app.tools.query_database_tool.sql_agent')
    @patch('app.tools.query_database_tool.audit_logger')
    def test_query_execution_error_handling(self, mock_audit, mock_sql_agent):
        """Test error handling during query execution"""
        # Mock SQL agent to raise error
        mock_sql_agent.generate_sql.side_effect = Exception("Database connection failed")

        # Execute query
        tool = QueryDatabaseTool()
        result = tool._run(
            question="How many employees?",
            user_id="admin_001",
            user_role="ADMIN"
        )

        # Verify error result
        assert result["success"] == False
        assert result["error"] is not None
        assert "Database connection failed" in result["error"]
        assert result["result_count"] == 0
        assert "error" in result["natural_answer"].lower()

        # Verify audit logging for failure
        mock_audit.log_tool_execution.assert_called_once()
        call_args = mock_audit.log_tool_execution.call_args
        assert call_args[1]["success"] == False
        assert call_args[1]["error"] == "Database connection failed"

    @patch('app.tools.query_database_tool.sql_agent')
    @patch('app.tools.query_database_tool.rbac_middleware')
    @patch('app.tools.query_database_tool.audit_logger')
    def test_audit_logging_success(self, mock_audit, mock_rbac, mock_sql_agent):
        """Test audit logging is called for successful execution"""
        # Mock SQL agent
        mock_sql_agent.generate_sql.return_value = {
            "sql_query": "SELECT COUNT(*) FROM Employees",
            "tables_referenced": ["Employees"]
        }
        mock_sql_agent.execute_query.return_value = [{"count": 10}]
        mock_sql_agent._format_answer.return_value = "Found 10 employees"

        # Mock RBAC scoping - ADMIN should return same SQL (no scoping)
        mock_rbac.apply_data_scoping.return_value = "SELECT COUNT(*) FROM Employees"

        # Execute query
        tool = QueryDatabaseTool()
        result = tool._run(
            question="Count employees",
            user_id="admin_001",
            user_role="ADMIN"
        )

        # Verify audit logging was called twice
        assert mock_audit.log_tool_execution.called
        assert mock_audit.log_data_access.called

        # Verify log_tool_execution arguments
        tool_exec_call = mock_audit.log_tool_execution.call_args
        assert tool_exec_call[1]["user_id"] == "admin_001"
        assert tool_exec_call[1]["user_role"] == "ADMIN"
        assert tool_exec_call[1]["tool_name"] == "query_database"
        assert tool_exec_call[1]["success"] == True
        assert tool_exec_call[1]["question"] == "Count employees"
        assert tool_exec_call[1]["rows_returned"] == 1

        # Verify log_data_access arguments
        data_access_call = mock_audit.log_data_access.call_args
        assert data_access_call[1]["user_id"] == "admin_001"
        assert data_access_call[1]["user_role"] == "ADMIN"
        assert data_access_call[1]["rows_returned"] == 1
        assert data_access_call[1]["data_scoped"] == False  # ADMIN not scoped


class TestQueryDatabaseToolMetadata:
    """Test suite for tool metadata"""

    def test_get_metadata_includes_rbac_info(self):
        """Test metadata includes RBAC configuration"""
        tool = QueryDatabaseTool()
        metadata = tool.get_metadata()

        assert metadata["name"] == "query_database"
        assert metadata["description"] is not None
        assert metadata["rbac_required"] == ["ADMIN", "HR_MANAGER", "HR_STAFF", "VIEWER"]
        assert metadata["destructive"] == False
        assert metadata["data_scoping_enabled"] == True
        assert "supported_roles" in metadata
        assert "role_capabilities" in metadata

    def test_role_capabilities_documented(self):
        """Test role capabilities are documented in metadata"""
        tool = QueryDatabaseTool()
        metadata = tool.get_metadata()

        role_caps = metadata["role_capabilities"]
        assert "ADMIN" in role_caps
        assert "HR_MANAGER" in role_caps
        assert "HR_STAFF" in role_caps
        assert "VIEWER" in role_caps

        # Verify descriptions mention scoping
        assert "Full" in role_caps["ADMIN"] or "no filter" in role_caps["ADMIN"].lower()
        assert "Department" in role_caps["HR_MANAGER"]
        assert "Own data" in role_caps["HR_STAFF"] or "own" in role_caps["HR_STAFF"].lower()


class TestQueryDatabaseToolIntegration:
    """Integration tests with base tool"""

    @patch('app.tools.query_database_tool.sql_agent')
    @patch('app.tools.query_database_tool.audit_logger')
    def test_run_method_with_permission_check(self, mock_audit, mock_sql_agent):
        """Test run() method includes permission check from base class"""
        # Mock SQL agent
        mock_sql_agent.generate_sql.return_value = {
            "sql_query": "SELECT * FROM Employees",
            "tables_referenced": ["Employees"]
        }
        mock_sql_agent.execute_query.return_value = []
        mock_sql_agent._format_answer.return_value = "No results"

        # Test allowed role
        tool = QueryDatabaseTool()
        result = tool.run(
            user_role="ADMIN",
            question="Test query",
            user_id="admin_001"
        )

        assert result["success"] == True

    def test_run_method_denies_unauthorized_role(self):
        """Test run() method denies unauthorized roles"""
        tool = QueryDatabaseTool()

        # Test denied role
        result = tool.run(
            user_role="UNAUTHORIZED",
            question="Test query",
            user_id="bad_user"
        )

        assert result["success"] == False
        assert "Permission denied" in result["error"]


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
