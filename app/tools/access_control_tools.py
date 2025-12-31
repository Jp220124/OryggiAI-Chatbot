"""
Access Control Tools - RBAC-enabled tools for managing physical and application access
Integrates with external Access Control API and requires human confirmation for destructive actions
"""

from typing import Any, Dict, Optional
from datetime import datetime, timedelta
from loguru import logger
import time

from app.tools.base_tool import ChatbotTool
from app.integrations.access_control_api import (
    access_control_client,
    AccessType,
    AccessControlError
)
from app.middleware.audit_logger import audit_logger


class GrantAccessTool(ChatbotTool):
    """
    Tool to grant user access to a door, zone, or terminal

    This is a DESTRUCTIVE action that requires human confirmation.
    Only ADMIN users can execute this tool.

    Example:
        result = await tool.run(
            user_role="ADMIN",
            target_user_id="EMP001",
            target_type="door",
            target_id="DOOR-45",
            target_name="Server Room",
            start_date="2025-01-22",
            end_date="2025-12-31",
            granted_by="admin"
        )
    """

    name = "grant_access"
    description = "Grant a user access to a door, zone, terminal, or building. Requires confirmation."
    rbac_required = ["ADMIN"]
    destructive = True  # Triggers confirmation workflow

    def __init__(self):
        super().__init__()
        logger.info("GrantAccessTool initialized")

    def _run(
        self,
        target_user_id: str,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        target_name: Optional[str] = None,
        granted_by: Optional[str] = None,
        user_id: Optional[str] = None,
        user_role: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        schedule: Optional[Dict] = None,
        terminal_group_id: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute the grant access action

        Args:
            target_user_id: ID of the user receiving access (VisitorID in Oryggi)
            target_type: Type of target (door, zone, terminal, building) - defaults to 'zone'
            target_id: ID of the target (or TerminalGroupID for Oryggi)
            target_name: Human-readable name of the target
            granted_by: User ID of the person granting access
            user_id: Current user ID
            user_role: Current user role
            start_date: Start date (ISO format or None for now)
            end_date: End date (ISO format or None for 1 year)
            schedule: Optional schedule (e.g., {"weekdays": [1,2,3,4,5]})
            terminal_group_id: Oryggi TerminalGroupID (optional)

        Returns:
            Dict with success status and permission details
        """
        start_time = time.time()

        try:
            # Set defaults for optional params
            target_type = target_type or "zone"
            target_name = target_name or "Specified Location"
            granted_by = granted_by or user_id or "system"

            # Parse dates
            start_dt = datetime.fromisoformat(start_date) if start_date else datetime.now()
            end_dt = datetime.fromisoformat(end_date) if end_date else (datetime.now() + timedelta(days=365))

            # Convert target type (handle None and invalid values)
            try:
                access_type = AccessType(target_type.lower())
            except (ValueError, AttributeError):
                access_type = AccessType.ZONE  # Default to zone

            # Execute via Access Control API (async call in sync context)
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    access_control_client.grant_access(
                        user_id=target_user_id,
                        target_type=access_type,
                        target_id=target_id or "",
                        target_name=target_name,
                        granted_by=granted_by,
                        start_date=start_dt,
                        end_date=end_dt,
                        schedule=schedule,
                        terminal_group_id=terminal_group_id
                    )
                )
            finally:
                loop.close()

            execution_time_ms = (time.time() - start_time) * 1000

            # Log to audit
            audit_logger.log_action_execution(
                user_id=user_id,
                user_role=user_role or "ADMIN",
                action_type="grant_access",
                tool_name=self.name,
                success=result.success,
                execution_time_ms=execution_time_ms,
                target_user_id=target_user_id,
                target_type=target_type,
                target_id=target_id,
                target_name=target_name
            )

            return {
                "success": result.success,
                "message": result.message,
                "permission_id": result.permission_id,
                "details": result.details,
                "action_type": "grant_access",
                "target": {
                    "user_id": target_user_id,
                    "type": target_type,
                    "id": target_id,
                    "name": target_name
                },
                "execution_time_ms": execution_time_ms
            }

        except AccessControlError as e:
            logger.error(f"Grant access failed: {e.message}")
            return {
                "success": False,
                "message": f"Failed to grant access: {e.message}",
                "error": str(e),
                "action_type": "grant_access"
            }
        except Exception as e:
            logger.error(f"Grant access error: {str(e)}")
            return {
                "success": False,
                "message": f"Error: {str(e)}",
                "error": str(e),
                "action_type": "grant_access"
            }

    def get_confirmation_message(
        self,
        target_user_id: str = "unknown",
        target_type: str = "terminal",
        target_id: str = None,
        target_name: str = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        employee_name: str = None,
        employee_code: str = None,
        employee_department: str = None,
        employee_designation: str = None,
        employee_card_no: str = None,
        **kwargs
    ) -> str:
        """Generate human-readable confirmation message with employee details"""
        start_str = start_date or "now"
        end_str = end_date or "1 year from now"
        target_name = target_name or "Specified Location"
        target_id = target_id or "default"

        # Build employee details section if available
        if employee_name:
            employee_section = (
                f"**Employee Details:**\n"
                f"- Name: {employee_name}\n"
                f"- Code: {employee_code or target_user_id}\n"
            )
            if employee_department:
                employee_section += f"- Department: {employee_department}\n"
            if employee_designation:
                employee_section += f"- Designation: {employee_designation}\n"
            if employee_card_no:
                employee_section += f"- Card No: {employee_card_no}\n"
        else:
            employee_section = f"**Employee:** {target_user_id}\n"

        return (
            f"**GRANT ACCESS REQUEST**\n\n"
            f"{employee_section}\n"
            f"**Access Details:**\n"
            f"- Target: {target_name}\n"
            f"- Start: {start_str}\n"
            f"- End: {end_str}\n\n"
            f"Do you want to proceed with granting access?"
        )


class BlockAccessTool(ChatbotTool):
    """
    Tool to block user access to a door, zone, or terminal

    This immediately revokes all active permissions and prevents future access.
    This is a DESTRUCTIVE action that requires human confirmation.
    Only ADMIN users can execute this tool.
    """

    name = "block_access"
    description = "Block a user's access to a door, zone, terminal, or building. Immediately effective. Requires confirmation."
    rbac_required = ["ADMIN"]
    destructive = True

    def __init__(self):
        super().__init__()
        logger.info("BlockAccessTool initialized")

    def _run(
        self,
        target_user_id: str,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        target_name: Optional[str] = None,
        blocked_by: Optional[str] = None,
        user_id: Optional[str] = None,
        user_role: Optional[str] = None,
        reason: str = "Blocked via chatbot",
        terminal_group_id: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute the block access action

        Args:
            target_user_id: ID of the user to block (VisitorID in Oryggi)
            target_type: Type of target - defaults to 'area'
            target_id: ID of the target
            target_name: Name of the target - defaults to 'all areas'
            blocked_by: User ID of the person blocking
            user_id: Current user ID
            user_role: Current user role
            reason: Reason for blocking
            terminal_group_id: Oryggi TerminalGroupID (optional)

        Returns:
            Dict with success status
        """
        start_time = time.time()

        try:
            # Set defaults for optional params
            target_type = target_type or "area"
            target_name = target_name or "all areas"
            target_id = target_id or "all"
            blocked_by = blocked_by or user_id or "system"

            # Convert target type (handle None and invalid values)
            try:
                access_type = AccessType(target_type.lower())
            except (ValueError, AttributeError):
                access_type = AccessType.AREA

            # Execute via Access Control API
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    access_control_client.block_access(
                        user_id=target_user_id,
                        target_type=access_type,
                        target_id=target_id,
                        target_name=target_name,
                        blocked_by=blocked_by,
                        reason=reason,
                        terminal_group_id=terminal_group_id
                    )
                )
            finally:
                loop.close()

            execution_time_ms = (time.time() - start_time) * 1000

            # Log to audit
            audit_logger.log_action_execution(
                user_id=user_id,
                user_role=user_role or "ADMIN",
                action_type="block_access",
                tool_name=self.name,
                success=result.success,
                execution_time_ms=execution_time_ms,
                target_user_id=target_user_id,
                target_type=target_type,
                target_id=target_id,
                target_name=target_name,
                reason=reason
            )

            return {
                "success": result.success,
                "message": result.message,
                "details": result.details,
                "action_type": "block_access",
                "target": {
                    "user_id": target_user_id,
                    "type": target_type,
                    "id": target_id,
                    "name": target_name
                },
                "reason": reason,
                "execution_time_ms": execution_time_ms
            }

        except AccessControlError as e:
            logger.error(f"Block access failed: {e.message}")
            return {
                "success": False,
                "message": f"Failed to block access: {e.message}",
                "error": str(e),
                "action_type": "block_access"
            }
        except Exception as e:
            logger.error(f"Block access error: {str(e)}")
            return {
                "success": False,
                "message": f"Error: {str(e)}",
                "error": str(e),
                "action_type": "block_access"
            }

    def get_confirmation_message(
        self,
        target_user_id: str = "unknown",
        target_type: str = "terminal",
        target_id: str = None,
        target_name: str = None,
        reason: str = "Blocked via chatbot",
        employee_name: str = None,
        employee_code: str = None,
        employee_department: str = None,
        employee_designation: str = None,
        employee_card_no: str = None,
        **kwargs
    ) -> str:
        """Generate human-readable confirmation message with employee details"""
        target_name = target_name or "All areas"
        target_id = target_id or "default"

        # Build employee details section if available
        if employee_name:
            employee_section = (
                f"**Employee Details:**\n"
                f"- Name: {employee_name}\n"
                f"- Code: {employee_code or target_user_id}\n"
            )
            if employee_department:
                employee_section += f"- Department: {employee_department}\n"
            if employee_designation:
                employee_section += f"- Designation: {employee_designation}\n"
            if employee_card_no:
                employee_section += f"- Card No: {employee_card_no}\n"
        else:
            employee_section = f"**Employee:** {target_user_id}\n"

        return (
            f"**[WARNING] BLOCK ACCESS REQUEST**\n\n"
            f"{employee_section}\n"
            f"**Action Details:**\n"
            f"- Target: {target_name}\n"
            f"- Reason: {reason}\n"
            f"- [WARNING] This action takes effect IMMEDIATELY\n\n"
            f"Do you want to proceed with blocking access?"
        )


class RevokeAccessTool(ChatbotTool):
    """
    Tool to revoke a specific access permission

    Revokes a single permission by ID. Use this when you know the specific
    permission to remove (e.g., from a list of user's permissions).
    This is a DESTRUCTIVE action that requires human confirmation.
    Only ADMIN users can execute this tool.
    """

    name = "revoke_access"
    description = "Revoke a specific access permission by ID. Requires confirmation."
    rbac_required = ["ADMIN"]
    destructive = True

    def __init__(self):
        super().__init__()
        logger.info("RevokeAccessTool initialized")

    def _run(
        self,
        permission_id: Optional[str] = None,
        revoked_by: Optional[str] = None,
        user_id: Optional[str] = None,
        user_role: Optional[str] = None,
        reason: str = "Revoked via chatbot",
        target_user_id: Optional[str] = None,
        terminal_group_id: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute the revoke access action

        Args:
            permission_id: ID of the permission to revoke
            revoked_by: User ID of the person revoking
            user_id: Current user ID (invoking user)
            user_role: Current user role
            reason: Reason for revocation
            target_user_id: User whose access to revoke (for Oryggi)
            terminal_group_id: Oryggi TerminalGroupID (optional)

        Returns:
            Dict with success status
        """
        start_time = time.time()

        try:
            # Set defaults
            revoked_by = revoked_by or user_id or "system"
            permission_id = permission_id or "unknown"

            # Execute via Access Control API
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    access_control_client.revoke_access(
                        permission_id=permission_id,
                        revoked_by=revoked_by,
                        reason=reason,
                        user_id=target_user_id,
                        terminal_group_id=terminal_group_id
                    )
                )
            finally:
                loop.close()

            execution_time_ms = (time.time() - start_time) * 1000

            # Log to audit
            audit_logger.log_action_execution(
                user_id=user_id,
                user_role=user_role or "ADMIN",
                action_type="revoke_access",
                tool_name=self.name,
                success=result.success,
                execution_time_ms=execution_time_ms,
                permission_id=permission_id,
                reason=reason
            )

            return {
                "success": result.success,
                "message": result.message,
                "permission_id": permission_id,
                "details": result.details,
                "action_type": "revoke_access",
                "reason": reason,
                "execution_time_ms": execution_time_ms
            }

        except AccessControlError as e:
            logger.error(f"Revoke access failed: {e.message}")
            return {
                "success": False,
                "message": f"Failed to revoke access: {e.message}",
                "error": str(e),
                "action_type": "revoke_access"
            }
        except Exception as e:
            logger.error(f"Revoke access error: {str(e)}")
            return {
                "success": False,
                "message": f"Error: {str(e)}",
                "error": str(e),
                "action_type": "revoke_access"
            }

    def get_confirmation_message(
        self,
        permission_id: str = "unknown",
        reason: str = "Revoked via chatbot",
        target_user_id: str = None,
        employee_name: str = None,
        employee_code: str = None,
        employee_department: str = None,
        employee_designation: str = None,
        employee_card_no: str = None,
        **kwargs
    ) -> str:
        """Generate human-readable confirmation message with employee details"""
        # Build employee details section if available
        if employee_name:
            employee_section = (
                f"**Employee Details:**\n"
                f"- Name: {employee_name}\n"
                f"- Code: {employee_code or target_user_id or 'N/A'}\n"
            )
            if employee_department:
                employee_section += f"- Department: {employee_department}\n"
            if employee_designation:
                employee_section += f"- Designation: {employee_designation}\n"
            if employee_card_no:
                employee_section += f"- Card No: {employee_card_no}\n"
        elif target_user_id:
            employee_section = f"**Employee:** {target_user_id}\n"
        else:
            employee_section = ""

        return (
            f"**[WARNING] REVOKE ACCESS REQUEST**\n\n"
            f"{employee_section}\n"
            f"**Action Details:**\n"
            f"- Permission ID: {permission_id}\n"
            f"- Reason: {reason}\n"
            f"- [WARNING] This action takes effect IMMEDIATELY\n\n"
            f"Do you want to proceed with revoking access?"
        )


class ListUserAccessTool(ChatbotTool):
    """
    Tool to list all access permissions for a user

    This is a READ-ONLY tool that doesn't require confirmation.
    Available to ADMIN and HR_MANAGER roles.
    """

    name = "list_user_access"
    description = "List all access permissions for a specific user"
    rbac_required = ["ADMIN", "HR_MANAGER"]
    destructive = False  # No confirmation needed

    def __init__(self):
        super().__init__()
        logger.info("ListUserAccessTool initialized")

    def _run(
        self,
        target_user_id: str,
        user_id: str,
        user_role: Optional[str] = None,
        include_inactive: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        List access permissions for a user

        Args:
            target_user_id: ID of the user to list permissions for
            user_id: Current user ID
            user_role: Current user role
            include_inactive: Whether to include blocked/revoked permissions

        Returns:
            Dict with list of permissions
        """
        try:
            # Execute via Access Control API
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                permissions = loop.run_until_complete(
                    access_control_client.get_user_permissions(
                        user_id=target_user_id,
                        include_inactive=include_inactive
                    )
                )
            finally:
                loop.close()

            # Format permissions for response
            formatted_permissions = []
            for perm in permissions:
                formatted_permissions.append({
                    "permission_id": perm.permission_id,
                    "access_type": perm.access_type.value,
                    "target_id": perm.target_id,
                    "target_name": perm.target_name,
                    "status": perm.status.value,
                    "granted_by": perm.granted_by,
                    "granted_at": perm.granted_at.isoformat(),
                    "expires_at": perm.expires_at.isoformat() if perm.expires_at else None
                })

            return {
                "success": True,
                "user_id": target_user_id,
                "permissions": formatted_permissions,
                "count": len(formatted_permissions),
                "message": f"Found {len(formatted_permissions)} access permission(s) for user {target_user_id}"
            }

        except AccessControlError as e:
            logger.error(f"List access failed: {e.message}")
            return {
                "success": False,
                "message": f"Failed to list access: {e.message}",
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"List access error: {str(e)}")
            return {
                "success": False,
                "message": f"Error: {str(e)}",
                "error": str(e)
            }


# Global tool instances
grant_access_tool = GrantAccessTool()
block_access_tool = BlockAccessTool()
revoke_access_tool = RevokeAccessTool()
list_user_access_tool = ListUserAccessTool()
