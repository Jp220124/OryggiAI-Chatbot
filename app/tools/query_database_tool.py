"""
QueryDatabaseTool - RBAC-enabled database query tool
Integrates RAG SQL Agent with role-based access control and data scoping
"""

from typing import Any, Dict, List, Optional
from loguru import logger
import time

from app.tools.base_tool import ChatbotTool
from app.agents.sql_agent import sql_agent
from app.middleware.rbac import rbac_middleware
from app.middleware.audit_logger import audit_logger


class QueryDatabaseTool(ChatbotTool):
    """
    Database query tool with RBAC integration

    Capabilities:
    - Natural language to SQL conversion using RAG
    - Role-based permission checking
    - Automatic data scoping based on user role
    - Comprehensive audit logging
    - Query result formatting

    Role Permissions:
    - ADMIN: Full database access, no filters
    - HR_MANAGER: Department-scoped queries
    - HR_STAFF: Own data only
    - VIEWER: Read-only access to own data

    Example:
        tool = QueryDatabaseTool()

        # ADMIN query (sees all data)
        result = tool.run(
            user_role="ADMIN",
            question="How many employees?",
            user_id="admin_001"
        )

        # HR_MANAGER query (sees department data)
        result = tool.run(
            user_role="HR_MANAGER",
            question="List employees in my department",
            user_id="manager_001",
            department="IT"
        )

        # HR_STAFF query (sees own data only)
        result = tool.run(
            user_role="HR_STAFF",
            question="Show my employment details",
            user_id="staff_001"
        )
    """

    # Tool metadata (required by ChatbotTool)
    name = "query_database"
    description = "Query the HR database using natural language. Automatically applies security filters based on your role."
    rbac_required = ["ADMIN", "HR_MANAGER", "HR_STAFF", "VIEWER"]
    destructive = False

    def __init__(self):
        """Initialize the query database tool"""
        super().__init__()
        logger.info(f"QueryDatabaseTool initialized with RBAC support")

    def _run(
        self,
        question: str,
        user_id: str,
        user_role: Optional[str] = None,
        department: Optional[str] = None,
        conversation_history: Optional[List[Dict]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute database query with RBAC enforcement

        Workflow:
        1. Get user role from database (if not provided)
        2. Check tool permission
        3. Generate SQL using RAG agent (with conversation history context)
        4. Apply data scoping filters
        5. Execute scoped query
        6. Log audit events
        7. Return formatted results

        Args:
            question: Natural language question
            user_id: User identifier (e.g., 'admin_001', 'staff_123')
            user_role: Optional user role (fetched from DB if not provided)
            department: Optional department for HR_MANAGER scoping
            conversation_history: Optional list of previous conversation messages for context
            **kwargs: Additional parameters

        Returns:
            Dict containing:
            - success: bool
            - sql_query: Generated SQL (before scoping)
            - scoped_sql_query: SQL after data scoping applied
            - results: Query results
            - result_count: Number of rows returned
            - natural_answer: Human-readable answer
            - data_scoped: Whether data scoping was applied
            - user_role: User's role
            - error: Error message (if failed)

        Example:
            result = tool._run(
                question="How many employees joined last month?",
                user_id="manager_001",
                user_role="HR_MANAGER",
                department="IT"
            )
        """
        start_time = time.time()

        try:
            # Step 1: Get user role if not provided
            if not user_role:
                user_role = rbac_middleware.get_user_role(user_id)
                logger.info(f"Fetched role for {user_id}: {user_role}")

            # Step 2: Check permission (already done in base class run(), but log it)
            logger.info(f"User {user_id} ({user_role}) executing query: {question}")

            # Step 3: Generate SQL using RAG agent (with conversation history for context)
            logger.info(f"Generating SQL for question: {question}")
            if conversation_history:
                logger.debug(f"Including {len(conversation_history)} conversation messages for context")
            logger.debug(f"DEBUG: Calling sql_agent.generate_sql for: {question}")
            try:
                sql_result = sql_agent.generate_sql(
                    question=question,
                    user_id=user_id,
                    conversation_history=conversation_history
                )
            except Exception as gen_err:
                logger.error(f"DEBUG: sql_agent.generate_sql FAILED: {type(gen_err).__name__}: {gen_err}")
                import traceback
                logger.error(traceback.format_exc())
                raise

            original_sql = sql_result["sql_query"]
            logger.info(f"Generated SQL: {original_sql[:100]}...")

            # Step 4: Apply data scoping based on role
            scoped_sql = self._apply_data_scoping(
                sql_query=original_sql,
                user_role=user_role,
                user_id=user_id,
                department=department
            )

            data_scoped = (scoped_sql != original_sql)
            if data_scoped:
                logger.info(f"Data scoping applied for {user_role}")
                logger.debug(f"Scoped SQL: {scoped_sql}")

            # Step 5: Execute the scoped query
            logger.info(f"Executing scoped query...")
            results = sql_agent.execute_query(scoped_sql)

            # Step 6: Format natural language answer (include SQL query in answer)
            natural_answer = sql_agent._format_answer(question, results, sql_query=scoped_sql)

            # Step 7: Log successful execution
            execution_time_ms = (time.time() - start_time) * 1000

            audit_logger.log_tool_execution(
                user_id=user_id,
                user_role=user_role,
                tool_name=self.name,
                success=True,
                execution_time_ms=execution_time_ms,
                question=question,
                rows_returned=len(results)
            )

            audit_logger.log_data_access(
                user_id=user_id,
                user_role=user_role,
                query=scoped_sql,
                rows_returned=len(results),
                data_scoped=data_scoped
            )

            logger.info(f"[OK] Query completed: {len(results)} rows returned")

            return {
                "success": True,
                "sql_query": original_sql,
                "scoped_sql_query": scoped_sql,
                "results": results,
                "result_count": len(results),
                "natural_answer": natural_answer,
                "data_scoped": data_scoped,
                "user_role": user_role,
                "tables_used": sql_result.get("tables_referenced", []),
                "execution_time_ms": execution_time_ms,
                "error": None
            }

        except Exception as e:
            # Log failed execution
            execution_time_ms = (time.time() - start_time) * 1000
            error_msg = str(e)

            logger.error(f"[ERROR] Query execution failed: {error_msg}")

            audit_logger.log_tool_execution(
                user_id=user_id,
                user_role=user_role or "UNKNOWN",
                tool_name=self.name,
                success=False,
                execution_time_ms=execution_time_ms,
                error=error_msg,
                question=question
            )

            # Capture original_sql if it exists (it might fail before generation)
            generated_sql = locals().get('original_sql')
            
            return {
                "success": False,
                "sql_query": generated_sql,
                "scoped_sql_query": None,
                "results": [],
                "result_count": 0,
                "natural_answer": f"I encountered an error: {error_msg}",
                "data_scoped": False,
                "user_role": user_role or "UNKNOWN",
                "error": error_msg
            }

    def _apply_data_scoping(
        self,
        sql_query: str,
        user_role: str,
        user_id: Optional[str] = None,
        department: Optional[str] = None
    ) -> str:
        """
        Apply data scoping filters to SQL query

        This method delegates to RBACMiddleware.apply_data_scoping()
        but adds additional logging and validation.

        Data Scoping Rules:
        - ADMIN: No filters (full access)
        - HR_MANAGER: Department filter (WHERE Department = 'X')
        - HR_STAFF: User filter (WHERE EmployeeId = 'user_id')
        - VIEWER: User filter (WHERE EmployeeId = 'user_id')

        Args:
            sql_query: Original SQL query
            user_role: User's role
            user_id: User identifier
            department: Department for HR_MANAGER scoping

        Returns:
            Modified SQL query with data scoping applied

        Example:
            # ADMIN - no scoping
            scoped = tool._apply_data_scoping(
                "SELECT * FROM Employees",
                user_role="ADMIN"
            )
            # Returns: "SELECT * FROM Employees"

            # HR_MANAGER - department scoping
            scoped = tool._apply_data_scoping(
                "SELECT * FROM Employees",
                user_role="HR_MANAGER",
                department="IT"
            )
            # Returns: "SELECT * FROM Employees WHERE Department = 'IT'"

            # HR_STAFF - user scoping
            scoped = tool._apply_data_scoping(
                "SELECT * FROM Employees",
                user_role="HR_STAFF",
                user_id="staff_001"
            )
            # Returns: "SELECT * FROM Employees WHERE EmployeeId = 'staff_001'"
        """
        logger.debug(f"Applying data scoping for role: {user_role}")

        # If department not provided for HR_MANAGER, try to fetch from UserRoles
        if user_role == "HR_MANAGER" and not department and user_id:
            department = self._get_user_department(user_id)
            if department:
                logger.info(f"Fetched department for {user_id}: {department}")

        # Delegate to RBAC middleware
        scoped_sql = rbac_middleware.apply_data_scoping(
            sql_query=sql_query,
            user_role=user_role,
            user_id=user_id,
            department=department
        )

        return scoped_sql

    def _get_user_department(self, user_id: str) -> Optional[str]:
        """
        Get user's department from UserRoles table

        Args:
            user_id: User identifier

        Returns:
            Department name or None
        """
        try:
            from app.config import Config
            import pyodbc

            conn = pyodbc.connect(Config.DATABASE_CONNECTION_STRING)
            cursor = conn.cursor()

            query = """
                SELECT Department
                FROM UserRoles
                WHERE UserId = ? AND IsActive = 1
            """

            cursor.execute(query, (user_id,))
            row = cursor.fetchone()
            conn.close()

            return row[0] if row and row[0] else None

        except Exception as e:
            logger.warning(f"Could not fetch department for {user_id}: {str(e)}")
            return None

    def get_metadata(self) -> Dict[str, Any]:
        """
        Get enhanced metadata including RBAC info

        Returns:
            Dict with tool metadata and RBAC configuration
        """
        metadata = super().get_metadata()

        metadata.update({
            "data_scoping_enabled": True,
            "supported_roles": self.rbac_required,
            "role_capabilities": {
                "ADMIN": "Full database access, no filters",
                "HR_MANAGER": "Department-scoped queries",
                "HR_STAFF": "Own data only",
                "VIEWER": "Read-only access to own data"
            }
        })

        return metadata

    def __repr__(self) -> str:
        """String representation"""
        return f"<QueryDatabaseTool: {len(self.rbac_required)} roles supported>"


# Global tool instance (for registration)
query_database_tool = QueryDatabaseTool()
