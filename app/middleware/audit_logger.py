"""
Audit Logger for Security and Compliance
Logs all permission checks, tool executions, and data access
"""

from typing import Dict, Any, Optional
from datetime import datetime
from loguru import logger
import json


class AuditLogger:
    """
    Security audit logger for tracking all user actions

    Logs:
    - Permission checks (granted/denied)
    - Tool executions (success/failure)
    - Data access attempts
    - Role changes
    - Security events

    Example:
        audit = AuditLogger()

        # Log permission check
        audit.log_permission_check(
            user_id="emp_123",
            user_role="HR_STAFF",
            action="query_database",
            allowed=True
        )

        # Log tool execution
        audit.log_tool_execution(
            user_id="emp_123",
            user_role="HR_STAFF",
            tool_name="query_database",
            success=True,
            execution_time_ms=450
        )

        # Log data access
        audit.log_data_access(
            user_id="emp_123",
            user_role="HR_STAFF",
            query="SELECT * FROM Employees WHERE EmployeeId = 'emp_123'",
            rows_returned=1
        )
    """

    def __init__(self):
        """Initialize audit logger"""
        logger.info("Audit logger initialized")

    def log_permission_check(
        self,
        user_id: str,
        user_role: str,
        action: str,
        allowed: bool,
        reason: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        Log permission check result

        Args:
            user_id: User identifier
            user_role: User's role
            action: Action being checked (e.g., "query_database", "generate_report")
            allowed: Whether permission was granted
            reason: Reason for denial (if allowed=False)
            **kwargs: Additional context

        Example:
            audit.log_permission_check(
                user_id="emp_123",
                user_role="VIEWER",
                action="delete_employee",
                allowed=False,
                reason="VIEWER role cannot perform destructive actions"
            )
        """
        timestamp = datetime.utcnow().isoformat()

        audit_entry = {
            "event_type": "PERMISSION_CHECK",
            "timestamp": timestamp,
            "user_id": user_id,
            "user_role": user_role,
            "action": action,
            "allowed": allowed,
            "reason": reason,
            **kwargs
        }

        # Log at appropriate level
        if allowed:
            logger.info(f"[AUDIT] Permission granted: {json.dumps(audit_entry)}")
        else:
            logger.warning(f"[AUDIT] Permission denied: {json.dumps(audit_entry)}")

    def log_tool_execution(
        self,
        user_id: str,
        user_role: str,
        tool_name: str,
        success: bool,
        execution_time_ms: Optional[float] = None,
        error: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        Log tool execution

        Args:
            user_id: User identifier
            user_role: User's role
            tool_name: Name of tool executed
            success: Whether execution succeeded
            execution_time_ms: Execution time in milliseconds
            error: Error message (if success=False)
            **kwargs: Additional context

        Example:
            audit.log_tool_execution(
                user_id="emp_123",
                user_role="HR_MANAGER",
                tool_name="query_database",
                success=True,
                execution_time_ms=450,
                question="How many employees in IT?"
            )
        """
        timestamp = datetime.utcnow().isoformat()

        audit_entry = {
            "event_type": "TOOL_EXECUTION",
            "timestamp": timestamp,
            "user_id": user_id,
            "user_role": user_role,
            "tool_name": tool_name,
            "success": success,
            "execution_time_ms": execution_time_ms,
            "error": error,
            **kwargs
        }

        # Log at appropriate level
        if success:
            logger.info(f"[AUDIT] Tool execution succeeded: {json.dumps(audit_entry)}")
        else:
            logger.error(f"[AUDIT] Tool execution failed: {json.dumps(audit_entry)}")

    def log_data_access(
        self,
        user_id: str,
        user_role: str,
        query: str,
        rows_returned: Optional[int] = None,
        data_scoped: bool = False,
        **kwargs
    ) -> None:
        """
        Log data access attempt

        Args:
            user_id: User identifier
            user_role: User's role
            query: SQL query executed
            rows_returned: Number of rows returned
            data_scoped: Whether data scoping was applied
            **kwargs: Additional context

        Example:
            audit.log_data_access(
                user_id="emp_123",
                user_role="HR_STAFF",
                query="SELECT * FROM Employees WHERE EmployeeId = 'emp_123'",
                rows_returned=1,
                data_scoped=True
            )
        """
        timestamp = datetime.utcnow().isoformat()

        audit_entry = {
            "event_type": "DATA_ACCESS",
            "timestamp": timestamp,
            "user_id": user_id,
            "user_role": user_role,
            "query": query,
            "rows_returned": rows_returned,
            "data_scoped": data_scoped,
            **kwargs
        }

        logger.info(f"[AUDIT] Data access: {json.dumps(audit_entry)}")

    def log_role_change(
        self,
        user_id: str,
        old_role: str,
        new_role: str,
        changed_by: str,
        **kwargs
    ) -> None:
        """
        Log user role change

        Args:
            user_id: User whose role changed
            old_role: Previous role
            new_role: New role
            changed_by: User who made the change
            **kwargs: Additional context

        Example:
            audit.log_role_change(
                user_id="emp_123",
                old_role="HR_STAFF",
                new_role="HR_MANAGER",
                changed_by="admin_456",
                reason="Promotion"
            )
        """
        timestamp = datetime.utcnow().isoformat()

        audit_entry = {
            "event_type": "ROLE_CHANGE",
            "timestamp": timestamp,
            "user_id": user_id,
            "old_role": old_role,
            "new_role": new_role,
            "changed_by": changed_by,
            **kwargs
        }

        logger.warning(f"[AUDIT] Role change: {json.dumps(audit_entry)}")

    def log_security_event(
        self,
        event_type: str,
        severity: str,
        user_id: Optional[str] = None,
        description: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        Log security-related event

        Args:
            event_type: Type of security event
            severity: Severity level (LOW, MEDIUM, HIGH, CRITICAL)
            user_id: User involved (if applicable)
            description: Description of event
            **kwargs: Additional context

        Example:
            audit.log_security_event(
                event_type="UNAUTHORIZED_ACCESS_ATTEMPT",
                severity="HIGH",
                user_id="emp_123",
                description="Attempted to access admin-only tool",
                tool_name="delete_all_employees"
            )
        """
        timestamp = datetime.utcnow().isoformat()

        audit_entry = {
            "event_type": f"SECURITY_{event_type}",
            "timestamp": timestamp,
            "severity": severity,
            "user_id": user_id,
            "description": description,
            **kwargs
        }

        # Log at appropriate level based on severity
        if severity in ["HIGH", "CRITICAL"]:
            logger.error(f"[AUDIT] Security event: {json.dumps(audit_entry)}")
        elif severity == "MEDIUM":
            logger.warning(f"[AUDIT] Security event: {json.dumps(audit_entry)}")
        else:
            logger.info(f"[AUDIT] Security event: {json.dumps(audit_entry)}")

    def log_action_execution(
        self,
        user_id: str,
        user_role: str,
        action_type: str,
        tool_name: str,
        success: bool,
        execution_time_ms: Optional[float] = None,
        target_user_id: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        target_name: Optional[str] = None,
        reason: Optional[str] = None,
        permission_id: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        Log access control action execution (Phase 5)

        Args:
            user_id: User executing the action
            user_role: User's role
            action_type: Type of action (grant_access, block_access, revoke_access)
            tool_name: Name of tool executed
            success: Whether execution succeeded
            execution_time_ms: Execution time in milliseconds
            target_user_id: User affected by the action
            target_type: Type of target (door, zone, terminal)
            target_id: ID of target
            target_name: Name of target
            reason: Reason for action (for block/revoke)
            permission_id: Permission ID (for revoke)
            **kwargs: Additional context

        Example:
            audit.log_action_execution(
                user_id="admin_001",
                user_role="ADMIN",
                action_type="grant_access",
                tool_name="grant_access_tool",
                success=True,
                target_user_id="EMP123",
                target_type="door",
                target_id="DOOR-45",
                target_name="Server Room"
            )
        """
        timestamp = datetime.utcnow().isoformat()

        audit_entry = {
            "event_type": "ACTION_EXECUTION",
            "timestamp": timestamp,
            "user_id": user_id,
            "user_role": user_role,
            "action_type": action_type,
            "tool_name": tool_name,
            "success": success,
            "execution_time_ms": execution_time_ms,
            "target": {
                "user_id": target_user_id,
                "type": target_type,
                "id": target_id,
                "name": target_name
            },
            "reason": reason,
            "permission_id": permission_id,
            **kwargs
        }

        # Log at appropriate level
        if success:
            logger.info(f"[AUDIT] Action executed: {json.dumps(audit_entry)}")
        else:
            logger.error(f"[AUDIT] Action failed: {json.dumps(audit_entry)}")

    def log_action_request(
        self,
        user_id: str,
        user_role: str,
        action_type: str,
        pending_action_id: str,
        confirmation_message: str,
        target_user_id: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        target_name: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        Log when an action is requested and awaiting confirmation

        Args:
            user_id: User requesting the action
            user_role: User's role
            action_type: Type of action requested
            pending_action_id: ID of the pending action
            confirmation_message: Message shown to user
            target_*: Target details
            **kwargs: Additional context
        """
        timestamp = datetime.utcnow().isoformat()

        audit_entry = {
            "event_type": "ACTION_REQUESTED",
            "timestamp": timestamp,
            "user_id": user_id,
            "user_role": user_role,
            "action_type": action_type,
            "pending_action_id": pending_action_id,
            "confirmation_message": confirmation_message[:100] + "..." if len(confirmation_message) > 100 else confirmation_message,
            "target": {
                "user_id": target_user_id,
                "type": target_type,
                "id": target_id,
                "name": target_name
            },
            **kwargs
        }

        logger.info(f"[AUDIT] Action requested: {json.dumps(audit_entry)}")

    def log_action_confirmation(
        self,
        user_id: str,
        user_role: str,
        pending_action_id: str,
        approved: bool,
        resolution_note: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        Log when a user confirms or rejects an action

        Args:
            user_id: User confirming/rejecting
            user_role: User's role
            pending_action_id: ID of the pending action
            approved: Whether the action was approved
            resolution_note: Optional note from user
            **kwargs: Additional context
        """
        timestamp = datetime.utcnow().isoformat()

        audit_entry = {
            "event_type": "ACTION_CONFIRMED" if approved else "ACTION_REJECTED",
            "timestamp": timestamp,
            "user_id": user_id,
            "user_role": user_role,
            "pending_action_id": pending_action_id,
            "approved": approved,
            "resolution_note": resolution_note,
            **kwargs
        }

        if approved:
            logger.info(f"[AUDIT] Action approved: {json.dumps(audit_entry)}")
        else:
            logger.warning(f"[AUDIT] Action rejected: {json.dumps(audit_entry)}")

    def log_login_attempt(
        self,
        user_id: str,
        success: bool,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        **kwargs
    ) -> None:
        """
        Log user login attempt

        Args:
            user_id: User attempting to login
            success: Whether login succeeded
            ip_address: User's IP address
            user_agent: User's browser/client
            **kwargs: Additional context

        Example:
            audit.log_login_attempt(
                user_id="emp_123",
                success=True,
                ip_address="192.168.1.100",
                user_agent="Mozilla/5.0..."
            )
        """
        timestamp = datetime.utcnow().isoformat()

        audit_entry = {
            "event_type": "LOGIN_ATTEMPT",
            "timestamp": timestamp,
            "user_id": user_id,
            "success": success,
            "ip_address": ip_address,
            "user_agent": user_agent,
            **kwargs
        }

        if success:
            logger.info(f"[AUDIT] Login succeeded: {json.dumps(audit_entry)}")
        else:
            logger.warning(f"[AUDIT] Login failed: {json.dumps(audit_entry)}")

    def __repr__(self) -> str:
        """String representation"""
        return "<AuditLogger: Security audit logging enabled>"


# Global audit logger instance
audit_logger = AuditLogger()
