"""
Enrollment API Routes

Endpoints for:
1. Device-facing APIs for QR-based biometric enrollment
2. Dropdown data (departments, designations)
3. Employee onboarding with QR generation
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy.orm import Session
from loguru import logger

from app.database.platform_connection import get_platform_db
from app.api.deps import CurrentUserDep, get_tenant_database
from app.models.platform import TenantDatabase


router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================

class DepartmentResponse(BaseModel):
    """Department/Section for dropdown"""
    code: int
    name: str


class DesignationResponse(BaseModel):
    """Designation for dropdown"""
    code: int
    name: str


class EmployeeCreateRequest(BaseModel):
    """Request to create new employee"""
    name: str = Field(..., min_length=2, max_length=200, description="Employee full name")
    email: EmailStr = Field(..., description="Employee email address")
    department_code: int = Field(..., gt=0, description="Department/Section code")
    designation_code: int = Field(..., gt=0, description="Designation code")
    phone: Optional[str] = Field(None, max_length=50, description="Phone number")
    gender: str = Field("male", description="Gender: male/female")
    send_enrollment_email: bool = Field(True, description="Send enrollment QR via email")


class EmployeeCreateResponse(BaseModel):
    """Response after creating employee"""
    success: bool
    ecode: Optional[int] = None
    corp_emp_code: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    enrollment_email_sent: bool = False
    message: str


class TokenValidationResponse(BaseModel):
    """Response for device token validation"""
    ecode: int
    name: str
    biometric_type: str


class EnrollmentCompleteRequest(BaseModel):
    """Request to mark enrollment complete"""
    device_ip: Optional[str] = None
    device_info: Optional[str] = None
    success: bool = True


class EnrollmentCompleteResponse(BaseModel):
    """Response after marking enrollment complete"""
    success: bool
    message: str


# =============================================================================
# Dropdown Data Endpoints
# =============================================================================

@router.get(
    "/departments",
    response_model=List[DepartmentResponse],
    summary="Get departments for dropdown",
    description="Get list of active departments/sections from SectionMaster"
)
async def get_departments(
    current_user: CurrentUserDep,
    tenant_db: TenantDatabase = Depends(get_tenant_database)
):
    """
    Get departments for employee creation dropdown.

    Returns list of {code, name} for active departments.
    """
    from app.services.employee_onboarding_service import EmployeeOnboardingService

    service = EmployeeOnboardingService(tenant_db)
    departments = service.get_departments()

    if not departments:
        logger.warning("No departments found or error fetching departments")

    return departments


@router.get(
    "/designations",
    response_model=List[DesignationResponse],
    summary="Get designations for dropdown",
    description="Get list of active designations from DesignationMaster"
)
async def get_designations(
    current_user: CurrentUserDep,
    tenant_db: TenantDatabase = Depends(get_tenant_database)
):
    """
    Get designations for employee creation dropdown.

    Returns list of {code, name} for active designations.
    """
    from app.services.employee_onboarding_service import EmployeeOnboardingService

    service = EmployeeOnboardingService(tenant_db)
    designations = service.get_designations()

    if not designations:
        logger.warning("No designations found or error fetching designations")

    return designations


# =============================================================================
# Employee Onboarding Endpoint
# =============================================================================

@router.post(
    "/create-employee",
    response_model=EmployeeCreateResponse,
    summary="Create new employee with enrollment QR",
    description="Create new employee in EmployeeMaster and send enrollment QR via email"
)
async def create_employee(
    request: EmployeeCreateRequest,
    current_user: CurrentUserDep,
    db: Session = Depends(get_platform_db),
    tenant_db: TenantDatabase = Depends(get_tenant_database)
):
    """
    Create a new employee and send biometric enrollment QR.

    Flow:
    1. Validate department and designation codes
    2. Check for duplicate email
    3. Auto-generate ECode (SQL Server IDENTITY)
    4. Create enrollment token
    5. Generate QR code
    6. Send welcome email with QR
    """
    from app.services.employee_onboarding_service import (
        EmployeeOnboardingService, NewEmployeeData
    )
    from app.services.qr_enrollment_service import QREnrollmentService

    # Create employee
    emp_service = EmployeeOnboardingService(tenant_db)

    success, employee, error = emp_service.create_employee(
        employee_data=NewEmployeeData(
            name=request.name,
            email=request.email,
            department_code=request.department_code,
            designation_code=request.designation_code,
            phone=request.phone,
            gender=request.gender,
        ),
        created_by=str(current_user.id)
    )

    if not success:
        return EmployeeCreateResponse(
            success=False,
            message=error or "Failed to create employee"
        )

    # Send enrollment QR email
    email_sent = False
    if request.send_enrollment_email:
        try:
            qr_service = QREnrollmentService(db)

            # Create enrollment token
            token, expires_at = qr_service.create_enrollment_token(
                ecode=employee.ecode,
                name=employee.name,
                email=employee.email,
                biometric_type="face",
                expires_hours=24,
                created_by_user_id=current_user.id,
                tenant_id=current_user.tenant_id,
            )

            # Send email
            email_sent = qr_service.send_enrollment_email(
                token=token,
                ecode=employee.ecode,
                name=employee.name,
                email=employee.email,
                expires_hours=24
            )

            if email_sent:
                logger.info(f"Enrollment email sent to {employee.email}")
            else:
                logger.warning(f"Failed to send enrollment email to {employee.email}")

        except Exception as e:
            logger.error(f"Error sending enrollment email: {e}")

    return EmployeeCreateResponse(
        success=True,
        ecode=employee.ecode,
        corp_emp_code=employee.corp_emp_code,
        name=employee.name,
        email=employee.email,
        department=employee.department_name,
        designation=employee.designation_name,
        enrollment_email_sent=email_sent,
        message=f"Employee created successfully (ECode: {employee.ecode})"
        + (". Enrollment QR sent via email." if email_sent else ". Email sending failed, please retry.")
    )


# =============================================================================
# Device-Facing Endpoints (No Auth Required)
# =============================================================================

@router.get(
    "/validate/{token}",
    response_model=TokenValidationResponse,
    summary="Validate enrollment token (for devices)",
    description="Biometric devices call this to get employee data from QR token"
)
async def validate_enrollment_token(
    token: str,
    request: Request,
    db: Session = Depends(get_platform_db)
):
    """
    Validate enrollment token and return employee data.

    Called by biometric devices when QR code is scanned.

    Returns:
    - 200: Employee data (ecode, name, biometric_type)
    - 404: Token not found
    - 410: Token expired or already used
    """
    from app.services.qr_enrollment_service import QREnrollmentService

    client_ip = request.client.host if request.client else "unknown"

    try:
        qr_service = QREnrollmentService(db)
        token_data = qr_service.validate_token(token)

        if token_data is None:
            # Check if token exists but is invalid
            from app.models.platform.enrollment_token import EnrollmentToken
            db_token = db.query(EnrollmentToken).filter(
                EnrollmentToken.token == token
            ).first()

            if db_token:
                if db_token.is_used:
                    raise HTTPException(
                        status_code=status.HTTP_410_GONE,
                        detail="Token has already been used"
                    )
                elif db_token.is_expired:
                    raise HTTPException(
                        status_code=status.HTTP_410_GONE,
                        detail="Token has expired"
                    )

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Token not found"
            )

        logger.info(
            f"Token validated for {token_data.name} (ECode: {token_data.ecode}) "
            f"from {client_ip}"
        )

        return TokenValidationResponse(
            ecode=token_data.ecode,
            name=token_data.name,
            biometric_type=token_data.biometric_type
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post(
    "/complete/{token}",
    response_model=EnrollmentCompleteResponse,
    summary="Mark enrollment as complete (for devices)",
    description="Biometric devices call this after capturing biometric"
)
async def complete_enrollment(
    token: str,
    body: EnrollmentCompleteRequest,
    request: Request,
    db: Session = Depends(get_platform_db)
):
    """
    Mark enrollment token as used after biometric capture.

    Called by biometric devices after successfully capturing face/fingerprint.
    """
    from app.services.qr_enrollment_service import QREnrollmentService

    client_ip = body.device_ip or (request.client.host if request.client else "unknown")

    try:
        qr_service = QREnrollmentService(db)

        # Validate token first
        token_data = qr_service.validate_token(token)
        if not token_data:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Token is invalid, expired, or already used"
            )

        # Mark as complete
        success = qr_service.complete_enrollment(
            token=token,
            device_ip=client_ip,
            device_info=body.device_info,
            success=body.success
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to mark enrollment as complete"
            )

        logger.info(
            f"Enrollment completed for ECode {token_data.ecode} from device {client_ip}"
        )

        return EnrollmentCompleteResponse(
            success=True,
            message=f"Enrollment recorded for {token_data.name}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Enrollment completion error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


# =============================================================================
# Admin Endpoints
# =============================================================================

@router.get(
    "/pending",
    summary="Get pending enrollment tokens",
    description="Get list of pending (unused, not expired) enrollment tokens"
)
async def get_pending_enrollments(
    current_user: CurrentUserDep,
    db: Session = Depends(get_platform_db),
    limit: int = 50
):
    """
    Get list of pending enrollment tokens.

    Returns enrollments that haven't been used and haven't expired.
    """
    from app.services.qr_enrollment_service import QREnrollmentService

    qr_service = QREnrollmentService(db)
    pending = qr_service.get_pending_enrollments(
        tenant_id=current_user.tenant_id,
        limit=limit
    )

    return [
        {
            "token": t.token[:16] + "...",  # Truncate for security
            "ecode": t.employee_ecode,
            "name": t.employee_name,
            "email": t.employee_email,
            "expires_at": t.expires_at.isoformat(),
            "created_at": t.created_at.isoformat(),
        }
        for t in pending
    ]


@router.delete(
    "/cancel/{token}",
    summary="Cancel enrollment token",
    description="Manually invalidate an enrollment token"
)
async def cancel_enrollment(
    token: str,
    current_user: CurrentUserDep,
    db: Session = Depends(get_platform_db)
):
    """
    Cancel/invalidate an enrollment token.

    Use this if HR needs to cancel an enrollment before it's used.
    """
    from app.services.qr_enrollment_service import QREnrollmentService

    qr_service = QREnrollmentService(db)
    success = qr_service.invalidate_token(token)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found"
        )

    logger.info(f"Enrollment token cancelled by {current_user.email}")

    return {"success": True, "message": "Enrollment token cancelled"}
