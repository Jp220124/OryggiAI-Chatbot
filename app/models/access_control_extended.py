"""
Extended Access Control Models - Pydantic models for new access control operations
Phase 6: Visitor Registration, Temporary Cards, Card/Employee Enrollment, Door Access, Database Backup
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from enum import Enum


# ============================================================================
# Enums
# ============================================================================

class IDProofType(str, Enum):
    """Types of ID proof for visitor registration"""
    AADHAR = "Aadhar"
    PAN = "PAN"
    PASSPORT = "Passport"
    DRIVING_LICENSE = "DL"
    VOTER_ID = "VoterID"
    OTHER = "Other"


class VisitPurpose(str, Enum):
    """Common visit purposes"""
    MEETING = "Meeting"
    INTERVIEW = "Interview"
    DELIVERY = "Delivery"
    MAINTENANCE = "Maintenance"
    CONTRACTOR = "Contractor"
    VISITOR = "Visitor"
    OTHER = "Other"


class CardType(str, Enum):
    """Types of access cards"""
    VISITOR = "visitor"
    CONTRACTOR = "contractor"
    TEMPORARY = "temporary"
    PERMANENT = "permanent"


class AccessScope(str, Enum):
    """Scope of access for card enrollment"""
    SPECIFIC_DOORS = "specific_doors"
    ALL_DOORS = "all_doors"


class DoorAction(str, Enum):
    """Actions for door-level access management"""
    GRANT = "grant"
    BLOCK = "block"


class BackupType(str, Enum):
    """Types of database backup"""
    FULL = "full"
    DIFFERENTIAL = "differential"
    LOG = "log"


# ============================================================================
# Visitor Registration Models
# ============================================================================

class VisitorRegistrationRequest(BaseModel):
    """Request model for visitor registration"""
    first_name: str = Field(..., min_length=1, max_length=100, description="Visitor's first name")
    last_name: Optional[str] = Field(None, max_length=100, description="Visitor's last name")
    mobile_number: Optional[str] = Field(None, max_length=15, description="Mobile number")
    whom_to_visit: Optional[str] = Field(None, description="Employee name or code being visited")
    purpose: Optional[str] = Field(None, description="Purpose of visit")
    id_proof_type: str = Field(..., description="Type of ID proof (Aadhar, PAN, Passport, DL, VoterID)")
    id_proof_detail: str = Field(..., min_length=1, description="ID proof number")
    expected_in_time: Optional[datetime] = Field(None, description="Expected check-in time (default: now)")
    expected_out_time: Optional[datetime] = Field(None, description="Expected check-out time (default: +8 hours)")
    issued_card_number: Optional[str] = Field(None, description="Visitor card number to assign")
    terminal_group_id: Optional[int] = Field(None, description="Access zone/terminal group ID")
    vehicle_number: Optional[str] = Field(None, description="Vehicle registration number")
    number_of_visitors: int = Field(default=1, ge=1, description="Number of visitors")
    email: Optional[str] = Field(None, description="Visitor's email address")
    company: Optional[str] = Field(None, description="Visitor's company/organization")
    address: Optional[str] = Field(None, description="Visitor's address")
    gender: Optional[str] = Field(None, pattern='^[MF]$', description="Gender (M/F)")
    visitor_type: Optional[str] = Field(None, description="Visitor type: Walk-in or Pre-Booked")
    need_escort: Optional[bool] = Field(False, description="Whether visitor needs escort")

    @field_validator('mobile_number')
    @classmethod
    def validate_mobile(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        # Remove spaces and dashes
        cleaned = v.replace(' ', '').replace('-', '')
        if not cleaned.replace('+', '').isdigit():
            raise ValueError('Mobile number must contain only digits')
        return cleaned


class VisitorRegistrationResponse(BaseModel):
    """Response model for visitor registration"""
    success: bool
    visitor_id: Optional[str] = None
    visitor_ecode: Optional[int] = None
    message: str
    details: Optional[Dict[str, Any]] = None


# ============================================================================
# Temporary Card Models
# ============================================================================

class TemporaryCardRequest(BaseModel):
    """Request model for temporary card assignment"""
    target_user_id: str = Field(..., description="Visitor ID, contractor code, or employee code")
    card_number: str = Field(..., description="Card number to assign")
    card_type: CardType = Field(default=CardType.TEMPORARY, description="Type of temporary card")
    start_datetime: Optional[datetime] = Field(None, description="Start time (default: now)")
    expiry_datetime: datetime = Field(..., description="Card expiry time")
    terminal_group_id: Optional[int] = Field(None, description="Access zones/terminal group")
    reason: Optional[str] = Field(None, description="Reason for temporary card assignment")


class TemporaryCardResponse(BaseModel):
    """Response model for temporary card assignment"""
    success: bool
    card_number: str
    assigned_to: str
    expiry: datetime
    message: str
    details: Optional[Dict[str, Any]] = None


# ============================================================================
# Database Backup Models
# ============================================================================

class DatabaseBackupRequest(BaseModel):
    """Request model for database backup"""
    database_name: str = Field(default="Oryggi", description="Database to backup")
    backup_path: Optional[str] = Field(None, description="Custom backup path (default from config)")
    backup_type: BackupType = Field(default=BackupType.FULL, description="Type of backup")
    compression: bool = Field(default=True, description="Whether to compress the backup")


class DatabaseBackupResponse(BaseModel):
    """Response model for database backup"""
    success: bool
    backup_file_path: Optional[str] = None
    backup_size_mb: Optional[float] = None
    backup_duration_seconds: Optional[float] = None
    message: str
    details: Optional[Dict[str, Any]] = None


# ============================================================================
# Card Enrollment Models
# ============================================================================

class CardEnrollmentRequest(BaseModel):
    """Request model for card enrollment"""
    employee_id: str = Field(..., description="Employee code or name to assign card to")
    card_number: str = Field(..., description="Card number to enroll")
    access_scope: AccessScope = Field(..., description="Access scope: 'all_doors' or 'specific_doors'")
    door_ids: Optional[List[int]] = Field(None, description="Door/terminal IDs for specific_doors scope")
    door_names: Optional[List[str]] = Field(None, description="Door names (alternative to door_ids)")
    terminal_group_id: Optional[int] = Field(None, description="Zone ID for zone-based access")
    start_date: Optional[datetime] = Field(None, description="Access start date (default: now)")
    expiry_date: Optional[datetime] = Field(None, description="Access expiry date (default: 1 year)")
    schedule_id: int = Field(default=63, description="Schedule ID (63=all access, 0=no access)")
    authentication_type: int = Field(default=1001, description="Auth type (1001=card, 2=fingerprint, 5=face)")


class CardEnrollmentResponse(BaseModel):
    """Response model for card enrollment"""
    success: bool
    card_number: str
    employee_id: str
    employee_ecode: Optional[int] = None
    doors_configured: int = 0
    failed_doors: List[int] = []
    message: str
    details: Optional[Dict[str, Any]] = None


# ============================================================================
# Employee Enrollment Models (Legacy - uses InsertEmployee API)
# ============================================================================

class AuthenticationType(int, Enum):
    """Oryggi authentication types for employee access"""
    CARD = 1001           # Access card only (most common)
    FINGERPRINT = 2       # Fingerprint biometric
    FACE = 5              # Face recognition
    CARD_FINGERPRINT = 3  # Card + Fingerprint combination
    CARD_FACE = 6         # Card + Face combination


class EmployeeEnrollmentRequest(BaseModel):
    """Request model for employee enrollment with optional authentication setup"""
    corp_emp_code: str = Field(..., min_length=1, description="Employee code (must be unique)")
    emp_name: str = Field(..., min_length=1, description="Employee full name")
    department_code: Optional[str] = Field(None, description="Department code")
    designation_code: Optional[str] = Field(None, description="Designation code")
    email: Optional[str] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    join_date: Optional[datetime] = Field(None, description="Join date (default: today)")
    gender: Optional[str] = Field(None, pattern='^[MF]$', description="Gender (M/F)")
    active: bool = Field(default=True, description="Active status")
    card_number: Optional[str] = Field(None, description="Card number to assign (optional)")
    # Authentication options (new)
    authentication_type: Optional[int] = Field(
        default=1001,
        description="Auth type: 1001=card, 2=fingerprint, 5=face, 3=card+fingerprint, 6=card+face"
    )
    setup_default_access: bool = Field(
        default=True,
        description="If True, sets up default door access after enrollment"
    )
    terminal_group_id: Optional[int] = Field(
        None,
        description="Terminal group ID for access (default: all terminals)"
    )
    schedule_id: int = Field(
        default=63,
        description="Access schedule ID (63=all access, 0=no access)"
    )


class EmployeeEnrollmentResponse(BaseModel):
    """Response model for employee enrollment"""
    success: bool
    ecode: Optional[int] = None
    corp_emp_code: str
    message: str
    card_enrolled: bool = False
    details: Optional[Dict[str, Any]] = None


# ============================================================================
# Employee Create/Update Models (Frontend API - UpdateEmployeeWithLog)
# ============================================================================

class EmployeeCreateUpdateRequest(BaseModel):
    """
    Request model for employee creation/update using frontend API pattern.
    Uses UpdateEmployeeWithLog API endpoint (same as Oryggi Manager Web frontend).

    This is the recommended model for employee management operations.
    """
    # Required fields
    corp_emp_code: str = Field(..., min_length=1, max_length=50, description="Employee code (must be unique)")
    emp_name: str = Field(..., min_length=1, max_length=100, description="Employee full name")

    # Optional basic info
    first_name: Optional[str] = Field(None, max_length=50, description="First name (extracted from emp_name if not provided)")
    last_name: Optional[str] = Field(None, max_length=50, description="Last name")
    email: Optional[str] = Field(None, max_length=100, description="Email address")
    phone: Optional[str] = Field(None, max_length=20, description="Phone number")
    mobile: Optional[str] = Field(None, max_length=20, description="Mobile number")
    gender: Optional[str] = Field(None, pattern='^[MF]$', description="Gender (M/F)")

    # Organization fields
    company_code: Optional[int] = Field(default=1, description="Company code")
    branch_code: Optional[int] = Field(default=1, description="Branch code")
    department_code: Optional[int] = Field(None, description="Department code")
    department_name: Optional[str] = Field(None, description="Department name (used if code not provided)")
    section_code: Optional[int] = Field(None, description="Section code")
    designation_code: Optional[int] = Field(None, description="Designation code")
    designation_name: Optional[str] = Field(None, description="Designation name (used if code not provided)")
    category_code: Optional[int] = Field(None, description="Category code")
    grade_code: Optional[int] = Field(None, description="Grade code")

    # Access control fields
    card_number: Optional[str] = Field(None, description="Access card number")
    user_group_id: Optional[int] = Field(default=2, description="User group ID (2=Employee)")
    role_id: Optional[int] = Field(None, description="Role ID")

    # Dates
    join_date: Optional[datetime] = Field(None, description="Join date (default: today)")
    start_date: Optional[datetime] = Field(None, description="Access start date")
    expiry_date: Optional[datetime] = Field(None, description="Access expiry date")

    # Status
    active: bool = Field(default=True, description="Active status")
    status_id: int = Field(default=1, description="Status ID (1=Active)")

    # Address
    address: Optional[str] = Field(None, max_length=500, description="Address")

    # Image (base64)
    image: Optional[str] = Field(None, description="Base64 encoded profile image")

    # Update mode
    is_update: bool = Field(default=False, description="True for update, False for create")
    ecode: Optional[int] = Field(None, description="Employee Ecode (required for update)")

    @field_validator('phone', 'mobile')
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        cleaned = v.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        return cleaned


class EmployeeCreateUpdateResponse(BaseModel):
    """Response model for employee create/update operations"""
    success: bool
    ecode: Optional[int] = None
    corp_emp_code: str
    emp_name: str
    operation: str = Field(description="'create' or 'update'")
    message: str
    card_enrolled: bool = False
    access_granted: bool = False
    details: Optional[Dict[str, Any]] = None


# ============================================================================
# Door-Specific Access Models
# ============================================================================

class DoorAccessRequest(BaseModel):
    """Request model for door-specific access management"""
    employee_id: str = Field(..., description="Employee code or name")
    action: DoorAction = Field(..., description="Action to perform: 'grant' or 'block'")
    door_ids: Optional[List[int]] = Field(None, description="List of door/terminal IDs")
    door_names: Optional[List[str]] = Field(None, description="List of door names (alternative to door_ids)")
    schedule_id: Optional[int] = Field(None, description="Schedule ID for access timing")
    start_date: Optional[datetime] = Field(None, description="Access start date")
    end_date: Optional[datetime] = Field(None, description="Access end date")
    reason: Optional[str] = Field(None, description="Reason for action")

    @field_validator('door_ids', 'door_names')
    @classmethod
    def validate_door_selection(cls, v, info):
        # At least one of door_ids or door_names must be provided
        # Validated at tool level
        return v


class DoorAccessResponse(BaseModel):
    """Response model for door-specific access"""
    success: bool
    employee_id: str
    employee_ecode: Optional[int] = None
    action: str
    doors_affected: int = 0
    failed_doors: List[int] = []
    message: str
    details: Optional[Dict[str, Any]] = None


# ============================================================================
# Terminal/Door Listing Models
# ============================================================================

class TerminalInfo(BaseModel):
    """Information about a terminal/door"""
    terminal_id: int
    terminal_name: str
    location: Optional[str] = None
    device_type: Optional[str] = None
    ip_address: Optional[str] = None
    is_active: bool = True


class TerminalGroupInfo(BaseModel):
    """Information about a terminal group/zone"""
    group_id: int
    group_name: str
    description: Optional[str] = None
    terminal_count: int = 0


class TerminalListResponse(BaseModel):
    """Response model for terminal listing"""
    success: bool
    terminals: List[TerminalInfo] = []
    terminal_groups: List[TerminalGroupInfo] = []
    total_count: int = 0
    message: str


# ============================================================================
# Common Result Models
# ============================================================================

class ExtendedAccessControlResult(BaseModel):
    """Generic result model for extended access control operations"""
    success: bool
    operation: str
    message: str
    permission_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: Optional[float] = None
