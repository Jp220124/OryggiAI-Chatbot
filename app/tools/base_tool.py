"""
Base Tool Class for Chatbot Tools
Provides standardized interface and RBAC integration
"""

from typing import Any, Dict, List, Optional, Tuple
from abc import ABC, abstractmethod
from loguru import logger
import inspect
import asyncio


class ChatbotTool(ABC):
    """
    Base class for all chatbot tools

    Provides:
    - Standardized tool interface
    - Built-in permission checking
    - Error handling
    - Execution logging

    All tools must inherit from this class and implement _run() method.

    Example:
        class MyTool(ChatbotTool):
            name = "my_tool"
            description = "Does something useful"
            rbac_required = ["ADMIN", "HR_MANAGER"]

            def _run(self, param1: str, **kwargs) -> Any:
                # Tool implementation
                return result
    """

    # Tool metadata (must be defined by subclasses)
    name: str
    description: str
    rbac_required: List[str]  # Roles that can use this tool
    destructive: bool = False  # Requires confirmation?

    def __init__(self):
        """
        Initialize tool and validate metadata

        Raises:
            ValueError: If required metadata is missing
        """
        # Validate required attributes
        if not hasattr(self, 'name') or not self.name:
            raise ValueError("Tool must define 'name' attribute")

        if not hasattr(self, 'description') or not self.description:
            raise ValueError("Tool must define 'description' attribute")

        if not hasattr(self, 'rbac_required'):
            raise ValueError("Tool must define 'rbac_required' attribute")

        if not isinstance(self.rbac_required, list):
            raise ValueError("'rbac_required' must be a list of role strings")

        logger.info(f"Initialized tool: {self.name}")

    def check_permission(self, user_role: str) -> Tuple[bool, Optional[str]]:
        """
        Check if user role has permission to use this tool

        Args:
            user_role: User's role (ADMIN, HR_MANAGER, HR_STAFF, VIEWER)

        Returns:
            Tuple of (allowed: bool, error_message: Optional[str])

        Example:
            allowed, error = tool.check_permission("HR_MANAGER")
            if not allowed:
                print(error)  # "Permission denied: ..."
        """
        if user_role in self.rbac_required:
            logger.info(f"Permission granted: {user_role} can use {self.name}")
            return True, None
        else:
            error = f"Permission denied: {user_role} cannot use {self.name}. Required roles: {', '.join(self.rbac_required)}"
            logger.warning(error)
            return False, error

    @abstractmethod
    def _run(self, **kwargs) -> Any:
        """
        Execute the tool (implemented by subclasses)

        Args:
            **kwargs: Tool-specific parameters

        Returns:
            Tool-specific result (Any type)

        Raises:
            NotImplementedError: If subclass doesn't implement this method
        """
        raise NotImplementedError("Tool must implement _run() method")

    async def run(self, user_role: str, **kwargs) -> Dict[str, Any]:
        """
        Execute tool with permission checking and error handling

        This method wraps _run() with:
        - Permission checking
        - Error handling
        - Result formatting
        - Execution logging

        Args:
            user_role: User's role for permission check
            **kwargs: Tool-specific parameters passed to _run()

        Returns:
            {
                "success": bool,      # True if execution succeeded
                "result": Any,        # Tool result (if success=True)
                "error": Optional[str] # Error message (if success=False)
            }

        Example:
            result = await tool.run(
                user_role="HR_MANAGER",
                question="How many employees?",
                user_id="manager_123"
            )

            if result["success"]:
                print(result["result"])
            else:
                print(result["error"])
        """
        logger.info(f"Executing tool: {self.name} (user_role: {user_role})")

        # Step 1: Check permission
        allowed, error = self.check_permission(user_role)
        if not allowed:
            logger.warning(f"Permission check failed: {error}")
            return {
                "success": False,
                "result": None,
                "error": error
            }

        # Step 2: Execute tool
        try:
            logger.debug(f"Running {self.name} with kwargs: {list(kwargs.keys())}")

            # Check if _run is async or sync
            if inspect.iscoroutinefunction(self._run):
                # Async _run method - await it
                result = await self._run(user_role=user_role, **kwargs)
            else:
                # Sync _run method - run in thread pool to avoid blocking
                # and to prevent event loop conflicts with Google API on Windows
                result = await asyncio.to_thread(
                    self._run, user_role=user_role, **kwargs
                )

            logger.info(f"Tool execution succeeded: {self.name}")
            return {
                "success": True,
                "result": result,
                "error": None
            }

        except Exception as e:
            logger.error(f"Tool execution failed: {self.name} - {str(e)}")
            return {
                "success": False,
                "result": None,
                "error": str(e)
            }

    def get_metadata(self) -> Dict[str, Any]:
        """
        Get tool metadata

        Returns:
            {
                "name": str,
                "description": str,
                "rbac_required": List[str],
                "destructive": bool
            }
        """
        return {
            "name": self.name,
            "description": self.description,
            "rbac_required": self.rbac_required,
            "destructive": self.destructive
        }

    def __repr__(self) -> str:
        """String representation of tool"""
        return f"<ChatbotTool: {self.name} (roles: {', '.join(self.rbac_required)})>"
