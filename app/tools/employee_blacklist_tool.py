"""
Employee Blacklist Tool - Blacklist/Remove from Blacklist Employees via Local Oryggi REST API

This tool enables the chatbot to perform employee blacklist actions on the
local Oryggi system through the Gateway Agent infrastructure.

Architecture:
    User -> Chatbot (Cloud) -> Gateway Agent (WebSocket) -> Local Oryggi API

Oryggi API Endpoints:
    GET /BlackListEmployee?CorpEmpCode={ecode}&Reason={reason}&BlackListingDate={date}&ClientVersion={version}&IPAddress={ip}&OperatorEcode={operator}
    GET /RemoveBlackListedEmployee?CorpEmpCode={ecode}&IPAddress={ip}&OperatorEcode={operator}&ClientVersion={version}
"""

import time
from datetime import datetime
from typing import Any, Dict, Optional
from loguru import logger

from app.tools.base_tool import ChatbotTool
from app.gateway.connection_manager import gateway_manager
from app.gateway.exceptions import GatewayNotConnectedError, GatewayTimeoutError
from app.middleware.audit_logger import audit_logger

# Oryggi API constants
ORYGGI_CLIENT_VERSION = "24.07.2025"
ORYGGI_DEFAULT_IP = "localhost"


class EmployeeBlacklistTool(ChatbotTool):
    """
    Tool for blacklisting/removing from blacklist employees via local Oryggi REST API

    Actions are executed through the Gateway Agent which forwards
    REST API calls to the local Oryggi service.

    This is a DESTRUCTIVE action that requires human confirmation.
    Only ADMIN and HR_MANAGER roles can execute this tool.

    Example:
        result = await tool.run(
            user_role="ADMIN",
            action="blacklist",
            ecode=12345,
            user_id="admin_user",
            database_id="db_123",
            reason="Policy violation"
        )
    """

    name = "employee_blacklist"
    description = (
        "Blacklist or remove from blacklist an employee in the Oryggi system. "
        "Blacklisting prevents the employee from accessing any Oryggi systems. "
        "Requires employee ECode (ID number). Actions are executed on the local "
        "Oryggi system via the Gateway Agent."
    )
    rbac_required = ["ADMIN", "HR_MANAGER", "OWNER", "owner"]
    destructive = True  # Triggers confirmation workflow

    def __init__(self):
        super().__init__()
        logger.info("EmployeeBlacklistTool initialized")

    async def _run(
        self,
        action: str,
        ecode: int,
        user_id: str,
        database_id: Optional[str] = None,
        user_role: Optional[str] = None,
        reason: Optional[str] = None,
        employee_name: Optional[str] = None,
        conversation_id: Optional[str] = None,
        operator_ecode: Optional[int] = 1,
        blacklist_date: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute employee blacklist action via gateway to local Oryggi REST API

        Oryggi API:
            GET /BlackListEmployee?CorpEmpCode={ecode}&Reason={reason}&BlackListingDate={date}&...
            GET /RemoveBlackListedEmployee?CorpEmpCode={ecode}&...

        Args:
            action: Action to perform - "blacklist" or "remove_blacklist" (or "unblacklist")
            ecode: Employee code (CorpEmpCode in Oryggi system)
            user_id: Current user ID (invoking user)
            database_id: Database ID to route request to correct gateway agent
            user_role: Current user role
            reason: Reason for blacklisting (required for blacklist action)
            employee_name: Optional employee name for logging
            conversation_id: Optional conversation ID for tracking
            operator_ecode: Operator's employee code performing the action (default: 1)
            blacklist_date: Date of blacklisting (default: today)

        Returns:
            Dict with success status and action details
        """
        start_time = time.perf_counter()

        try:
            # Use provided database_id or auto-detect if not provided
            if database_id:
                logger.info(f"[{self.name}] Using provided database_id: {database_id}")
            else:
                database_id = gateway_manager.get_first_active_database_id()
                if not database_id:
                    error_msg = (
                        "No gateway agent is connected. Cannot reach the local Oryggi system. "
                        "Please ensure the Gateway Agent is running on your server."
                    )
                    logger.error(f"[{self.name}] {error_msg}")
                    return {
                        "success": False,
                        "error": error_msg,
                        "error_code": "NO_GATEWAY_CONNECTED",
                        "action_type": "employee_blacklist"
                    }
                logger.warning(f"[{self.name}] No database_id provided, auto-detected: {database_id}")

            # Validate and normalize action
            action = action.lower().strip()
            # Support multiple ways to say "remove from blacklist"
            if action in ["remove_blacklist", "unblacklist", "remove blacklist", "un-blacklist", "removeblacklist"]:
                action = "remove_blacklist"
            elif action in ["blacklist", "add_blacklist", "add blacklist"]:
                action = "blacklist"
            else:
                error_msg = f"Invalid action '{action}'. Must be 'blacklist' or 'remove_blacklist'."
                logger.error(f"[{self.name}] {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "action_type": "employee_blacklist"
                }

            # Validate ecode
            try:
                ecode = int(ecode)
            except (ValueError, TypeError):
                error_msg = f"Invalid employee code '{ecode}'. Must be a number."
                logger.error(f"[{self.name}] {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "action_type": "employee_blacklist"
                }

            # Build endpoint and query parameters based on action
            if action == "blacklist":
                # Blacklist endpoint
                endpoint = "/BlackListEmployee"

                # Use provided date or today
                if not blacklist_date:
                    blacklist_date = datetime.now().strftime("%Y-%m-%d")

                # Reason is required for blacklisting
                if not reason:
                    reason = "Blacklisted by HR"

                query_params = {
                    "CorpEmpCode": str(ecode),
                    "Reason": reason,
                    "BlackListingDate": blacklist_date,
                    "ClientVersion": ORYGGI_CLIENT_VERSION,
                    "IPAddress": ORYGGI_DEFAULT_IP,
                    "OperatorEcode": str(operator_ecode)
                }
                action_display = "blacklisted"
            else:
                # Remove from blacklist endpoint
                endpoint = "/RemoveBlackListedEmployee"

                query_params = {
                    "CorpEmpCode": str(ecode),
                    "IPAddress": ORYGGI_DEFAULT_IP,
                    "OperatorEcode": str(operator_ecode),
                    "ClientVersion": ORYGGI_CLIENT_VERSION
                }
                action_display = "removed from blacklist"

            logger.info(
                f"[{self.name}] Executing {action} for employee {ecode} "
                f"(database: {database_id}, user: {user_id})"
            )
            logger.debug(f"[{self.name}] Endpoint: {endpoint}, Query params: {query_params}")

            # Execute via gateway connection manager (GET with query parameters)
            try:
                response = await gateway_manager.execute_api_request(
                    database_id=database_id,
                    method="GET",
                    endpoint=endpoint,
                    query_params=query_params,
                    timeout=10,
                    user_id=user_id,
                    conversation_id=conversation_id,
                )
            except GatewayNotConnectedError:
                error_msg = (
                    "Gateway agent is not connected. Cannot reach the local Oryggi system. "
                    "Please ensure the Gateway Agent is running on your server."
                )
                logger.error(f"[{self.name}] {error_msg}")

                audit_logger.log_action_execution(
                    user_id=user_id,
                    user_role=user_role or "UNKNOWN",
                    action_type=f"employee_{action}",
                    tool_name=self.name,
                    success=False,
                    error=error_msg,
                    ecode=ecode,
                    database_id=database_id
                )

                return {
                    "success": False,
                    "error": error_msg,
                    "error_code": "GATEWAY_NOT_CONNECTED",
                    "action_type": "employee_blacklist"
                }
            except GatewayTimeoutError:
                error_msg = (
                    "Request timed out. The local Oryggi system may be unavailable "
                    "or taking too long to respond."
                )
                logger.error(f"[{self.name}] {error_msg}")

                audit_logger.log_action_execution(
                    user_id=user_id,
                    user_role=user_role or "UNKNOWN",
                    action_type=f"employee_{action}",
                    tool_name=self.name,
                    success=False,
                    error=error_msg,
                    ecode=ecode,
                    database_id=database_id
                )

                return {
                    "success": False,
                    "error": error_msg,
                    "error_code": "TIMEOUT",
                    "action_type": "employee_blacklist"
                }

            # Calculate execution time
            execution_time_ms = (time.perf_counter() - start_time) * 1000

            # Process response from gateway agent
            status_code = response.status_code
            response_body = response.body

            # Check if action was successful (2xx status codes)
            if 200 <= status_code < 300:
                success_msg = (
                    f"Employee {ecode}"
                    f"{f' ({employee_name})' if employee_name else ''} "
                    f"has been {action_display} successfully.\n\n"
                    f"Response time: {execution_time_ms:.0f}ms"
                )

                logger.success(
                    f"[{self.name}] {success_msg} "
                    f"(status: {status_code}, time: {execution_time_ms:.2f}ms)"
                )

                audit_logger.log_action_execution(
                    user_id=user_id,
                    user_role=user_role or "UNKNOWN",
                    action_type=f"employee_{action}",
                    tool_name=self.name,
                    success=True,
                    execution_time_ms=execution_time_ms,
                    ecode=ecode,
                    employee_name=employee_name,
                    database_id=database_id,
                    reason=reason
                )

                return {
                    "success": True,
                    "action": action,
                    "ecode": ecode,
                    "employee_name": employee_name,
                    "message": success_msg,
                    "status_code": status_code,
                    "response": response_body,
                    "execution_time_ms": execution_time_ms,
                    "action_type": "employee_blacklist"
                }
            else:
                # API returned error status
                error_detail = ""
                if response_body:
                    if isinstance(response_body, dict):
                        error_detail = response_body.get("message") or response_body.get("error") or str(response_body)
                    else:
                        error_detail = str(response_body)

                error_msg = (
                    f"Failed to {action.replace('_', ' ')} employee {ecode}. "
                    f"API returned status {status_code}"
                    f"{f': {error_detail}' if error_detail else ''}"
                )

                logger.error(f"[{self.name}] {error_msg}")

                audit_logger.log_action_execution(
                    user_id=user_id,
                    user_role=user_role or "UNKNOWN",
                    action_type=f"employee_{action}",
                    tool_name=self.name,
                    success=False,
                    error=error_msg,
                    execution_time_ms=execution_time_ms,
                    ecode=ecode,
                    database_id=database_id,
                    status_code=status_code
                )

                return {
                    "success": False,
                    "error": error_msg,
                    "status_code": status_code,
                    "response": response_body,
                    "action_type": "employee_blacklist"
                }

        except Exception as e:
            execution_time_ms = (time.perf_counter() - start_time) * 1000
            error_msg = f"Unexpected error during {action}: {str(e)}"
            logger.error(f"[{self.name}] {error_msg}", exc_info=True)

            audit_logger.log_action_execution(
                user_id=user_id,
                user_role=user_role or "UNKNOWN",
                action_type=f"employee_{action}",
                tool_name=self.name,
                success=False,
                error=error_msg,
                ecode=ecode if 'ecode' in locals() else None,
                database_id=database_id
            )

            return {
                "success": False,
                "error": error_msg,
                "exception": type(e).__name__,
                "action_type": "employee_blacklist"
            }

    def get_confirmation_message(
        self,
        action: str = "unknown",
        ecode: int = 0,
        employee_name: Optional[str] = None,
        employee_code: Optional[str] = None,
        employee_department: Optional[str] = None,
        employee_designation: Optional[str] = None,
        employee_card_no: Optional[str] = None,
        reason: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Generate human-readable confirmation message

        Args:
            action: "blacklist" or "remove_blacklist"
            ecode: Employee code
            employee_name: Employee's full name
            employee_code: Alternative employee code
            employee_department: Employee's department
            employee_designation: Employee's job title
            employee_card_no: Employee's card number
            reason: Reason for the action

        Returns:
            Formatted confirmation message string
        """
        action = action.lower()

        # Normalize action display
        if action in ["remove_blacklist", "unblacklist", "remove blacklist"]:
            action_display = "Remove from Blacklist"
            header = f"**REMOVE FROM BLACKLIST REQUEST**"
            warning_text = (
                "- This action takes effect IMMEDIATELY\n"
                "- The employee will regain access to Oryggi systems\n"
                "- The employee will be removed from the blacklist"
            )
        else:
            action_display = "Blacklist"
            header = f"**[WARNING] BLACKLIST EMPLOYEE REQUEST**"
            warning_text = (
                "- [WARNING] This action takes effect IMMEDIATELY\n"
                "- The employee will lose access to ALL Oryggi systems\n"
                "- The employee will be added to the blacklist\n"
                "- This is a serious action - please confirm"
            )

        # Build employee details section
        if employee_name:
            employee_section = (
                f"**Employee Details:**\n"
                f"- Name: {employee_name}\n"
                f"- ECode: {employee_code or ecode}\n"
            )
            if employee_department:
                employee_section += f"- Department: {employee_department}\n"
            if employee_designation:
                employee_section += f"- Designation: {employee_designation}\n"
            if employee_card_no:
                employee_section += f"- Card No: {employee_card_no}\n"
        else:
            employee_section = f"**Employee:** ECode {ecode}\n"

        # Build reason section
        reason_section = f"- Reason: {reason}\n" if reason else ""

        return (
            f"{header}\n\n"
            f"{employee_section}\n"
            f"**Action Details:**\n"
            f"- Action: {action_display}\n"
            f"{reason_section}"
            f"{warning_text}\n\n"
            f"Do you want to proceed with {'blacklisting' if 'blacklist' in action and 'remove' not in action else 'removing from blacklist'} this employee?"
        )


# Global tool instance
employee_blacklist_tool = EmployeeBlacklistTool()
