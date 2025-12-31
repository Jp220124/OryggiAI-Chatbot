"""
Unit Tests for ChatbotTool Base Class and ToolRegistry
Tests permission checking, tool execution, and registry management
"""

import sys
sys.path.insert(0, "D:\\OryggiAI_Service\\Advance_Chatbot")

import pytest
from app.tools.base_tool import ChatbotTool
from app.tools import ToolRegistry, tool_registry


# Mock Tool for Testing
class MockQueryTool(ChatbotTool):
    """Mock tool for testing - simulates database query"""
    name = "mock_query"
    description = "Mock database query tool for testing"
    rbac_required = ["ADMIN", "HR_MANAGER", "HR_STAFF"]

    def _run(self, question: str, **kwargs) -> dict:
        """Execute mock query"""
        return {
            "question": question,
            "result_count": 42,
            "data": [{"id": 1, "name": "Test"}]
        }


class MockAdminOnlyTool(ChatbotTool):
    """Mock tool for testing - admin only"""
    name = "mock_admin_only"
    description = "Admin-only tool for testing"
    rbac_required = ["ADMIN"]
    destructive = True

    def _run(self, action: str, **kwargs) -> dict:
        """Execute admin action"""
        return {"action": action, "status": "executed"}


class MockFailingTool(ChatbotTool):
    """Mock tool that raises exception"""
    name = "mock_failing"
    description = "Tool that always fails"
    rbac_required = ["ADMIN"]

    def _run(self, **kwargs) -> dict:
        """Raise exception"""
        raise ValueError("Intentional test failure")


# Test ChatbotTool Base Class
class TestChatbotTool:
    """Test suite for ChatbotTool base class"""

    def test_tool_initialization(self):
        """Test tool can be initialized"""
        tool = MockQueryTool()
        assert tool.name == "mock_query"
        assert tool.description is not None
        assert len(tool.rbac_required) > 0

    def test_tool_missing_name(self):
        """Test tool without name raises error"""
        class InvalidTool(ChatbotTool):
            description = "Invalid tool"
            rbac_required = ["ADMIN"]

            def _run(self, **kwargs):
                return {}

        with pytest.raises(ValueError):
            InvalidTool()

    def test_tool_missing_description(self):
        """Test tool without description raises error"""
        class InvalidTool(ChatbotTool):
            name = "invalid"
            rbac_required = ["ADMIN"]

            def _run(self, **kwargs):
                return {}

        with pytest.raises(ValueError):
            InvalidTool()

    def test_permission_check_allowed(self):
        """Test permission check allows authorized role"""
        tool = MockQueryTool()

        # ADMIN should have access
        allowed, error = tool.check_permission("ADMIN")
        assert allowed == True
        assert error is None

        # HR_MANAGER should have access
        allowed, error = tool.check_permission("HR_MANAGER")
        assert allowed == True
        assert error is None

    def test_permission_check_denied(self):
        """Test permission check denies unauthorized role"""
        tool = MockQueryTool()

        # VIEWER should NOT have access
        allowed, error = tool.check_permission("VIEWER")
        assert allowed == False
        assert error is not None
        assert "Permission denied" in error

    def test_permission_check_unknown_role(self):
        """Test permission check denies unknown role"""
        tool = MockQueryTool()

        allowed, error = tool.check_permission("UNKNOWN_ROLE")
        assert allowed == False
        assert error is not None

    def test_tool_execution_success(self):
        """Test successful tool execution"""
        tool = MockQueryTool()

        result = tool.run(
            user_role="ADMIN",
            question="How many employees?"
        )

        assert result["success"] == True
        assert result["result"] is not None
        assert result["error"] is None
        assert result["result"]["question"] == "How many employees?"
        assert result["result"]["result_count"] == 42

    def test_tool_execution_permission_denied(self):
        """Test tool execution blocks unauthorized users"""
        tool = MockQueryTool()

        result = tool.run(
            user_role="VIEWER",
            question="How many employees?"
        )

        assert result["success"] == False
        assert result["result"] is None
        assert result["error"] is not None
        assert "Permission denied" in result["error"]

    def test_tool_execution_with_error(self):
        """Test tool execution handles exceptions"""
        tool = MockFailingTool()

        result = tool.run(user_role="ADMIN")

        assert result["success"] == False
        assert result["result"] is None
        assert result["error"] is not None
        assert "Intentional test failure" in result["error"]

    def test_admin_only_tool(self):
        """Test admin-only tool restricts access"""
        tool = MockAdminOnlyTool()

        # ADMIN should have access
        result = tool.run(user_role="ADMIN", action="delete_all")
        assert result["success"] == True

        # HR_MANAGER should NOT have access
        result = tool.run(user_role="HR_MANAGER", action="delete_all")
        assert result["success"] == False
        assert "Permission denied" in result["error"]

    def test_destructive_tool_flag(self):
        """Test destructive flag is set correctly"""
        regular_tool = MockQueryTool()
        admin_tool = MockAdminOnlyTool()

        assert regular_tool.destructive == False
        assert admin_tool.destructive == True

    def test_get_metadata(self):
        """Test tool metadata retrieval"""
        tool = MockQueryTool()
        metadata = tool.get_metadata()

        assert metadata["name"] == "mock_query"
        assert metadata["description"] is not None
        assert "ADMIN" in metadata["rbac_required"]
        assert metadata["destructive"] == False

    def test_tool_repr(self):
        """Test tool string representation"""
        tool = MockQueryTool()
        repr_str = repr(tool)

        assert "mock_query" in repr_str
        assert "ChatbotTool" in repr_str


# Test ToolRegistry
class TestToolRegistry:
    """Test suite for ToolRegistry"""

    def test_registry_initialization(self):
        """Test registry can be initialized"""
        registry = ToolRegistry()
        assert registry.get_tool_count() == 0

    def test_register_tool(self):
        """Test tool registration"""
        registry = ToolRegistry()
        tool = MockQueryTool()

        registry.register(tool)
        assert registry.get_tool_count() == 1

    def test_register_duplicate_tool(self):
        """Test duplicate tool registration raises error"""
        registry = ToolRegistry()
        tool1 = MockQueryTool()
        tool2 = MockQueryTool()

        registry.register(tool1)

        with pytest.raises(ValueError):
            registry.register(tool2)

    def test_register_invalid_type(self):
        """Test registering non-tool raises error"""
        registry = ToolRegistry()

        with pytest.raises(TypeError):
            registry.register("not a tool")

    def test_get_tool_exists(self):
        """Test retrieving existing tool"""
        registry = ToolRegistry()
        tool = MockQueryTool()
        registry.register(tool)

        retrieved = registry.get_tool("mock_query")
        assert retrieved is not None
        assert retrieved.name == "mock_query"

    def test_get_tool_not_exists(self):
        """Test retrieving non-existent tool returns None"""
        registry = ToolRegistry()

        retrieved = registry.get_tool("nonexistent_tool")
        assert retrieved is None

    def test_list_all_tools(self):
        """Test listing all tools"""
        registry = ToolRegistry()
        registry.register(MockQueryTool())
        registry.register(MockAdminOnlyTool())

        all_tools = registry.list_all_tools()
        assert len(all_tools) == 2
        assert all([isinstance(t, dict) for t in all_tools])

    def test_list_tools_for_role_admin(self):
        """Test listing tools for ADMIN role"""
        registry = ToolRegistry()
        registry.register(MockQueryTool())
        registry.register(MockAdminOnlyTool())

        admin_tools = registry.list_tools_for_role("ADMIN")
        assert len(admin_tools) == 2  # ADMIN can use both

    def test_list_tools_for_role_hr_manager(self):
        """Test listing tools for HR_MANAGER role"""
        registry = ToolRegistry()
        registry.register(MockQueryTool())
        registry.register(MockAdminOnlyTool())

        hr_tools = registry.list_tools_for_role("HR_MANAGER")
        assert len(hr_tools) == 1  # HR_MANAGER can only use mock_query

    def test_list_tools_for_role_viewer(self):
        """Test listing tools for VIEWER role"""
        registry = ToolRegistry()
        registry.register(MockQueryTool())
        registry.register(MockAdminOnlyTool())

        viewer_tools = registry.list_tools_for_role("VIEWER")
        assert len(viewer_tools) == 0  # VIEWER has no access

    def test_execute_tool_success(self):
        """Test executing tool through registry"""
        registry = ToolRegistry()
        registry.register(MockQueryTool())

        result = registry.execute_tool(
            tool_name="mock_query",
            user_role="ADMIN",
            question="Test question"
        )

        assert result["success"] == True
        assert result["result"]["question"] == "Test question"

    def test_execute_tool_not_found(self):
        """Test executing non-existent tool"""
        registry = ToolRegistry()

        result = registry.execute_tool(
            tool_name="nonexistent",
            user_role="ADMIN"
        )

        assert result["success"] == False
        assert "not found" in result["error"]

    def test_execute_tool_permission_denied(self):
        """Test executing tool without permission"""
        registry = ToolRegistry()
        registry.register(MockAdminOnlyTool())

        result = registry.execute_tool(
            tool_name="mock_admin_only",
            user_role="HR_MANAGER",
            action="delete"
        )

        assert result["success"] == False
        assert "Permission denied" in result["error"]

    def test_registry_repr(self):
        """Test registry string representation"""
        registry = ToolRegistry()
        registry.register(MockQueryTool())

        repr_str = repr(registry)
        assert "ToolRegistry" in repr_str
        assert "1 tools" in repr_str


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
