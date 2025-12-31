"""
Oryggi Access Control API Client
Integration with Oryggi Access Control system for physical door/terminal access management

This client communicates with the Oryggi Access Control API to:
- Grant user access to terminals/zones (AddAuthentication_Terminal)
- Block user access (Set ScheduleID=0)
- Revoke previously granted access
- Query current access permissions
"""

import httpx
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from loguru import logger

from app.config import settings


class AccessControlError(Exception):
    """Custom exception for Access Control API errors"""

    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict] = None):
        self.message = message
        self.status_code = status_code
        self.response_data = response_data
        super().__init__(self.message)


class AccessType(str, Enum):
    """Types of access that can be granted"""
    DOOR = "door"
    ZONE = "zone"
    TERMINAL = "terminal"
    BUILDING = "building"
    AREA = "area"


class AccessStatus(str, Enum):
    """Status of access permissions"""
    ACTIVE = "active"
    BLOCKED = "blocked"
    REVOKED = "revoked"
    EXPIRED = "expired"
    PENDING = "pending"


class AuthenticationType(int, Enum):
    """Oryggi authentication types"""
    CARD = 1001
    FINGERPRINT = 2
    FACE = 5


class ScheduleType(int, Enum):
    """Oryggi schedule types"""
    NO_ACCESS = 0
    ALL_ACCESS = 63


@dataclass
class AccessPermission:
    """Represents an access permission"""
    permission_id: str
    user_id: str
    access_type: AccessType
    target_id: str
    target_name: str
    status: AccessStatus
    granted_by: str
    granted_at: datetime
    expires_at: Optional[datetime]
    schedule: Optional[Dict[str, Any]] = None


@dataclass
class AccessControlResult:
    """Result of an access control operation"""
    success: bool
    message: str
    permission_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class AccessControlAPIClient:
    """Client for interacting with the Oryggi Access Control System API"""

    def __init__(self):
        """Initialize the Oryggi Access Control API client"""
        self.base_url = settings.access_control_api_url
        self.api_key = settings.access_control_api_key
        self.client_version = settings.access_control_client_version
        self.timeout = 30
        self.mock_mode = settings.access_control_mock_mode
        self.default_auth_type = settings.access_control_default_auth_type
        self.default_schedule = settings.access_control_default_schedule

        logger.info(f"AccessControlAPIClient initialized. Mock mode: {self.mock_mode}")
        if not self.mock_mode:
            logger.info(f"Oryggi API URL: {self.base_url}")

    def _get_base_params(self) -> Dict[str, str]:
        """Get base parameters required for all Oryggi API calls"""
        return {
            "APIKey": self.api_key,
            "ClientVersion": self.client_version
        }

    async def _get_ecode_from_employee_id(self, employee_id: str) -> Optional[int]:
        """
        Lookup the internal Ecode from CorpEmpCode or direct Ecode.
        Uses direct SQL query to Oryggi database (using Windows Auth).
        """
        import pyodbc
        try:
            conn_str = (
                "DRIVER={ODBC Driver 17 for SQL Server};"
                "SERVER=DESKTOP-UOD2VBS\\MSSQLSERVER2022;"
                "DATABASE=Oryggi;"
                "Trusted_Connection=yes;"
            )
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()
            cursor.execute("SELECT Ecode FROM EmployeeMaster WHERE CorpEmpCode = ?", (employee_id,))
            row = cursor.fetchone()
            if row:
                ecode = row[0]
                logger.info(f"[ORYGGI_API] Found employee by CorpEmpCode: {employee_id} -> Ecode {ecode}")
                conn.close()
                return ecode
            if employee_id.isdigit():
                cursor.execute("SELECT Ecode FROM EmployeeMaster WHERE Ecode = ?", (int(employee_id),))
                row = cursor.fetchone()
                if row:
                    ecode = row[0]
                    logger.info(f"[ORYGGI_API] Found employee by Ecode: {employee_id}")
                    conn.close()
                    return ecode
            conn.close()
            logger.warning(f"[ORYGGI_API] Could not find Ecode for employee: {employee_id}")
            return None
        except Exception as e:
            logger.error(f"[ORYGGI_API] Error looking up Ecode: {str(e)}")
            return None

    async def _get_terminal_id(self) -> int:
        """Get the default terminal ID (BS3 device)"""
        return 1

    async def _resend_authentication_to_terminal(self, ecode: int, terminal_id: int) -> bool:
        """
        Call ResendAuthenticationRelation API to sync access data to the physical terminal.
        This is required after any database update to push changes to the device.
        """
        try:
            result = await self._make_request(
                "GET",
                "ResendAuthenticationRelation",
                params={
                    "TerminalId": terminal_id,
                    "Ecode": ecode
                }
            )
            success = result == True or result == "true" or str(result).lower() == "true"
            if success:
                logger.info(f"[ORYGGI_API] ResendAuthenticationRelation successful for Ecode {ecode}, Terminal {terminal_id}")
            else:
                logger.warning(f"[ORYGGI_API] ResendAuthenticationRelation returned: {result}")
            return success
        except Exception as e:
            logger.error(f"[ORYGGI_API] ResendAuthenticationRelation failed: {str(e)}")
            return False

    async def _deactivate_employee(self, corp_emp_code: str, reason: str = "De-Activate User") -> bool:
        """
        Call deActivateEmployee API to de-activate/block an employee (StatusID=2, Active=0).
        This is the correct API used by Oryggi Manager Web to block user access.
        """
        try:
            result = await self._make_request(
                "GET", "deActivateEmployee",
                params={"CorpEmpCode": corp_emp_code, "StatusID": 2, "LeavingReason": reason, "Active": 0, "IPAddress": "localhost", "OperatorEcode": 1}
            )
            success = result == True or result == "true" or str(result).lower() == "true" or (isinstance(result, str) and "success" in result.lower())
            logger.info(f"[ORYGGI_API] deActivateEmployee {'successful' if success else 'returned: ' + str(result)} for {corp_emp_code}")
            return success
        except Exception as e:
            logger.error(f"[ORYGGI_API] deActivateEmployee failed: {str(e)}")
            return False

    async def _activate_employee(self, corp_emp_code: str, reason: str = "Activate User") -> bool:
        """
        Call deActivateEmployee API with activation params to re-activate/unblock (StatusID=1, Active=1).
        This is the correct API used by Oryggi Manager Web to unblock user access.
        """
        try:
            result = await self._make_request(
                "GET", "deActivateEmployee",
                params={"CorpEmpCode": corp_emp_code, "StatusID": 1, "LeavingReason": reason, "Active": 1, "IPAddress": "localhost", "OperatorEcode": 1}
            )
            success = result == True or result == "true" or str(result).lower() == "true" or (isinstance(result, str) and "success" in result.lower())
            logger.info(f"[ORYGGI_API] activateEmployee {'successful' if success else 'returned: ' + str(result)} for {corp_emp_code}")
            return success
        except Exception as e:
            logger.error(f"[ORYGGI_API] activateEmployee failed: {str(e)}")
            return False


    async def _grant_access_direct_sql(self, ecode: int, terminal_id: int, authentication_id: int, schedule_id: int, start_date, end_date) -> bool:
        """Direct SQL fallback for granting access when API fails."""
        import pyodbc
        try:
            conn_str = "DRIVER={ODBC Driver 17 for SQL Server};SERVER=DESKTOP-UOD2VBS\MSSQLSERVER2022;DATABASE=Oryggi;Trusted_Connection=yes;"
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()
            cursor.execute("SELECT ID FROM Employee_Terminal_Authentication_Relation WHERE Ecode = ? AND TerminalID = ? AND AuthenticationID = ?", (ecode, terminal_id, authentication_id))
            existing = cursor.fetchone()
            if existing:
                cursor.execute("UPDATE Employee_Terminal_Authentication_Relation SET ScheduleID = ?, Start_date = ?, Expiry_date = ?, Status = 'Pending', DataLocation = 'Server', ServerSync = 0 WHERE Ecode = ? AND TerminalID = ? AND AuthenticationID = ?", (schedule_id, start_date, end_date, ecode, terminal_id, authentication_id))
                logger.info(f"[ORYGGI_SQL] Updated access for Ecode {ecode}")
            else:
                cursor.execute("INSERT INTO Employee_Terminal_Authentication_Relation (Ecode, AuthenticationID, TerminalID, ScheduleID, Start_date, Expiry_date, Group01, BypassTZLevel, Status, DataLocation, CreateDate, ServerSync) VALUES (?, ?, ?, ?, ?, ?, 1, 1, 'Pending', 'Server', GETDATE(), 0)", (ecode, authentication_id, terminal_id, schedule_id, start_date, end_date))
                logger.info(f"[ORYGGI_SQL] Inserted access for Ecode {ecode}")
            conn.commit()
            conn.close()
            # Trigger sync to physical terminal
            await self._resend_authentication_to_terminal(ecode, terminal_id)
            return True
        except Exception as e:
            logger.error(f"[ORYGGI_SQL] Direct SQL failed: {str(e)}")
            return False

    async def _block_access_direct_sql(self, ecode: int, terminal_id: int, authentication_id: int) -> bool:
        """Direct SQL fallback for blocking access."""
        import pyodbc
        try:
            conn_str = "DRIVER={ODBC Driver 17 for SQL Server};SERVER=DESKTOP-UOD2VBS\MSSQLSERVER2022;DATABASE=Oryggi;Trusted_Connection=yes;"
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()
            cursor.execute("UPDATE Employee_Terminal_Authentication_Relation SET ScheduleID = 0, Status = 'Pending', DataLocation = 'Server', ServerSync = 0 WHERE Ecode = ? AND TerminalID = ? AND AuthenticationID = ?", (ecode, terminal_id, authentication_id))
            conn.commit()
            rows = cursor.rowcount
            conn.close()
            if rows > 0:
                logger.info(f"[ORYGGI_SQL] Blocked access for Ecode {ecode}")
                # Trigger sync to physical terminal
                await self._resend_authentication_to_terminal(ecode, terminal_id)
                return True
            return False
        except Exception as e:
            logger.error(f"[ORYGGI_SQL] Block failed: {str(e)}")
            return False

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None
    ) -> Any:
        """Make HTTP request to the Oryggi Access Control API"""
        url = f"{self.base_url}/{endpoint}"
        # APIKey goes in the header, not query params
        headers = {"APIKey": self.api_key}
        # ClientVersion goes in query params
        all_params = {"ClientVersion": self.client_version}
        if params:
            all_params.update(params)

        async with httpx.AsyncClient(timeout=self.timeout, verify=False) as client:
            try:
                logger.debug(f"[ORYGGI_API] {method} {url}")
                logger.debug(f"[ORYGGI_API] Params: {all_params}")
                if data:
                    logger.debug(f"[ORYGGI_API] Body: {data}")

                if method.upper() == "GET":
                    response = await client.get(url, params=all_params, headers=headers)
                else:
                    response = await client.post(url, params=all_params, json=data, headers=headers)

                logger.debug(f"[ORYGGI_API] Response status: {response.status_code}")
                logger.debug(f"[ORYGGI_API] Response: {response.text[:500] if response.text else 'empty'}")

                if response.status_code >= 400:
                    raise AccessControlError(
                        message=response.text or f"API error: {response.status_code}",
                        status_code=response.status_code
                    )

                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    return response.json() if response.content else {}
                return response.text

            except httpx.RequestError as e:
                logger.error(f"[ORYGGI_API] Request failed: {str(e)}")
                raise AccessControlError(f"Connection error: {str(e)}")

    def _mock_grant_access(self, user_id, target_type, target_id, target_name, granted_by, start_date, end_date, schedule=None):
        import uuid
        return AccessControlResult(
            success=True,
            message=f"Access granted successfully to {target_name}",
            permission_id=f"PERM-{uuid.uuid4().hex[:8].upper()}",
            details={"mock": True, "user_id": user_id}
        )

    def _mock_block_access(self, user_id, target_type, target_id, target_name, blocked_by, reason):
        return AccessControlResult(
            success=True,
            message=f"Access blocked for user {user_id} to {target_name}",
            details={"mock": True, "user_id": user_id, "reason": reason}
        )

    def _mock_revoke_access(self, permission_id, revoked_by, reason):
        return AccessControlResult(
            success=True,
            message=f"Access permission {permission_id} revoked successfully",
            permission_id=permission_id,
            details={"mock": True}
        )

    def _mock_get_user_permissions(self, user_id):
        return []

    async def grant_access(
        self,
        user_id: str,
        target_type: AccessType,
        target_id: str,
        target_name: str,
        granted_by: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        schedule: Optional[Dict[str, Any]] = None,
        terminal_group_id: Optional[int] = None,
        authentication_type: Optional[int] = None
    ) -> AccessControlResult:
        """
        Grant access to a user for a specific door/zone/terminal
        Calls Oryggi API: AddAuthentication_Terminal (per-terminal authentication)
        """
        start_date = start_date or datetime.now()
        end_date = end_date or (datetime.now() + timedelta(days=365))

        if self.mock_mode:
            return self._mock_grant_access(
                user_id, target_type, target_id, target_name,
                granted_by, start_date, end_date, schedule
            )

        try:
            # Primary method: Use _activate_employee API (same as Oryggi Manager Web)
            logger.info(f"[ORYGGI_API] Attempting to activate {user_id} using deActivateEmployee API")
            success = await self._activate_employee(user_id, f"Grant access to {target_name}")
            
            if success:
                import uuid
                permission_id = f"PERM-{uuid.uuid4().hex[:8].upper()}"
                return AccessControlResult(
                    success=True,
                    message=f"Access granted successfully to {target_name}",
                    permission_id=permission_id,
                    details={
                        "user_id": user_id,
                        "target_type": target_type.value,
                        "target_id": target_id,
                        "target_name": target_name,
                        "granted_by": granted_by,
                        "method": "deActivateEmployee API (Activate)",
                        "oryggi_response": "Success"
                    }
                )
            
            # Fallback: Convert CorpEmpCode to internal Ecode
            logger.warning(f"[ORYGGI_API] _activate_employee failed, trying AddAuthentication_Terminal fallback")
            ecode = await self._get_ecode_from_employee_id(user_id)
            if ecode is None:
                return AccessControlResult(
                    success=False,
                    message=f"Employee not found: {user_id}",
                    details={"error": f"Could not find Ecode for employee {user_id}"}
                )

            logger.info(f"[ORYGGI_API] Resolved employee {user_id} to Ecode {ecode}")

            # Fallback Step 2: Get terminal ID (BS3 device = 1)
            terminal_id = await self._get_terminal_id()

            # Fallback Step 3: Build JSON body for AddAuthentication_TerminalV2
            # V2 API expects array format, V1 silently fails
            body = [{
                "ecode": ecode,
                "terminalID": terminal_id,  # V2 expects integer, not string
                "authenticationID": authentication_type or 1001,  # 1001 = Card
                "scheduleID": self.default_schedule,  # 63 = All Access
                "expiry_date": end_date.strftime("%Y-%m-%d %H:%M:%S"),
                "start_date": start_date.strftime("%Y-%m-%d %H:%M:%S"),
                "group01": 1,
                "bypassTZLevel": 1,
                "isAntipassBack": 0,
                "OfflinePriority": 0,
                "UserType": 0,
                "iSDeleted": False
            }]

            logger.info(f"[ORYGGI_API] Calling AddAuthentication_TerminalV2 with body: {body}")

            # Try API first, fallback to direct SQL if it fails
            try:
                result = await self._make_request("POST", "AddAuthentication_TerminalV2", data=body)
                success = result == "Success" or (isinstance(result, str) and "success" in result.lower())
            except AccessControlError as api_error:
                logger.warning(f"[ORYGGI_API] API failed ({api_error.message}), using direct SQL fallback")
                success = await self._grant_access_direct_sql(ecode, terminal_id, authentication_type or 1001, self.default_schedule, start_date, end_date)
                result = "Success (via direct SQL)" if success else "Failed (direct SQL)"

            if success:
                import uuid
                permission_id = f"PERM-{uuid.uuid4().hex[:8].upper()}"

                return AccessControlResult(
                    success=True,
                    message=f"Access granted successfully to {target_name}",
                    permission_id=permission_id,
                    details={
                        "user_id": user_id,
                        "ecode": ecode,
                        "target_type": target_type.value,
                        "target_id": target_id,
                        "target_name": target_name,
                        "granted_by": granted_by,
                        "terminal_id": terminal_id,
                        "schedule_id": self.default_schedule,
                        "oryggi_response": result
                    }
                )
            else:
                return AccessControlResult(
                    success=False,
                    message=f"Failed to grant access: {result}",
                    details={"oryggi_response": result, "ecode": ecode, "terminal_id": terminal_id}
                )

        except AccessControlError as e:
            logger.error(f"[ORYGGI_API] Grant access failed: {e.message}")
            return AccessControlResult(
                success=False,
                message=f"Error: {e.message}",
                details={"error": str(e)}
            )

    async def block_access(
        self,
        user_id: str,
        target_type: AccessType = AccessType.AREA,
        target_id: str = "all",
        target_name: str = "all areas",
        blocked_by: str = "admin",
        reason: str = "Blocked via chatbot",
        terminal_group_id: Optional[int] = None
    ) -> AccessControlResult:
        """
        Block a user's access using deActivateEmployee API (same as Oryggi Manager Web).
        Falls back to AddAuthentication_Terminal with ScheduleID=0 if needed.
        """
        if self.mock_mode:
            return self._mock_block_access(
                user_id, target_type, target_id, target_name,
                blocked_by, reason
            )

        try:
            # Primary method: Use deActivateEmployee API (same as Oryggi Manager Web)
            logger.info(f"[ORYGGI_API] Attempting to block {user_id} using deActivateEmployee API")
            success = await self._deactivate_employee(user_id, reason)
            
            if success:
                return AccessControlResult(
                    success=True,
                    message=f"Access blocked for user {user_id} to {target_name}",
                    details={
                        "user_id": user_id,
                        "target_type": target_type.value,
                        "target_id": target_id,
                        "target_name": target_name,
                        "blocked_by": blocked_by,
                        "reason": reason,
                        "blocked_at": datetime.now().isoformat(),
                        "method": "deActivateEmployee API",
                        "oryggi_response": "Success"
                    }
                )
            
            # Fallback: Convert CorpEmpCode to internal Ecode
            logger.warning(f"[ORYGGI_API] deActivateEmployee failed, trying fallback")
            ecode = await self._get_ecode_from_employee_id(user_id)
            if ecode is None:
                return AccessControlResult(
                    success=False,
                    message=f"Employee not found: {user_id}",
                    details={"error": f"Could not find Ecode for employee {user_id}"}
                )

            logger.info(f"[ORYGGI_API] Resolved employee {user_id} to Ecode {ecode}")

            # Step 2: Get terminal ID (BS3 device = 1)
            terminal_id = await self._get_terminal_id()

            # Step 3: Build JSON body with ScheduleID=0 (blocked)
            # V2 API expects array format, V1 silently fails
            body = [{
                "ecode": ecode,
                "terminalID": terminal_id,  # V2 expects integer, not string
                "authenticationID": 1001,  # Card
                "scheduleID": ScheduleType.NO_ACCESS.value,  # 0 = No Access (Blocked)
                "expiry_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "start_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "group01": 1,
                "bypassTZLevel": 0,
                "isAntipassBack": 0,
                "OfflinePriority": 0,
                "UserType": 0,
                "iSDeleted": True  # Mark as deleted/blocked
            }]

            logger.info(f"[ORYGGI_API] Calling AddAuthentication_TerminalV2 (BLOCK) with body: {body}")

            # Try API first, fallback to direct SQL if it fails
            try:
                result = await self._make_request("POST", "AddAuthentication_TerminalV2", data=body)
                success = result == "Success" or (isinstance(result, str) and "success" in result.lower())
            except AccessControlError as api_error:
                logger.warning(f"[ORYGGI_API] Block API failed ({api_error.message}), using direct SQL fallback")
                success = await self._block_access_direct_sql(ecode, terminal_id, 1001)
                result = "Success (via direct SQL)" if success else "Failed (direct SQL)"

            if success:
                return AccessControlResult(
                    success=True,
                    message=f"Access blocked for user {user_id} to {target_name}",
                    details={
                        "user_id": user_id,
                        "ecode": ecode,
                        "target_type": target_type.value,
                        "target_id": target_id,
                        "target_name": target_name,
                        "blocked_by": blocked_by,
                        "reason": reason,
                        "terminal_id": terminal_id,
                        "blocked_at": datetime.now().isoformat(),
                        "oryggi_response": result
                    }
                )
            else:
                return AccessControlResult(
                    success=False,
                    message=f"Failed to block access: {result}",
                    details={"oryggi_response": result, "ecode": ecode, "terminal_id": terminal_id}
                )

        except AccessControlError as e:
            logger.error(f"[ORYGGI_API] Block access failed: {e.message}")
            return AccessControlResult(
                success=False,
                message=f"Error: {e.message}",
                details={"error": str(e)}
            )

    async def revoke_access(
        self,
        permission_id: str,
        revoked_by: str,
        reason: str = "Revoked via chatbot",
        user_id: Optional[str] = None,
        terminal_group_id: Optional[int] = None
    ) -> AccessControlResult:
        """
        Revoke a specific access permission
        Calls Oryggi API: AddAuthentication_Terminal with ScheduleID=0
        """
        if self.mock_mode:
            return self._mock_revoke_access(permission_id, revoked_by, reason)

        if not user_id:
            return AccessControlResult(
                success=False,
                message="User ID required to revoke access in Oryggi",
                permission_id=permission_id
            )

        try:
            ecode = await self._get_ecode_from_employee_id(user_id)
            if ecode is None:
                return AccessControlResult(
                    success=False,
                    message=f"Employee not found: {user_id}",
                    permission_id=permission_id,
                    details={"error": f"Could not find Ecode for employee {user_id}"}
                )

            terminal_id = await self._get_terminal_id()

            body = {
                "ecode": ecode,
                "terminalID": str(terminal_id),
                "authenticationID": 1001,
                "scheduleID": ScheduleType.NO_ACCESS.value,
                "expiry_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "start_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "group01": 1,
                "bypassTZLevel": 0,
                "isAntipassBack": 0,
                "OfflinePriority": 0,
                "UserType": 0,
                "iSDeleted": True
            }

            logger.info(f"[ORYGGI_API] Calling AddAuthentication_Terminal (REVOKE) with body: {body}")

            result = await self._make_request("POST", "AddAuthentication_Terminal", data=body)

            success = result == "Success" or (isinstance(result, str) and "success" in result.lower())

            if success:
                return AccessControlResult(
                    success=True,
                    message=f"Access permission {permission_id} revoked successfully",
                    permission_id=permission_id,
                    details={
                        "permission_id": permission_id,
                        "user_id": user_id,
                        "ecode": ecode,
                        "revoked_by": revoked_by,
                        "reason": reason,
                        "terminal_id": terminal_id,
                        "revoked_at": datetime.now().isoformat(),
                        "oryggi_response": result
                    }
                )
            else:
                return AccessControlResult(
                    success=False,
                    message=f"Failed to revoke access: {result}",
                    permission_id=permission_id,
                    details={"oryggi_response": result, "ecode": ecode, "terminal_id": terminal_id}
                )

        except AccessControlError as e:
            logger.error(f"[ORYGGI_API] Revoke access failed: {e.message}")
            return AccessControlResult(
                success=False,
                message=f"Error: {e.message}",
                permission_id=permission_id,
                details={"error": str(e)}
            )

    async def get_user_permissions(self, user_id: str, include_inactive: bool = False) -> List[AccessPermission]:
        """Get all access permissions for a user"""
        if self.mock_mode:
            return self._mock_get_user_permissions(user_id)
        try:
            result = await self._make_request("GET", "Get_Visitor_Detail_By_Visitor_ID_V3", params={"Visitor_ID": user_id})
            permissions = []
            if isinstance(result, list):
                for visitor in result:
                    if visitor:
                        permission = AccessPermission(
                            permission_id=f"PERM-{visitor.get('ID', 'unknown')}",
                            user_id=visitor.get('VisitorID', user_id),
                            access_type=AccessType.ZONE,
                            target_id=str(visitor.get('TerminalGroupID', '')),
                            target_name=visitor.get('SecName', 'Unknown Location'),
                            status=AccessStatus.ACTIVE if visitor.get('Status', '').lower() == 'active' else AccessStatus.BLOCKED,
                            granted_by=visitor.get('Whom_Employee_Name', 'System'),
                            granted_at=datetime.now(),
                            expires_at=None
                        )
                        permissions.append(permission)
            return permissions
        except Exception as e:
            logger.error(f"[ORYGGI_API] Get permissions failed: {str(e)}")
            return []

    async def get_visitor_details(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed visitor information from Oryggi"""
        if self.mock_mode:
            return {"EmployeeID": user_id, "Status": "Active", "mock": True}
        try:
            result = await self._make_request("GET", "Get_Visitor_Detail_By_Visitor_ID_V3", params={"Visitor_ID": user_id})
            if isinstance(result, list) and len(result) > 0:
                return result[0]
            elif isinstance(result, dict):
                return result
            return None
        except AccessControlError as e:
            logger.error(f"[ORYGGI_API] Get visitor details failed: {e.message}")
            return None

    async def get_all_terminal_groups(self) -> List[Dict[str, Any]]:
        """Get all available terminal groups from Oryggi"""
        if self.mock_mode:
            return [{"ID": 1, "Name": "Main Entrance"}, {"ID": 2, "Name": "Server Room"}]
        try:
            result = await self._make_request("GET", "Get_All_TerminalGroups_V3")
            return result if isinstance(result, list) else []
        except AccessControlError:
            return []

    async def health_check(self) -> Dict[str, Any]:
        """Check if the Oryggi Access Control API is available"""
        if self.mock_mode:
            return {"status": "healthy", "mode": "mock", "api_url": self.base_url, "timestamp": datetime.now().isoformat()}
        try:
            params = {"UserID": "test", "ClientVersion": self.client_version}
            await self._make_request("GET", "iSUserExits", params=params)
            return {"status": "healthy", "mode": "live", "api_url": self.base_url, "timestamp": datetime.now().isoformat()}
        except AccessControlError as e:
            return {"status": "unhealthy", "mode": "live", "api_url": self.base_url, "error": str(e), "timestamp": datetime.now().isoformat()}


# Global client instance
access_control_client = AccessControlAPIClient()
