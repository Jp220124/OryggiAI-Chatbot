"""
Extended Access Control Tools - Phase 6 RBAC-enabled tools
New functionality for: Visitor Registration, Temporary Cards, Database Backup,
Card Enrollment, Employee Enrollment, and Door-Specific Access Management.

All tools require ADMIN role and human confirmation for destructive actions.
"""

from typing import Any, Dict, Optional, List
from datetime import datetime, timedelta
from loguru import logger
import time

from app.tools.base_tool import ChatbotTool
from app.integrations.access_control_extended import extended_access_control_client
from app.services.employee_lookup import employee_lookup_service
from app.models.access_control_extended import (
    VisitorRegistrationRequest, TemporaryCardRequest,
    DatabaseBackupRequest, CardEnrollmentRequest,
    EmployeeEnrollmentRequest, DoorAccessRequest,
    EmployeeCreateUpdateRequest,
    AccessScope, DoorAction, CardType, BackupType
)
from app.middleware.audit_logger import audit_logger


# =============================================================================
# Visitor Registration Tool
# =============================================================================

class VisitorRegistrationTool(ChatbotTool):
    """
    Tool to register a new visitor in the access control system.

    Collects visitor details and creates entry with optional card assignment
    and terminal group access.

    This is a DESTRUCTIVE action that requires human confirmation.
    Only ADMIN users can execute this tool.

    Example:
        result = await tool.run(
            user_role="ADMIN",
            first_name="John",
            last_name="Doe",
            mobile_number="9876543210",
            whom_to_visit="EMP001",
            purpose="Meeting",
            id_proof_type="Aadhar",
            id_proof_detail="1234-5678-9012"
        )
    """

    name = "register_visitor"
    description = "Register a new visitor with details like name, phone, purpose, ID proof, and optional card assignment. Requires confirmation."
    rbac_required = ["ADMIN"]
    destructive = True

    def __init__(self):
        super().__init__()
        logger.info("VisitorRegistrationTool initialized")

    def _run(
        self,
        first_name: str,
        last_name: Optional[str] = None,
        mobile_number: Optional[str] = None,
        whom_to_visit: Optional[str] = None,
        purpose: Optional[str] = None,
        id_proof_type: str = "Other",
        id_proof_detail: str = "",
        expected_in_time: Optional[str] = None,
        expected_out_time: Optional[str] = None,
        issued_card_number: Optional[str] = None,
        terminal_group_id: Optional[int] = None,
        vehicle_number: Optional[str] = None,
        number_of_visitors: int = 1,
        email: Optional[str] = None,
        company: Optional[str] = None,
        address: Optional[str] = None,
        gender: Optional[str] = None,
        visitor_type: Optional[str] = None,
        need_escort: bool = False,
        user_id: Optional[str] = None,
        user_role: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute the visitor registration action using real Oryggi API.

        Args:
            first_name: Visitor's first name (required)
            last_name: Visitor's last name (optional)
            mobile_number: Mobile phone number (optional)
            whom_to_visit: Employee code or name being visited (optional)
            purpose: Purpose of visit (Meeting, Interview, Delivery, etc.)
            id_proof_type: Type of ID (Aadhar, PAN, Passport, DL, VoterID)
            id_proof_detail: ID proof number
            expected_in_time: Expected check-in time (ISO format)
            expected_out_time: Expected check-out time (ISO format)
            issued_card_number: Optional visitor card to assign
            terminal_group_id: Optional zone/terminal group for access
            vehicle_number: Optional vehicle registration
            number_of_visitors: Number of visitors (default: 1)
            email: Visitor's email address (optional)
            company: Visitor's company/organization (optional)
            address: Visitor's address (optional)
            gender: Gender M/F (optional)
            visitor_type: Walk-in or Pre-Booked (optional)
            need_escort: Whether visitor needs escort (optional)
            user_id: Current user ID
            user_role: Current user role

        Returns:
            Dict with success status and visitor details
        """
        start_time = time.time()

        try:
            # Parse datetime fields
            exp_in = datetime.fromisoformat(expected_in_time) if expected_in_time else None
            exp_out = datetime.fromisoformat(expected_out_time) if expected_out_time else None

            # Create request model with new fields
            request = VisitorRegistrationRequest(
                first_name=first_name,
                last_name=last_name,
                mobile_number=mobile_number,
                whom_to_visit=whom_to_visit,
                purpose=purpose,
                id_proof_type=id_proof_type,
                id_proof_detail=id_proof_detail,
                expected_in_time=exp_in,
                expected_out_time=exp_out,
                issued_card_number=issued_card_number,
                terminal_group_id=terminal_group_id,
                vehicle_number=vehicle_number,
                number_of_visitors=number_of_visitors,
                email=email,
                company=company,
                address=address,
                gender=gender,
                visitor_type=visitor_type,
                need_escort=need_escort
            )

            # Execute via Extended API
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    extended_access_control_client.register_visitor(request)
                )
            finally:
                loop.close()

            execution_time_ms = (time.time() - start_time) * 1000

            # Log to audit
            audit_logger.log_action_execution(
                user_id=user_id,
                user_role=user_role or "ADMIN",
                action_type="register_visitor",
                tool_name=self.name,
                success=result.success,
                execution_time_ms=execution_time_ms,
                visitor_name=f"{first_name} {last_name}",
                whom_to_visit=whom_to_visit,
                purpose=purpose
            )

            return {
                "success": result.success,
                "message": result.message,
                "visitor_id": result.visitor_id,
                "visitor_ecode": result.visitor_ecode,
                "details": result.details,
                "action_type": "register_visitor",
                "execution_time_ms": execution_time_ms
            }

        except Exception as e:
            logger.error(f"Visitor registration error: {str(e)}")
            return {
                "success": False,
                "message": f"Error: {str(e)}",
                "error": str(e),
                "action_type": "register_visitor"
            }

    def get_confirmation_message(
        self,
        first_name: str = "",
        last_name: str = "",
        mobile_number: str = "",
        whom_to_visit: str = "",
        purpose: str = "",
        id_proof_type: str = "",
        id_proof_detail: str = "",
        issued_card_number: str = None,
        terminal_group_id: int = None,
        vehicle_number: str = None,
        number_of_visitors: int = 1,
        email: str = None,
        company: str = None,
        **kwargs
    ) -> str:
        """Generate human-readable confirmation message"""
        card_info = f"- Card: {issued_card_number}\n" if issued_card_number else ""
        zone_info = f"- Access Zone: {terminal_group_id}\n" if terminal_group_id else ""
        vehicle_info = f"- Vehicle: {vehicle_number}\n" if vehicle_number else ""
        email_info = f"- Email: {email}\n" if email else ""
        company_info = f"- Company: {company}\n" if company else ""
        mobile_info = f"- Mobile: {mobile_number}\n" if mobile_number else ""

        return (
            f"**VISITOR REGISTRATION REQUEST**\n\n"
            f"**Visitor Details:**\n"
            f"- Name: {first_name} {last_name or ''}\n"
            f"{mobile_info}{email_info}{company_info}"
            f"- ID Proof: {id_proof_type} - {id_proof_detail}\n"
            f"- Number of Visitors: {number_of_visitors}\n"
            f"{vehicle_info}\n"
            f"**Visit Details:**\n"
            f"- Visiting: {whom_to_visit or 'Not specified'}\n"
            f"- Purpose: {purpose or 'Not specified'}\n"
            f"{card_info}{zone_info}\n"
            f"This will register the visitor using the Oryggi Access Control System.\n"
            f"Do you want to proceed with visitor registration?"
        )


# =============================================================================
# Temporary Card Assignment Tool
# =============================================================================

class TemporaryCardTool(ChatbotTool):
    """
    Tool to assign a temporary card to a visitor, contractor, or employee.

    This is a DESTRUCTIVE action that requires human confirmation.
    Only ADMIN users can execute this tool.

    Example:
        result = await tool.run(
            user_role="ADMIN",
            target_user_id="V000001",
            card_number="TEMP-001",
            expiry_datetime="2025-11-26T18:00:00"
        )
    """

    name = "assign_temporary_card"
    description = "Assign a temporary access card to a visitor, contractor, or employee with expiry time. Requires confirmation."
    rbac_required = ["ADMIN"]
    destructive = True

    def __init__(self):
        super().__init__()
        logger.info("TemporaryCardTool initialized")

    def _run(
        self,
        target_user_id: str,
        card_number: str,
        expiry_datetime: str,
        card_type: str = "temporary",
        start_datetime: Optional[str] = None,
        terminal_group_id: Optional[int] = None,
        reason: Optional[str] = None,
        user_id: Optional[str] = None,
        user_role: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute the temporary card assignment action

        Args:
            target_user_id: Visitor ID, contractor code, or employee code
            card_number: Card number to assign
            expiry_datetime: Card expiry time (ISO format)
            card_type: Type of card (visitor, contractor, temporary)
            start_datetime: Optional start time (defaults to now)
            terminal_group_id: Optional zone for access
            reason: Reason for assignment
            user_id: Current user ID
            user_role: Current user role

        Returns:
            Dict with success status and card details
        """
        start_time = time.time()

        try:
            # Parse datetime fields
            expiry = datetime.fromisoformat(expiry_datetime)
            start = datetime.fromisoformat(start_datetime) if start_datetime else None

            # Map card type
            card_type_enum = CardType.TEMPORARY
            if card_type.lower() == "visitor":
                card_type_enum = CardType.VISITOR
            elif card_type.lower() == "contractor":
                card_type_enum = CardType.CONTRACTOR

            # Create request model
            request = TemporaryCardRequest(
                target_user_id=target_user_id,
                card_number=card_number,
                card_type=card_type_enum,
                start_datetime=start,
                expiry_datetime=expiry,
                terminal_group_id=terminal_group_id,
                reason=reason
            )

            # Execute via Extended API
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    extended_access_control_client.assign_temporary_card(request)
                )
            finally:
                loop.close()

            execution_time_ms = (time.time() - start_time) * 1000

            # Log to audit
            audit_logger.log_action_execution(
                user_id=user_id,
                user_role=user_role or "ADMIN",
                action_type="assign_temporary_card",
                tool_name=self.name,
                success=result.success,
                execution_time_ms=execution_time_ms,
                target_user_id=target_user_id,
                card_number=card_number,
                expiry=expiry_datetime
            )

            return {
                "success": result.success,
                "message": result.message,
                "card_number": result.card_number,
                "assigned_to": result.assigned_to,
                "expiry": result.expiry.isoformat() if result.expiry else None,
                "details": result.details,
                "action_type": "assign_temporary_card",
                "execution_time_ms": execution_time_ms
            }

        except Exception as e:
            logger.error(f"Temporary card assignment error: {str(e)}")
            return {
                "success": False,
                "message": f"Error: {str(e)}",
                "error": str(e),
                "action_type": "assign_temporary_card"
            }

    def get_confirmation_message(
        self,
        target_user_id: str = "",
        card_number: str = "",
        expiry_datetime: str = "",
        card_type: str = "temporary",
        terminal_group_id: int = None,
        reason: str = None,
        **kwargs
    ) -> str:
        """Generate human-readable confirmation message"""
        zone_info = f"- Access Zone: {terminal_group_id}\n" if terminal_group_id else ""
        reason_info = f"- Reason: {reason}\n" if reason else ""

        return (
            f"**TEMPORARY CARD ASSIGNMENT**\n\n"
            f"**Assignment Details:**\n"
            f"- User: {target_user_id}\n"
            f"- Card Number: {card_number}\n"
            f"- Card Type: {card_type}\n"
            f"- Expiry: {expiry_datetime}\n"
            f"{zone_info}{reason_info}\n"
            f"Do you want to proceed with card assignment?"
        )


# =============================================================================
# Database Backup Tool
# =============================================================================

class DatabaseBackupTool(ChatbotTool):
    """
    Tool to create a full SQL Server backup of the Oryggi database.

    This is a DESTRUCTIVE action that requires human confirmation.
    Only ADMIN users can execute this tool.

    Example:
        result = await tool.run(
            user_role="ADMIN",
            database_name="Oryggi",
            backup_type="full"
        )
    """

    name = "database_backup"
    description = "Create a full SQL Server backup of the access control database. Requires confirmation."
    rbac_required = ["ADMIN"]
    destructive = True

    def __init__(self):
        super().__init__()
        logger.info("DatabaseBackupTool initialized")

    def _run(
        self,
        database_name: str = "Oryggi",
        backup_path: Optional[str] = None,
        backup_type: str = "full",
        compression: bool = True,
        user_id: Optional[str] = None,
        user_role: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute the database backup action

        Args:
            database_name: Database to backup (default: Oryggi)
            backup_path: Custom backup path (optional)
            backup_type: Type of backup (full, differential, log)
            compression: Whether to compress the backup
            user_id: Current user ID
            user_role: Current user role

        Returns:
            Dict with success status and backup details
        """
        start_time = time.time()

        try:
            # Map backup type
            backup_type_enum = BackupType.FULL
            if backup_type.lower() == "differential":
                backup_type_enum = BackupType.DIFFERENTIAL
            elif backup_type.lower() == "log":
                backup_type_enum = BackupType.LOG

            # Create request model
            request = DatabaseBackupRequest(
                database_name=database_name,
                backup_path=backup_path,
                backup_type=backup_type_enum,
                compression=compression
            )

            # Execute via Extended API
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    extended_access_control_client.backup_database(request)
                )
            finally:
                loop.close()

            execution_time_ms = (time.time() - start_time) * 1000

            # Log to audit
            audit_logger.log_action_execution(
                user_id=user_id,
                user_role=user_role or "ADMIN",
                action_type="database_backup",
                tool_name=self.name,
                success=result.success,
                execution_time_ms=execution_time_ms,
                database_name=database_name,
                backup_type=backup_type,
                backup_file=result.backup_file_path
            )

            return {
                "success": result.success,
                "message": result.message,
                "backup_file_path": result.backup_file_path,
                "backup_size_mb": result.backup_size_mb,
                "backup_duration_seconds": result.backup_duration_seconds,
                "details": result.details,
                "action_type": "database_backup",
                "execution_time_ms": execution_time_ms
            }

        except Exception as e:
            logger.error(f"Database backup error: {str(e)}")
            return {
                "success": False,
                "message": f"Error: {str(e)}",
                "error": str(e),
                "action_type": "database_backup"
            }

    def get_confirmation_message(
        self,
        database_name: str = "Oryggi",
        backup_path: str = None,
        backup_type: str = "full",
        compression: bool = True,
        **kwargs
    ) -> str:
        """Generate human-readable confirmation message"""
        path_info = f"- Path: {backup_path}\n" if backup_path else "- Path: Default location\n"

        return (
            f"**DATABASE BACKUP REQUEST**\n\n"
            f"**Backup Details:**\n"
            f"- Database: {database_name}\n"
            f"- Type: {backup_type.upper()}\n"
            f"{path_info}"
            f"- Compression: {'Yes' if compression else 'No'}\n\n"
            f"This operation may take several minutes.\n"
            f"Do you want to proceed with the database backup?"
        )


# =============================================================================
# Card Enrollment Tool
# =============================================================================

class CardEnrollmentTool(ChatbotTool):
    """
    Tool to enroll a card for an employee with access to specific doors or all doors.

    This is a DESTRUCTIVE action that requires human confirmation.
    Only ADMIN users can execute this tool.

    Example (specific doors):
        result = await tool.run(
            user_role="ADMIN",
            employee_id="EMP001",
            card_number="CARD-12345",
            access_scope="specific_doors",
            door_ids=[1, 2, 3]
        )

    Example (all doors):
        result = await tool.run(
            user_role="ADMIN",
            employee_id="EMP001",
            card_number="CARD-12345",
            access_scope="all_doors"
        )
    """

    name = "enroll_card"
    description = "Enroll an access card for an employee with access to specific doors or all doors. Requires confirmation."
    rbac_required = ["ADMIN"]
    destructive = True

    def __init__(self):
        super().__init__()
        logger.info("CardEnrollmentTool initialized")

    def _run(
        self,
        employee_id: str,
        card_number: str,
        access_scope: str = "card_only",
        door_ids: Optional[List[int]] = None,
        door_names: Optional[List[str]] = None,
        terminal_group_id: Optional[int] = None,
        start_date: Optional[str] = None,
        expiry_date: Optional[str] = None,
        schedule_id: int = 63,
        authentication_type: int = 1001,
        sync_to_terminals: bool = True,
        user_id: Optional[str] = None,
        user_role: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute the card enrollment action

        Args:
            employee_id: Employee code or name
            card_number: Card number to enroll
            access_scope: 'card_only' (just assign card), 'all_doors' or 'specific_doors'
            door_ids: List of terminal IDs (for specific_doors)
            door_names: List of door names (alternative to door_ids)
            terminal_group_id: Zone ID for zone-based access
            start_date: Access start date (ISO format)
            expiry_date: Access expiry date (ISO format)
            schedule_id: Schedule ID (63=all access, 0=no access)
            authentication_type: Auth type (1001=card, 2=fingerprint, 5=face)
            sync_to_terminals: Whether to sync card to terminals
            user_id: Current user ID
            user_role: Current user role

        Returns:
            Dict with success status and enrollment details
        """
        start_time = time.time()

        try:
            # Determine if this is a simple card enrollment
            # Use card_only mode if:
            # 1. access_scope is "card_only"
            # 2. access_scope is empty/None
            # 3. access_scope is "specific_doors" but no doors are specified
            scope_lower = access_scope.lower() if access_scope else "card_only"

            # Determine enrollment type based on access scope
            # Simple enrollment: card_only OR no scope OR specific_doors with no doors specified
            is_simple_enrollment = (
                scope_lower == "card_only" or
                not access_scope or
                (scope_lower == "specific_doors" and not door_ids and not door_names)
            )

            # Simple card enrollment (just assign card to employee)
            if is_simple_enrollment:
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(
                        extended_access_control_client.enroll_card(
                            corp_emp_code=employee_id,
                            card_number=card_number,
                            card_type="permanent",
                            sync_to_terminals=sync_to_terminals
                        )
                    )
                finally:
                    loop.close()

                execution_time_ms = (time.time() - start_time) * 1000

                # Log to audit
                audit_logger.log_action_execution(
                    user_id=user_id,
                    user_role=user_role or "ADMIN",
                    action_type="enroll_card",
                    tool_name=self.name,
                    success=result.get("success", False),
                    execution_time_ms=execution_time_ms,
                    employee_id=employee_id,
                    card_number=card_number,
                    access_scope="card_only"
                )

                return {
                    "success": result.get("success", False),
                    "message": result.get("message", "Card enrolled"),
                    "card_number": result.get("card_number"),
                    "employee_id": employee_id,
                    "employee_ecode": result.get("ecode"),
                    "old_card": result.get("old_card"),
                    "verified": result.get("verified", False),
                    "details": result,
                    "action_type": "enroll_card",
                    "execution_time_ms": execution_time_ms
                }

            # Full card enrollment with door access
            scope_enum = AccessScope.ALL_DOORS if access_scope.lower() == "all_doors" else AccessScope.SPECIFIC_DOORS

            # Parse datetime fields
            start = datetime.fromisoformat(start_date) if start_date else None
            expiry = datetime.fromisoformat(expiry_date) if expiry_date else None

            # Create request model
            request = CardEnrollmentRequest(
                employee_id=employee_id,
                card_number=card_number,
                access_scope=scope_enum,
                door_ids=door_ids,
                door_names=door_names,
                terminal_group_id=terminal_group_id,
                start_date=start,
                expiry_date=expiry,
                schedule_id=schedule_id,
                authentication_type=authentication_type
            )

            # Execute via Extended API - using the original method for door access
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    extended_access_control_client.enroll_card_with_access(request)
                )
            finally:
                loop.close()

            execution_time_ms = (time.time() - start_time) * 1000

            # Log to audit
            audit_logger.log_action_execution(
                user_id=user_id,
                user_role=user_role or "ADMIN",
                action_type="enroll_card",
                tool_name=self.name,
                success=result.success,
                execution_time_ms=execution_time_ms,
                employee_id=employee_id,
                card_number=card_number,
                access_scope=access_scope,
                doors_configured=result.doors_configured
            )

            return {
                "success": result.success,
                "message": result.message,
                "card_number": result.card_number,
                "employee_id": result.employee_id,
                "employee_ecode": result.employee_ecode,
                "doors_configured": result.doors_configured,
                "failed_doors": result.failed_doors,
                "details": result.details,
                "action_type": "enroll_card",
                "execution_time_ms": execution_time_ms
            }

        except Exception as e:
            logger.error(f"Card enrollment error: {str(e)}")
            return {
                "success": False,
                "message": f"Error: {str(e)}",
                "error": str(e),
                "action_type": "enroll_card"
            }

    def get_confirmation_message(
        self,
        employee_id: str = "",
        card_number: str = "",
        access_scope: str = "card_only",
        door_ids: List[int] = None,
        door_names: List[str] = None,
        schedule_id: int = 63,
        **kwargs
    ) -> str:
        """Generate human-readable confirmation message"""
        scope_lower = access_scope.lower() if access_scope else "card_only"

        if scope_lower == "card_only":
            doors_info = "- Mode: Card assignment only (no door access changes)\n"
        elif scope_lower == "all_doors":
            doors_info = "- Access: ALL DOORS (Full building access)\n"
        else:
            if door_ids:
                doors_info = f"- Door IDs: {', '.join(map(str, door_ids))}\n"
            elif door_names:
                doors_info = f"- Doors: {', '.join(door_names)}\n"
            else:
                doors_info = "- Doors: Not specified\n"

        schedule_info = "Full access (24/7)" if schedule_id == 63 else f"Schedule ID: {schedule_id}"

        # Don't show schedule for card_only
        schedule_line = "" if scope_lower == "card_only" else f"- Schedule: {schedule_info}\n"

        return (
            f"**CARD ENROLLMENT REQUEST**\n\n"
            f"**Enrollment Details:**\n"
            f"- Employee: {employee_id}\n"
            f"- Card Number: {card_number}\n"
            f"{doors_info}"
            f"{schedule_line}\n"
            f"Do you want to proceed with card enrollment?"
        )


# =============================================================================
# Employee Enrollment Tool
# =============================================================================

class EmployeeEnrollmentTool(ChatbotTool):
    """
    Tool to enroll a new employee in the access control system.

    This is a DESTRUCTIVE action that requires human confirmation.
    Only ADMIN users can execute this tool.

    Example:
        result = await tool.run(
            user_role="ADMIN",
            corp_emp_code="EMP001",
            emp_name="John Doe",
            department_code="IT",
            email="john.doe@company.com"
        )
    """

    name = "enroll_employee"
    description = "Enroll a new employee in the access control system with optional card assignment. Requires confirmation."
    rbac_required = ["ADMIN"]
    destructive = True

    def __init__(self):
        super().__init__()
        logger.info("EmployeeEnrollmentTool initialized")

    def _run(
        self,
        corp_emp_code: str,
        emp_name: str,
        department_code: Optional[str] = None,
        designation_code: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        join_date: Optional[str] = None,
        gender: Optional[str] = None,
        active: bool = True,
        card_number: Optional[str] = None,
        authentication_type: Optional[int] = 1001,
        setup_default_access: bool = True,
        terminal_group_id: Optional[int] = None,
        schedule_id: int = 63,
        user_id: Optional[str] = None,
        user_role: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute the employee enrollment action

        Args:
            corp_emp_code: Employee code (must be unique)
            emp_name: Employee full name
            department_code: Department code
            designation_code: Designation code
            email: Email address
            phone: Phone number
            join_date: Join date (ISO format)
            gender: Gender (M/F)
            active: Active status
            card_number: Optional card to assign
            authentication_type: Auth type (1001=card, 2=fingerprint, 5=face, 3=card+fingerprint, 6=card+face)
            setup_default_access: If True, sets up default door access after enrollment
            terminal_group_id: Terminal group ID for access (default: all terminals)
            schedule_id: Access schedule ID (63=all access, 0=no access)
            user_id: Current user ID
            user_role: Current user role

        Returns:
            Dict with success status and employee details
        """
        start_time = time.time()

        try:
            # Parse datetime field
            join_dt = datetime.fromisoformat(join_date) if join_date else None

            # Create request model
            request = EmployeeEnrollmentRequest(
                corp_emp_code=corp_emp_code,
                emp_name=emp_name,
                department_code=department_code,
                designation_code=designation_code,
                email=email,
                phone=phone,
                join_date=join_dt,
                gender=gender,
                active=active,
                card_number=card_number,
                authentication_type=authentication_type,
                setup_default_access=setup_default_access,
                terminal_group_id=terminal_group_id,
                schedule_id=schedule_id
            )

            # Execute via Extended API
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    extended_access_control_client.enroll_employee(request)
                )
            finally:
                loop.close()

            execution_time_ms = (time.time() - start_time) * 1000

            # Log to audit
            audit_logger.log_action_execution(
                user_id=user_id,
                user_role=user_role or "ADMIN",
                action_type="enroll_employee",
                tool_name=self.name,
                success=result.success,
                execution_time_ms=execution_time_ms,
                employee_code=corp_emp_code,
                employee_name=emp_name,
                department=department_code
            )

            return {
                "success": result.success,
                "message": result.message,
                "ecode": result.ecode,
                "corp_emp_code": result.corp_emp_code,
                "card_enrolled": result.card_enrolled,
                "details": result.details,
                "action_type": "enroll_employee",
                "execution_time_ms": execution_time_ms
            }

        except Exception as e:
            logger.error(f"Employee enrollment error: {str(e)}")
            return {
                "success": False,
                "message": f"Error: {str(e)}",
                "error": str(e),
                "action_type": "enroll_employee"
            }

    def get_confirmation_message(
        self,
        corp_emp_code: str = "",
        emp_name: str = "",
        department_code: str = None,
        designation_code: str = None,
        email: str = None,
        phone: str = None,
        card_number: str = None,
        authentication_type: int = 1001,
        setup_default_access: bool = True,
        **kwargs
    ) -> str:
        """Generate human-readable confirmation message"""
        # Authentication type display names
        auth_type_names = {
            1001: "Card Only",
            2: "Fingerprint Only",
            5: "Face Recognition Only",
            3: "Card + Fingerprint",
            6: "Card + Face"
        }
        auth_name = auth_type_names.get(authentication_type, f"Type {authentication_type}")

        dept_info = f"- Department: {department_code}\n" if department_code else ""
        des_info = f"- Designation: {designation_code}\n" if designation_code else ""
        email_info = f"- Email: {email}\n" if email else ""
        phone_info = f"- Phone: {phone}\n" if phone else ""
        card_info = f"- Card: {card_number}\n" if card_number else ""
        auth_info = f"- Authentication: {auth_name}\n"
        access_info = f"- Default Access Setup: {'Yes' if setup_default_access else 'No'}\n"

        return (
            f"**EMPLOYEE ENROLLMENT REQUEST**\n\n"
            f"**Employee Details:**\n"
            f"- Code: {corp_emp_code}\n"
            f"- Name: {emp_name}\n"
            f"{dept_info}{des_info}{email_info}{phone_info}{card_info}{auth_info}{access_info}\n"
            f"Do you want to proceed with employee enrollment?"
        )


# =============================================================================
# Door Access Management Tool
# =============================================================================

class DoorAccessTool(ChatbotTool):
    """
    Tool to grant or block access to specific doors for an employee.

    This is a DESTRUCTIVE action that requires human confirmation.
    Only ADMIN users can execute this tool.

    Example (grant):
        result = await tool.run(
            user_role="ADMIN",
            employee_id="EMP001",
            action="grant",
            door_ids=[1, 2, 3]
        )

    Example (block):
        result = await tool.run(
            user_role="ADMIN",
            employee_id="EMP001",
            action="block",
            door_names=["Main Entrance", "Server Room"]
        )
    """

    name = "manage_door_access"
    description = "Grant or block access to specific doors for an employee. Supports door IDs or names. Requires confirmation."
    rbac_required = ["ADMIN"]
    destructive = True

    def __init__(self):
        super().__init__()
        logger.info("DoorAccessTool initialized")

    def _run(
        self,
        employee_id: str,
        action: str,
        door_ids: Optional[List[int]] = None,
        door_names: Optional[List[str]] = None,
        schedule_id: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        reason: Optional[str] = None,
        user_id: Optional[str] = None,
        user_role: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute the door access management action

        Args:
            employee_id: Employee code or name
            action: 'grant' or 'block'
            door_ids: List of terminal IDs
            door_names: List of door names (alternative to door_ids)
            schedule_id: Schedule ID for access timing
            start_date: Access start date (ISO format)
            end_date: Access end date (ISO format)
            reason: Reason for action
            user_id: Current user ID
            user_role: Current user role

        Returns:
            Dict with success status and affected doors
        """
        start_time = time.time()

        try:
            # Map action
            action_enum = DoorAction.GRANT if action.lower() == "grant" else DoorAction.BLOCK

            # Parse datetime fields
            start = datetime.fromisoformat(start_date) if start_date else None
            end = datetime.fromisoformat(end_date) if end_date else None

            # Create request model
            request = DoorAccessRequest(
                employee_id=employee_id,
                action=action_enum,
                door_ids=door_ids,
                door_names=door_names,
                schedule_id=schedule_id,
                start_date=start,
                end_date=end,
                reason=reason
            )

            # Execute via Extended API
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    extended_access_control_client.manage_door_access(request)
                )
            finally:
                loop.close()

            execution_time_ms = (time.time() - start_time) * 1000

            # Log to audit
            audit_logger.log_action_execution(
                user_id=user_id,
                user_role=user_role or "ADMIN",
                action_type="manage_door_access",
                tool_name=self.name,
                success=result.success,
                execution_time_ms=execution_time_ms,
                employee_id=employee_id,
                action=action,
                doors_affected=result.doors_affected,
                reason=reason
            )

            return {
                "success": result.success,
                "message": result.message,
                "employee_id": result.employee_id,
                "employee_ecode": result.employee_ecode,
                "action": result.action,
                "doors_affected": result.doors_affected,
                "failed_doors": result.failed_doors,
                "details": result.details,
                "action_type": "manage_door_access",
                "execution_time_ms": execution_time_ms
            }

        except Exception as e:
            logger.error(f"Door access management error: {str(e)}")
            return {
                "success": False,
                "message": f"Error: {str(e)}",
                "error": str(e),
                "action_type": "manage_door_access"
            }

    def get_confirmation_message(
        self,
        employee_id: str = "",
        action: str = "grant",
        door_ids: List[int] = None,
        door_names: List[str] = None,
        reason: str = None,
        **kwargs
    ) -> str:
        """Generate human-readable confirmation message"""
        if door_ids:
            doors_info = f"- Door IDs: {', '.join(map(str, door_ids))}\n"
        elif door_names:
            doors_info = f"- Doors: {', '.join(door_names)}\n"
        else:
            doors_info = "- Doors: Not specified\n"

        reason_info = f"- Reason: {reason}\n" if reason else ""
        action_upper = action.upper()
        warning = "\n- This action takes effect IMMEDIATELY" if action.lower() == "block" else ""

        return (
            f"**DOOR ACCESS {action_upper} REQUEST**\n\n"
            f"**Action Details:**\n"
            f"- Employee: {employee_id}\n"
            f"- Action: {action_upper}\n"
            f"{doors_info}{reason_info}{warning}\n\n"
            f"Do you want to proceed with {action.lower()}ing access?"
        )


# =============================================================================
# Employee Management Tool (Create/Update using Frontend API)
# =============================================================================

class EmployeeManagementTool(ChatbotTool):
    """
    Tool to create or update employees in the access control system.

    Uses the UpdateEmployeeWithLog API - the same API used by Oryggi Manager Web frontend.
    This is the recommended tool for employee management operations.

    Supports:
    - Creating new employees
    - Updating existing employees
    - Optional card assignment
    - Department/designation by name or code

    This is a DESTRUCTIVE action that requires human confirmation.
    Only ADMIN users can execute this tool.

    Example (create):
        result = await tool.run(
            user_role="ADMIN",
            corp_emp_code="EMP002",
            emp_name="Jane Smith",
            department_name="IT",
            designation_name="Developer",
            email="jane.smith@company.com",
            phone="1234567890",
            card_number="CARD-002"
        )

    Example (update):
        result = await tool.run(
            user_role="ADMIN",
            corp_emp_code="EMP002",
            emp_name="Jane Smith-Johnson",
            is_update=True,
            email="jane.johnson@company.com"
        )
    """

    name = "manage_employee"
    description = "Create or update an employee in the access control system. Supports creating new employees with card assignment and updating existing employee details. Uses the same API as Oryggi Manager Web. Requires confirmation."
    rbac_required = ["ADMIN"]
    destructive = True

    def __init__(self):
        super().__init__()
        logger.info("EmployeeManagementTool initialized")

    def _run(
        self,
        corp_emp_code: str,
        emp_name: str,
        is_update: bool = False,
        ecode: Optional[int] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        mobile: Optional[str] = None,
        gender: Optional[str] = None,
        department_code: Optional[int] = None,
        department_name: Optional[str] = None,
        designation_code: Optional[int] = None,
        designation_name: Optional[str] = None,
        company_code: Optional[int] = None,
        branch_code: Optional[int] = None,
        section_code: Optional[int] = None,
        category_code: Optional[int] = None,
        grade_code: Optional[int] = None,
        card_number: Optional[str] = None,
        user_group_id: Optional[int] = None,
        role_id: Optional[int] = None,
        join_date: Optional[str] = None,
        start_date: Optional[str] = None,
        expiry_date: Optional[str] = None,
        active: bool = True,
        status_id: int = 1,
        address: Optional[str] = None,
        image: Optional[str] = None,
        user_id: Optional[str] = None,
        user_role: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute the employee create/update action using the frontend API pattern.

        Args:
            corp_emp_code: Employee code (must be unique for create)
            emp_name: Employee full name
            is_update: True for update operation, False for create (default: False)
            ecode: Employee Ecode (required for update if corp_emp_code not unique)
            first_name: First name (optional, extracted from emp_name if not provided)
            last_name: Last name (optional)
            email: Email address
            phone: Phone number
            mobile: Mobile number
            gender: Gender (M/F)
            department_code: Department code (int)
            department_name: Department name (used if code not provided)
            designation_code: Designation code (int)
            designation_name: Designation name (used if code not provided)
            company_code: Company code (default: 1)
            branch_code: Branch code (default: 1)
            section_code: Section code
            category_code: Category code
            grade_code: Grade code
            card_number: Access card number to assign
            user_group_id: User group ID (default: 2 for Employee)
            role_id: Role ID
            join_date: Join date (ISO format)
            start_date: Access start date (ISO format)
            expiry_date: Access expiry date (ISO format)
            active: Active status (default: True)
            status_id: Status ID (default: 1)
            address: Address
            image: Base64 encoded profile image
            user_id: Current user ID
            user_role: Current user role

        Returns:
            Dict with success status and employee details
        """
        start_time = time.time()

        try:
            # Parse datetime fields
            join_dt = datetime.fromisoformat(join_date) if join_date else None
            start_dt = datetime.fromisoformat(start_date) if start_date else None
            expiry_dt = datetime.fromisoformat(expiry_date) if expiry_date else None

            # Create request model
            request = EmployeeCreateUpdateRequest(
                corp_emp_code=corp_emp_code,
                emp_name=emp_name,
                is_update=is_update,
                ecode=ecode,
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=phone,
                mobile=mobile,
                gender=gender,
                department_code=department_code,
                department_name=department_name,
                designation_code=designation_code,
                designation_name=designation_name,
                company_code=company_code,
                branch_code=branch_code,
                section_code=section_code,
                category_code=category_code,
                grade_code=grade_code,
                card_number=card_number,
                user_group_id=user_group_id,
                role_id=role_id,
                join_date=join_dt,
                start_date=start_dt,
                expiry_date=expiry_dt,
                active=active,
                status_id=status_id,
                address=address,
                image=image
            )

            # Execute via Extended API
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    extended_access_control_client.create_or_update_employee(request)
                )
            finally:
                loop.close()

            execution_time_ms = (time.time() - start_time) * 1000

            # Log to audit
            audit_logger.log_action_execution(
                user_id=user_id,
                user_role=user_role or "ADMIN",
                action_type="manage_employee",
                tool_name=self.name,
                success=result.success,
                execution_time_ms=execution_time_ms,
                employee_code=corp_emp_code,
                employee_name=emp_name,
                operation=result.operation,
                department=department_name or department_code
            )

            return {
                "success": result.success,
                "message": result.message,
                "operation": result.operation,
                "ecode": result.ecode,
                "corp_emp_code": result.corp_emp_code,
                "emp_name": result.emp_name,
                "card_enrolled": result.card_enrolled,
                "access_granted": result.access_granted,
                "details": result.details,
                "action_type": "manage_employee",
                "execution_time_ms": execution_time_ms
            }

        except Exception as e:
            logger.error(f"Employee management error: {str(e)}")
            return {
                "success": False,
                "message": f"Error: {str(e)}",
                "error": str(e),
                "action_type": "manage_employee"
            }

    def get_confirmation_message(
        self,
        corp_emp_code: str = "",
        emp_name: str = "",
        is_update: bool = False,
        department_code: int = None,
        department_name: str = None,
        designation_code: int = None,
        designation_name: str = None,
        email: str = None,
        phone: str = None,
        card_number: str = None,
        **kwargs
    ) -> str:
        """Generate human-readable confirmation message"""
        operation = "UPDATE" if is_update else "CREATE"

        dept_info = ""
        if department_name:
            dept_info = f"- Department: {department_name}\n"
        elif department_code:
            dept_info = f"- Department Code: {department_code}\n"

        des_info = ""
        if designation_name:
            des_info = f"- Designation: {designation_name}\n"
        elif designation_code:
            des_info = f"- Designation Code: {designation_code}\n"

        email_info = f"- Email: {email}\n" if email else ""
        phone_info = f"- Phone: {phone}\n" if phone else ""
        card_info = f"- Card Number: {card_number}\n" if card_number else ""

        if is_update:
            action_desc = "This will UPDATE the existing employee record."
        else:
            action_desc = "This will CREATE a new employee in the access control system."

        return (
            f"**EMPLOYEE {operation} REQUEST**\n\n"
            f"**Employee Details:**\n"
            f"- Employee Code: {corp_emp_code}\n"
            f"- Name: {emp_name}\n"
            f"{dept_info}{des_info}{email_info}{phone_info}{card_info}\n"
            f"{action_desc}\n\n"
            f"Do you want to proceed with this {operation.lower()} operation?"
        )


# =============================================================================
# Authentication Management Tool
# =============================================================================

class AuthenticationManagementTool(ChatbotTool):
    """
    Tool to manage authentication methods for existing employees.

    This tool allows adding or removing authentication types (card, fingerprint, face)
    for employees who are already in the system.

    IMPORTANT: For biometric auth types (Face, Fusion, Palm, etc.), the employee must
    have biometrics enrolled FIRST via the Oryggi Manager dashboard before setting
    the authentication type. The tool will check for enrolled biometrics and return
    a helpful error if they're not enrolled.

    Common Authentication Types (use authentication_type_name for these):
    - "Card Only": Card-based access
    - "Face Only": Face recognition only
    - "Fusion": Multiple biometric methods (face + palm typically)
    - "Card + Face": Card and face combined
    - "Card + Finger": Card and fingerprint combined

    This is a DESTRUCTIVE action that requires human confirmation.
    Only ADMIN users can execute this tool.

    Example (add Fusion by name - recommended):
        result = await tool.run(
            user_role="ADMIN",
            employee_id="EMP001",
            action="add",
            authentication_type_name="Fusion"  # Uses name lookup
        )

    Example (add by ID):
        result = await tool.run(
            user_role="ADMIN",
            employee_id="EMP001",
            action="add",
            authentication_type=13  # Fusion ID
        )

    Example (remove card):
        result = await tool.run(
            user_role="ADMIN",
            employee_id="EMP001",
            action="remove",
            authentication_type_name="Card Only"
        )
    """

    name = "manage_authentication"
    description = "Add or remove authentication methods (card, fingerprint, face, fusion) for existing employees. Supports auth type names like 'Fusion', 'Face Only', 'Card Only'. For biometric types, employee must have biometrics enrolled first. Requires confirmation."
    rbac_required = ["ADMIN"]
    destructive = True

    # Common authentication type display names (for reference, actual names come from API)
    AUTH_TYPE_NAMES = {
        1001: "Card Only",
        2: "Fingerprint Only",
        5: "Face Recognition Only",
        3: "Card + Fingerprint",
        6: "Card + Face",
        13: "Fusion"
    }

    def __init__(self):
        super().__init__()
        logger.info("AuthenticationManagementTool initialized")

    def _run(
        self,
        employee_id: str,
        action: str,
        authentication_type: Optional[int] = None,
        authentication_type_name: Optional[str] = None,
        terminal_ids: Optional[List[int]] = None,
        terminal_group_id: Optional[int] = None,
        schedule_id: int = 63,
        check_biometrics: bool = True,
        user_id: Optional[str] = None,
        user_role: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute the authentication management action.

        Args:
            employee_id: Employee code or name
            action: 'add' or 'remove'
            authentication_type: Auth type ID (e.g., 13=Fusion, 5=Face Only, 1001=Card Only)
            authentication_type_name: Auth type name (e.g., "Fusion", "Face Only", "Card Only")
                                     Recommended to use this instead of authentication_type ID.
            terminal_ids: Specific terminal IDs (optional, defaults to all terminals)
            terminal_group_id: Terminal group ID (optional, overrides terminal_ids)
            schedule_id: Schedule ID for access (63=all access)
            check_biometrics: If True, check if biometrics are enrolled before setting biometric auth
            user_id: Current user ID
            user_role: Current user role

        Returns:
            Dict with success status and details
        """
        start_time = time.time()

        # Validate that at least one auth type identifier is provided
        if not authentication_type and not authentication_type_name:
            return {
                "success": False,
                "message": "Please specify authentication_type_name (e.g., 'Fusion', 'Face Only', 'Card Only') or authentication_type (ID).",
                "action_type": "manage_authentication"
            }

        try:
            # Look up employee ecode
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                # Get employee ecode
                ecode = loop.run_until_complete(
                    extended_access_control_client._get_ecode_from_employee_id(employee_id)
                )

                if not ecode:
                    return {
                        "success": False,
                        "message": f"Employee '{employee_id}' not found",
                        "action_type": "manage_authentication"
                    }

                # Execute the appropriate action
                if action.lower() == "add":
                    result = loop.run_until_complete(
                        extended_access_control_client.add_authentication_for_employee(
                            ecode=ecode,
                            authentication_type=authentication_type,
                            authentication_type_name=authentication_type_name,
                            terminal_ids=terminal_ids,
                            terminal_group_id=terminal_group_id,
                            schedule_id=schedule_id,
                            check_biometrics=check_biometrics
                        )
                    )
                elif action.lower() == "remove":
                    # For remove, we need to resolve the auth type name to ID first if only name provided
                    auth_type_for_remove = authentication_type
                    if authentication_type_name and not authentication_type:
                        auth_type_for_remove = loop.run_until_complete(
                            extended_access_control_client.get_auth_type_id_by_name(authentication_type_name)
                        )
                        if not auth_type_for_remove:
                            return {
                                "success": False,
                                "message": f"Authentication type '{authentication_type_name}' not found.",
                                "action_type": "manage_authentication"
                            }

                    result = loop.run_until_complete(
                        extended_access_control_client.remove_authentication_for_employee(
                            ecode=ecode,
                            authentication_type=auth_type_for_remove,
                            terminal_ids=terminal_ids
                        )
                    )
                else:
                    return {
                        "success": False,
                        "message": f"Invalid action '{action}'. Use 'add' or 'remove'.",
                        "action_type": "manage_authentication"
                    }

            finally:
                loop.close()

            execution_time_ms = (time.time() - start_time) * 1000

            # Get auth display name from result or lookup
            auth_name = result.get("authentication_name") or authentication_type_name or self.AUTH_TYPE_NAMES.get(authentication_type, f"Type {authentication_type}")
            auth_type_id = result.get("authentication_type") or authentication_type

            # Log to audit
            audit_logger.log_action_execution(
                user_id=user_id,
                user_role=user_role or "ADMIN",
                action_type="manage_authentication",
                tool_name=self.name,
                success=result.get("success", False),
                execution_time_ms=execution_time_ms,
                employee_id=employee_id,
                action=action,
                authentication_type=auth_name
            )

            return {
                "success": result.get("success", False),
                "message": result.get("message", ""),
                "employee_id": employee_id,
                "employee_ecode": ecode,
                "action": action,
                "authentication_type": auth_type_id,
                "authentication_name": auth_name,
                "terminals_affected": result.get("terminals_configured") or result.get("terminals_removed", 0),
                "failed_terminals": result.get("failed_terminals", []),
                "biometrics_status": result.get("biometrics_status"),
                "action_type": "manage_authentication",
                "execution_time_ms": execution_time_ms
            }

        except Exception as e:
            logger.error(f"Authentication management error: {str(e)}")
            return {
                "success": False,
                "message": f"Error: {str(e)}",
                "error": str(e),
                "action_type": "manage_authentication"
            }

    def get_confirmation_message(
        self,
        employee_id: str = "",
        action: str = "add",
        authentication_type: Optional[int] = None,
        authentication_type_name: Optional[str] = None,
        check_biometrics: bool = True,
        **kwargs
    ) -> str:
        """Generate human-readable confirmation message"""
        # Determine display name for auth type
        if authentication_type_name:
            auth_name = authentication_type_name
        elif authentication_type:
            auth_name = self.AUTH_TYPE_NAMES.get(authentication_type, f"Type {authentication_type}")
        else:
            auth_name = "Not specified"

        action_upper = action.upper()
        action_verb = "adding" if action.lower() == "add" else "removing"

        # Warning for remove action
        warning = ""
        if action.lower() == "remove":
            warning = "\n**WARNING:** Removing authentication may lock the employee out of secured areas!"

        # Note about biometric check for add action with biometric types
        biometric_note = ""
        if action.lower() == "add" and check_biometrics:
            biometric_keywords = ["face", "fusion", "finger", "palm", "iris"]
            auth_lower = auth_name.lower() if auth_name else ""
            if any(kw in auth_lower for kw in biometric_keywords):
                biometric_note = "\n**Note:** Biometrics must be enrolled first for this authentication type."

        return (
            f"**AUTHENTICATION {action_upper} REQUEST**\n\n"
            f"**Details:**\n"
            f"- Employee: {employee_id}\n"
            f"- Action: {action_upper}\n"
            f"- Authentication Type: {auth_name}\n"
            f"{warning}{biometric_note}\n\n"
            f"Do you want to proceed with {action_verb} {auth_name} authentication?"
        )


# =============================================================================
# Biometric Enrollment Tool
# =============================================================================

class BiometricEnrollmentTool(ChatbotTool):
    """
    Tool for triggering biometric enrollment mode on devices.

    This tool sends commands to biometric devices to enter enrollment mode,
    allowing employees to register their face, palm, or fingerprint directly
    at the device.

    Supported biometric types:
    - "face": Face recognition enrollment
    - "palm": Palm print enrollment
    - "finger": Fingerprint enrollment
    - "all": All biometrics enrollment

    Usage examples:
    - "Enroll face for employee EMP001"
    - "Start palm enrollment for John at Main Entrance"
    - "Trigger fingerprint enrollment for employee 12345"
    """

    name = "trigger_biometric_enrollment"
    description = (
        "Trigger biometric enrollment mode on a device for an employee. "
        "Supports face, palm, finger, or all biometrics. "
        "The employee must be physically present at the device to complete enrollment. "
        "Requires confirmation."
    )
    rbac_required = ["ADMIN"]
    destructive = True

    def __init__(self):
        super().__init__()
        logger.info("BiometricEnrollmentTool initialized")

    async def _run(
        self,
        employee_id: str,
        biometric_type: str = "face",
        terminal_id: Optional[int] = None,
        terminal_name: Optional[str] = None,
        timeout_seconds: int = 60,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Trigger biometric enrollment on a device.

        Args:
            employee_id: Employee identifier (code or name)
            biometric_type: Type of biometric ('face', 'palm', 'finger', 'all')
            terminal_id: Specific terminal ID (optional)
            terminal_name: Terminal name (optional)
            timeout_seconds: Enrollment timeout in seconds (default: 60)

        Returns:
            Dict with enrollment trigger status and instructions
        """
        start_time = datetime.now()

        try:
            logger.info(f"[BIOMETRIC_ENROLL] Triggering {biometric_type} enrollment for {employee_id}")

            # Validate biometric type
            valid_types = ["face", "palm", "finger", "all"]
            if biometric_type.lower() not in valid_types:
                return {
                    "success": False,
                    "error": f"Invalid biometric type: {biometric_type}. Valid types: {', '.join(valid_types)}",
                    "action_type": "trigger_biometric_enrollment"
                }

            # Look up employee to get ECode
            employee = await employee_lookup_service.get_employee_by_identifier(employee_id)
            if not employee:
                return {
                    "success": False,
                    "error": f"Employee not found: {employee_id}",
                    "action_type": "trigger_biometric_enrollment"
                }

            ecode = employee.ecode

            # Trigger enrollment via extended client
            result = await extended_access_control_client.trigger_biometric_enrollment(
                ecode=ecode,
                biometric_type=biometric_type,
                terminal_id=terminal_id,
                terminal_name=terminal_name,
                timeout_seconds=timeout_seconds
            )

            execution_time_ms = (datetime.now() - start_time).total_seconds() * 1000

            if result.get("success"):
                device_info = result.get("device", {})
                terminal_display = device_info.get("name") or terminal_name or "Auto-selected"
                return {
                    "success": True,
                    "employee_id": employee_id,
                    "employee_name": employee.name,
                    "ecode": ecode,
                    "biometric_type": biometric_type,
                    "terminal_name": terminal_display,
                    "device": device_info,
                    "timeout_seconds": timeout_seconds,
                    "instructions": result.get("instructions", ""),
                    "command_sent": result.get("command_sent", False),
                    "message": result.get("message"),
                    "action_type": "trigger_biometric_enrollment",
                    "execution_time_ms": execution_time_ms
                }
            else:
                # Include all relevant info even in failure case for proper error display
                device_info = result.get("device", {})
                return {
                    "success": False,
                    "error": result.get("error") or result.get("message"),
                    "employee_id": employee_id,
                    "ecode": ecode,
                    "biometric_type": biometric_type,
                    "terminal_name": device_info.get("terminal_name") or terminal_name or "Auto-selected",
                    "device": device_info,
                    "timeout_seconds": timeout_seconds,
                    "action_type": "trigger_biometric_enrollment",
                    "execution_time_ms": execution_time_ms
                }

        except Exception as e:
            logger.error(f"[BIOMETRIC_ENROLL] Failed: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "action_type": "trigger_biometric_enrollment"
            }

    def get_confirmation_message(
        self,
        employee_id: str,
        biometric_type: str = "face",
        terminal_name: Optional[str] = None,
        **kwargs
    ) -> str:
        """Generate human-readable confirmation message"""
        biometric_display = {
            "face": "Face",
            "palm": "Palm",
            "finger": "Fingerprint",
            "all": "All Biometrics"
        }
        bio_name = biometric_display.get(biometric_type.lower(), biometric_type)
        device_info = f" at {terminal_name}" if terminal_name else ""

        return (
            f"**BIOMETRIC ENROLLMENT REQUEST**\n\n"
            f"**Details:**\n"
            f"- Employee: {employee_id}\n"
            f"- Biometric Type: {bio_name}\n"
            f"- Device: {terminal_name or 'Auto-select'}\n\n"
            f"**Important:** The employee must be physically present at the device{device_info} "
            f"to complete enrollment.\n\n"
            f"Do you want to trigger {bio_name.lower()} enrollment for {employee_id}?"
        )


# =============================================================================
# Global Tool Instances
# =============================================================================

visitor_registration_tool = VisitorRegistrationTool()
temporary_card_tool = TemporaryCardTool()
database_backup_tool = DatabaseBackupTool()
card_enrollment_tool = CardEnrollmentTool()
employee_enrollment_tool = EmployeeEnrollmentTool()
door_access_tool = DoorAccessTool()
employee_management_tool = EmployeeManagementTool()
authentication_management_tool = AuthenticationManagementTool()
biometric_enrollment_tool = BiometricEnrollmentTool()
