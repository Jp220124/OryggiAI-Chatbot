"""
Gateway Employee Lookup Service

Provides methods to search and retrieve employee details through the Gateway Agent.
Routes employee lookup queries via WebSocket to the local database on-premises.

This service replaces the direct pyodbc connection which times out from the cloud VM.
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from loguru import logger

from app.gateway.connection_manager import gateway_manager
from app.gateway.schemas import EmployeeLookupResponse, EmployeeLookupStatus


@dataclass
class EmployeeInfo:
    """Employee information data class"""
    ecode: int
    corp_emp_code: str
    name: str
    department: Optional[str] = None
    designation: Optional[str] = None
    card_no: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "ecode": self.ecode,
            "corp_emp_code": self.corp_emp_code,
            "name": self.name,
            "department": self.department,
            "designation": self.designation,
            "card_no": self.card_no,
            "email": self.email,
            "phone": self.phone,
            "active": self.active
        }


class GatewayEmployeeLookupService:
    """
    Service for looking up employee details through the Gateway Agent.

    Routes queries via WebSocket to the on-premises Gateway Agent which
    executes them on the local SQL Server database.

    This replaces the direct pyodbc connection that times out from the cloud VM.
    """

    def __init__(self):
        """Initialize the lookup service"""
        pass

    async def get_employee_by_identifier(
        self,
        identifier: str,
        database_id: Optional[str] = None,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> Optional[EmployeeInfo]:
        """
        Look up employee by any identifier (code, name, or card number).

        Args:
            identifier: Employee code, name, or card number
            database_id: Optional database ID (auto-detected if not provided)
            user_id: User who initiated the lookup
            conversation_id: Associated conversation

        Returns:
            EmployeeInfo if found, None otherwise
        """
        if not identifier:
            return None

        identifier = str(identifier).strip()
        logger.info(f"[GATEWAY_EMPLOYEE_LOOKUP] Looking up employee: {identifier}")

        # Get database_id if not provided
        if not database_id:
            database_id = gateway_manager.get_first_active_database_id()
            if not database_id:
                logger.error("[GATEWAY_EMPLOYEE_LOOKUP] No active gateway connection")
                return None

        try:
            # Execute lookup through gateway
            response = await gateway_manager.execute_employee_lookup(
                database_id=database_id,
                identifier=identifier,
                lookup_type="auto",
                timeout=10,
                user_id=user_id,
                conversation_id=conversation_id,
            )

            # Check response status
            if response.status == EmployeeLookupStatus.SUCCESS:
                if response.employee:
                    employee = self._response_to_employee_info(response.employee)
                    logger.info(f"[GATEWAY_EMPLOYEE_LOOKUP] Found: {employee.name} ({employee.corp_emp_code})")
                    return employee
                else:
                    logger.warning(f"[GATEWAY_EMPLOYEE_LOOKUP] Success but no employee data")
                    return None

            elif response.status == EmployeeLookupStatus.MULTIPLE_FOUND:
                # Return first match when multiple found
                if response.employee:
                    employee = self._response_to_employee_info(response.employee)
                    logger.warning(
                        f"[GATEWAY_EMPLOYEE_LOOKUP] Multiple found for '{identifier}', "
                        f"returning first: {employee.name}"
                    )
                    return employee
                return None

            elif response.status == EmployeeLookupStatus.NOT_FOUND:
                logger.warning(f"[GATEWAY_EMPLOYEE_LOOKUP] No employee found for: {identifier}")
                return None

            else:
                # Error, timeout, or connection error
                logger.error(
                    f"[GATEWAY_EMPLOYEE_LOOKUP] Lookup failed: status={response.status}, "
                    f"error={response.error_message}"
                )
                return None

        except Exception as e:
            logger.error(f"[GATEWAY_EMPLOYEE_LOOKUP] Exception during lookup: {e}")
            return None

    async def search_employees(
        self,
        search_term: str,
        database_id: Optional[str] = None,
        limit: int = 5,
    ) -> List[EmployeeInfo]:
        """
        Search employees by name or code (for disambiguation).

        Args:
            search_term: Search term
            database_id: Optional database ID
            limit: Maximum results to return

        Returns:
            List of matching employees
        """
        if not search_term:
            return []

        search_term = str(search_term).strip()
        logger.info(f"[GATEWAY_EMPLOYEE_LOOKUP] Searching employees: {search_term}")

        # Get database_id if not provided
        if not database_id:
            database_id = gateway_manager.get_first_active_database_id()
            if not database_id:
                logger.error("[GATEWAY_EMPLOYEE_LOOKUP] No active gateway connection")
                return []

        try:
            # Execute lookup through gateway with name lookup type
            response = await gateway_manager.execute_employee_lookup(
                database_id=database_id,
                identifier=search_term,
                lookup_type="name",  # Force name search
                timeout=10,
            )

            # Check response status
            if response.status == EmployeeLookupStatus.SUCCESS:
                if response.employee:
                    return [self._response_to_employee_info(response.employee)]
                return []

            elif response.status == EmployeeLookupStatus.MULTIPLE_FOUND:
                if response.employees:
                    employees = [
                        self._response_to_employee_info(emp)
                        for emp in response.employees[:limit]
                    ]
                    logger.info(f"[GATEWAY_EMPLOYEE_LOOKUP] Found {len(employees)} employees")
                    return employees
                return []

            else:
                return []

        except Exception as e:
            logger.error(f"[GATEWAY_EMPLOYEE_LOOKUP] Search error: {e}")
            return []

    def _response_to_employee_info(self, employee_data) -> EmployeeInfo:
        """Convert employee data from response to EmployeeInfo object"""
        # Handle both dict and EmployeeData pydantic model
        if hasattr(employee_data, 'model_dump'):
            data = employee_data.model_dump()
        elif isinstance(employee_data, dict):
            data = employee_data
        else:
            data = vars(employee_data)

        return EmployeeInfo(
            ecode=data.get("ecode", 0),
            corp_emp_code=str(data.get("corp_emp_code", "")),
            name=data.get("name", "Unknown"),
            department=data.get("department"),
            designation=data.get("designation"),
            card_no=data.get("card_no"),
            email=data.get("email"),
            phone=data.get("phone"),
            active=data.get("active", True),
        )


# Global instance
gateway_employee_lookup_service = GatewayEmployeeLookupService()
