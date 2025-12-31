"""
RBAC Middleware for Role-Based Access Control
Manages role hierarchy, permissions, and data scoping
"""

from typing import Optional, Tuple, Dict, Any
from loguru import logger
import pyodbc


class RBACMiddleware:
    """
    Role-Based Access Control Middleware

    Provides:
    - Role hierarchy management (ADMIN > HR_MANAGER > HR_STAFF > VIEWER)
    - User role retrieval from database
    - Tool permission checking
    - Data scoping for SQL queries

    Role Hierarchy:
        ADMIN:      100 (Full access, can use any tool)
        HR_MANAGER:  50 (Manage team, reports, queries)
        HR_STAFF:    30 (View and basic operations)
        VIEWER:      10 (Read-only access)

    Example:
        rbac = RBACMiddleware()

        # Get user's role
        role = rbac.get_user_role(user_id="emp_123")

        # Check tool permission
        allowed, error = rbac.check_tool_permission(
            user_role="HR_MANAGER",
            tool_name="query_database"
        )

        # Apply data scoping to SQL query
        scoped_sql = rbac.apply_data_scoping(
            sql_query="SELECT * FROM Employees",
            user_role="HR_STAFF",
            user_id="emp_123"
        )
    """

    # Role hierarchy (higher number = more permissions)
    ROLE_HIERARCHY = {
        "ADMIN": 100,
        "HR_MANAGER": 50,
        "HR_STAFF": 30,
        "VIEWER": 10
    }

    # Default role for unknown users
    DEFAULT_ROLE = "VIEWER"

    def __init__(self, connection_string: Optional[str] = None):
        """
        Initialize RBAC middleware

        Args:
            connection_string: Optional database connection string.
                             If not provided, will be loaded from Config when needed.
        """
        logger.info("RBAC middleware initialized")
        self._connection_string = connection_string

    def get_user_role(self, user_id: str) -> str:
        """
        Get user's role from database

        Args:
            user_id: User's unique identifier (e.g., "emp_123", "manager_456")

        Returns:
            Role name (ADMIN, HR_MANAGER, HR_STAFF, or VIEWER)

        Example:
            role = rbac.get_user_role("emp_123")
            # Returns: "HR_STAFF"
        """
        try:
            import sys
            print(f"DEBUG: get_user_role called for {user_id}", file=sys.stderr)
            # Lazy-load connection string from Config if not provided
            if not self._connection_string:
                from app.config import Config
                self._connection_string = Config.DATABASE_CONNECTION_STRING

            # Query UserRoles table
            conn = pyodbc.connect(self._connection_string)
            cursor = conn.cursor()

            query = """
                SELECT Role
                FROM UserRoles
                WHERE UserId = ?
            """

            cursor.execute(query, (user_id,))
            row = cursor.fetchone()

            if row:
                role = row[0]
                logger.info(f"User {user_id} has role: {role}")
                return role
            else:
                logger.warning(f"User {user_id} not found in UserRoles, using default role: {self.DEFAULT_ROLE}")
                return self.DEFAULT_ROLE

        except Exception as e:
            import sys
            print(f"DEBUG: get_user_role caught exception: {e}", file=sys.stderr)
            logger.error(f"Error fetching user role: {str(e)}")
            # Return default role on error
            return self.DEFAULT_ROLE

        finally:
            if 'conn' in locals():
                conn.close()

    def check_tool_permission(
        self,
        user_role: str,
        tool_name: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if user role has permission to use a tool

        This is a wrapper that integrates with the ToolRegistry.
        The actual permission checking happens in ChatbotTool.check_permission()

        Args:
            user_role: User's role
            tool_name: Name of tool to check

        Returns:
            Tuple of (allowed: bool, error_message: Optional[str])

        Example:
            allowed, error = rbac.check_tool_permission(
                user_role="HR_MANAGER",
                tool_name="query_database"
            )
        """
        # Import here to avoid circular dependency
        from app.tools import tool_registry

        # Get tool from registry
        tool = tool_registry.get_tool(tool_name)
        if not tool:
            error = f"Tool '{tool_name}' not found in registry"
            logger.error(error)
            return False, error

        # Check permission using tool's built-in method
        return tool.check_permission(user_role)

    def apply_data_scoping(
        self,
        sql_query: str,
        user_role: str,
        user_id: Optional[str] = None,
        department: Optional[str] = None
    ) -> str:
        """
        Apply data scoping filters to SQL query based on user role

        Data Scoping Rules:
        - ADMIN: See all data (no filters)
        - HR_MANAGER: See all data in their department
        - HR_STAFF: See only their own data
        - VIEWER: See only their own data (read-only)

        Args:
            sql_query: Original SQL query
            user_role: User's role
            user_id: User's ID (required for HR_STAFF/VIEWER)
            department: User's department (required for HR_MANAGER)

        Returns:
            Modified SQL query with data scoping applied

        Example:
            # HR_STAFF sees only their data
            scoped_sql = rbac.apply_data_scoping(
                sql_query="SELECT * FROM Employees",
                user_role="HR_STAFF",
                user_id="emp_123"
            )
            # Returns: "SELECT * FROM Employees WHERE EmployeeId = 'emp_123'"

            # HR_MANAGER sees department data
            scoped_sql = rbac.apply_data_scoping(
                sql_query="SELECT * FROM Employees",
                user_role="HR_MANAGER",
                department="IT"
            )
            # Returns: "SELECT * FROM Employees WHERE Department = 'IT'"
        """
        logger.debug(f"Applying data scoping for role: {user_role}")

        # ADMIN: No scoping needed
        if user_role == "ADMIN":
            logger.debug("ADMIN role: No data scoping applied")
            return sql_query

        # HR_MANAGER: Filter by department
        elif user_role == "HR_MANAGER":
            if not department:
                logger.warning("HR_MANAGER role requires department, but none provided")
                return sql_query

            # Add department filter
            if "WHERE" in sql_query.upper():
                scoped_query = f"{sql_query} AND Department = '{department}'"
            else:
                scoped_query = f"{sql_query} WHERE Department = '{department}'"

            logger.debug(f"HR_MANAGER scoping: Added department filter for '{department}'")
            return scoped_query

        # HR_STAFF and VIEWER: Filter by user's own data
        elif user_role in ["HR_STAFF", "VIEWER"]:
            if not user_id:
                logger.warning(f"{user_role} role requires user_id, but none provided")
                return sql_query

            # Skip RBAC filtering for test/non-numeric user IDs
            # Ecode is an integer column, so we can only filter by numeric user IDs
            if not user_id.isdigit():
                logger.debug(f"{user_role} scoping: Skipping filter for non-numeric user_id '{user_id}'")
                return sql_query

            # Add user filter (using Ecode column which exists in EmployeeMaster)
            # Need to insert WHERE clause before ORDER BY, GROUP BY, etc.
            import re

            # Find position of ORDER BY, GROUP BY, HAVING, LIMIT clauses (case-insensitive)
            pattern = r'\b(ORDER\s+BY|GROUP\s+BY|HAVING|LIMIT)\b'
            match = re.search(pattern, sql_query, re.IGNORECASE)

            if match:
                # Insert WHERE condition before these clauses
                insert_pos = match.start()
                base_query = sql_query[:insert_pos].rstrip()
                tail_query = sql_query[insert_pos:]

                if "WHERE" in base_query.upper():
                    scoped_query = f"{base_query} AND Ecode = {user_id} {tail_query}"  # No quotes for integer
                else:
                    scoped_query = f"{base_query} WHERE Ecode = {user_id} {tail_query}"
            else:
                # No ORDER BY/GROUP BY, can append at end
                if "WHERE" in sql_query.upper():
                    scoped_query = f"{sql_query} AND Ecode = {user_id}"
                else:
                    scoped_query = f"{sql_query} WHERE Ecode = {user_id}"

            logger.debug(f"{user_role} scoping: Added user filter for Ecode = {user_id}")
            return scoped_query

        else:
            logger.warning(f"Unknown role '{user_role}', no data scoping applied")
            return sql_query

    def get_role_level(self, role: str) -> int:
        """
        Get numeric level for a role

        Args:
            role: Role name

        Returns:
            Numeric level (higher = more permissions)

        Example:
            level = rbac.get_role_level("HR_MANAGER")
            # Returns: 50
        """
        return self.ROLE_HIERARCHY.get(role, 0)

    def has_higher_role(self, user_role: str, required_role: str) -> bool:
        """
        Check if user role has equal or higher permissions than required role

        Args:
            user_role: User's current role
            required_role: Minimum required role

        Returns:
            True if user_role >= required_role

        Example:
            # ADMIN can do HR_MANAGER tasks
            has_access = rbac.has_higher_role("ADMIN", "HR_MANAGER")
            # Returns: True

            # HR_STAFF cannot do HR_MANAGER tasks
            has_access = rbac.has_higher_role("HR_STAFF", "HR_MANAGER")
            # Returns: False
        """
        user_level = self.get_role_level(user_role)
        required_level = self.get_role_level(required_role)

        return user_level >= required_level

    def get_audit_context(
        self,
        user_id: str,
        user_role: str,
        action: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate audit context for logging

        Args:
            user_id: User identifier
            user_role: User's role
            action: Action being performed
            **kwargs: Additional context

        Returns:
            Dictionary with audit information

        Example:
            context = rbac.get_audit_context(
                user_id="emp_123",
                user_role="HR_MANAGER",
                action="query_database",
                tool_name="query_database",
                question="How many employees?"
            )
        """
        return {
            "user_id": user_id,
            "user_role": user_role,
            "role_level": self.get_role_level(user_role),
            "action": action,
            "timestamp": None,  # Will be added by audit logger
            **kwargs
        }

    def __repr__(self) -> str:
        """String representation"""
        return f"<RBACMiddleware: {len(self.ROLE_HIERARCHY)} roles configured>"


# Global RBAC middleware instance
rbac_middleware = RBACMiddleware()
