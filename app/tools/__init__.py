"""
Tool Registry for Chatbot Tools
Manages tool discovery, registration, and execution
"""

from typing import Dict, List, Optional
from loguru import logger

from app.tools.base_tool import ChatbotTool


class ToolRegistry:
    """
    Central registry for all chatbot tools

    Manages:
    - Tool registration
    - Tool discovery
    - Tool execution
    - Permission enforcement

    Example:
        registry = ToolRegistry()
        registry.register(QueryDatabaseTool())
        registry.register(GeneratePDFReportTool())

        # List available tools for a role
        tools = registry.list_tools_for_role("HR_MANAGER")

        # Execute a tool
        result = registry.execute_tool(
            tool_name="query_database",
            user_role="HR_MANAGER",
            question="How many employees?"
        )
    """

    def __init__(self):
        """Initialize empty tool registry"""
        self._tools: Dict[str, ChatbotTool] = {}
        logger.info("Tool registry initialized")

    def register(self, tool: ChatbotTool) -> None:
        """
        Register a new tool

        Args:
            tool: ChatbotTool instance to register

        Raises:
            ValueError: If tool with same name already registered
        """
        if not isinstance(tool, ChatbotTool):
            raise TypeError(f"Tool must be instance of ChatbotTool, got {type(tool)}")

        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' already registered")

        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name} (roles: {', '.join(tool.rbac_required)})")

    def get_tool(self, tool_name: str) -> Optional[ChatbotTool]:
        """
        Get tool by name

        Args:
            tool_name: Name of tool to retrieve

        Returns:
            ChatbotTool instance or None if not found
        """
        return self._tools.get(tool_name)

    def list_all_tools(self) -> List[Dict]:
        """
        List all registered tools

        Returns:
            List of tool metadata dictionaries
        """
        return [tool.get_metadata() for tool in self._tools.values()]

    def list_tools_for_role(self, user_role: str) -> List[Dict]:
        """
        List tools available to a specific role

        Args:
            user_role: User's role (ADMIN, HR_MANAGER, etc.)

        Returns:
            List of tool metadata for accessible tools
        """
        available_tools = []

        for tool in self._tools.values():
            allowed, _ = tool.check_permission(user_role)
            if allowed:
                available_tools.append(tool.get_metadata())

        logger.info(f"Found {len(available_tools)} tools for role {user_role}")
        return available_tools

    def execute_tool(
        self,
        tool_name: str,
        user_role: str,
        **kwargs
    ) -> Dict:
        """
        Execute a tool by name

        Args:
            tool_name: Name of tool to execute
            user_role: User's role for permission check
            **kwargs: Tool-specific parameters

        Returns:
            {
                "success": bool,
                "result": Any,
                "error": Optional[str]
            }

        Example:
            result = registry.execute_tool(
                tool_name="query_database",
                user_role="HR_MANAGER",
                question="How many employees?",
                user_id="manager_123"
            )
        """
        # Check if tool exists
        tool = self.get_tool(tool_name)
        if not tool:
            error = f"Tool '{tool_name}' not found"
            logger.error(error)
            return {
                "success": False,
                "result": None,
                "error": error
            }

        # Execute tool with permission checking
        logger.info(f"Executing tool: {tool_name} (user_role: {user_role})")
        return tool.run(user_role=user_role, **kwargs)

    def get_tool_count(self) -> int:
        """Get number of registered tools"""
        return len(self._tools)

    def __repr__(self) -> str:
        """String representation of registry"""
        return f"<ToolRegistry: {len(self._tools)} tools registered>"


# Global tool registry instance
tool_registry = ToolRegistry()


# Auto-register available tools
def _register_default_tools():
    """Register all default tools on module import"""
    try:
        from app.tools.query_database_tool import query_database_tool
        tool_registry.register(query_database_tool)
        logger.info("Auto-registered QueryDatabaseTool")
    except Exception as e:
        logger.warning(f"Could not auto-register QueryDatabaseTool: {e}")

    try:
        from app.tools.generate_report_tool import generate_report_tool
        tool_registry.register(generate_report_tool)
        logger.info("Auto-registered GenerateReportTool")
    except Exception as e:
        logger.warning(f"Could not auto-register GenerateReportTool: {e}")

    # Access Control Tools (Phase 5)
    try:
        from app.tools.access_control_tools import (
            grant_access_tool,
            block_access_tool,
            revoke_access_tool,
            list_user_access_tool
        )
        tool_registry.register(grant_access_tool)
        tool_registry.register(block_access_tool)
        tool_registry.register(revoke_access_tool)
        tool_registry.register(list_user_access_tool)
        logger.info("Auto-registered Access Control Tools (grant, block, revoke, list)")
    except Exception as e:
        logger.warning(f"Could not auto-register Access Control Tools: {e}")

    # Extended Access Control Tools (Phase 6)
    try:
        from app.tools.access_control_tools_extended import (
            visitor_registration_tool,
            temporary_card_tool,
            database_backup_tool,
            card_enrollment_tool,
            employee_enrollment_tool,
            door_access_tool,
            employee_management_tool
        )
        tool_registry.register(visitor_registration_tool)
        tool_registry.register(temporary_card_tool)
        tool_registry.register(database_backup_tool)
        tool_registry.register(card_enrollment_tool)
        tool_registry.register(employee_enrollment_tool)
        tool_registry.register(door_access_tool)
        tool_registry.register(employee_management_tool)
        logger.info("Auto-registered Extended Access Control Tools (visitor, temp_card, backup, card_enroll, emp_enroll, door_access, emp_management)")
    except Exception as e:
        logger.warning(f"Could not auto-register Extended Access Control Tools: {e}")

    # Employee Onboarding Tools (QR-based biometric enrollment)
    try:
        from app.tools.employee_onboarding_tool import (
            EmployeeOnboardingTool,
            GetDepartmentsListTool,
            GetDesignationsListTool
        )
        tool_registry.register(EmployeeOnboardingTool())
        tool_registry.register(GetDepartmentsListTool())
        tool_registry.register(GetDesignationsListTool())
        logger.info("Auto-registered Employee Onboarding Tools (onboard_new_employee, get_departments_list, get_designations_list)")
    except Exception as e:
        logger.warning(f"Could not auto-register Employee Onboarding Tools: {e}")

    # Employee Action Tool (Activate/Deactivate via Gateway Agent)
    try:
        from app.tools.employee_action_tool import employee_action_tool
        tool_registry.register(employee_action_tool)
        logger.info("Auto-registered Employee Action Tool (activate/deactivate via gateway)")
    except Exception as e:
        logger.warning(f"Could not auto-register Employee Action Tool: {e}")

    # Employee Blacklist Tool (Blacklist/Remove from Blacklist via Gateway Agent)
    try:
        from app.tools.employee_blacklist_tool import employee_blacklist_tool
        tool_registry.register(employee_blacklist_tool)
        logger.info("Auto-registered Employee Blacklist Tool (blacklist/remove_blacklist via gateway)")
    except Exception as e:
        logger.warning(f"Could not auto-register Employee Blacklist Tool: {e}")

    # Employee Terminate Tool (Terminate/Un-terminate via Gateway Agent)
    try:
        from app.tools.employee_terminate_tool import employee_terminate_tool
        tool_registry.register(employee_terminate_tool)
        logger.info("Auto-registered Employee Terminate Tool (terminate/un-terminate via gateway)")
    except Exception as e:
        logger.warning(f"Could not auto-register Employee Terminate Tool: {e}")


# Auto-register tools when module is imported
_register_default_tools()


# Export base class and registry
__all__ = [
    "ChatbotTool",
    "ToolRegistry",
    "tool_registry"
]
