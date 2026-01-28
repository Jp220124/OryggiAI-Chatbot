"""
Employee Terminate Tool - Terminate/Un-terminate Employees via Local Oryggi REST API

This tool enables the chatbot to perform employee termination actions on the
local Oryggi system through the Gateway Agent infrastructure.

Architecture:
    User -> Chatbot (Cloud) -> Gateway Agent (WebSocket) -> Local Oryggi API

Oryggi API Endpoints:
    GET /TerminateEmployee?CorpEmpCode={ecode}&Reason={reason}&LeavingDate={date}&ClientVersion={version}&IPAddress={ip}&OperatorEcode={operator}

For Un-terminate (Reinstate):
    Step 1: GET /deActivateEmployee?CorpEmpCode={ecode}&...
    Step 2: GET /ActivateEmployee?CorpEmpCode={ecode}&...
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


class EmployeeTerminateTool(ChatbotTool):
    """
    Tool for terminating/un-terminating employees via local Oryggi REST API

    Actions are executed through the Gateway Agent which forwards
    REST API calls to the local Oryggi service.

    This is a DESTRUCTIVE action that requires human confirmation.
    Only ADMIN and HR_MANAGER roles can execute this tool.

    Terminate: Permanently disables all access for an employee
    Un-terminate: Reinstates an employee by deactivating then activating

    Example:
        result = await tool.run(
            user_role="ADMIN",
            action="terminate",
            ecode=12345,
            user_id="admin_user",
            database_id="db_123",
            reason="Resignation"
        )
    """

    name = "employee_terminate"
    description = (
        "Terminate or un-terminate (reinstate) an employee in the Oryggi system. "
        "Terminating permanently disables all access for the employee. "
        "Un-terminating reinstates the employee by deactivating then activating them. "
        "Requires employee ECode (ID number). Actions are executed on the local "
        "Oryggi system via the Gateway Agent."
    )
    rbac_required = ["ADMIN", "HR_MANAGER", "OWNER", "owner"]
    destructive = True  # Triggers confirmation workflow

    def __init__(self):
        super().__init__()
        logger.info("EmployeeTerminateTool initialized")

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
        leaving_date: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute employee terminate action via gateway to local Oryggi REST API

        Oryggi API:
            GET /TerminateEmployee?CorpEmpCode={ecode}&Reason={reason}&LeavingDate={date}&...

        For Un-terminate:
            GET /deActivateEmployee then GET /ActivateEmployee

        Args:
            action: Action to perform - "terminate" or "un_terminate" (or "reinstate", "unterminate")
            ecode: Employee code (CorpEmpCode in Oryggi system)
            user_id: Current user ID (invoking user)
            database_id: Database ID to route request to correct gateway agent
            user_role: Current user role
            reason: Reason for termination (required for terminate action)
            employee_name: Optional employee name for logging
            conversation_id: Optional conversation ID for tracking
            operator_ecode: Operator's employee code performing the action (default: 1)
            leaving_date: Date of leaving/termination (default: today)

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
                        "action_type": "employee_terminate"
                    }
                logger.warning(f"[{self.name}] No database_id provided, auto-detected: {database_id}")

            # Validate and normalize action
            action = action.lower().strip()
            # Support multiple ways to say "un-terminate" / "reinstate"
            if action in ["un_terminate", "unterminate", "un-terminate", "reinstate", "un terminate"]:
                action = "un_terminate"
            elif action in ["terminate", "term"]:
                action = "terminate"
            else:
                error_msg = f"Invalid action '{action}'. Must be 'terminate' or 'un_terminate' (reinstate)."
                logger.error(f"[{self.name}] {error_msg}")
                return {
                    "success": False,
                    "error": error_msg,
                    "action_type": "employee_terminate"
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
                    "action_type": "employee_terminate"
                }

            if action == "terminate":
                return await self._execute_terminate(
                    ecode=ecode,
                    user_id=user_id,
                    database_id=database_id,
                    user_role=user_role,
                    reason=reason,
                    employee_name=employee_name,
                    conversation_id=conversation_id,
                    operator_ecode=operator_ecode,
                    leaving_date=leaving_date,
                    start_time=start_time
                )
            else:
                # Un-terminate requires deactivate then activate
                return await self._execute_unterminate(
                    ecode=ecode,
                    user_id=user_id,
                    database_id=database_id,
                    user_role=user_role,
                    employee_name=employee_name,
                    conversation_id=conversation_id,
                    operator_ecode=operator_ecode,
                    start_time=start_time
                )

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
                "action_type": "employee_terminate"
            }

    async def _execute_terminate(
        self,
        ecode: int,
        user_id: str,
        database_id: str,
        user_role: Optional[str],
        reason: Optional[str],
        employee_name: Optional[str],
        conversation_id: Optional[str],
        operator_ecode: int,
        leaving_date: Optional[str],
        start_time: float
    ) -> Dict[str, Any]:
        """Execute the terminate action"""

        # Terminate endpoint
        endpoint = "/TerminateEmployee"

        # Use provided date or today
        if not leaving_date:
            leaving_date = datetime.now().strftime("%Y-%m-%d")

        # Reason is required for termination
        if not reason:
            reason = "Terminated by HR"

        query_params = {
            "CorpEmpCode": str(ecode),
            "Reason": reason,
            "LeavingDate": leaving_date,
            "ClientVersion": ORYGGI_CLIENT_VERSION,
            "IPAddress": ORYGGI_DEFAULT_IP,
            "OperatorEcode": str(operator_ecode)
        }

        logger.info(
            f"[{self.name}] Executing terminate for employee {ecode} "
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
                action_type="employee_terminate",
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
                "action_type": "employee_terminate"
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
                action_type="employee_terminate",
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
                "action_type": "employee_terminate"
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
                f"has been terminated successfully.\n\n"
                f"Response time: {execution_time_ms:.0f}ms"
            )

            logger.success(
                f"[{self.name}] {success_msg} "
                f"(status: {status_code}, time: {execution_time_ms:.2f}ms)"
            )

            audit_logger.log_action_execution(
                user_id=user_id,
                user_role=user_role or "UNKNOWN",
                action_type="employee_terminate",
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
                "action": "terminate",
                "ecode": ecode,
                "employee_name": employee_name,
                "message": success_msg,
                "status_code": status_code,
                "response": response_body,
                "execution_time_ms": execution_time_ms,
                "action_type": "employee_terminate",
                "reason": reason,
                "leaving_date": leaving_date
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
                f"Failed to terminate employee {ecode}. "
                f"API returned status {status_code}"
                f"{f': {error_detail}' if error_detail else ''}"
            )

            logger.error(f"[{self.name}] {error_msg}")

            audit_logger.log_action_execution(
                user_id=user_id,
                user_role=user_role or "UNKNOWN",
                action_type="employee_terminate",
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
                "action_type": "employee_terminate"
            }

    async def _execute_unterminate(
        self,
        ecode: int,
        user_id: str,
        database_id: str,
        user_role: Optional[str],
        employee_name: Optional[str],
        conversation_id: Optional[str],
        operator_ecode: int,
        start_time: float
    ) -> Dict[str, Any]:
        """
        Execute the un-terminate (reinstate) action.

        This is a two-step process:
        1. Deactivate the employee
        2. Activate the employee
        """

        logger.info(
            f"[{self.name}] Executing un-terminate for employee {ecode} "
            f"(database: {database_id}, user: {user_id})"
        )

        # Step 1: Deactivate
        deactivate_endpoint = "/deActivateEmployee"
        deactivate_params = {
            "CorpEmpCode": str(ecode),
            "ClientVersion": ORYGGI_CLIENT_VERSION,
            "IPAddress": ORYGGI_DEFAULT_IP,
            "OperatorEcode": str(operator_ecode)
        }

        logger.info(f"[{self.name}] Step 1: Deactivating employee {ecode}")

        try:
            deactivate_response = await gateway_manager.execute_api_request(
                database_id=database_id,
                method="GET",
                endpoint=deactivate_endpoint,
                query_params=deactivate_params,
                timeout=10,
                user_id=user_id,
                conversation_id=conversation_id,
            )
        except (GatewayNotConnectedError, GatewayTimeoutError) as e:
            error_msg = f"Failed to deactivate employee during un-terminate: {str(e)}"
            logger.error(f"[{self.name}] {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "action_type": "employee_terminate"
            }

        # Check deactivate result
        if not (200 <= deactivate_response.status_code < 300):
            error_msg = f"Deactivate step failed with status {deactivate_response.status_code}"
            logger.error(f"[{self.name}] {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "status_code": deactivate_response.status_code,
                "action_type": "employee_terminate"
            }

        logger.info(f"[{self.name}] Step 1 complete: Employee {ecode} deactivated")

        # Step 2: Activate
        activate_endpoint = "/ActivateEmployee"
        activate_params = {
            "CorpEmpCode": str(ecode),
            "ClientVersion": ORYGGI_CLIENT_VERSION,
            "IPAddress": ORYGGI_DEFAULT_IP,
            "OperatorEcode": str(operator_ecode)
        }

        logger.info(f"[{self.name}] Step 2: Activating employee {ecode}")

        try:
            activate_response = await gateway_manager.execute_api_request(
                database_id=database_id,
                method="GET",
                endpoint=activate_endpoint,
                query_params=activate_params,
                timeout=10,
                user_id=user_id,
                conversation_id=conversation_id,
            )
        except (GatewayNotConnectedError, GatewayTimeoutError) as e:
            error_msg = f"Failed to activate employee during un-terminate: {str(e)}"
            logger.error(f"[{self.name}] {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "action_type": "employee_terminate"
            }

        # Calculate execution time
        execution_time_ms = (time.perf_counter() - start_time) * 1000

        # Check activate result
        if 200 <= activate_response.status_code < 300:
            success_msg = (
                f"Employee {ecode}"
                f"{f' ({employee_name})' if employee_name else ''} "
                f"has been un-terminated (reinstated) successfully.\n\n"
                f"The employee's access has been restored.\n"
                f"Response time: {execution_time_ms:.0f}ms"
            )

            logger.success(
                f"[{self.name}] {success_msg} "
                f"(status: {activate_response.status_code}, time: {execution_time_ms:.2f}ms)"
            )

            audit_logger.log_action_execution(
                user_id=user_id,
                user_role=user_role or "UNKNOWN",
                action_type="employee_un_terminate",
                tool_name=self.name,
                success=True,
                execution_time_ms=execution_time_ms,
                ecode=ecode,
                employee_name=employee_name,
                database_id=database_id
            )

            return {
                "success": True,
                "action": "un_terminate",
                "ecode": ecode,
                "employee_name": employee_name,
                "message": success_msg,
                "status_code": activate_response.status_code,
                "execution_time_ms": execution_time_ms,
                "action_type": "employee_terminate"
            }
        else:
            # Activate step failed
            error_detail = ""
            if activate_response.body:
                if isinstance(activate_response.body, dict):
                    error_detail = activate_response.body.get("message") or str(activate_response.body)
                else:
                    error_detail = str(activate_response.body)

            error_msg = (
                f"Un-terminate failed at activate step. "
                f"API returned status {activate_response.status_code}"
                f"{f': {error_detail}' if error_detail else ''}"
            )

            logger.error(f"[{self.name}] {error_msg}")

            audit_logger.log_action_execution(
                user_id=user_id,
                user_role=user_role or "UNKNOWN",
                action_type="employee_un_terminate",
                tool_name=self.name,
                success=False,
                error=error_msg,
                execution_time_ms=execution_time_ms,
                ecode=ecode,
                database_id=database_id,
                status_code=activate_response.status_code
            )

            return {
                "success": False,
                "error": error_msg,
                "status_code": activate_response.status_code,
                "action_type": "employee_terminate"
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
        leaving_date: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Generate human-readable confirmation message

        Args:
            action: "terminate" or "un_terminate"
            ecode: Employee code
            employee_name: Employee's full name
            employee_code: Alternative employee code
            employee_department: Employee's department
            employee_designation: Employee's job title
            employee_card_no: Employee's card number
            reason: Reason for the action
            leaving_date: Date of leaving/termination

        Returns:
            Formatted confirmation message string
        """
        action = action.lower()

        # Normalize action display
        if action in ["un_terminate", "unterminate", "reinstate", "un-terminate"]:
            action_display = "Un-terminate (Reinstate)"
            header = f"**UN-TERMINATE (REINSTATE) EMPLOYEE REQUEST**"
            warning_text = (
                "- This action takes effect IMMEDIATELY\n"
                "- The employee will be deactivated then activated\n"
                "- The employee's access will be restored\n"
                "- The employee will be removed from terminated status"
            )
        else:
            action_display = "Terminate"
            header = f"**[WARNING] TERMINATE EMPLOYEE REQUEST**"
            warning_text = (
                "- [WARNING] This action takes effect IMMEDIATELY\n"
                "- The employee will be PERMANENTLY marked as terminated\n"
                "- The employee will lose access to ALL Oryggi systems\n"
                "- This is a serious HR action - please confirm"
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
        date_section = f"- Leaving Date: {leaving_date}\n" if leaving_date else ""

        return (
            f"{header}\n\n"
            f"{employee_section}\n"
            f"**Action Details:**\n"
            f"- Action: {action_display}\n"
            f"{reason_section}"
            f"{date_section}"
            f"{warning_text}\n\n"
            f"Do you want to proceed with {'terminating' if action == 'terminate' else 'un-terminating (reinstating)'} this employee?"
        )


# Global tool instance
employee_terminate_tool = EmployeeTerminateTool()
