"""
Extended Oryggi Access Control API Client
New functionality for Phase 6: Visitor Registration, Temporary Cards, Database Backup,
Card/Employee Enrollment, and Door-Specific Access Management.

Extends the base AccessControlAPIClient with additional operations.
Uses the same REST API approach as the base AccessControlAPIClient.

Oryggi API Endpoints Used:
- SaveVisitorDetailsWithAccessControl: POST - Main visitor registration
- GetNewID: GET - Get next ID for EmployeeMaster
- GetIDTypes: GET - Get available ID proof types
- GetPurposeTypes: GET - Get available visit purposes
- GetSearchedVisitors: GET - Search existing visitors
- CheckEmailUniqueness: GET - Validate email
"""

import pyodbc
import httpx
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from loguru import logger

from app.config import settings
from app.models.access_control_extended import (
    VisitorRegistrationRequest, VisitorRegistrationResponse,
    TemporaryCardRequest, TemporaryCardResponse,
    DatabaseBackupRequest, DatabaseBackupResponse,
    CardEnrollmentRequest, CardEnrollmentResponse,
    EmployeeEnrollmentRequest, EmployeeEnrollmentResponse,
    EmployeeCreateUpdateRequest, EmployeeCreateUpdateResponse,
    DoorAccessRequest, DoorAccessResponse,
    AccessScope, DoorAction
)
from app.integrations.access_control_api import (
    AccessControlAPIClient, AccessControlError, ScheduleType
)


class ExtendedAccessControlClient(AccessControlAPIClient):
    """
    Extended Access Control Client with new functionality for:
    - Visitor Registration
    - Temporary Card Assignment
    - Database Backup
    - Card Enrollment (to specific or all doors)
    - Employee Enrollment
    - Door-Specific Access Management (Grant/Block)
    """

    # Default values
    DEFAULT_VISITOR_CATEGORY = 4  # Visitor category code
    DEFAULT_SCHEDULE_ALL_ACCESS = 63
    DEFAULT_SCHEDULE_NO_ACCESS = 0
    DEFAULT_AUTH_CARD = 1001
    DEFAULT_AUTH_FINGERPRINT = 2
    DEFAULT_AUTH_FACE = 5

    def __init__(self):
        """Initialize the extended client"""
        super().__init__()
        self.backup_path = getattr(settings, 'database_backup_path', 'D:\\Backups\\Oryggi')
        logger.info("[EXTENDED_API] Extended Access Control Client initialized")

    # =========================================================================
    # Visitor Registration (Using Real Oryggi API)
    # =========================================================================

    async def register_visitor(
        self,
        request: VisitorRegistrationRequest,
        operator_ecode: int = 1
    ) -> VisitorRegistrationResponse:
        """
        Register a new visitor in the Oryggi system using the real Oryggi REST API.
        Calls SaveVisitorDetailsWithAccessControl endpoint (same as Oryggi Manager Web).

        Args:
            request: VisitorRegistrationRequest with visitor details
            operator_ecode: Ecode of the operator performing registration

        Returns:
            VisitorRegistrationResponse with success status and visitor ID
        """
        if self.mock_mode:
            import uuid
            visitor_id = f"V{uuid.uuid4().hex[:8].upper()}"
            return VisitorRegistrationResponse(
                success=True,
                visitor_id=visitor_id,
                visitor_ecode=99999,
                message=f"Visitor {request.first_name} {request.last_name} registered (mock)",
                details={"mock": True}
            )

        try:
            logger.info(f"[EXTENDED_API] Registering visitor via Oryggi API: {request.first_name} {request.last_name}")

            # Step 1: Get next available Ecode using GetNewID API
            new_ecode = await self._get_new_id("EmployeeMaster", "Ecode")
            if not new_ecode:
                return VisitorRegistrationResponse(
                    success=False,
                    message="Failed to get new visitor ID from Oryggi API",
                    details={"error": "GetNewID API failed"}
                )

            # Step 2: Resolve whom_to_visit employee Ecode
            whom_ecode = 0
            if request.whom_to_visit:
                whom_ecode = await self._get_ecode_from_employee_id(request.whom_to_visit) or 0

            # Step 3: Set default times
            expected_in = request.expected_in_time or datetime.now()
            expected_out = request.expected_out_time or (datetime.now() + timedelta(hours=8))

            # Step 4: Map ID proof type to Oryggi ID type code
            id_type_code = await self._get_id_type_code(request.id_proof_type)

            # Step 5: Build the visitor payload for SaveVisitorDetailsWithAccessControl
            # IMPORTANT: Field names MUST be PascalCase as captured from working Oryggi Manager Web
            full_name = f"{request.first_name} {request.last_name or ''}".strip()

            # Use the mobile number as the visitor code (this is what Oryggi Manager Web does)
            # Or generate a unique code if no mobile number
            visitor_code = request.mobile_number or f"V{new_ecode}"

            # Map purpose text to purposeType code (1=Meeting is default)
            purpose_map = {
                "meeting": 1, "interview": 2, "delivery": 3, "maintenance": 4,
                "contractor": 5, "visitor": 6, "visit": 1, "other": 0
            }
            purpose_type = purpose_map.get((request.purpose or "meeting").lower(), 1)

            # PascalCase payload exactly matching the working Oryggi Manager Web format
            # Captured via Playwright network interception from SaveVisitorDetailsWithAccessControl
            visitor_payload = {
                # Core identity fields
                "Ecode": new_ecode,
                "FName": request.first_name,
                "LName": request.last_name or "",
                "Email": request.email or "",
                "PhoneNumber": visitor_code,  # Used as visitor identifier

                # Images (empty for API registration)
                "Image": "",
                "ImageId": "",
                "isVisitorImageSaved": False,

                # Gender and escort
                "Sex": True if (request.gender == "M" or not request.gender) else False,
                "GenderID": 1 if (request.gender == "M" or not request.gender) else 2,
                "EscortRequired": request.need_escort or False,

                # Address
                "Address1": request.address or "",

                # Meeting details
                "WhomToVisitEmployeeID": whom_ecode if whom_ecode else 1,  # Default to Admin (1) if not specified
                "WhomToMeetId": "",
                "Filter": request.whom_to_visit or "Admin",
                "WhomToMeetName": "",
                "WhomDepartmentName": "",

                # Creation metadata
                "Created_By": "Admin",

                # Fingerprint IDs (required, set to -1 for none)
                "FP1_ID": -1,
                "FP2_ID": -1,
                "DFP_ID": -1,

                # Purpose
                "PurposeType": purpose_type,
                "Purpose": "",

                # ID proof
                "IDProofType": id_type_code,
                "IDProofDetail": request.id_proof_detail or "",

                # Card
                "PresentCardNo": request.issued_card_number or str(new_ecode),  # Use ecode as card if not specified

                # Blacklist flag
                "IsBlackListed": False,

                # Client version (required)
                "ClientVersion": "24.07.2025",

                # Remarks
                "Remarks": "",

                # Visitor type and count
                "VisitorType": request.visitor_type or "Walk-In",
                "NumberOfVisitors": request.number_of_visitors or 1,

                # Status
                "Status": "Pending",

                # Client info
                "ClientName": "NONE",

                # Vehicle
                "VehicleDetail": request.vehicle_number or "",

                # Time flags
                "TimeRescheduled": False,
                "TimeExtended": False,
                "IsWhomToMeetChanged": False,

                # Application URL
                "ApplicationUrl": "https://localhost/OryggiManagerWeb/login",

                # Additional fields
                "Field1": "",
                "AreaGroupID": request.terminal_group_id or 0,
                "DocumentDetails": "",
                "DocumentFile": "",

                # Time fields (IN/OUT empty, Expected filled)
                "INTime": "",
                "OUTTime": "",

                # QR Code
                "QRCodeValue": "",

                # Custom fields (all empty)
                "CustomField1": "",
                "CustomField2": "",
                "CustomField3": "",
                "CustomField4": "",
                "CustomField5": "",
                "CustomField6": "",
                "CustomField7": "",
                "CustomField8": "",
                "CustomField9": "",

                # Expected times in ISO format without seconds
                "ExpectedINTime": expected_in.strftime("%Y-%m-%dT%H:%M"),
                "ExpectedOUTTime": expected_out.strftime("%Y-%m-%dT%H:%M")
            }

            logger.info(f"[EXTENDED_API] Calling SaveVisitorDetailsWithAccessControl API")
            logger.info(f"[EXTENDED_API] DEBUG Payload: {visitor_payload}")

            # Step 6: Call SaveVisitorDetailsWithAccessControl API
            result = await self._make_request(
                "POST",
                "SaveVisitorDetailsWithAccessControl",
                data=visitor_payload
            )

            # Check result - the Oryggi API returns a numeric pass number (like "11") on success
            # Parse the result directly instead of using _check_api_success
            logger.info(f"[EXTENDED_API] SaveVisitorDetailsWithAccessControl raw result: {result!r} (type: {type(result).__name__})")

            # Determine success: numeric string > 0 means success (returns pass number)
            pass_number = None
            success = False

            if result is not None:
                result_str = str(result).strip()
                if result_str.isdigit():
                    pass_number = int(result_str)
                    success = pass_number > 0
                    logger.info(f"[EXTENDED_API] Numeric result: pass_number={pass_number}, success={success}")
                elif isinstance(result, int) and result > 0:
                    pass_number = result
                    success = True
                    logger.info(f"[EXTENDED_API] Int result: pass_number={pass_number}, success={success}")
                else:
                    # Check for failure keywords
                    result_lower = result_str.lower()
                    if "fail" in result_lower or "error" in result_lower or result_lower == "false":
                        success = False
                        logger.warning(f"[EXTENDED_API] API returned failure indicator: {result}")
                    else:
                        # Might be some other success response
                        success = True
                        logger.info(f"[EXTENDED_API] Non-numeric result treated as success: {result}")

            if success:
                # visitor_code already defined earlier at payload creation (e.g., "V18")
                # pass_number is the visitor pass number returned by API
                logger.info(f"[EXTENDED_API] Visitor registration successful: {visitor_code} (Ecode: {new_ecode}, Pass#: {pass_number})")

                return VisitorRegistrationResponse(
                    success=True,
                    visitor_id=str(pass_number) if pass_number else visitor_code,
                    visitor_ecode=new_ecode,
                    message=f"Visitor {full_name} registered successfully via Oryggi API",
                    details={
                        "visitor_id": str(pass_number) if pass_number else visitor_code,
                        "pass_number": pass_number,
                        "corp_emp_code": visitor_code,
                        "ecode": new_ecode,
                        "first_name": request.first_name,
                        "last_name": request.last_name or "",
                        "name": full_name,
                        "whom_to_visit": request.whom_to_visit,
                        "whom_ecode": whom_ecode,
                        "purpose": request.purpose,
                        "expected_in": expected_in.isoformat(),
                        "expected_out": expected_out.isoformat(),
                        "card_assigned": request.issued_card_number,
                        "issued_card_number": request.issued_card_number,
                        "api_response": str(result),
                        "method": "SaveVisitorDetailsWithAccessControl API"
                    }
                )
            else:
                logger.warning(f"[EXTENDED_API] SaveVisitorDetailsWithAccessControl returned: {result}")
                return VisitorRegistrationResponse(
                    success=False,
                    message=f"Visitor registration failed: {result}",
                    details={"error": str(result), "api_response": str(result)}
                )

        except Exception as e:
            logger.error(f"[EXTENDED_API] Visitor registration failed: {str(e)}")
            return VisitorRegistrationResponse(
                success=False,
                message=f"Registration failed: {str(e)}",
                details={"error": str(e)}
            )

    async def _get_new_id(self, table_name: str, field_name: str) -> Optional[int]:
        """
        Get the next available ID using the Oryggi GetNewID API.
        This is the same API used by Oryggi Manager Web.
        """
        try:
            result = await self._make_request(
                "GET",
                "GetNewID",
                params={
                    "TableName": table_name,
                    "FieldName": field_name
                }
            )

            # The API returns the next available ID as a number or string
            if result is not None:
                new_id = int(result) if isinstance(result, (int, str)) else None
                logger.info(f"[EXTENDED_API] GetNewID({table_name}.{field_name}) = {new_id}")
                return new_id
            return None
        except Exception as e:
            logger.error(f"[EXTENDED_API] GetNewID failed: {str(e)}")
            return None

    async def _get_id_type_code(self, id_type_name: str) -> int:
        """
        Map ID proof type name to Oryggi ID type code.
        Mapping captured from Oryggi Manager Web enrollment form:
        1 = Muti-Purpose ID
        2 = Aadhaar Card
        3 = Pan Card
        4 = Driving Licence
        5 = Passport
        6 = Voter ID
        """
        # Mapping based on actual Oryggi Manager Web dropdown options
        id_type_map = {
            "multipurpose": 1,
            "muti-purpose": 1,
            "multi-purpose": 1,
            "aadhaar": 2,
            "aadhar": 2,
            "pan": 3,
            "driving": 4,
            "dl": 4,
            "licence": 4,
            "license": 4,
            "passport": 5,
            "voter": 6,
            "voter id": 6
        }

        if not id_type_name:
            return 2  # Default to "Aadhaar Card"

        # Try to match by name
        id_type_lower = id_type_name.lower()
        for key, code in id_type_map.items():
            if key in id_type_lower:
                return code

        return 2  # Default to "Aadhaar Card"

    async def _get_purpose_code(self, purpose_name: str) -> int:
        """
        Map purpose name to Oryggi purpose code.
        Uses GetPurposeTypes API or fallback mapping.
        """
        # Default mapping based on Oryggi system
        purpose_map = {
            "meeting": 1,
            "interview": 2,
            "delivery": 3,
            "maintenance": 4,
            "visitor": 5,
            "contractor": 6,
            "other": 7
        }

        if not purpose_name:
            return 1  # Default to "Meeting"

        # Try to match by name
        purpose_lower = purpose_name.lower()
        for key, code in purpose_map.items():
            if key in purpose_lower:
                return code

        return 1  # Default to "Meeting"

    def _check_api_success(self, result: Any) -> bool:
        """Check if an API response indicates success."""
        logger.info(f"[_check_api_success] Checking result: {result!r} (type: {type(result).__name__})")

        if result is None:
            logger.debug("[_check_api_success] Result is None -> False")
            return False
        if isinstance(result, bool):
            logger.debug(f"[_check_api_success] Result is bool -> {result}")
            return result
        if isinstance(result, int):
            # Positive integers (like returned IDs) indicate success
            success = result > 0
            logger.debug(f"[_check_api_success] Result is int {result} > 0 -> {success}")
            return success
        if isinstance(result, str):
            result_lower = result.lower()
            # Check for explicit success indicators
            if "success" in result_lower or result_lower == "true":
                logger.debug("[_check_api_success] String contains 'success' -> True")
                return True
            # Check for explicit failure indicators
            if "fail" in result_lower or "error" in result_lower or result_lower == "false":
                logger.debug(f"[_check_api_success] String contains failure indicator: {result_lower} -> False")
                return False
            # If it's a numeric string (like "5" for visitor Ecode), treat as success
            if result.strip().isdigit():
                success = int(result.strip()) > 0
                logger.debug(f"[_check_api_success] Numeric string '{result}' -> {success}")
                return success
            # Default to success if not explicitly an error
            logger.debug(f"[_check_api_success] String default -> True (value: {result[:50] if len(result) > 50 else result})")
            return True
        if isinstance(result, dict):
            # Check standard success keys
            success = result.get("success", False) or result.get("Success", False)
            if success:
                logger.debug(f"[_check_api_success] Dict has success=True -> True")
                return True
            # Check Oryggi-specific returnMessage field
            return_message = result.get("returnMessage", "")
            if "success" in return_message.lower():
                logger.debug(f"[_check_api_success] Dict returnMessage contains 'success' -> True")
                return True
            # Check for positive Ecode (indicates successful creation)
            ecode = result.get("Ecode", 0)
            if ecode and int(ecode) > 0:
                logger.debug(f"[_check_api_success] Dict has positive Ecode={ecode} -> True")
                return True
            # Check for explicit failure
            if "fail" in return_message.lower():
                logger.debug(f"[_check_api_success] Dict returnMessage contains 'fail' -> False")
                return False
            logger.debug(f"[_check_api_success] Dict result -> {success}")
            return success
        logger.debug(f"[_check_api_success] Unknown type {type(result).__name__} -> True (default)")
        return True  # Assume success if we got a non-error response

    async def _generate_visitor_id(self) -> str:
        """Generate unique visitor ID with V prefix"""
        import uuid
        conn = self._get_db_connection()
        cursor = conn.cursor()

        # Get max visitor number
        cursor.execute("""
            SELECT MAX(CAST(SUBSTRING(CorpEmpCode, 2, LEN(CorpEmpCode)-1) AS INT))
            FROM EmployeeMaster
            WHERE CorpEmpCode LIKE 'V%' AND ISNUMERIC(SUBSTRING(CorpEmpCode, 2, LEN(CorpEmpCode)-1)) = 1
        """)
        result = cursor.fetchone()
        next_num = (result[0] or 0) + 1
        conn.close()

        return f"V{next_num:06d}"

    async def _assign_card_to_employee(
        self,
        cursor,
        ecode: int,
        card_number: str
    ) -> bool:
        """Assign a card to an employee in Employee_Card_Relation"""
        try:
            # Check if card already assigned
            cursor.execute(
                "SELECT ID FROM Employee_Card_Relation WHERE CardNo = ? AND Status = 1",
                (card_number,)
            )
            if cursor.fetchone():
                logger.warning(f"[EXTENDED_API] Card {card_number} already assigned")
                return False

            # Insert card relation
            cursor.execute("""
                INSERT INTO Employee_Card_Relation (Ecode, CardNo, Status, CreateDate)
                VALUES (?, ?, 1, GETDATE())
            """, (ecode, card_number))

            logger.info(f"[EXTENDED_API] Card {card_number} assigned to Ecode {ecode}")
            return True
        except Exception as e:
            logger.error(f"[EXTENDED_API] Card assignment failed: {str(e)}")
            return False

    async def _grant_visitor_access_to_group(
        self,
        cursor,
        ecode: int,
        terminal_group_id: int
    ) -> bool:
        """Grant visitor access to a terminal group"""
        try:
            # Get terminals in group
            cursor.execute("""
                SELECT TerminalID FROM TerminalGroupRelation WHERE TerminalGroupID = ?
            """, (terminal_group_id,))
            terminals = cursor.fetchall()

            for terminal in terminals:
                terminal_id = terminal[0]
                cursor.execute("""
                    INSERT INTO Employee_Terminal_Authentication_Relation (
                        Ecode, AuthenticationID, TerminalID, ScheduleID,
                        Start_date, Expiry_date, Group01, BypassTZLevel,
                        Status, DataLocation, CreateDate, ServerSync
                    )
                    VALUES (?, ?, ?, ?, GETDATE(), DATEADD(day, 1, GETDATE()), 1, 1,
                            'Pending', 'Server', GETDATE(), 0)
                """, (ecode, self.DEFAULT_AUTH_CARD, terminal_id, self.DEFAULT_SCHEDULE_ALL_ACCESS))

            logger.info(f"[EXTENDED_API] Access granted to {len(terminals)} terminals in group {terminal_group_id}")
            return True
        except Exception as e:
            logger.error(f"[EXTENDED_API] Access grant failed: {str(e)}")
            return False

    # =========================================================================
    # Temporary Card Assignment (Using Real Oryggi API)
    # =========================================================================

    async def assign_temporary_card(
        self,
        request: TemporaryCardRequest
    ) -> TemporaryCardResponse:
        """
        Assign a temporary card to a visitor, contractor, or employee.
        Uses the real Oryggi AddTemprorayCard API endpoint.

        Args:
            request: TemporaryCardRequest with card details

        Returns:
            TemporaryCardResponse with assignment status
        """
        if self.mock_mode:
            return TemporaryCardResponse(
                success=True,
                card_number=request.card_number,
                assigned_to=request.target_user_id,
                expiry=request.expiry_datetime,
                message=f"Temporary card {request.card_number} assigned (mock)",
                details={"mock": True}
            )

        try:
            logger.info(f"[EXTENDED_API] Assigning temporary card {request.card_number} to {request.target_user_id}")

            # Step 1: Get user's Ecode
            ecode = await self._get_ecode_from_employee_id(request.target_user_id)
            if not ecode:
                return TemporaryCardResponse(
                    success=False,
                    card_number=request.card_number,
                    assigned_to=request.target_user_id,
                    expiry=request.expiry_datetime,
                    message=f"User not found: {request.target_user_id}",
                    details={"error": "User not found"}
                )

            # Step 2: Check if card is available using CheckCardAvailability API
            try:
                card_check = await self._make_request(
                    "GET",
                    "CheckCardAvailability",
                    params={"CardNo": request.card_number}
                )
                if card_check and str(card_check).lower() not in ["true", "available", "success"]:
                    # Card may already be in use
                    logger.warning(f"[EXTENDED_API] Card availability check returned: {card_check}")
            except Exception as check_err:
                logger.warning(f"[EXTENDED_API] Card availability check failed: {check_err}")

            # Step 3: Set default times
            start_time = request.start_datetime or datetime.now()
            expiry_time = request.expiry_datetime

            # Step 4: Build the payload for AddTemprorayCard API
            temp_card_payload = {
                "Ecode": ecode,
                "CardNo": request.card_number,
                "StartDate": start_time.strftime("%Y-%m-%d %H:%M:%S"),
                "ExpiryDate": expiry_time.strftime("%Y-%m-%d %H:%M:%S"),
                "CardType": request.card_type.value if hasattr(request.card_type, 'value') else str(request.card_type),
                "TerminalGroupID": request.terminal_group_id or 0,
                "Reason": request.reason or "Temporary card assignment via chatbot",
                "OperatorEcode": 1,
                "IPAddress": "localhost"
            }

            logger.info(f"[EXTENDED_API] Calling AddTemprorayCard API")
            logger.debug(f"[EXTENDED_API] Payload: {temp_card_payload}")

            # Step 5: Call AddTemprorayCard API
            result = await self._make_request(
                "POST",
                "AddTemprorayCard",
                data=temp_card_payload
            )

            # Check result
            success = self._check_api_success(result)

            if success:
                logger.info(f"[EXTENDED_API] Temporary card {request.card_number} assigned successfully to Ecode {ecode}")

                # Step 6: If terminal group specified, grant access using AddAuthentication_TerminalGroup
                if request.terminal_group_id:
                    try:
                        await self._make_request(
                            "POST",
                            "AddAuthentication_TerminalGroup",
                            data={
                                "Ecode": ecode,
                                "TerminalGroupID": request.terminal_group_id,
                                "AuthenticationID": self.DEFAULT_AUTH_CARD,
                                "ScheduleID": self.DEFAULT_SCHEDULE_ALL_ACCESS,
                                "StartDate": start_time.strftime("%Y-%m-%d %H:%M:%S"),
                                "ExpiryDate": expiry_time.strftime("%Y-%m-%d %H:%M:%S")
                            }
                        )
                        logger.info(f"[EXTENDED_API] Access granted to terminal group {request.terminal_group_id}")
                    except Exception as access_err:
                        logger.warning(f"[EXTENDED_API] Terminal group access grant failed: {access_err}")

                return TemporaryCardResponse(
                    success=True,
                    card_number=request.card_number,
                    assigned_to=request.target_user_id,
                    expiry=expiry_time,
                    message=f"Temporary card {request.card_number} assigned successfully via Oryggi API",
                    details={
                        "ecode": ecode,
                        "card_number": request.card_number,
                        "card_type": request.card_type.value if hasattr(request.card_type, 'value') else str(request.card_type),
                        "start_time": start_time.isoformat(),
                        "expiry_time": expiry_time.isoformat(),
                        "terminal_group": request.terminal_group_id,
                        "api_response": str(result),
                        "method": "AddTemprorayCard API"
                    }
                )
            else:
                logger.warning(f"[EXTENDED_API] AddTemprorayCard API returned: {result}")
                return TemporaryCardResponse(
                    success=False,
                    card_number=request.card_number,
                    assigned_to=request.target_user_id,
                    expiry=expiry_time,
                    message=f"Temporary card assignment failed: {result}",
                    details={"error": str(result), "api_response": str(result)}
                )

        except Exception as e:
            logger.error(f"[EXTENDED_API] Temporary card assignment failed: {str(e)}")
            return TemporaryCardResponse(
                success=False,
                card_number=request.card_number,
                assigned_to=request.target_user_id,
                expiry=request.expiry_datetime,
                message=f"Assignment failed: {str(e)}",
                details={"error": str(e)}
            )

    # =========================================================================
    # Database Backup
    # =========================================================================

    async def backup_database(
        self,
        request: DatabaseBackupRequest
    ) -> DatabaseBackupResponse:
        """
        Create a full SQL Server backup of the Oryggi database.

        Args:
            request: DatabaseBackupRequest with backup options

        Returns:
            DatabaseBackupResponse with backup status and file path
        """
        if self.mock_mode:
            return DatabaseBackupResponse(
                success=True,
                backup_file_path="D:\\Backups\\Oryggi_mock_backup.bak",
                backup_size_mb=100.5,
                backup_duration_seconds=5.0,
                message="Database backup completed (mock)",
                details={"mock": True}
            )

        import time
        start_time = time.time()

        try:
            # Generate backup file name
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = request.backup_path or self.backup_path
            backup_file = f"{backup_path}\\{request.database_name}_{timestamp}.bak"

            # Build backup command
            backup_type_clause = ""
            if request.backup_type.value == "differential":
                backup_type_clause = "WITH DIFFERENTIAL"
            elif request.backup_type.value == "log":
                backup_type_clause = "WITH NORECOVERY"

            compression = ", COMPRESSION" if request.compression else ""

            backup_sql = f"""
                BACKUP DATABASE [{request.database_name}]
                TO DISK = '{backup_file}'
                {backup_type_clause}{compression}
            """

            # Execute backup
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute(backup_sql)
            conn.commit()
            conn.close()

            duration = time.time() - start_time

            # Get file size
            import os
            file_size_mb = os.path.getsize(backup_file) / (1024 * 1024) if os.path.exists(backup_file) else 0

            logger.info(f"[EXTENDED_API] Database backup completed: {backup_file} ({file_size_mb:.2f} MB)")

            return DatabaseBackupResponse(
                success=True,
                backup_file_path=backup_file,
                backup_size_mb=round(file_size_mb, 2),
                backup_duration_seconds=round(duration, 2),
                message=f"Database backup completed successfully",
                details={
                    "database": request.database_name,
                    "backup_type": request.backup_type.value,
                    "compression": request.compression,
                    "timestamp": timestamp
                }
            )

        except Exception as e:
            logger.error(f"[EXTENDED_API] Database backup failed: {str(e)}")
            return DatabaseBackupResponse(
                success=False,
                message=f"Backup failed: {str(e)}",
                details={"error": str(e)}
            )

    # =========================================================================
    # Card Enrollment with Door Access (Using Real Oryggi API)
    # =========================================================================

    async def enroll_card_with_access(
        self,
        request: CardEnrollmentRequest
    ) -> CardEnrollmentResponse:
        """
        Enroll a card for an employee with access to specific doors or all doors.
        Uses real Oryggi APIs: InsertCardInCardMaster and AddAuthentication_Terminal.

        Args:
            request: CardEnrollmentRequest with enrollment details

        Returns:
            CardEnrollmentResponse with enrollment status
        """
        if self.mock_mode:
            return CardEnrollmentResponse(
                success=True,
                card_number=request.card_number,
                employee_id=request.employee_id,
                employee_ecode=12345,
                doors_configured=10 if request.access_scope == AccessScope.ALL_DOORS else len(request.door_ids or []),
                message=f"Card enrolled successfully (mock)",
                details={"mock": True}
            )

        try:
            logger.info(f"[EXTENDED_API] Enrolling card {request.card_number} for employee {request.employee_id}")

            # Step 1: Get employee Ecode
            ecode = await self._get_ecode_from_employee_id(request.employee_id)
            if not ecode:
                return CardEnrollmentResponse(
                    success=False,
                    card_number=request.card_number,
                    employee_id=request.employee_id,
                    message=f"Employee not found: {request.employee_id}",
                    details={"error": "Employee not found"}
                )

            # Step 2: Check if card is duplicate using CheckDuplicateCardNo API
            try:
                dup_check = await self._make_request(
                    "GET",
                    "CheckDuplicateCardNo",
                    params={"CardNo": request.card_number}
                )
                if dup_check and str(dup_check).lower() in ["true", "duplicate", "exists"]:
                    logger.warning(f"[EXTENDED_API] Card {request.card_number} already exists")
            except Exception as check_err:
                logger.warning(f"[EXTENDED_API] Card duplicate check failed: {check_err}")

            # Step 3: Register card in CardMaster using InsertCardInCardMaster API
            try:
                card_insert_result = await self._make_request(
                    "POST",
                    "InsertCardInCardMaster",
                    data={
                        "CardNo": request.card_number,
                        "Ecode": ecode,
                        "CardType": "permanent",
                        "Status": 1,
                        "OperatorEcode": 1
                    }
                )
                logger.info(f"[EXTENDED_API] InsertCardInCardMaster result: {card_insert_result}")
            except Exception as card_err:
                logger.warning(f"[EXTENDED_API] Card master insert failed (may already exist): {card_err}")

            # Step 4: Set dates
            start_date = request.start_date or datetime.now()
            expiry_date = request.expiry_date or (datetime.now() + timedelta(days=365))

            # Step 5: Grant access to doors using real API
            doors_configured = 0
            failed_doors = []

            if request.access_scope == AccessScope.ALL_DOORS:
                # Use AddAuthentication_TerminalGroup for all doors (more efficient)
                if request.terminal_group_id:
                    try:
                        result = await self._make_request(
                            "POST",
                            "AddAuthentication_TerminalGroupV2",
                            data={
                                "Ecode": ecode,
                                "TerminalGroupID": request.terminal_group_id,
                                "AuthenticationID": request.authentication_type,
                                "ScheduleID": request.schedule_id,
                                "StartDate": start_date.strftime("%Y-%m-%d %H:%M:%S"),
                                "ExpiryDate": expiry_date.strftime("%Y-%m-%d %H:%M:%S"),
                                "OperatorEcode": 1
                            }
                        )
                        if self._check_api_success(result):
                            doors_configured = -1  # Indicates all doors via group
                            logger.info(f"[EXTENDED_API] Access granted to terminal group {request.terminal_group_id}")
                    except Exception as group_err:
                        logger.warning(f"[EXTENDED_API] Terminal group access failed: {group_err}")
                else:
                    # Get all terminals and grant access to each
                    try:
                        terminals = await self._make_request("GET", "GetAllTerminal")
                        if isinstance(terminals, list):
                            for terminal in terminals:
                                terminal_id = terminal.get("TerminalID") or terminal.get("terminalID")
                                if terminal_id:
                                    try:
                                        await self._grant_terminal_access_via_api(
                                            ecode, terminal_id, request.authentication_type,
                                            request.schedule_id, start_date, expiry_date
                                        )
                                        doors_configured += 1
                                    except Exception as term_err:
                                        failed_doors.append(terminal_id)
                    except Exception as list_err:
                        logger.warning(f"[EXTENDED_API] Get all terminals failed: {list_err}")
            else:
                # Grant access to specific doors
                terminal_ids = list(request.door_ids or [])

                # Resolve door names to IDs if provided
                if request.door_names:
                    try:
                        from app.services.terminal_service import terminal_service
                        resolved = await terminal_service.resolve_terminal_ids(
                            door_ids=request.door_ids,
                            door_names=request.door_names
                        )
                        terminal_ids = resolved
                    except Exception as resolve_err:
                        logger.warning(f"[EXTENDED_API] Door name resolution failed: {resolve_err}")

                # Grant access to each terminal using AddAuthentication_Terminal API
                for terminal_id in terminal_ids:
                    try:
                        success = await self._grant_terminal_access_via_api(
                            ecode, terminal_id, request.authentication_type,
                            request.schedule_id, start_date, expiry_date
                        )
                        if success:
                            doors_configured += 1
                        else:
                            failed_doors.append(terminal_id)
                    except Exception as term_err:
                        logger.warning(f"[EXTENDED_API] Failed to grant access to terminal {terminal_id}: {term_err}")
                        failed_doors.append(terminal_id)

            # Build response message
            if doors_configured == -1:
                message = f"Card {request.card_number} enrolled with access to all doors in group"
                doors_configured = 0  # Reset for response
            else:
                message = f"Card {request.card_number} enrolled with access to {doors_configured} doors"
            if failed_doors:
                message += f" ({len(failed_doors)} failed)"

            success = doors_configured > 0 or (request.access_scope == AccessScope.ALL_DOORS and not failed_doors)
            logger.info(f"[EXTENDED_API] {message}")

            return CardEnrollmentResponse(
                success=success,
                card_number=request.card_number,
                employee_id=request.employee_id,
                employee_ecode=ecode,
                doors_configured=doors_configured,
                failed_doors=failed_doors,
                message=message + " via Oryggi API",
                details={
                    "ecode": ecode,
                    "access_scope": request.access_scope.value,
                    "schedule_id": request.schedule_id,
                    "start_date": start_date.isoformat(),
                    "expiry_date": expiry_date.isoformat(),
                    "method": "InsertCardInCardMaster + AddAuthentication_Terminal API"
                }
            )

        except Exception as e:
            logger.error(f"[EXTENDED_API] Card enrollment failed: {str(e)}")
            return CardEnrollmentResponse(
                success=False,
                card_number=request.card_number,
                employee_id=request.employee_id,
                message=f"Enrollment failed: {str(e)}",
                details={"error": str(e)}
            )

    async def get_terminals(self) -> list:
        """
        Get list of all terminals from the system.

        Returns:
            List of terminal dictionaries with terminalID, terminalName, ipAddress, etc.
        """
        try:
            result = await self._make_request(
                "GET",
                "GetAllTerminal",
                params={"OperatorEcode": 1, "hardWareTypeID": 0}
            )
            if isinstance(result, list):
                logger.info(f"[EXTENDED_API] Retrieved {len(result)} terminals")
                return result
            else:
                logger.warning(f"[EXTENDED_API] GetAllTerminal returned non-list: {result}")
                return []
        except Exception as e:
            logger.error(f"[EXTENDED_API] get_terminals failed: {e}")
            return []

    async def get_authentication_master(self) -> List[Dict[str, Any]]:
        """
        Get all authentication types from GetAuthenticationMaster API.

        Returns:
            List of authentication type dictionaries with authenticationID, authenticationName, etc.
            Examples: Card Only, Face Only, Fusion, Card + Face, etc.
        """
        try:
            result = await self._make_request(
                "GET",
                "GetAuthenticationMaster",
                params={}
            )
            if isinstance(result, list):
                logger.info(f"[EXTENDED_API] Retrieved {len(result)} authentication types")
                return result
            else:
                logger.warning(f"[EXTENDED_API] GetAuthenticationMaster returned non-list: {result}")
                return []
        except Exception as e:
            logger.error(f"[EXTENDED_API] get_authentication_master failed: {e}")
            return []

    async def get_auth_type_id_by_name(self, auth_name: str) -> Optional[int]:
        """
        Get authentication type ID by name (case-insensitive).

        Args:
            auth_name: Authentication type name (e.g., "Fusion", "Face Only", "Card + Face")

        Returns:
            Authentication type ID or None if not found
        """
        try:
            auth_types = await self.get_authentication_master()
            auth_name_lower = auth_name.lower().strip()

            for auth in auth_types:
                name = auth.get("authenticationName", "") or auth.get("AuthenticationName", "")
                if name.lower().strip() == auth_name_lower:
                    return auth.get("authenticationID") or auth.get("AuthenticationID")

            # Try partial match
            for auth in auth_types:
                name = auth.get("authenticationName", "") or auth.get("AuthenticationName", "")
                if auth_name_lower in name.lower():
                    return auth.get("authenticationID") or auth.get("AuthenticationID")

            logger.warning(f"[EXTENDED_API] Auth type '{auth_name}' not found")
            return None
        except Exception as e:
            logger.error(f"[EXTENDED_API] get_auth_type_id_by_name failed: {e}")
            return None

    async def check_biometric_enrolled(
        self,
        ecode: int,
        biometric_type: str = "FACE"
    ) -> Dict[str, Any]:
        """
        Check if a specific biometric type is enrolled for an employee.

        Args:
            ecode: Employee Ecode
            biometric_type: Type of biometric - "FACE", "PALM", or "FINGER"

        Returns:
            Dict with enrolled status and template details
        """
        try:
            result = await self._make_request(
                "GET",
                "GetFingerListByTemplate",
                params={"Ecode": ecode, "TemplateType": biometric_type.upper()}
            )

            templates = []
            if isinstance(result, list):
                templates = result
            elif isinstance(result, dict) and "templates" in result:
                templates = result.get("templates", [])

            enrolled = len(templates) > 0

            logger.info(f"[EXTENDED_API] Biometric check for ecode={ecode}, type={biometric_type}: enrolled={enrolled}, count={len(templates)}")

            return {
                "enrolled": enrolled,
                "biometric_type": biometric_type,
                "template_count": len(templates),
                "templates": templates
            }
        except Exception as e:
            logger.error(f"[EXTENDED_API] check_biometric_enrolled failed: {e}")
            return {
                "enrolled": False,
                "biometric_type": biometric_type,
                "template_count": 0,
                "error": str(e)
            }

    async def get_employee_biometrics_status(self, ecode: int) -> Dict[str, Any]:
        """
        Get complete biometric enrollment status for an employee.

        Args:
            ecode: Employee Ecode

        Returns:
            Dict with status of all biometric types (face, palm, finger)
        """
        try:
            face_status = await self.check_biometric_enrolled(ecode, "FACE")
            palm_status = await self.check_biometric_enrolled(ecode, "PALM")
            finger_status = await self.check_biometric_enrolled(ecode, "FINGER")

            return {
                "ecode": ecode,
                "face": face_status,
                "palm": palm_status,
                "finger": finger_status,
                "has_any_biometric": (
                    face_status.get("enrolled", False) or
                    palm_status.get("enrolled", False) or
                    finger_status.get("enrolled", False)
                )
            }
        except Exception as e:
            logger.error(f"[EXTENDED_API] get_employee_biometrics_status failed: {e}")
            return {
                "ecode": ecode,
                "error": str(e),
                "has_any_biometric": False
            }

    async def _grant_terminal_access_via_api(
        self,
        ecode: int,
        terminal_id: int,
        authentication_type: int,
        schedule_id: int,
        start_date: datetime,
        expiry_date: datetime
    ) -> bool:
        """
        Grant access to a specific terminal using AddAuthentication_Terminal API.

        This method follows the same approach as the Oryggi dashboard:
        1. Call AddAuthentication_Terminal API
        2. Always call SendTCPCommand to sync (even if API returns "Failed")
        3. Verify by checking if terminal auth record exists

        Note: The API returns "Failed" both for errors AND for updates to existing records,
        so we verify success by checking the terminal auth list afterward.
        """
        try:
            # Check if employee already has access to this terminal
            existing_auth = await self._get_terminal_auth_for_employee(ecode)
            has_existing = any(
                auth.get("TerminalID") == terminal_id or auth.get("terminalID") == terminal_id
                for auth in existing_auth
            ) if existing_auth else False

            logger.info(f"[EXTENDED_API] Granting terminal access: ecode={ecode}, terminal={terminal_id}, existing={has_existing}")

            # Use AddAuthentication_Terminal (same as dashboard) with correct query params
            # Dashboard uses: POST AddAuthentication_Terminal?IPAddress=localhost&OperatorEcode=1
            # IMPORTANT: This endpoint expects a SINGLE OBJECT, not an array!
            auth_url = f"{self.base_url}/AddAuthentication_Terminal"
            auth_params = {
                "IPAddress": "localhost",
                "OperatorEcode": 1
            }
            # Single object (NOT array) - the API expects PersonAuthenticationRelation object
            auth_data = {
                "ecode": ecode,
                "terminalID": terminal_id,
                "authenticationID": authentication_type,
                "scheduleID": schedule_id,
                "expiry_date": expiry_date.strftime("%Y-%m-%d %H:%M:%S"),
                "start_date": start_date.strftime("%Y-%m-%d %H:%M:%S"),
                "group01": 1,
                "bypassTZLevel": 1,
                "isAntipassBack": 0,
                "OfflinePriority": 0,
                "UserType": 0,
                "iSDeleted": False
            }

            logger.info(f"[EXTENDED_API] Calling AddAuthentication_Terminal: {auth_url} params={auth_params}")
            logger.info(f"[EXTENDED_API] Auth data: {auth_data}")

            async with httpx.AsyncClient(timeout=30, verify=False) as client:
                response = await client.post(
                    auth_url,
                    params=auth_params,
                    json=auth_data,
                    headers={"APIKey": self.api_key}
                )
                result = response.text.strip()

            api_success = self._check_api_success(result)
            logger.info(f"[EXTENDED_API] AddAuthentication_Terminal result: {result}, api_success={api_success}")

            # Always trigger sync (as dashboard does)
            # The sync ensures the terminal device gets the updated credentials
            await self._resend_authentication_to_terminal(ecode, terminal_id)

            # Verify success by checking if terminal auth now exists
            # This handles both new additions and updates
            updated_auth = await self._get_terminal_auth_for_employee(ecode)
            has_access_now = any(
                auth.get("TerminalID") == terminal_id or auth.get("terminalID") == terminal_id
                for auth in updated_auth
            ) if updated_auth else False

            if has_access_now:
                logger.info(f"[EXTENDED_API] Terminal access verified for ecode={ecode}, terminal={terminal_id}")
                return True
            elif api_success:
                # API said success but we can't verify - trust the API
                return True
            else:
                logger.warning(f"[EXTENDED_API] Could not verify terminal access for ecode={ecode}, terminal={terminal_id}")
                return False

        except Exception as e:
            logger.error(f"[EXTENDED_API] AddAuthentication_Terminal failed: {e}")
            return False

    async def _get_terminal_auth_for_employee(self, ecode: int) -> list:
        """Get terminal authentication records for an employee."""
        try:
            result = await self._make_request(
                "GET",
                "GetTerminalAuthenticationListByEcode",
                params={"Ecode": ecode}
            )
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"[EXTENDED_API] GetTerminalAuthenticationListByEcode failed: {e}")
            return []

    async def _resend_authentication_to_terminal(
        self,
        ecode: int,
        terminal_id: int
    ) -> bool:
        """
        Send TCP command to sync authentication data to a terminal.
        Uses the SendTCPCommand API with EATR command.

        Args:
            ecode: Employee code
            terminal_id: Terminal ID to sync

        Returns:
            True if sync command was sent successfully
        """
        try:
            # Get terminal IP address
            terminals = await self.get_terminals()
            terminal_ip = None
            for terminal in terminals:
                if terminal.get("terminalID") == terminal_id or terminal.get("TerminalID") == terminal_id:
                    terminal_ip = terminal.get("ipAddress") or terminal.get("IPAddress")
                    break

            if not terminal_ip:
                logger.warning(f"[EXTENDED_API] Could not find IP for terminal {terminal_id}, skipping sync")
                return False

            # Send EATR (Enroll Authentication To Reader) command
            # Command format: EATR,<ecode>
            command = f"EATR,{ecode}"

            result = await self._make_request(
                "GET",
                "SendTCPCommand",
                params={
                    "Command": command,
                    "host": terminal_ip,
                    "LogDetail": f"Sync auth for ecode {ecode}",
                    "Port": 13000
                }
            )

            logger.info(f"[EXTENDED_API] SendTCPCommand result for terminal {terminal_id} ({terminal_ip}): {result}")
            return True

        except Exception as e:
            logger.error(f"[EXTENDED_API] SendTCPCommand failed for terminal {terminal_id}: {e}")
            return False

    async def grant_terminal_access(
        self,
        ecode: int,
        terminal_id: int = None,
        terminal_name: str = None,
        authentication_type: int = 3,  # Default: Card/Finger (3)
        schedule_id: int = 63,  # Default: All Access (63)
        start_date: datetime = None,
        expiry_date: datetime = None,
        grant_all_terminals: bool = False
    ) -> dict:
        """
        Grant terminal access to an employee.

        Args:
            ecode: Employee code (Ecode)
            terminal_id: Specific terminal ID to grant access to
            terminal_name: Terminal name (if terminal_id not provided)
            authentication_type: Authentication type (1001=Card, 2=Finger, 3=Card/Finger, 5=Face)
            schedule_id: Access schedule ID (63=All Access, 0=No Access)
            start_date: Access start date (default: now)
            expiry_date: Access expiry date (default: 5 years from now)
            grant_all_terminals: If True, grant access to all terminals

        Returns:
            dict with success status and details
        """
        try:
            # Set default dates
            if not start_date:
                start_date = datetime.now()
            if not expiry_date:
                expiry_date = datetime.now() + timedelta(days=365 * 5)  # 5 years

            # Get available terminals
            terminals = await self.get_terminals()

            if not terminals:
                return {
                    "success": False,
                    "error": "No terminals found in the system",
                    "ecode": ecode
                }

            terminals_to_grant = []

            if grant_all_terminals:
                terminals_to_grant = terminals
            elif terminal_id:
                # Find terminal by ID
                for t in terminals:
                    tid = t.get("terminalID") or t.get("TerminalID")
                    if tid == terminal_id:
                        terminals_to_grant = [t]
                        break
            elif terminal_name:
                # Find terminal by name
                for t in terminals:
                    tname = t.get("terminalName") or t.get("TerminalName") or ""
                    if terminal_name.lower() in tname.lower():
                        terminals_to_grant = [t]
                        break

            if not terminals_to_grant:
                return {
                    "success": False,
                    "error": f"Terminal not found: {terminal_id or terminal_name}",
                    "ecode": ecode,
                    "available_terminals": [
                        {
                            "id": t.get("terminalID") or t.get("TerminalID"),
                            "name": t.get("terminalName") or t.get("TerminalName")
                        }
                        for t in terminals
                    ]
                }

            # Grant access to each terminal
            success_count = 0
            failed_terminals = []
            granted_terminals = []

            for terminal in terminals_to_grant:
                tid = terminal.get("terminalID") or terminal.get("TerminalID")
                tname = terminal.get("terminalName") or terminal.get("TerminalName")

                success = await self._grant_terminal_access_via_api(
                    ecode=ecode,
                    terminal_id=tid,
                    authentication_type=authentication_type,
                    schedule_id=schedule_id,
                    start_date=start_date,
                    expiry_date=expiry_date
                )

                if success:
                    success_count += 1
                    granted_terminals.append({"id": tid, "name": tname})
                else:
                    failed_terminals.append({"id": tid, "name": tname})

            return {
                "success": success_count > 0,
                "ecode": ecode,
                "terminals_granted": success_count,
                "terminals_failed": len(failed_terminals),
                "granted_terminals": granted_terminals,
                "failed_terminals": failed_terminals,
                "authentication_type": authentication_type,
                "schedule_id": schedule_id,
                "start_date": start_date.isoformat(),
                "expiry_date": expiry_date.isoformat(),
                "message": f"Granted access to {success_count} terminal(s)" if success_count > 0 else "Failed to grant access"
            }

        except Exception as e:
            logger.error(f"[EXTENDED_API] grant_terminal_access failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "ecode": ecode
            }

    # =========================================================================
    # Card Enrollment
    # =========================================================================

    async def _get_ecode_by_corp_emp_code_db(self, corp_emp_code: str) -> Optional[int]:
        """
        Get employee ecode from database directly by CorpEmpCode.
        This is a fallback when the getEcodeByCorpEmpCode API returns -1.

        Args:
            corp_emp_code: Employee corp code (ID)

        Returns:
            int ecode or None if not found
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

            # Look up ecode by CorpEmpCode
            cursor.execute("""
                SELECT TOP 1 Ecode
                FROM EmployeeMaster
                WHERE CorpEmpCode = ?
            """, (corp_emp_code,))

            row = cursor.fetchone()
            conn.close()

            if row and row[0] and row[0] > 0:
                logger.info(f"[EXTENDED_API] Found ecode {row[0]} for CorpEmpCode {corp_emp_code} via DB")
                return row[0]

            logger.warning(f"[EXTENDED_API] CorpEmpCode {corp_emp_code} not found in DB")
            return None

        except Exception as e:
            logger.error(f"[EXTENDED_API] _get_ecode_by_corp_emp_code_db failed: {e}")
            return None

    async def _get_employee_details_by_ecode_db(self, ecode: int) -> Optional[dict]:
        """
        Get employee details from database directly using SQL query.
        This is a fallback when the API endpoint doesn't work.

        Args:
            ecode: Employee code

        Returns:
            dict with employee details or None if not found
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

            # Get employee details from EmployeeMaster table
            # Using actual column names from the table
            cursor.execute("""
                SELECT Ecode, CorpEmpCode, EmpName, FName, LName, E_mail, Telephone1,
                       Address1, Gcode, DesCode, StatusID, DateofBirth, DateofJoin,
                       Sex, Role, Catcode, PresentCardNo
                FROM EmployeeMaster
                WHERE Ecode = ?
            """, (ecode,))

            row = cursor.fetchone()
            if row:
                columns = [column[0] for column in cursor.description]
                emp_dict = dict(zip(columns, row))
                # Map to expected field names for UpdateEmployeeWithLog API
                emp_dict["DeptCode"] = emp_dict.get("Gcode", 1)
                emp_dict["Gender"] = "M" if emp_dict.get("Sex", True) else "F"
                emp_dict["RoleID"] = emp_dict.get("Role", 12)
                emp_dict["CategoryID"] = emp_dict.get("Catcode", 1)
                emp_dict["OrganizationID"] = 1  # Default
                emp_dict["Grade"] = 1  # Default
                emp_dict["Pin"] = "0"  # Default
                logger.info(f"[EXTENDED_API] Got employee details from DB for ecode {ecode}: {emp_dict.get('EmpName')}")
                conn.close()
                return emp_dict

            conn.close()
            logger.warning(f"[EXTENDED_API] Employee with ecode {ecode} not found in DB")
            return None

        except Exception as e:
            logger.error(f"[EXTENDED_API] _get_employee_details_by_ecode_db failed: {e}")
            return None

    async def check_duplicate_card(self, card_number: str, exclude_ecode: int = 0) -> dict:
        """
        Check if a card number is already in use.

        Args:
            card_number: Card number to check
            exclude_ecode: Ecode to exclude from duplicate check (for updates)

        Returns:
            dict with is_duplicate and details
        """
        try:
            result = await self._make_request(
                "GET",
                "CheckDuplicateCardNo",
                params={"CardNo": card_number, "Ecode": exclude_ecode}
            )

            # API returns different formats, handle them
            is_duplicate = False
            if result is not None:
                if isinstance(result, dict):
                    is_duplicate = result.get("isDuplicate", False) or result.get("exists", False)
                elif isinstance(result, str):
                    is_duplicate = result.lower() in ["true", "duplicate", "exists"]
                elif isinstance(result, bool):
                    is_duplicate = result

            logger.info(f"[EXTENDED_API] CheckDuplicateCardNo result for {card_number}: {result}, is_duplicate={is_duplicate}")

            return {
                "is_duplicate": is_duplicate,
                "card_number": card_number,
                "raw_response": result
            }

        except Exception as e:
            logger.error(f"[EXTENDED_API] CheckDuplicateCardNo failed: {e}")
            return {
                "is_duplicate": False,
                "card_number": card_number,
                "error": str(e)
            }

    async def enroll_card(
        self,
        ecode: int = None,
        corp_emp_code: str = None,
        card_number: str = None,
        card_type: str = "permanent",
        sync_to_terminals: bool = True
    ) -> dict:
        """
        Enroll a card for an employee. This updates the employee's PresentCardNo
        and optionally syncs to terminals.

        The card enrollment in Oryggi works by:
        1. Updating employee's PresentCardNo field via UpdateEmployeeWithLog API
        2. Optionally adding to CardMaster (for terminal access)
        3. Syncing to terminals that the employee has access to

        Args:
            ecode: Employee code (Ecode) - required if corp_emp_code not provided
            corp_emp_code: Employee corp code - used to look up ecode
            card_number: Card number to enroll
            card_type: Card type (permanent, temporary) - default: permanent
            sync_to_terminals: Whether to sync card to terminals (default: True)

        Returns:
            dict with success status and details
        """
        try:
            # Validate inputs
            if not card_number:
                return {
                    "success": False,
                    "error": "card_number is required",
                    "ecode": ecode
                }

            # Get ecode if not provided
            if not ecode and corp_emp_code:
                # First try the API
                ecode_result = await self._make_request(
                    "GET",
                    "getEcodeByCorpEmpCode",
                    params={"CorpEmpCode": corp_emp_code}
                )
                if isinstance(ecode_result, int) and ecode_result > 0:
                    ecode = ecode_result
                elif isinstance(ecode_result, dict):
                    ecode = ecode_result.get("ecode") or ecode_result.get("Ecode")
                    if ecode and ecode <= 0:
                        ecode = None
                elif isinstance(ecode_result, str) and ecode_result.lstrip('-').isdigit():
                    ecode = int(ecode_result)
                    if ecode <= 0:
                        ecode = None

                # API returned -1 or failed, try direct database lookup as fallback
                if not ecode or ecode <= 0:
                    logger.info(f"[EXTENDED_API] API returned {ecode_result}, trying direct DB lookup for {corp_emp_code}")
                    ecode = await self._get_ecode_by_corp_emp_code_db(corp_emp_code)

            # Also handle case where ecode was passed but is invalid (-1)
            if ecode and ecode <= 0:
                ecode = None

            if not ecode:
                return {
                    "success": False,
                    "error": "Could not determine ecode. Provide ecode or valid corp_emp_code.",
                    "corp_emp_code": corp_emp_code
                }

            logger.info(f"[EXTENDED_API] Enrolling card {card_number} for ecode {ecode}")

            # Check if card is duplicate
            dup_result = await self.check_duplicate_card(card_number, exclude_ecode=ecode)
            if dup_result.get("is_duplicate"):
                return {
                    "success": False,
                    "error": f"Card {card_number} is already assigned to another employee",
                    "ecode": ecode,
                    "is_duplicate": True
                }

            # Get current employee details using direct DB query
            # (API endpoint Get_Employee_Details_By_Ecode returns 404)
            emp = await self._get_employee_details_by_ecode_db(ecode)

            if not emp:
                return {
                    "success": False,
                    "error": f"Employee with ecode {ecode} not found",
                    "ecode": ecode
                }

            old_card = emp.get("PresentCardNo", "")

            # Update the employee's PresentCardNo directly in database
            # (The UpdateEmployeeWithLog API has complex parameter requirements)
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

                # Update PresentCardNo
                cursor.execute(
                    "UPDATE EmployeeMaster SET PresentCardNo = ? WHERE Ecode = ?",
                    (str(card_number), ecode)
                )
                rows_affected = cursor.rowcount
                conn.commit()
                conn.close()

                api_success = rows_affected > 0
                logger.info(f"[EXTENDED_API] Updated PresentCardNo in DB for ecode {ecode}: {rows_affected} rows affected")

            except Exception as db_err:
                logger.error(f"[EXTENDED_API] Direct DB update failed: {db_err}")
                api_success = False

            if not api_success:
                return {
                    "success": False,
                    "error": f"Failed to update employee card in database",
                    "ecode": ecode
                }

            # Verify the card was updated using direct DB query
            updated_emp = await self._get_employee_details_by_ecode_db(ecode)

            verified = False
            if updated_emp:
                verified = str(updated_emp.get("PresentCardNo", "")) == str(card_number)

            # Optionally try to add to CardMaster (for terminal access compatibility)
            card_master_success = False
            try:
                card_result = await self._make_request(
                    "POST",
                    "InsertCardInCardMaster",
                    data={
                        "CardNo": card_number,
                        "Ecode": ecode,
                        "CardType": card_type,
                        "Status": 1,
                        "OperatorEcode": 1
                    }
                )
                card_master_success = self._check_api_success(card_result)
                logger.info(f"[EXTENDED_API] InsertCardInCardMaster result: {card_result}")
            except Exception as e:
                logger.warning(f"[EXTENDED_API] InsertCardInCardMaster failed (non-fatal): {e}")

            # Sync to terminals if requested
            sync_results = []
            if sync_to_terminals:
                terminal_auth = await self._get_terminal_auth_for_employee(ecode)
                for auth in terminal_auth:
                    terminal_id = auth.get("TerminalID") or auth.get("terminalID")
                    if terminal_id:
                        sync_ok = await self._resend_authentication_to_terminal(ecode, terminal_id)
                        sync_results.append({
                            "terminal_id": terminal_id,
                            "synced": sync_ok
                        })

            return {
                "success": True,
                "ecode": ecode,
                "card_number": card_number,
                "old_card": old_card,
                "card_type": card_type,
                "verified": verified,
                "card_master_enrolled": card_master_success,
                "terminals_synced": len([s for s in sync_results if s.get("synced")]),
                "sync_results": sync_results,
                "message": f"Card {card_number} enrolled successfully for employee {ecode}"
            }

        except Exception as e:
            logger.error(f"[EXTENDED_API] enroll_card failed: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "ecode": ecode
            }

    async def get_employee_cards(self, ecode: int) -> dict:
        """
        Get all cards assigned to an employee.

        Args:
            ecode: Employee code

        Returns:
            dict with card details
        """
        try:
            # Get employee's PresentCardNo using direct DB query
            # (API endpoint Get_Employee_Details_By_Ecode returns 404)
            emp = await self._get_employee_details_by_ecode_db(ecode)

            present_card = None
            if emp:
                present_card = emp.get("PresentCardNo")

            # Get cards from CardMaster (this API may work)
            card_master = []
            try:
                card_master_result = await self._make_request(
                    "GET",
                    "getCardDetailsByEcode",
                    params={"Ecode": ecode}
                )
                if isinstance(card_master_result, list):
                    card_master = card_master_result
            except Exception as cm_err:
                logger.warning(f"[EXTENDED_API] getCardDetailsByEcode failed: {cm_err}")

            return {
                "success": True,
                "ecode": ecode,
                "present_card": present_card,
                "card_master_cards": card_master,
                "has_card": bool(present_card)
            }

        except Exception as e:
            logger.error(f"[EXTENDED_API] get_employee_cards failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "ecode": ecode
            }

    # =========================================================================
    # Employee Enrollment
    # =========================================================================

    async def enroll_employee(
        self,
        request: EmployeeEnrollmentRequest
    ) -> EmployeeEnrollmentResponse:
        """
        Enroll a new employee in the access control system.
        First tries the Oryggi InsertEmployee API, falls back to direct DB insertion if API fails.

        Args:
            request: EmployeeEnrollmentRequest with employee details

        Returns:
            EmployeeEnrollmentResponse with enrollment status
        """
        if self.mock_mode:
            return EmployeeEnrollmentResponse(
                success=True,
                ecode=99999,
                corp_emp_code=request.corp_emp_code,
                message=f"Employee {request.emp_name} enrolled (mock)",
                card_enrolled=bool(request.card_number),
                details={"mock": True}
            )

        try:
            logger.info(f"[EXTENDED_API] Enrolling employee: {request.corp_emp_code} - {request.emp_name}")

            # Use default codes for department and designation
            dept_code = 1  # Default department
            des_code = 1   # Default designation

            # Set dates
            join_date = request.join_date or datetime.now()

            # Parse first/last name from emp_name
            name_parts = request.emp_name.split(' ', 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ""

            # Sex should be boolean: True=Male, False=Female
            is_male = request.gender in ("M", "Male", "m", "male", None, "")

            # Build payload for InsertEmployee API
            address = getattr(request, 'address', '') or ""
            employee_payload = {
                "CorpEmpCode": request.corp_emp_code,
                "EmpName": request.emp_name,
                "FName": first_name,
                "LName": last_name,
                "E_mail": request.email or "",
                "Telephone1": request.phone or "",
                "Sex": is_male,
                "Active": request.active if isinstance(request.active, bool) else True,
                "Ccode": 1,
                "BranchCode": 1,
                "Dcode": dept_code or 1,
                "SecCode": 1,
                "DesCode": des_code or 1,
                "Catcode": 1,
                "Gcode": 1,
                "PresentCardNo": str(request.card_number) if request.card_number else "",
                "UserGroupID": [],
                "StatusID": 1,
                "DateofBirth": "1990-01-01T00:00:00",
                "DateofJoin": join_date.strftime("%Y-%m-%dT00:00:00"),
                "Address1": address,
                "Image": "",
                "FP1_ID": 0,
                "FP2_ID": 0,
                "DFP_ID": 0,
                "Pin": 0
            }

            # Try API first
            api_success = False
            ecode = None
            api_error = None

            try:
                logger.info(f"[EXTENDED_API] Attempting InsertEmployee API...")
                result = await self._make_request(
                    "POST",
                    "InsertEmployee",
                    params={
                        "IPAddress": "localhost",
                        "OperatorEcode": 1
                    },
                    data=employee_payload
                )
                logger.info(f"[EXTENDED_API] InsertEmployee result: {result}")

                if self._check_api_success(result):
                    api_success = True
                    if isinstance(result, dict):
                        ecode = result.get("Ecode") or result.get("ecode") or result.get("employeeId")
                else:
                    api_error = result.get("message", str(result)) if isinstance(result, dict) else str(result)
                    logger.warning(f"[EXTENDED_API] InsertEmployee API returned failure: {api_error}")
            except Exception as api_ex:
                api_error = str(api_ex)
                logger.warning(f"[EXTENDED_API] InsertEmployee API exception: {api_error}")

            # If API failed, fall back to direct database insertion
            if not api_success:
                logger.info(f"[EXTENDED_API] API failed, falling back to direct DB insertion...")
                try:
                    ecode = await self._enroll_employee_direct_db(request, first_name, last_name, is_male, dept_code, des_code, join_date)
                    if ecode:
                        api_success = True
                        logger.info(f"[EXTENDED_API] Direct DB insertion successful: Ecode={ecode}")
                except Exception as db_ex:
                    logger.error(f"[EXTENDED_API] Direct DB insertion also failed: {db_ex}")
                    return EmployeeEnrollmentResponse(
                        success=False,
                        corp_emp_code=request.corp_emp_code,
                        message=f"Failed to create employee (API: {api_error}, DB: {str(db_ex)})",
                        details={"api_error": api_error, "db_error": str(db_ex)}
                    )

            if not ecode:
                # Try to look up the employee we just created
                ecode = await self._get_ecode_from_employee_id(request.corp_emp_code)
                if not ecode:
                    logger.warning("[EXTENDED_API] Could not retrieve Ecode after creation")

            card_enrolled = False
            if request.card_number and ecode:
                try:
                    card_enrolled = await self._enroll_card_via_api(ecode, request.card_number)
                except Exception as ce:
                    logger.warning(f"[EXTENDED_API] Card enrollment failed: {ce}")

            # Setup default access if requested
            access_setup_success = False
            terminals_configured = 0
            if request.setup_default_access and ecode:
                try:
                    access_setup_success, terminals_configured = await self._setup_employee_authentication(
                        ecode=ecode,
                        authentication_type=request.authentication_type or self.DEFAULT_AUTH_CARD,
                        schedule_id=request.schedule_id,
                        terminal_group_id=request.terminal_group_id
                    )
                    logger.info(f"[EXTENDED_API] Authentication setup: success={access_setup_success}, terminals={terminals_configured}")
                except Exception as auth_err:
                    logger.warning(f"[EXTENDED_API] Authentication setup failed: {auth_err}")

            logger.info(f"[EXTENDED_API] Employee enrolled: {request.corp_emp_code} (Ecode: {ecode})")

            # Build success message
            message_parts = [f"Employee {request.emp_name} enrolled successfully"]
            if card_enrolled:
                message_parts.append(f"Card {request.card_number} assigned")
            if access_setup_success:
                auth_type_names = {1001: "Card", 2: "Fingerprint", 5: "Face", 3: "Card+Fingerprint", 6: "Card+Face"}
                auth_name = auth_type_names.get(request.authentication_type or 1001, "Card")
                message_parts.append(f"{auth_name} authentication configured for {terminals_configured} terminal(s)")

            return EmployeeEnrollmentResponse(
                success=True,
                ecode=ecode,
                corp_emp_code=request.corp_emp_code,
                message=". ".join(message_parts),
                card_enrolled=card_enrolled,
                details={
                    "ecode": ecode,
                    "name": request.emp_name,
                    "department_code": dept_code,
                    "designation_code": des_code,
                    "join_date": join_date.isoformat(),
                    "card_number": request.card_number if card_enrolled else None,
                    "method": "direct_db" if not api_success else "api",
                    "authentication_type": request.authentication_type,
                    "access_setup": access_setup_success,
                    "terminals_configured": terminals_configured
                }
            )

        except Exception as e:
            import traceback
            tb_str = traceback.format_exc()
            logger.error(f"[EXTENDED_API] Employee enrollment failed: {str(e)}\nTraceback:\n{tb_str}")
            return EmployeeEnrollmentResponse(
                success=False,
                corp_emp_code=request.corp_emp_code,
                message=f"Enrollment failed: {str(e)}",
                details={"error": str(e), "traceback": tb_str}
            )

    async def _enroll_employee_direct_db(
        self,
        request: EmployeeEnrollmentRequest,
        first_name: str,
        last_name: str,
        is_male: bool,
        dept_code: int,
        des_code: int,
        join_date: datetime
    ) -> Optional[int]:
        """
        Direct database insertion fallback when API is unavailable.
        Uses Oryggi database with Windows Authentication access.
        """
        conn = None
        try:
            # Connect to Oryggi database
            conn_str = (
                "DRIVER={ODBC Driver 17 for SQL Server};"
                "SERVER=DESKTOP-UOD2VBS\\MSSQLSERVER2022;"
                "DATABASE=Oryggi;"
                "Trusted_Connection=yes;"
            )
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()

            # Check if employee already exists
            cursor.execute("SELECT Ecode FROM EmployeeMaster WHERE CorpEmpCode = ?", (request.corp_emp_code,))
            existing = cursor.fetchone()
            if existing:
                logger.warning(f"[EXTENDED_API] Employee {request.corp_emp_code} already exists with Ecode {existing[0]}")
                return existing[0]

            # Insert employee - Ecode is an IDENTITY column, let SQL Server auto-generate it
            # Using only columns that exist in OryggiDB.EmployeeMaster
            # Disable triggers that cause issues with duty roster generation
            cursor.execute("DISABLE TRIGGER ALL ON EmployeeMaster")
            insert_sql = """
                INSERT INTO EmployeeMaster (
                    CorpEmpCode, EmpName, FName, LName, E_mail, Telephone1,
                    Sex, Active, SecCode, DesCode, Catcode, Gcode,
                    PresentCardNo, StatusID, DateofBirth, DateofJoin, Address1,
                    FP1_ID, FP2_ID, DFP_ID, Created_Date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE())
            """
            cursor.execute(insert_sql, (
                request.corp_emp_code,
                request.emp_name,
                first_name,
                last_name,
                request.email or "",
                request.phone or "",
                1 if is_male else 0,  # SQL uses int for boolean
                1,  # Active
                1,  # SecCode
                des_code,
                1,  # Catcode
                1,  # Gcode
                request.card_number or "",
                1,  # StatusID
                "1990-01-01",
                join_date.strftime("%Y-%m-%d"),
                getattr(request, 'address', '') or "",
                0,  # FP1_ID
                0,  # FP2_ID
                0   # DFP_ID
            ))
            conn.commit()

            # Get the generated Ecode using SCOPE_IDENTITY()
            cursor.execute("SELECT SCOPE_IDENTITY()")
            new_ecode = cursor.fetchone()[0]

            # Re-enable triggers
            cursor.execute("ENABLE TRIGGER ALL ON EmployeeMaster")
            conn.commit()

            logger.info(f"[EXTENDED_API] Direct DB insert successful: Ecode={new_ecode}")
            return int(new_ecode) if new_ecode else None

        except Exception as e:
            if conn:
                try:
                    # Make sure triggers are re-enabled even on error
                    cursor.execute("ENABLE TRIGGER ALL ON EmployeeMaster")
                    conn.commit()
                except:
                    pass
                conn.rollback()
            raise e
        finally:
            if conn:
                conn.close()

    async def _enroll_card_via_api(self, ecode: int, card_number: str) -> bool:
        """Helper method to enroll a card for an employee using InsertCardInCardMaster API."""
        try:
            # Check if card already exists
            dup_check = await self._make_request(
                "GET",
                "CheckDuplicateCardNo",
                params={"CardNo": card_number}
            )

            if dup_check and (dup_check.get("isDuplicate") or dup_check.get("exists")):
                logger.warning(f"[EXTENDED_API] Card {card_number} already exists")
                return False

            # Insert card
            card_result = await self._make_request(
                "POST",
                "InsertCardInCardMaster",
                data={
                    "CardNo": card_number,
                    "Ecode": ecode,
                    "CardType": "permanent",
                    "Status": 1,
                    "OperatorEcode": 1
                }
            )

            return self._check_api_success(card_result)
        except Exception as e:
            logger.error(f"[EXTENDED_API] Card enrollment via API failed: {e}")
            return False

    # =========================================================================
    # Employee Create/Update (Using Frontend API - UpdateEmployeeWithLog)
    # =========================================================================

    async def create_or_update_employee(
        self,
        request: EmployeeCreateUpdateRequest,
        operator_ecode: int = 1
    ) -> EmployeeCreateUpdateResponse:
        """
        Create or update an employee using the UpdateEmployeeWithLog API.
        This is the same API used by Oryggi Manager Web frontend.

        The frontend uses this single API for both create and update operations.
        It matches the payload captured via Playwright from the actual frontend.

        Args:
            request: EmployeeCreateUpdateRequest with employee details
            operator_ecode: Ecode of the operator performing the operation

        Returns:
            EmployeeCreateUpdateResponse with success status and employee details
        """
        if self.mock_mode:
            return EmployeeCreateUpdateResponse(
                success=True,
                ecode=99999,
                corp_emp_code=request.corp_emp_code,
                emp_name=request.emp_name,
                operation="update" if request.is_update else "create",
                message=f"Employee {request.emp_name} {'updated' if request.is_update else 'created'} (mock)",
                card_enrolled=bool(request.card_number),
                details={"mock": True}
            )

        try:
            operation = "update" if request.is_update else "create"
            logger.info(f"[EXTENDED_API] {operation.title()}ing employee via UpdateEmployeeWithLog: {request.corp_emp_code} - {request.emp_name}")

            # Step 1: For create, get new Ecode. For update, use provided Ecode or look it up.
            ecode = request.ecode
            if not request.is_update:
                # Get new Ecode for new employee
                new_ecode = await self._get_new_id("EmployeeMaster", "Ecode")
                if not new_ecode:
                    return EmployeeCreateUpdateResponse(
                        success=False,
                        corp_emp_code=request.corp_emp_code,
                        emp_name=request.emp_name,
                        operation=operation,
                        message="Failed to get new employee ID from Oryggi API",
                        details={"error": "GetNewID API failed"}
                    )
                ecode = new_ecode
                logger.info(f"[EXTENDED_API] New Ecode assigned: {ecode}")
            else:
                # For update, look up Ecode if not provided
                if not ecode:
                    ecode = await self._get_ecode_from_employee_id(request.corp_emp_code)
                    if not ecode:
                        return EmployeeCreateUpdateResponse(
                            success=False,
                            corp_emp_code=request.corp_emp_code,
                            emp_name=request.emp_name,
                            operation=operation,
                            message=f"Employee not found: {request.corp_emp_code}",
                            details={"error": "Employee not found for update"}
                        )

            # Step 2: Parse name into first/last if not provided
            first_name = request.first_name
            last_name = request.last_name
            if not first_name:
                name_parts = request.emp_name.split(' ', 1)
                first_name = name_parts[0]
                last_name = name_parts[1] if len(name_parts) > 1 else ""

            # Step 3: Resolve department code if name provided
            dept_code = request.department_code or 1
            if request.department_name and not request.department_code:
                dept_code = await self._resolve_department_code(request.department_name) or 1

            # Step 4: Resolve designation code if name provided
            des_code = request.designation_code or 0
            if request.designation_name and not request.designation_code:
                des_code = await self._resolve_designation_code(request.designation_name) or 0

            # Step 5: Set dates
            join_date = request.join_date or datetime.now()
            start_date = request.start_date or datetime.now()
            expiry_date = request.expiry_date or (datetime.now() + timedelta(days=3650))  # 10 years

            # Step 6: Build the employee payload matching working Oryggi API format
            # Verified via direct curl test - this format returns "Enrolled Successfully"
            employee_payload = {
                # Core identity
                "Ecode": ecode,
                "CorpEmpCode": request.corp_emp_code,
                "EmpName": request.emp_name,
                "FName": first_name,
                "LName": last_name or "",

                # Contact info
                "E_mail": request.email or "",
                "Telephone1": request.phone or "",

                # Gender (must be boolean: True=Male, False=Female)
                "Sex": True if (request.gender == "M" or not request.gender) else False,

                # Status (must be boolean)
                "Active": True if request.active else False,

                # Organization structure - use correct field names
                "Ccode": request.company_code or 1,
                "BranchCode": request.branch_code or 1,
                "Dcode": dept_code,
                "SecCode": request.section_code or 1,  # Correct field name (was Scode)
                "DesCode": des_code or 1,  # Correct field name (was Descode)
                "Catcode": request.category_code or 1,  # Correct field name (was CategoryCode)
                "Gcode": request.grade_code or 1,

                # Access control
                "PresentCardNo": request.card_number or "",
                "UserGroupID": [],  # Empty array - not [user_group_id]

                # Dates
                "DateofBirth": "1990-01-01T00:00:00",
                "DateofJoin": join_date.strftime("%Y-%m-%dT00:00:00"),

                # Status
                "StatusID": request.status_id or 1,

                # Address
                "Address1": request.address or "",

                # Image
                "Image": request.image or "",

                # Fingerprint placeholders (required by API, 0 = not enrolled)
                "FP1_ID": 0,
                "FP2_ID": 0,
                "DFP_ID": 0,
                "Pin": 0
            }

            # Step 7: Call the appropriate API based on operation type
            # - InsertEmployee for CREATE (as used by frontend)
            # - UpdateEmployeeWithLog for UPDATE
            if request.is_update:
                api_endpoint = "UpdateEmployeeWithLog"
                logger.info(f"[EXTENDED_API] Calling UpdateEmployeeWithLog API for update")
            else:
                api_endpoint = "InsertEmployee"
                logger.info(f"[EXTENDED_API] Calling InsertEmployee API for create")

            logger.debug(f"[EXTENDED_API] Payload: {employee_payload}")

            result = await self._make_request(
                "POST",
                api_endpoint,
                params={
                    "IPAddress": "localhost",
                    "OperatorEcode": operator_ecode
                },
                data=employee_payload
            )

            # Step 8: Check result
            logger.info(f"[EXTENDED_API] {api_endpoint} raw result: {result!r} (type: {type(result).__name__})")

            success = self._check_api_success(result)

            card_enrolled = False
            access_granted = False

            if success:
                # Step 9: Handle card enrollment if card number provided
                if request.card_number:
                    try:
                        # Check if card is duplicate
                        dup_check = await self._make_request(
                            "GET",
                            "CheckDuplicateCardNo",
                            params={"CardNo": request.card_number, "Ecode": ecode}
                        )

                        # Add card to CardMaster if not duplicate
                        if not dup_check or str(dup_check).lower() not in ["true", "duplicate"]:
                            card_result = await self._make_request(
                                "POST",
                                "AddCardInCardMaster",
                                data={
                                    "CardNo": request.card_number,
                                    "Ecode": ecode,
                                    "CardType": "permanent",
                                    "Status": 1
                                }
                            )
                            card_enrolled = self._check_api_success(card_result)
                            logger.info(f"[EXTENDED_API] Card enrollment result: {card_enrolled}")
                    except Exception as card_err:
                        logger.warning(f"[EXTENDED_API] Card enrollment failed: {card_err}")

                logger.info(f"[EXTENDED_API] Employee {operation}d successfully: {request.corp_emp_code} (Ecode: {ecode})")

                return EmployeeCreateUpdateResponse(
                    success=True,
                    ecode=ecode,
                    corp_emp_code=request.corp_emp_code,
                    emp_name=request.emp_name,
                    operation=operation,
                    message=f"Employee {request.emp_name} {operation}d successfully via Oryggi API",
                    card_enrolled=card_enrolled,
                    access_granted=access_granted,
                    details={
                        "ecode": ecode,
                        "corp_emp_code": request.corp_emp_code,
                        "name": request.emp_name,
                        "department_code": dept_code,
                        "designation_code": des_code,
                        "email": request.email,
                        "phone": request.phone,
                        "card_number": request.card_number if card_enrolled else None,
                        "join_date": join_date.isoformat(),
                        "api_response": str(result),
                        "method": "UpdateEmployeeWithLog API"
                    }
                )
            else:
                logger.warning(f"[EXTENDED_API] UpdateEmployeeWithLog returned: {result}")
                return EmployeeCreateUpdateResponse(
                    success=False,
                    corp_emp_code=request.corp_emp_code,
                    emp_name=request.emp_name,
                    operation=operation,
                    message=f"Employee {operation} failed: {result}",
                    details={"error": str(result), "api_response": str(result)}
                )

        except Exception as e:
            logger.error(f"[EXTENDED_API] Employee {operation} failed: {str(e)}")
            return EmployeeCreateUpdateResponse(
                success=False,
                corp_emp_code=request.corp_emp_code,
                emp_name=request.emp_name,
                operation=operation if 'operation' in dir() else "create",
                message=f"Operation failed: {str(e)}",
                details={"error": str(e)}
            )

    async def _resolve_department_code(self, department_name: str) -> Optional[int]:
        """Resolve department name to code using API."""
        try:
            dept_list = await self._make_request(
                "GET",
                "Get_DepartmentDetail_By_BranchCode",
                params={"BranchCode": 1}
            )
            if dept_list and isinstance(dept_list, list):
                for dept in dept_list:
                    dept_name_field = dept.get("Dname") or dept.get("DeptName") or dept.get("dname") or ""
                    if department_name.lower() in dept_name_field.lower():
                        return int(dept.get("Dcode") or dept.get("DeptCode") or dept.get("dcode") or 0)
            return None
        except Exception as e:
            logger.warning(f"[EXTENDED_API] Department resolution failed: {e}")
            return None

    async def _resolve_designation_code(self, designation_name: str) -> Optional[int]:
        """Resolve designation name to code using API."""
        try:
            des_list = await self._make_request(
                "GET",
                "Get_Designation_Detail"
            )
            if des_list and isinstance(des_list, list):
                for des in des_list:
                    des_name_field = des.get("DesName") or des.get("Desname") or des.get("desname") or ""
                    if designation_name.lower() in des_name_field.lower():
                        return int(des.get("Descode") or des.get("DesCode") or des.get("descode") or 0)
            return None
        except Exception as e:
            logger.warning(f"[EXTENDED_API] Designation resolution failed: {e}")
            return None

    # =========================================================================
    # Door-Specific Access Management
    # =========================================================================

    async def manage_door_access(
        self,
        request: DoorAccessRequest
    ) -> DoorAccessResponse:
        """
        Grant or block access to specific doors for an employee.
        Uses the real Oryggi AddAuthentication_Terminal and RemoveAuthentication_Terminal APIs.

        Args:
            request: DoorAccessRequest with action and door details

        Returns:
            DoorAccessResponse with operation status
        """
        if self.mock_mode:
            return DoorAccessResponse(
                success=True,
                employee_id=request.employee_id,
                employee_ecode=12345,
                action=request.action.value,
                doors_affected=len(request.door_ids or []) + len(request.door_names or []),
                message=f"Access {request.action.value} for specified doors (mock)",
                details={"mock": True}
            )

        try:
            logger.info(f"[EXTENDED_API] Managing door access for {request.employee_id}, action: {request.action.value}")

            # Step 1: Get employee Ecode
            ecode = await self._get_ecode_from_employee_id(request.employee_id)
            if not ecode:
                return DoorAccessResponse(
                    success=False,
                    employee_id=request.employee_id,
                    action=request.action.value,
                    message=f"Employee not found: {request.employee_id}",
                    details={"error": "Employee not found"}
                )

            # Step 2: Resolve terminal IDs
            from app.services.terminal_service import terminal_service
            terminal_ids = await terminal_service.resolve_terminal_ids(
                door_ids=request.door_ids,
                door_names=request.door_names
            )

            if not terminal_ids:
                return DoorAccessResponse(
                    success=False,
                    employee_id=request.employee_id,
                    employee_ecode=ecode,
                    action=request.action.value,
                    message="No valid doors specified",
                    details={"error": "Could not resolve any door IDs or names"}
                )

            # Step 3: Determine schedule based on action
            schedule_id = (
                request.schedule_id or self.DEFAULT_SCHEDULE_ALL_ACCESS
                if request.action == DoorAction.GRANT
                else self.DEFAULT_SCHEDULE_NO_ACCESS
            )

            # Step 4: Set dates
            start_date = request.start_date or datetime.now()
            end_date = request.end_date or (datetime.now() + timedelta(days=365))

            doors_affected = 0
            failed_doors = []

            # Step 5: Process each terminal using the appropriate API
            for terminal_id in terminal_ids:
                try:
                    if request.action == DoorAction.GRANT:
                        # Use AddAuthentication_Terminal API to grant access
                        success = await self._grant_door_access_via_api(
                            ecode=ecode,
                            terminal_id=terminal_id,
                            schedule_id=schedule_id,
                            start_date=start_date,
                            end_date=end_date
                        )
                    else:  # BLOCK
                        # Use RemoveAuthentication_Terminal API to block access
                        success = await self._block_door_access_via_api(
                            ecode=ecode,
                            terminal_id=terminal_id
                        )

                    if success:
                        doors_affected += 1
                    else:
                        failed_doors.append(terminal_id)

                except Exception as te:
                    logger.warning(f"[EXTENDED_API] Failed to manage terminal {terminal_id}: {te}")
                    failed_doors.append(terminal_id)

            success = doors_affected > 0
            action_word = "granted" if request.action == DoorAction.GRANT else "blocked"
            message = f"Access {action_word} for {doors_affected} doors via Oryggi API"
            if failed_doors:
                message += f" ({len(failed_doors)} failed)"

            logger.info(f"[EXTENDED_API] {message} for employee {request.employee_id}")

            return DoorAccessResponse(
                success=success,
                employee_id=request.employee_id,
                employee_ecode=ecode,
                action=request.action.value,
                doors_affected=doors_affected,
                failed_doors=failed_doors,
                message=message,
                details={
                    "ecode": ecode,
                    "terminal_ids": terminal_ids,
                    "schedule_id": schedule_id,
                    "start_date": start_date.isoformat() if request.action == DoorAction.GRANT else None,
                    "end_date": end_date.isoformat() if request.action == DoorAction.GRANT else None,
                    "reason": request.reason,
                    "api_used": "AddAuthentication_Terminal" if request.action == DoorAction.GRANT else "RemoveAuthentication_Terminal"
                }
            )

        except Exception as e:
            logger.error(f"[EXTENDED_API] Door access management failed: {str(e)}")
            return DoorAccessResponse(
                success=False,
                employee_id=request.employee_id,
                action=request.action.value,
                message=f"Operation failed: {str(e)}",
                details={"error": str(e)}
            )

    async def _grant_door_access_via_api(
        self,
        ecode: int,
        terminal_id: int,
        schedule_id: int,
        start_date: datetime,
        end_date: datetime
    ) -> bool:
        """Grant access to a specific door using AddAuthentication_Terminal API."""
        try:
            # Build payload for AddAuthentication_Terminal
            payload = {
                "ecode": ecode,
                "terminalID": str(terminal_id),
                "authenticationID": 1001,  # Card authentication
                "scheduleID": schedule_id,
                "expiry_date": end_date.strftime("%Y-%m-%d %H:%M:%S"),
                "start_date": start_date.strftime("%Y-%m-%d %H:%M:%S"),
                "group01": 1,
                "bypassTZLevel": 1,
                "isAntipassBack": 0,
                "OfflinePriority": 0,
                "UserType": 0,
                "iSDeleted": False
            }

            logger.info(f"[EXTENDED_API] Calling AddAuthentication_Terminal for ecode={ecode}, terminal={terminal_id}")

            result = await self._make_request(
                "POST",
                "AddAuthentication_Terminal",
                data=payload
            )

            success = self._check_api_success(result)

            if success:
                # Trigger sync to terminal
                await self._resend_authentication_to_terminal(ecode, terminal_id)
                logger.info(f"[EXTENDED_API] Access granted via API: ecode={ecode}, terminal={terminal_id}")
            else:
                logger.warning(f"[EXTENDED_API] AddAuthentication_Terminal failed: {result}")

            return success

        except Exception as e:
            logger.error(f"[EXTENDED_API] _grant_door_access_via_api failed: {e}")
            return False

    async def _block_door_access_via_api(
        self,
        ecode: int,
        terminal_id: int
    ) -> bool:
        """Block access to a specific door using RemoveAuthentication_Terminal API."""
        try:
            # Build payload for RemoveAuthentication_Terminal
            payload = {
                "ecode": ecode,
                "terminalID": str(terminal_id),
                "authenticationID": 1001  # Card authentication
            }

            logger.info(f"[EXTENDED_API] Calling RemoveAuthentication_Terminal for ecode={ecode}, terminal={terminal_id}")

            result = await self._make_request(
                "POST",
                "RemoveAuthentication_Terminal",
                data=payload
            )

            success = self._check_api_success(result)

            if success:
                # Trigger sync to terminal
                await self._resend_authentication_to_terminal(ecode, terminal_id)
                logger.info(f"[EXTENDED_API] Access blocked via API: ecode={ecode}, terminal={terminal_id}")
            else:
                # If RemoveAuthentication_Terminal fails, try setting schedule to 0 (no access)
                logger.warning(f"[EXTENDED_API] RemoveAuthentication_Terminal returned: {result}, trying schedule update")
                # Fallback: Update existing authentication to schedule 0
                fallback_payload = {
                    "ecode": ecode,
                    "terminalID": str(terminal_id),
                    "authenticationID": 1001,
                    "scheduleID": 0,  # No access schedule
                    "expiry_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "start_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "group01": 1,
                    "bypassTZLevel": 1,
                    "isAntipassBack": 0,
                    "OfflinePriority": 0,
                    "UserType": 0,
                    "iSDeleted": True  # Mark as deleted
                }
                fallback_result = await self._make_request(
                    "POST",
                    "AddAuthentication_Terminal",
                    data=fallback_payload
                )
                success = self._check_api_success(fallback_result)

            return success

        except Exception as e:
            logger.error(f"[EXTENDED_API] _block_door_access_via_api failed: {e}")
            return False

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _get_db_connection(self) -> pyodbc.Connection:
        """Get database connection to Oryggi database"""
        conn_str = (
            "DRIVER={ODBC Driver 17 for SQL Server};"
            "SERVER=DESKTOP-UOD2VBS\\MSSQLSERVER2022;"
            "DATABASE=Oryggi;"
            "Trusted_Connection=yes;"
        )
        return pyodbc.connect(conn_str)

    # =========================================================================
    # Authentication Setup Methods
    # =========================================================================

    async def _setup_employee_authentication(
        self,
        ecode: int,
        authentication_type: int = 1001,
        schedule_id: int = 63,
        terminal_group_id: Optional[int] = None
    ) -> tuple:
        """
        Setup authentication for an employee on all terminals or a specific terminal group.

        Args:
            ecode: Employee Ecode
            authentication_type: Auth type (1001=card, 2=fingerprint, 5=face, etc.)
            schedule_id: Schedule ID (63=all access, 0=no access)
            terminal_group_id: Optional terminal group ID (if None, uses all terminals)

        Returns:
            Tuple of (success: bool, terminals_configured: int)
        """
        try:
            logger.info(f"[EXTENDED_API] Setting up authentication for ecode={ecode}, auth_type={authentication_type}")

            start_date = datetime.now()
            expiry_date = datetime.now() + timedelta(days=365)  # 1 year validity
            terminals_configured = 0

            # If terminal group specified, use AddAuthentication_TerminalGroupV2
            if terminal_group_id:
                try:
                    result = await self._make_request(
                        "POST",
                        "AddAuthentication_TerminalGroupV2",
                        data={
                            "Ecode": ecode,
                            "TerminalGroupID": terminal_group_id,
                            "AuthenticationID": authentication_type,
                            "ScheduleID": schedule_id,
                            "StartDate": start_date.strftime("%Y-%m-%d %H:%M:%S"),
                            "ExpiryDate": expiry_date.strftime("%Y-%m-%d %H:%M:%S"),
                            "OperatorEcode": 1
                        }
                    )
                    if self._check_api_success(result):
                        logger.info(f"[EXTENDED_API] Authentication set up via terminal group {terminal_group_id}")
                        return (True, -1)  # -1 indicates all doors via group
                except Exception as group_err:
                    logger.warning(f"[EXTENDED_API] Terminal group auth failed: {group_err}")

            # Otherwise, get all terminals and grant access to each
            try:
                terminals = await self.get_terminals()
                if not terminals:
                    logger.warning("[EXTENDED_API] No terminals found for authentication setup")
                    return (False, 0)

                for terminal in terminals:
                    terminal_id = terminal.get("TerminalID") or terminal.get("terminalID")
                    if terminal_id:
                        try:
                            success = await self._grant_terminal_access_via_api(
                                ecode, terminal_id, authentication_type,
                                schedule_id, start_date, expiry_date
                            )
                            if success:
                                terminals_configured += 1
                        except Exception as term_err:
                            logger.warning(f"[EXTENDED_API] Terminal {terminal_id} auth failed: {term_err}")

                logger.info(f"[EXTENDED_API] Authentication configured for {terminals_configured}/{len(terminals)} terminals")
                return (terminals_configured > 0, terminals_configured)

            except Exception as list_err:
                logger.error(f"[EXTENDED_API] Get terminals for auth setup failed: {list_err}")
                return (False, 0)

        except Exception as e:
            logger.error(f"[EXTENDED_API] _setup_employee_authentication failed: {e}")
            return (False, 0)

    async def add_authentication_for_employee(
        self,
        ecode: int,
        authentication_type: Optional[int] = None,
        authentication_type_name: Optional[str] = None,
        terminal_ids: Optional[List[int]] = None,
        terminal_group_id: Optional[int] = None,
        schedule_id: int = 63,
        check_biometrics: bool = True
    ) -> Dict[str, Any]:
        """
        Add authentication type to an existing employee.
        Can be used to add new authentication methods (card, fingerprint, face) to employees.

        IMPORTANT: For biometric auth types (Face, Fusion, etc.), the employee must have
        biometrics enrolled first via the Oryggi Manager dashboard before this will work.

        Args:
            ecode: Employee Ecode
            authentication_type: Auth type ID (e.g., 13=Fusion, 5=Face Only, 1001=Card Only)
            authentication_type_name: Auth type name (e.g., "Fusion", "Face Only", "Card + Face")
                                     If provided, will look up the ID from GetAuthenticationMaster
            terminal_ids: Specific terminal IDs (if None and no group, uses all terminals)
            terminal_group_id: Terminal group ID (overrides terminal_ids)
            schedule_id: Schedule ID (63=all access)
            check_biometrics: If True, check if biometrics are enrolled before setting biometric auth

        Returns:
            Dict with success status and details
        """
        try:
            # Resolve auth type by name if provided
            auth_type_id = authentication_type
            auth_type_display_name = None

            if authentication_type_name and not authentication_type:
                auth_type_id = await self.get_auth_type_id_by_name(authentication_type_name)
                if not auth_type_id:
                    return {
                        "success": False,
                        "message": f"Authentication type '{authentication_type_name}' not found. "
                                   f"Use GetAuthenticationMaster to see available types.",
                        "error": "Invalid authentication type name"
                    }
                auth_type_display_name = authentication_type_name

            if not auth_type_id:
                return {
                    "success": False,
                    "message": "No authentication type specified. Provide either authentication_type (ID) or authentication_type_name.",
                    "error": "Missing authentication type"
                }

            logger.info(f"[EXTENDED_API] Adding auth type {auth_type_id} ({auth_type_display_name or 'by ID'}) for ecode={ecode}")

            # Check if biometrics are required and enrolled
            # Auth types that require biometrics (face, palm, finger, fusion, etc.)
            biometric_auth_keywords = ["face", "fusion", "finger", "palm", "iris", "biometric"]

            requires_biometric = False
            if auth_type_display_name:
                requires_biometric = any(kw in auth_type_display_name.lower() for kw in biometric_auth_keywords)
            else:
                # Check by getting the name from master
                auth_types = await self.get_authentication_master()
                for auth in auth_types:
                    if (auth.get("authenticationID") or auth.get("AuthenticationID")) == auth_type_id:
                        name = auth.get("authenticationName", "") or auth.get("AuthenticationName", "")
                        auth_type_display_name = name
                        requires_biometric = any(kw in name.lower() for kw in biometric_auth_keywords)
                        break

            if requires_biometric and check_biometrics:
                biometric_status = await self.get_employee_biometrics_status(ecode)

                if not biometric_status.get("has_any_biometric", False):
                    return {
                        "success": False,
                        "message": f"Cannot set '{auth_type_display_name or auth_type_id}' authentication: "
                                   f"Employee (ecode={ecode}) has no biometric data enrolled. "
                                   f"Please enroll biometrics first via Oryggi Manager dashboard "
                                   f"(Biometric tab → Select device → Capture face/palm/finger).",
                        "error": "Biometrics not enrolled",
                        "biometric_status": biometric_status,
                        "requires_enrollment": True
                    }

                logger.info(f"[EXTENDED_API] Biometric check passed for ecode={ecode}: {biometric_status}")

            start_date = datetime.now()
            expiry_date = datetime.now() + timedelta(days=365)
            terminals_configured = 0
            failed_terminals = []

            # Use terminal group if specified
            if terminal_group_id:
                result = await self._make_request(
                    "POST",
                    "AddAuthentication_TerminalGroupV2",
                    data={
                        "Ecode": ecode,
                        "TerminalGroupID": terminal_group_id,
                        "AuthenticationID": auth_type_id,
                        "ScheduleID": schedule_id,
                        "StartDate": start_date.strftime("%Y-%m-%d %H:%M:%S"),
                        "ExpiryDate": expiry_date.strftime("%Y-%m-%d %H:%M:%S"),
                        "OperatorEcode": 1
                    }
                )
                if self._check_api_success(result):
                    return {
                        "success": True,
                        "message": f"'{auth_type_display_name or auth_type_id}' authentication added for terminal group {terminal_group_id}",
                        "authentication_type": auth_type_display_name or auth_type_id,
                        "terminals_configured": -1
                    }

            # Get terminals to configure
            if terminal_ids:
                target_terminals = terminal_ids
            else:
                # Get all terminals
                all_terminals = await self.get_terminals()
                target_terminals = [
                    t.get("TerminalID") or t.get("terminalID")
                    for t in all_terminals
                    if t.get("TerminalID") or t.get("terminalID")
                ]

            # Configure each terminal
            for terminal_id in target_terminals:
                try:
                    success = await self._grant_terminal_access_via_api(
                        ecode, terminal_id, auth_type_id,
                        schedule_id, start_date, expiry_date
                    )
                    if success:
                        terminals_configured += 1
                    else:
                        failed_terminals.append(terminal_id)
                except Exception as term_err:
                    logger.warning(f"[EXTENDED_API] Terminal {terminal_id} auth add failed: {term_err}")
                    failed_terminals.append(terminal_id)

            # Use resolved display name or fallback to common names
            auth_name = auth_type_display_name
            if not auth_name:
                auth_type_names = {1001: "Card", 2: "Fingerprint", 5: "Face", 3: "Card+Fingerprint", 6: "Card+Face", 13: "Fusion"}
                auth_name = auth_type_names.get(auth_type_id, f"Type {auth_type_id}")

            return {
                "success": terminals_configured > 0,
                "message": f"{auth_name} authentication configured for {terminals_configured} terminal(s)",
                "terminals_configured": terminals_configured,
                "failed_terminals": failed_terminals
            }

        except Exception as e:
            logger.error(f"[EXTENDED_API] add_authentication_for_employee failed: {e}")
            return {
                "success": False,
                "message": f"Failed to add authentication: {str(e)}",
                "error": str(e)
            }

    async def remove_authentication_for_employee(
        self,
        ecode: int,
        authentication_type: int,
        terminal_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Remove authentication type from an existing employee.

        Args:
            ecode: Employee Ecode
            authentication_type: Auth type to remove (1001=card, 2=fingerprint, 5=face, etc.)
            terminal_ids: Specific terminal IDs (if None, removes from all terminals)

        Returns:
            Dict with success status and details
        """
        try:
            logger.info(f"[EXTENDED_API] Removing auth type {authentication_type} for ecode={ecode}")

            terminals_removed = 0
            failed_terminals = []

            # Get terminals to remove from
            if terminal_ids:
                target_terminals = terminal_ids
            else:
                # Get all terminals where employee has this auth type
                all_auth = await self._get_terminal_auth_for_employee(ecode)
                target_terminals = [
                    auth.get("TerminalID") or auth.get("terminalID")
                    for auth in all_auth
                    if (auth.get("AuthenticationID") or auth.get("authenticationID")) == authentication_type
                ]

            # Remove from each terminal
            for terminal_id in target_terminals:
                try:
                    payload = {
                        "ecode": ecode,
                        "terminalID": str(terminal_id),
                        "authenticationID": authentication_type
                    }
                    result = await self._make_request(
                        "POST",
                        "RemoveAuthentication_Terminal",
                        data=payload
                    )
                    if self._check_api_success(result):
                        terminals_removed += 1
                    else:
                        failed_terminals.append(terminal_id)
                except Exception as term_err:
                    logger.warning(f"[EXTENDED_API] Terminal {terminal_id} auth remove failed: {term_err}")
                    failed_terminals.append(terminal_id)

            auth_type_names = {1001: "Card", 2: "Fingerprint", 5: "Face", 3: "Card+Fingerprint", 6: "Card+Face"}
            auth_name = auth_type_names.get(authentication_type, f"Type {authentication_type}")

            return {
                "success": terminals_removed > 0 or len(target_terminals) == 0,
                "message": f"{auth_name} authentication removed from {terminals_removed} terminal(s)",
                "terminals_removed": terminals_removed,
                "failed_terminals": failed_terminals
            }

        except Exception as e:
            logger.error(f"[EXTENDED_API] remove_authentication_for_employee failed: {e}")
            return {
                "success": False,
                "message": f"Failed to remove authentication: {str(e)}",
                "error": str(e)
            }

    # =========================================================================
    # Biometric Enrollment Trigger (Device-based enrollment)
    # =========================================================================

    # TCP Commands for biometric device enrollment
    BIOMETRIC_ENROLL_COMMANDS = {
        "face": "CENR",      # Camera/Face Enroll
        "palm": "PENR",      # Palm Enroll
        "finger": "FENR",    # Finger Enroll
        "all": "BENR",       # All Biometrics Enroll
    }

    async def trigger_biometric_enrollment(
        self,
        ecode: int,
        biometric_type: str,
        terminal_id: Optional[int] = None,
        terminal_name: Optional[str] = None,
        timeout_seconds: int = 60
    ) -> Dict[str, Any]:
        """
        Trigger biometric enrollment mode on a device for an employee.

        This sends a TCP command to the biometric device to enter enrollment mode.
        The employee must then physically present their biometric (face/palm/finger)
        at the device within the timeout period.

        Args:
            ecode: Employee Ecode
            biometric_type: Type of biometric to enroll ('face', 'palm', 'finger', 'all')
            terminal_id: Specific terminal ID to use for enrollment (optional)
            terminal_name: Terminal name if terminal_id not provided (optional)
            timeout_seconds: How long the device stays in enrollment mode (default: 60s)

        Returns:
            Dict with success status, device info, and enrollment instructions
        """
        try:
            biometric_type_lower = biometric_type.lower()
            if biometric_type_lower not in self.BIOMETRIC_ENROLL_COMMANDS:
                return {
                    "success": False,
                    "message": f"Invalid biometric type: {biometric_type}. Valid types: face, palm, finger, all",
                    "error": "Invalid biometric type"
                }

            # Get the enrollment command
            command_prefix = self.BIOMETRIC_ENROLL_COMMANDS[biometric_type_lower]

            # Get available terminals
            terminals = await self.get_terminals()
            if not terminals:
                return {
                    "success": False,
                    "message": "No terminals/devices found in the system",
                    "error": "No terminals available"
                }

            # Find the target terminal
            target_terminal = None

            if terminal_id:
                for t in terminals:
                    if t.get("terminalID") == terminal_id or t.get("TerminalID") == terminal_id:
                        target_terminal = t
                        break
            elif terminal_name:
                for t in terminals:
                    name = t.get("domainName") or t.get("DomainName") or ""
                    if terminal_name.lower() in name.lower():
                        target_terminal = t
                        break

            # If no specific terminal, find first one that supports the biometric type
            if not target_terminal:
                # Look for terminals with biometric capability
                for t in terminals:
                    device_type = str(t.get("deviceType") or t.get("DeviceType") or "")
                    # Check if device supports the requested biometric
                    if biometric_type_lower == "face" and ("face" in device_type.lower() or "cam" in device_type.lower()):
                        target_terminal = t
                        break
                    elif biometric_type_lower == "palm" and "palm" in device_type.lower():
                        target_terminal = t
                        break
                    elif biometric_type_lower == "finger" and ("finger" in device_type.lower() or "bio" in device_type.lower()):
                        target_terminal = t
                        break
                    elif biometric_type_lower == "all":
                        target_terminal = t
                        break

            # If still no terminal, use the first available ONLINE terminal (skip Notification devices)
            if not target_terminal and terminals:
                # Prefer online terminals that are not "Notification" type
                for t in terminals:
                    device_type = str(t.get("deviceType") or t.get("DeviceType") or "").lower()
                    status = str(t.get("status") or t.get("Status") or "").lower()
                    ip = t.get("ipAddress") or t.get("IPAddress") or ""

                    # Skip notification/system devices and offline terminals
                    if device_type == "notification" or status == "offline" or ip == "127.0.0.1":
                        continue

                    target_terminal = t
                    logger.warning(f"[EXTENDED_API] No specific terminal found for {biometric_type}, using first available online device")
                    break

                # If still no terminal found, try any terminal with valid IP (excluding localhost)
                if not target_terminal:
                    for t in terminals:
                        ip = t.get("ipAddress") or t.get("IPAddress") or ""
                        if ip and ip != "127.0.0.1":
                            target_terminal = t
                            logger.warning(f"[EXTENDED_API] Using fallback terminal with IP: {ip}")
                            break

            if not target_terminal:
                return {
                    "success": False,
                    "message": "Could not find a suitable biometric device",
                    "error": "No suitable terminal found"
                }

            # Extract terminal details
            term_id = target_terminal.get("terminalID") or target_terminal.get("TerminalID")
            term_name = target_terminal.get("domainName") or target_terminal.get("DomainName") or f"Terminal {term_id}"
            term_ip = target_terminal.get("ipAddress") or target_terminal.get("IPAddress")

            if not term_ip:
                return {
                    "success": False,
                    "message": f"Terminal {term_name} does not have an IP address configured",
                    "error": "Terminal IP not found"
                }

            logger.info(f"[EXTENDED_API] Triggering {biometric_type} enrollment for ecode={ecode} on {term_name} ({term_ip})")

            # Map biometric type to FingerID for EnrollV22 API
            # FingerID mapping based on Oryggi dashboard V-22 device:
            # 0-9: Fingers (0-4 right hand, 5-9 left hand typically)
            # 11: Face (confirmed from dashboard network requests)
            # 12: Left Hand (Palm)
            # Note: FingerID=10 does NOT trigger face enrollment on V-22 devices
            finger_id_map = {
                "palm": 12,         # Left Hand palm
                "palm_left": 12,    # Left Hand palm
                "palm_right": 11,   # Right Hand palm (same as face on V-22)
                "face": 11,         # Face - V-22 devices use FingerID=11 for face!
                "finger": 0,        # Default to first finger (right thumb)
                "all": 12           # Default to palm for "all"
            }

            finger_id = finger_id_map.get(biometric_type_lower, 12)

            # Use EnrollV22 API endpoint (same as dashboard)
            # IMPORTANT: Dashboard waits for EnrollV22 to complete (~67 seconds), then checks template.
            # The device needs time to: enter enrollment mode -> wait for user -> capture -> sync to server
            # EnrollV22 always returns "Time Out" even on success, but we must wait for it to complete.
            import asyncio

            headers = {"APIKey": self.api_key}
            enrollment_success = False
            command_sent = False

            try:
                enroll_url = f"{self.base_url}/EnrollV22"
                enroll_params = {
                    "Ecode": ecode,
                    "FingerID": finger_id,
                    "DeviceIP": term_ip,
                    "OperatorEcode": 1,
                    "ClientVersion": "24.07.2025"
                }

                logger.info(f"[EXTENDED_API] EnrollV22 request: {enroll_url} params={enroll_params}")
                logger.info(f"[EXTENDED_API] WAITING for EnrollV22 to complete (up to 90s) - user should present {biometric_type_lower} now...")

                # Step 1a: Wait for EnrollV22 to complete with LONG timeout
                # The device needs time to enter enrollment mode and capture the biometric
                enroll_response_text = ""
                try:
                    async with httpx.AsyncClient(timeout=90, verify=False) as enroll_client:
                        response = await enroll_client.get(
                            enroll_url,
                            params=enroll_params,
                            headers=headers
                        )
                        enroll_response_text = response.text.strip() if response.text else ""
                        logger.info(f"[EXTENDED_API] EnrollV22 completed, status: {response.status_code}, response: {enroll_response_text[:200]}")
                except httpx.TimeoutException:
                    logger.info(f"[EXTENDED_API] EnrollV22 HTTP timeout after 90s - checking template anyway")
                except Exception as e:
                    logger.warning(f"[EXTENDED_API] EnrollV22 request error: {e}")

                # Step 1b: Check GetFingerListByTemplate to verify if face was captured
                # After EnrollV22 completes, template should be available if capture was successful
                template_type_map = {
                    "face": "FACE",
                    "palm": "PALM",
                    "palm_left": "PALM",
                    "palm_right": "PALM",
                    "finger": "FINGER"
                }
                template_type = template_type_map.get(biometric_type_lower, "FACE")

                verify_url = f"{self.base_url}/GetFingerListByTemplate"
                verify_params = {
                    "Ecode": ecode,
                    "TemplateType": template_type,
                    "ClientVersion": "24.07.2025"
                }

                logger.info(f"[EXTENDED_API] Checking template after EnrollV22: {verify_url} params={verify_params}")

                # Poll a few times to give server time to sync (sometimes there's a short delay)
                max_retries = 5
                retry_interval = 2  # seconds

                for retry in range(1, max_retries + 1):
                    try:
                        async with httpx.AsyncClient(timeout=15, verify=False) as verify_client:
                            verify_response = await verify_client.get(
                                verify_url,
                                params=verify_params,
                                headers=headers
                            )
                            verify_result = verify_response.text.strip()

                            logger.info(f"[EXTENDED_API] Template check #{retry}: {verify_result[:200] if verify_result else 'empty'}")

                            # Check if template was captured
                            # Response is a JSON array - if non-empty, template exists
                            if verify_response.status_code == 200 and verify_result:
                                # Parse JSON to check if array has entries
                                try:
                                    import json
                                    templates = json.loads(verify_result)
                                    if isinstance(templates, list) and len(templates) > 0:
                                        # Found template! Face was captured successfully
                                        logger.info(f"[EXTENDED_API] TEMPLATE FOUND! {biometric_type_lower} captured successfully")
                                        logger.info(f"[EXTENDED_API] Template data: {templates}")
                                        enrollment_success = True
                                        command_sent = True
                                        break
                                except json.JSONDecodeError:
                                    # Not JSON or invalid - check if it contains data
                                    if verify_result and verify_result != "[]" and "error" not in verify_result.lower():
                                        logger.info(f"[EXTENDED_API] Template detected (non-JSON): {verify_result}")
                                        enrollment_success = True
                                        command_sent = True
                                        break

                    except Exception as verify_err:
                        logger.warning(f"[EXTENDED_API] Template check #{retry} error: {verify_err}")

                    if retry < max_retries:
                        await asyncio.sleep(retry_interval)

                if not enrollment_success:
                    logger.warning(f"[EXTENDED_API] No template found after {max_retries} checks - biometric was not captured")

            except Exception as enroll_err:
                logger.error(f"[EXTENDED_API] Enrollment process failed: {enroll_err}")
                command_sent = False

            # Step 2: Add to Terminal - Use the PROVEN working method
            # This method uses correct headers (APIKey) and handles sync automatically
            add_to_terminal_success = False
            if command_sent:
                try:
                    logger.info(f"[EXTENDED_API] Step 2: Adding authentication to terminal using _grant_terminal_access_via_api...")

                    from datetime import datetime, timedelta
                    today = datetime.now()
                    end_date = today + timedelta(days=365 * 10)  # 10 years validity

                    # Use the WORKING method that has correct headers and handles sync
                    # This method uses APIKey header (not Authorization: Bearer) which is what Oryggi expects
                    add_to_terminal_success = await self._grant_terminal_access_via_api(
                        ecode=ecode,
                        terminal_id=term_id,
                        authentication_type=13,  # Fusion authentication for biometrics
                        schedule_id=1,  # Default schedule
                        start_date=today,
                        expiry_date=end_date
                    )

                    if add_to_terminal_success:
                        logger.info(f"[EXTENDED_API] AddAuthentication_Terminal SUCCESS via _grant_terminal_access_via_api")

                        # Step 2b: Send TCP Command to sync with controller (like dashboard does)
                        # Dashboard sends: SendTCPCommand?Command=EATR,1&host=192.168.1.88&Port=13000
                        try:
                            # Try to get controller IP from terminal info or use default
                            controller_host = "192.168.1.88"  # Default controller IP
                            controller_port = 13000

                            tcp_url = f"{self.base_url}/SendTCPCommand"
                            tcp_params = {
                                "Command": "EATR,1",  # Enable All Terminal Readers command
                                "host": controller_host,
                                "LogDetail": f"Enrollment sync for ECode {ecode}",
                                "Port": controller_port
                            }

                            logger.info(f"[EXTENDED_API] Sending TCP command to controller: {tcp_url} params={tcp_params}")

                            async with httpx.AsyncClient(timeout=30, verify=False) as tcp_client:
                                tcp_response = await tcp_client.get(
                                    tcp_url,
                                    params=tcp_params,
                                    headers=headers
                                )
                                tcp_result = tcp_response.text
                                logger.info(f"[EXTENDED_API] SendTCPCommand response: {tcp_result}")

                                if tcp_response.status_code == 200:
                                    logger.info(f"[EXTENDED_API] TCP Command sent successfully to controller")
                                else:
                                    logger.warning(f"[EXTENDED_API] TCP Command may have failed: {tcp_result}")

                        except Exception as tcp_err:
                            logger.warning(f"[EXTENDED_API] SendTCPCommand failed (non-critical): {tcp_err}")
                            # Continue anyway - TCP sync is optional

                        # Step 2c: Poll status until all components report success
                        # Dashboard polls GetTerminalAuthenticationListByEcode multiple times
                        try:
                            import asyncio
                            status_url = f"{self.base_url}/GetTerminalAuthenticationListByEcode"
                            status_params = {
                                "Ecode": ecode,
                                "ClientVersion": "24.07.2025"
                            }

                            max_polls = 5
                            poll_interval = 2  # seconds

                            for poll_num in range(1, max_polls + 1):
                                logger.info(f"[EXTENDED_API] Status poll {poll_num}/{max_polls}: {status_url}")

                                async with httpx.AsyncClient(timeout=30, verify=False) as status_client:
                                    status_response = await status_client.get(
                                        status_url,
                                        params=status_params,
                                        headers=headers
                                    )

                                    if status_response.status_code == 200:
                                        status_text = status_response.text.lower()
                                        logger.info(f"[EXTENDED_API] Status poll {poll_num} response: {status_response.text[:200]}...")

                                        # Check if all success indicators are present
                                        # Dashboard shows: User:Success Access:Success TimeZone:Success Face:Success
                                        if "success" in status_text:
                                            logger.info(f"[EXTENDED_API] Status poll {poll_num}: SUCCESS indicators found")
                                            break
                                    else:
                                        logger.warning(f"[EXTENDED_API] Status poll {poll_num} failed: {status_response.status_code}")

                                if poll_num < max_polls:
                                    await asyncio.sleep(poll_interval)

                            logger.info(f"[EXTENDED_API] Status polling completed after {poll_num} polls")

                        except Exception as poll_err:
                            logger.warning(f"[EXTENDED_API] Status polling failed (non-critical): {poll_err}")
                            # Continue anyway - polling is just verification

                    else:
                        logger.warning(f"[EXTENDED_API] AddAuthentication_Terminal FAILED via _grant_terminal_access_via_api")

                except Exception as add_err:
                    logger.warning(f"[EXTENDED_API] Add to Terminal step failed: {add_err}")
                    # Enrollment was done, but pushing to terminal failed
                    add_to_terminal_success = False

            # Return result with appropriate status
            biometric_display = {
                "face": "Face",
                "palm": "Palm",
                "finger": "Fingerprint",
                "all": "All Biometrics"
            }

            # Determine the completion status message based on actual success
            if command_sent and add_to_terminal_success:
                # Full success - biometric captured AND pushed to terminal
                status_message = f"{biometric_display[biometric_type_lower]} enrollment completed and pushed to {term_name}"
                completion_note = "Biometric has been enrolled and pushed to the terminal. The employee can now use the device for authentication."
                overall_success = True
            elif command_sent:
                # Partial success - biometric captured but push to terminal failed
                status_message = f"{biometric_display[biometric_type_lower]} enrollment completed on {term_name}, but push to terminal failed - manual sync needed"
                completion_note = "Biometric enrolled but manual sync via dashboard required."
                overall_success = True
            else:
                # FAILURE - biometric was NOT captured (timeout or error)
                status_message = f"{biometric_display[biometric_type_lower]} enrollment FAILED on {term_name} - biometric was not captured"
                completion_note = "**ENROLLMENT NOT COMPLETED.** The biometric was not captured (timeout or device issue). Please try again and ensure the employee places their palm on the device within the timeout period."
                overall_success = False

            return {
                "success": overall_success,
                "message": status_message,
                "enrollment_triggered": True,
                "biometric_captured": command_sent,
                "add_to_terminal_success": add_to_terminal_success,
                "fully_completed": command_sent and add_to_terminal_success,
                "device": {
                    "terminal_id": term_id,
                    "terminal_name": term_name,
                    "ip_address": term_ip
                },
                "biometric_type": biometric_type_lower,
                "timeout_seconds": timeout_seconds,
                "instructions": (
                    f"Enrollment process on {term_name}.\n\n"
                    f"**Status:** {completion_note}\n\n"
                    + (f"**Employee (ECode: {ecode})** can now authenticate using their {biometric_display[biometric_type_lower].lower()} at:\n"
                       f"**Device:** {term_name} (IP: {term_ip})" if overall_success else
                       f"**Employee (ECode: {ecode})** needs to retry enrollment at:\n"
                       f"**Device:** {term_name} (IP: {term_ip})")
                )
            }

        except Exception as e:
            logger.error(f"[EXTENDED_API] trigger_biometric_enrollment failed: {e}")
            return {
                "success": False,
                "message": f"Failed to trigger enrollment: {str(e)}",
                "error": str(e)
            }

    async def get_biometric_capable_terminals(
        self,
        biometric_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get list of terminals that support biometric enrollment.

        Args:
            biometric_type: Filter by biometric type ('face', 'palm', 'finger') or None for all

        Returns:
            List of terminal details with biometric capabilities
        """
        try:
            terminals = await self.get_terminals()
            biometric_terminals = []

            for t in terminals:
                device_type = str(t.get("deviceType") or t.get("DeviceType") or "").lower()
                term_name = t.get("domainName") or t.get("DomainName") or ""

                # Determine biometric capabilities
                capabilities = []
                if "face" in device_type or "cam" in device_type or "camera" in device_type:
                    capabilities.append("face")
                if "palm" in device_type:
                    capabilities.append("palm")
                if "finger" in device_type or "bio" in device_type or "fp" in device_type:
                    capabilities.append("finger")

                # If device type doesn't specify, assume it might support all
                if not capabilities and t.get("ipAddress"):
                    capabilities = ["face", "palm", "finger"]  # Assume multi-function device

                # Filter by requested type
                if biometric_type:
                    if biometric_type.lower() not in capabilities:
                        continue

                if capabilities:
                    biometric_terminals.append({
                        "terminal_id": t.get("terminalID") or t.get("TerminalID"),
                        "terminal_name": term_name,
                        "ip_address": t.get("ipAddress") or t.get("IPAddress"),
                        "capabilities": capabilities,
                        "device_type": device_type
                    })

            return biometric_terminals

        except Exception as e:
            logger.error(f"[EXTENDED_API] get_biometric_capable_terminals failed: {e}")
            return []


# Global extended client instance
extended_access_control_client = ExtendedAccessControlClient()
