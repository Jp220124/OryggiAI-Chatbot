"""
Gateway WebSocket API Endpoint

Provides WebSocket endpoint for on-premises gateway agents to connect
and execute queries on behalf of the SaaS platform.
"""

import os
import zipfile
import tempfile
from typing import Optional
from pathlib import Path
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from loguru import logger

from app.database.platform_connection import get_platform_db
from app.gateway.connection_manager import gateway_manager
from app.gateway.message_handler import message_handler
from app.gateway.schemas import GatewaySessionInfo
from app.api.deps import get_current_active_user, CurrentUser
from app.models.platform import TenantDatabase, ApiKey
from app.config import get_settings


router = APIRouter(prefix="/gateway", tags=["Gateway"])


@router.websocket("/ws")
async def gateway_websocket_endpoint(
    websocket: WebSocket,
):
    """
    WebSocket endpoint for gateway agent connections

    Protocol:
    1. Agent connects and sends AUTH_REQUEST with gateway token
    2. Server validates token and sends AUTH_RESPONSE
    3. Server sends QUERY_REQUEST when queries need execution
    4. Agent returns QUERY_RESPONSE with results
    5. Agent sends periodic HEARTBEAT, server responds with HEARTBEAT_ACK

    Message Types:
    - AUTH_REQUEST: Agent authentication
    - AUTH_RESPONSE: Server auth response
    - QUERY_REQUEST: SQL query to execute
    - QUERY_RESPONSE: Query results
    - HEARTBEAT: Keep-alive from agent
    - HEARTBEAT_ACK: Server acknowledgment
    - ERROR: Error notification
    - DISCONNECT: Clean disconnect
    """
    await message_handler.handle_connection(
        websocket=websocket,
        get_db=get_platform_db,
    )


@router.get("/status")
async def get_gateway_status(
    current_user: CurrentUser = Depends(get_current_active_user),
    db: Session = Depends(get_platform_db),
):
    """
    Get status of all gateway connections for the current tenant

    Returns:
        List of active gateway sessions
    """
    sessions = gateway_manager.get_all_sessions()

    # Filter to current tenant's sessions
    tenant_sessions = [
        s for s in sessions if s.tenant_id == str(current_user.tenant_id)
    ]

    return {
        "success": True,
        "sessions": [s.model_dump() for s in tenant_sessions],
        "total_count": len(tenant_sessions),
    }


@router.get("/status/{database_id}")
async def get_database_gateway_status(
    database_id: str,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: Session = Depends(get_platform_db),
):
    """
    Get gateway status for a specific database

    Args:
        database_id: Database UUID

    Returns:
        Gateway connection status and session info
    """
    from uuid import UUID

    # Verify database belongs to tenant
    tenant_db = db.query(TenantDatabase).filter(
        TenantDatabase.id == UUID(database_id),
        TenantDatabase.tenant_id == current_user.tenant_id,
    ).first()

    if not tenant_db:
        raise HTTPException(status_code=404, detail="Database not found")

    is_connected = gateway_manager.is_connected(database_id)
    session_info = gateway_manager.get_session_info(database_id)

    return {
        "success": True,
        "database_id": database_id,
        "database_name": tenant_db.name,
        "gateway_connected": is_connected,
        "connection_mode": getattr(tenant_db, "connection_mode", "auto"),
        "session": session_info.model_dump() if session_info else None,
    }


@router.get("/databases/{database_id}/token-status")
async def get_gateway_token_status(
    database_id: str,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: Session = Depends(get_platform_db),
):
    """
    Check if an active gateway token exists for this database.
    Returns token metadata (not the token itself) for UI display.
    """
    from uuid import UUID
    from datetime import datetime

    try:
        tenant_db = db.query(TenantDatabase).filter(
            TenantDatabase.id == UUID(database_id),
            TenantDatabase.tenant_id == current_user.tenant_id,
        ).first()

        if not tenant_db:
            raise HTTPException(status_code=404, detail="Database not found")

        # Check if active token exists
        if hasattr(tenant_db, "gateway_api_key_id") and tenant_db.gateway_api_key_id:
            existing_key = db.query(ApiKey).filter(
                ApiKey.id == tenant_db.gateway_api_key_id,
                ApiKey.is_active == True,
            ).first()

            if existing_key:
                return {
                    "has_active_token": True,
                    "token_prefix": existing_key.key_prefix,
                    "created_at": existing_key.created_at.isoformat() if existing_key.created_at else None,
                    "last_used_at": existing_key.last_used_at.isoformat() if existing_key.last_used_at else None,
                    "expires_at": existing_key.expires_at.isoformat() if existing_key.expires_at else "Never",
                    "gateway_connected": gateway_manager.is_connected(database_id),
                }

        return {
            "has_active_token": False,
            "gateway_connected": False,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get token status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/databases/{database_id}/generate-token")
async def generate_gateway_token(
    database_id: str,
    token_name: Optional[str] = Query(None, description="Name for the token"),
    force: bool = Query(False, description="Force regenerate even if active token exists"),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: Session = Depends(get_platform_db),
):
    """
    Generate a gateway token for a database.

    This token is used by the gateway agent to authenticate.
    Tokens DO NOT expire automatically (enterprise-grade).

    IMPORTANT: If an active token exists and force=False, returns warning.
    Use force=True to revoke old token and generate new one.

    Args:
        database_id: Database UUID
        token_name: Optional name for the token
        force: If True, revoke existing token and generate new one

    Returns:
        Generated token (shown only once) or warning if active token exists
    """
    from uuid import UUID
    import secrets
    import hashlib
    from datetime import datetime
    import traceback

    try:
        # Verify database belongs to tenant
        tenant_db = db.query(TenantDatabase).filter(
            TenantDatabase.id == UUID(database_id),
            TenantDatabase.tenant_id == current_user.tenant_id,
        ).first()

        if not tenant_db:
            raise HTTPException(status_code=404, detail="Database not found")

        # Check for existing active token
        existing_key = None
        if hasattr(tenant_db, "gateway_api_key_id") and tenant_db.gateway_api_key_id:
            existing_key = db.query(ApiKey).filter(
                ApiKey.id == tenant_db.gateway_api_key_id,
                ApiKey.is_active == True,
            ).first()

        # If active token exists and force=False, return warning
        if existing_key and not force:
            is_connected = gateway_manager.is_connected(database_id)
            return {
                "success": False,
                "warning": True,
                "message": "An active gateway token already exists for this database.",
                "details": {
                    "token_prefix": existing_key.key_prefix,
                    "created_at": existing_key.created_at.isoformat() if existing_key.created_at else None,
                    "last_used_at": existing_key.last_used_at.isoformat() if existing_key.last_used_at else None,
                    "gateway_connected": is_connected,
                },
                "action_required": "Set force=true to revoke the existing token and generate a new one. WARNING: This will disconnect your Gateway Agent!",
            }

        # If force=True, revoke existing token
        if existing_key and force:
            existing_key.revoke("Replaced by new gateway token (user confirmed)")
            logger.info(f"Revoked old gateway token for database {database_id} (user confirmed)")

        # Generate new gateway token (NO EXPIRATION - enterprise grade)
        token = f"gw_{secrets.token_urlsafe(32)}"
        key_prefix = token[:10]  # gw_XXXXXX (fits NVARCHAR(10) column)
        key_hash = hashlib.sha256(token.encode()).hexdigest()
        name = token_name or f"Gateway Token - {tenant_db.name}"

        new_key = ApiKey(
            tenant_id=current_user.tenant_id,
            user_id=current_user.user_id,
            name=name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            scopes='["gateway"]',
            is_active=True,
            expires_at=None,  # NEVER EXPIRES - Enterprise grade!
        )
        db.add(new_key)
        db.flush()

        # Link token to database
        tenant_db.gateway_api_key_id = new_key.id
        tenant_db.connection_mode = "gateway_only"  # Enable gateway mode

        db.commit()

        logger.info(f"Generated gateway token for database {database_id}")

        return {
            "success": True,
            "token": token,
            "token_id": str(new_key.id),
            "expires_at": "Never",  # Tokens don't expire
            "database_id": database_id,
            "database_name": tenant_db.name,
            "message": "Save this token securely. It will not be shown again.",
            "was_replaced": existing_key is not None,
        }
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to generate gateway token: {str(e)}"
        error_trace = traceback.format_exc()
        logger.error(f"{error_msg}\n{error_trace}")
        raise HTTPException(
            status_code=500,
            detail=error_msg
        )


@router.delete("/databases/{database_id}/revoke-token")
async def revoke_gateway_token(
    database_id: str,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: Session = Depends(get_platform_db),
):
    """
    Revoke the gateway token for a database

    Args:
        database_id: Database UUID

    Returns:
        Success status
    """
    from uuid import UUID

    # Verify database belongs to tenant
    tenant_db = db.query(TenantDatabase).filter(
        TenantDatabase.id == UUID(database_id),
        TenantDatabase.tenant_id == current_user.tenant_id,
    ).first()

    if not tenant_db:
        raise HTTPException(status_code=404, detail="Database not found")

    if not hasattr(tenant_db, "gateway_api_key_id") or not tenant_db.gateway_api_key_id:
        raise HTTPException(status_code=404, detail="No gateway token found")

    # Revoke token
    api_key = db.query(ApiKey).filter(ApiKey.id == tenant_db.gateway_api_key_id).first()
    if api_key:
        api_key.revoke("Token revoked by user")

    # Disconnect any active gateway
    await gateway_manager.disconnect(database_id)

    # Clear gateway settings
    tenant_db.gateway_api_key_id = None
    tenant_db.gateway_connected = False
    tenant_db.connection_mode = "direct_only"

    db.commit()

    logger.info(f"Revoked gateway token for database {database_id}")

    return {
        "success": True,
        "message": "Gateway token revoked",
        "database_id": database_id,
    }


@router.post("/databases/{database_id}/set-connection-mode")
async def set_connection_mode(
    database_id: str,
    mode: str = Query(..., description="Connection mode: auto, gateway_only, direct_only"),
    current_user: CurrentUser = Depends(get_current_active_user),
    db: Session = Depends(get_platform_db),
):
    """
    Set the connection mode for a database

    Modes:
    - auto: Try direct first, fallback to gateway
    - gateway_only: Only use gateway (requires gateway token)
    - direct_only: Only use direct connection

    Args:
        database_id: Database UUID
        mode: Connection mode

    Returns:
        Updated database configuration
    """
    from uuid import UUID

    if mode not in ["auto", "gateway_only", "direct_only"]:
        raise HTTPException(status_code=400, detail="Invalid mode. Use: auto, gateway_only, direct_only")

    tenant_db = db.query(TenantDatabase).filter(
        TenantDatabase.id == UUID(database_id),
        TenantDatabase.tenant_id == current_user.tenant_id,
    ).first()

    if not tenant_db:
        raise HTTPException(status_code=404, detail="Database not found")

    # Validate mode requirements
    if mode == "gateway_only":
        if not hasattr(tenant_db, "gateway_api_key_id") or not tenant_db.gateway_api_key_id:
            raise HTTPException(
                status_code=400,
                detail="Gateway token required for gateway_only mode. Generate one first.",
            )

    tenant_db.connection_mode = mode
    db.commit()

    logger.info(f"Set connection mode to '{mode}' for database {database_id}")

    return {
        "success": True,
        "database_id": database_id,
        "connection_mode": mode,
        "gateway_connected": gateway_manager.is_connected(database_id),
    }


@router.get("/download-agent")
async def download_gateway_agent():
    """
    Download the Gateway Agent package

    Returns a ZIP file containing the gateway agent for installation
    on client premises.
    """
    # Path to the gateway agent directory
    base_path = Path(__file__).parent.parent.parent
    agent_dir = base_path / "oryggi-gateway-agent"

    if not agent_dir.exists():
        raise HTTPException(
            status_code=404,
            detail="Gateway agent package not found. Contact support."
        )

    # Create a temporary ZIP file
    temp_dir = tempfile.gettempdir()
    zip_path = os.path.join(temp_dir, "oryggi-gateway-agent.zip")

    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(agent_dir):
                # Skip __pycache__ and .git directories
                dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', 'venv', '.venv']]

                for file in files:
                    # Skip Python cache files
                    if file.endswith('.pyc') or file.endswith('.pyo'):
                        continue

                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, agent_dir.parent)
                    zipf.write(file_path, arcname)

        logger.info("Gateway agent ZIP created for download")

        return FileResponse(
            path=zip_path,
            filename="oryggi-gateway-agent.zip",
            media_type="application/zip",
        )
    except Exception as e:
        logger.error(f"Failed to create gateway agent ZIP: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to create download package"
        )


@router.get("/download-installer")
async def download_installer_script(
    gateway_token: str = Query(..., description="Gateway token to embed in script"),
    db_database: str = Query("YourDatabaseName", description="Database name"),
    db_host: str = Query("host.docker.internal", description="SQL Server host"),
    db_port: str = Query("1433", description="SQL Server port"),
    db_username: str = Query("sa", description="SQL Server username"),
    format: str = Query("powershell", description="Script format: powershell, batch, or compose"),
):
    """
    Download a pre-configured installer script with gateway token embedded.

    This endpoint generates a customized setup script that users can run
    to automatically install and configure the gateway agent.

    Args:
        gateway_token: The gateway token (from generate-token endpoint)
        db_database: SQL Server database name
        db_host: SQL Server host (default: host.docker.internal for Docker)
        db_port: SQL Server port (default: 1433)
        db_username: SQL Server username (default: sa)
        format: Script format - powershell, batch, or compose

    Returns:
        A downloadable script file with pre-filled configuration
    """
    from fastapi.responses import Response

    # Get gateway WebSocket URL from settings
    settings = get_settings()
    gateway_ws_url = settings.gateway_ws_url

    if format == "powershell":
        # PowerShell one-click installer for Windows
        script_content = f'''# OryggiAI Gateway Agent - One-Click Installer
# This script will automatically set up the gateway agent using Docker
# Run this in PowerShell as Administrator

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  OryggiAI Gateway Agent Installer" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Configuration (pre-filled from dashboard)
$GATEWAY_TOKEN = "{gateway_token}"
$GATEWAY_URL = "{gateway_ws_url}"
$DB_HOST = "{db_host}"
$DB_PORT = "{db_port}"
$DB_DATABASE = "{db_database}"
$DB_USERNAME = "{db_username}"

# Check if Docker is installed
Write-Host "[1/4] Checking Docker installation..." -ForegroundColor Yellow
$docker = Get-Command docker -ErrorAction SilentlyContinue
if (-not $docker) {{
    Write-Host "Docker is not installed!" -ForegroundColor Red
    Write-Host "Please install Docker Desktop from: https://www.docker.com/products/docker-desktop/" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Press any key to open Docker download page..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    Start-Process "https://www.docker.com/products/docker-desktop/"
    exit 1
}}
Write-Host "Docker found!" -ForegroundColor Green

# Check if Docker is running
Write-Host "[2/4] Checking if Docker is running..." -ForegroundColor Yellow
try {{
    docker info 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {{
        throw "Docker not running"
    }}
    Write-Host "Docker is running!" -ForegroundColor Green
}} catch {{
    Write-Host "Docker Desktop is not running. Please start Docker Desktop and try again." -ForegroundColor Red
    exit 1
}}

# Prompt for password (not stored in script for security)
Write-Host ""
Write-Host "[3/4] Database Configuration" -ForegroundColor Yellow
Write-Host "Database: $DB_DATABASE"
Write-Host "Host: $DB_HOST"
Write-Host "Port: $DB_PORT"
Write-Host "Username: $DB_USERNAME"
Write-Host ""
$DB_PASSWORD = Read-Host -Prompt "Enter your SQL Server password" -AsSecureString
$BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($DB_PASSWORD)
$DB_PASSWORD_PLAIN = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)

# Remove existing container if any
Write-Host ""
Write-Host "[4/4] Setting up Gateway Agent..." -ForegroundColor Yellow
docker rm -f oryggi-gateway 2>&1 | Out-Null

# Run the gateway agent
Write-Host "Starting OryggiAI Gateway Agent..."
$result = docker run -d --name oryggi-gateway `
    --restart unless-stopped `
    -e GATEWAY_TOKEN=$GATEWAY_TOKEN `
    -e GATEWAY_SAAS_URL=$GATEWAY_URL `
    -e DB_HOST=$DB_HOST `
    -e DB_PORT=$DB_PORT `
    -e DB_DATABASE=$DB_DATABASE `
    -e DB_USERNAME=$DB_USERNAME `
    -e DB_PASSWORD=$DB_PASSWORD_PLAIN `
    oryggiai/gateway-agent:latest

if ($LASTEXITCODE -eq 0) {{
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  Gateway Agent Started Successfully!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Container ID: $result"
    Write-Host ""
    Write-Host "Useful commands:" -ForegroundColor Cyan
    Write-Host "  View logs:    docker logs oryggi-gateway -f"
    Write-Host "  Stop agent:   docker stop oryggi-gateway"
    Write-Host "  Start agent:  docker start oryggi-gateway"
    Write-Host "  Remove:       docker rm -f oryggi-gateway"
    Write-Host ""
    Write-Host "Your database should now appear as 'Online' in the OryggiAI dashboard!"
    Write-Host ""
    Write-Host "Press any key to view the agent logs..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    docker logs oryggi-gateway -f
}} else {{
    Write-Host "Failed to start gateway agent!" -ForegroundColor Red
    Write-Host "Check if Docker is running and try again."
    exit 1
}}
'''
        return Response(
            content=script_content,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": "attachment; filename=install-oryggi-gateway.ps1"
            }
        )

    elif format == "batch":
        # Windows Batch file for CMD
        script_content = f'''@echo off
REM OryggiAI Gateway Agent - Windows Installer
REM Run this as Administrator

echo ========================================
echo   OryggiAI Gateway Agent Installer
echo ========================================
echo.

REM Configuration (pre-filled from dashboard)
set GATEWAY_TOKEN={gateway_token}
set GATEWAY_URL={gateway_ws_url}
set DB_HOST={db_host}
set DB_PORT={db_port}
set DB_DATABASE={db_database}
set DB_USERNAME={db_username}

REM Check if Docker is installed
echo [1/4] Checking Docker installation...
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Docker is not installed!
    echo Please install Docker Desktop from: https://www.docker.com/products/docker-desktop/
    pause
    start https://www.docker.com/products/docker-desktop/
    exit /b 1
)
echo Docker found!

REM Check if Docker is running
echo [2/4] Checking if Docker is running...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo Docker Desktop is not running. Please start Docker Desktop and try again.
    pause
    exit /b 1
)
echo Docker is running!

REM Prompt for password
echo.
echo [3/4] Database Configuration
echo Database: %DB_DATABASE%
echo Host: %DB_HOST%
echo Port: %DB_PORT%
echo Username: %DB_USERNAME%
echo.
set /p DB_PASSWORD=Enter your SQL Server password:

REM Remove existing container if any
echo.
echo [4/4] Setting up Gateway Agent...
docker rm -f oryggi-gateway >nul 2>&1

REM Run the gateway agent
echo Starting OryggiAI Gateway Agent...
docker run -d --name oryggi-gateway ^
    --restart unless-stopped ^
    -e GATEWAY_TOKEN=%GATEWAY_TOKEN% ^
    -e GATEWAY_SAAS_URL=%GATEWAY_URL% ^
    -e DB_HOST=%DB_HOST% ^
    -e DB_PORT=%DB_PORT% ^
    -e DB_DATABASE=%DB_DATABASE% ^
    -e DB_USERNAME=%DB_USERNAME% ^
    -e DB_PASSWORD=%DB_PASSWORD% ^
    oryggiai/gateway-agent:latest

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo   Gateway Agent Started Successfully!
    echo ========================================
    echo.
    echo Useful commands:
    echo   View logs:    docker logs oryggi-gateway -f
    echo   Stop agent:   docker stop oryggi-gateway
    echo   Start agent:  docker start oryggi-gateway
    echo   Remove:       docker rm -f oryggi-gateway
    echo.
    echo Your database should now appear as 'Online' in the OryggiAI dashboard!
    echo.
    pause
    docker logs oryggi-gateway -f
) else (
    echo Failed to start gateway agent!
    pause
    exit /b 1
)
'''
        return Response(
            content=script_content,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": "attachment; filename=install-oryggi-gateway.bat"
            }
        )

    elif format == "compose":
        # Docker Compose file
        compose_content = f'''# OryggiAI Gateway Agent - Docker Compose Configuration
#
# Instructions:
# 1. Save this file as docker-compose.yml
# 2. Update DB_PASSWORD with your SQL Server password
# 3. Run: docker-compose up -d
# 4. View logs: docker-compose logs -f

version: '3.8'

services:
  oryggi-gateway:
    image: oryggiai/gateway-agent:latest
    container_name: oryggi-gateway-agent
    restart: unless-stopped
    environment:
      # Gateway token (DO NOT SHARE - this is your unique token)
      - GATEWAY_TOKEN={gateway_token}

      # Gateway server URL
      - GATEWAY_SAAS_URL={gateway_ws_url}

      # SQL Server connection settings
      - DB_HOST={db_host}
      - DB_PORT={db_port}
      - DB_DATABASE={db_database}
      - DB_USERNAME={db_username}
      - DB_PASSWORD=YOUR_PASSWORD_HERE  # <-- UPDATE THIS

      # Optional settings
      - LOG_LEVEL=INFO

    # For connecting to SQL Server on host machine
    extra_hosts:
      - "host.docker.internal:host-gateway"

    # Health check
    healthcheck:
      test: ["CMD", "python", "-c", "import sys; sys.exit(0)"]
      interval: 30s
      timeout: 10s
      retries: 3
'''
        return Response(
            content=compose_content,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": "attachment; filename=docker-compose.yml"
            }
        )

    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid format. Use: powershell, batch, or compose"
        )


@router.get("/download-native-installer")
async def download_native_installer(
    gateway_token: str = Query(..., description="Gateway token to embed"),
    db_database: str = Query("", description="Database name (optional, can be selected in app)"),
    db: Session = Depends(get_platform_db),
    # NOTE: No auth required - gateway_token serves as validation
    # This allows direct browser download via window.location.href
):
    """
    Download the native Windows installer for zero-config gateway setup.

    This installer:
    - Requires NO Docker
    - Uses Windows Authentication (no SQL password needed!)
    - Auto-discovers databases
    - Runs as Windows Service for auto-start

    Args:
        gateway_token: The gateway token from generate-token endpoint
        db_database: Optional database name to pre-select

    Returns:
        Redirect to download the native installer with embedded token
    """
    import hashlib
    from fastapi.responses import RedirectResponse

    # Validate gateway_token format (basic validation)
    if not gateway_token or not gateway_token.startswith("gw_"):
        raise HTTPException(
            status_code=400,
            detail="Invalid gateway token format. Token must start with 'gw_'"
        )

    # Look up database configuration from gateway token
    db_host = "localhost"  # Default fallback
    db_port = 1433  # Default fallback

    try:
        # Hash the token to find the ApiKey
        token_hash = hashlib.sha256(gateway_token.encode()).hexdigest()

        # Find the ApiKey with this hash
        api_key = db.query(ApiKey).filter(ApiKey.key_hash == token_hash).first()

        if api_key:
            # Find the TenantDatabase linked to this gateway token
            tenant_db = db.query(TenantDatabase).filter(
                TenantDatabase.gateway_api_key_id == api_key.id
            ).first()

            if tenant_db:
                db_host = tenant_db.host or "localhost"
                db_port = tenant_db.port or 1433
                # Use database name from the record if not provided
                if not db_database:
                    db_database = tenant_db.database_name or ""
                logger.info(f"Found database config: host={db_host}, port={db_port}, db={db_database}")
    except Exception as e:
        logger.warning(f"Could not look up database from token: {e}. Using defaults.")

    # Get gateway WebSocket URL from settings
    settings = get_settings()
    gateway_ws_url = settings.gateway_ws_url

    # ALWAYS return the PowerShell installer script
    # The script contains the embedded token and will:
    # 1. Save configuration with the token
    # 2. Discover SQL Server databases
    # 3. Download the gateway agent exe from /api/gateway/download-agent-exe
    # 4. Run the gateway agent automatically
    #
    # This is TRUE zero-config - users just run the script and everything works!

    # Return a TRUE zero-config PowerShell script that:
    # 1. Saves configuration
    # 2. Discovers SQL Server databases
    # 3. Downloads the gateway agent
    # 4. Runs the gateway agent automatically

    # Derive base URL from gateway WS URL (ws:// -> http://)
    base_url = gateway_ws_url.replace("ws://", "http://").replace("wss://", "https://")
    base_url = base_url.rsplit("/api/gateway", 1)[0]  # Remove /api/gateway/ws path

    script_content = f'''# OryggiAI Gateway Agent - Zero Config Windows Service Installer
# This script runs NATIVELY on Windows - NO DOCKER REQUIRED!
# Uses Windows Authentication - NO SQL PASSWORD NEEDED!
# Installs as a WINDOWS SERVICE - auto-starts silently in background!

#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  OryggiAI Gateway Agent" -ForegroundColor Cyan
Write-Host "  WINDOWS SERVICE INSTALLER" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {{
    Write-Host "ERROR: This script must be run as Administrator!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    Write-Host "Then run this script again." -ForegroundColor Yellow
    Write-Host ""
    pause
    exit 1
}}

# Configuration (pre-filled from your dashboard!)
$GATEWAY_TOKEN = "{gateway_token}"
$GATEWAY_URL = "{gateway_ws_url}"
$DB_DATABASE = "{db_database}"
$DB_HOST = "{db_host}"
$DB_PORT = {db_port}
$SERVER_URL = "{base_url}"
$SERVICE_NAME = "OryggiGatewayAgent"
$SERVICE_DISPLAY = "OryggiAI Gateway Agent"

# Installation directory
$installDir = "$env:ProgramData\\OryggiAI"
$configPath = "$installDir\\gateway-config.json"
$exePath = "$installDir\\OryggiGatewayService.exe"
$logsDir = "$installDir\\logs"

# Create installation directories
Write-Host "[1/5] Creating installation directories..." -ForegroundColor Yellow
New-Item -ItemType Directory -Path $installDir -Force | Out-Null
New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
Write-Host "      Done!" -ForegroundColor Green

# Discover SQL Server databases using Windows Authentication
Write-Host ""
Write-Host "[2/5] Discovering SQL Server databases..." -ForegroundColor Yellow

$selectedDatabase = $DB_DATABASE
$connectionString = "Server=$DB_HOST;Database=master;Integrated Security=True;TrustServerCertificate=True;"

try {{
    $connection = New-Object System.Data.SqlClient.SqlConnection($connectionString)
    $connection.Open()

    $command = $connection.CreateCommand()
    $command.CommandText = "SELECT name FROM sys.databases WHERE name NOT IN ('master','tempdb','model','msdb') ORDER BY name"
    $reader = $command.ExecuteReader()

    $databases = @()
    while ($reader.Read()) {{
        $databases += $reader["name"]
    }}
    $connection.Close()

    if ($databases.Count -gt 0) {{
        Write-Host "      Found $($databases.Count) database(s):" -ForegroundColor Green
        for ($i = 0; $i -lt $databases.Count; $i++) {{
            Write-Host "        [$($i+1)] $($databases[$i])" -ForegroundColor White
        }}

        if (-not $selectedDatabase -or $selectedDatabase -eq "") {{
            Write-Host ""
            $selection = Read-Host "      Select database number (1-$($databases.Count))"
            $selectedDatabase = $databases[[int]$selection - 1]
        }}
        Write-Host ""
        Write-Host "      Selected: $selectedDatabase" -ForegroundColor Cyan
    }} else {{
        Write-Host "      No user databases found." -ForegroundColor Yellow
        $selectedDatabase = Read-Host "      Enter database name manually"
    }}
}} catch {{
    Write-Host "      Could not auto-discover databases: $($_.Exception.Message)" -ForegroundColor Yellow
    if (-not $selectedDatabase) {{
        $selectedDatabase = Read-Host "      Enter database name manually"
    }}
}}

# Save configuration (using ASCII to avoid BOM issues)
Write-Host ""
Write-Host "[3/5] Saving configuration..." -ForegroundColor Yellow

$config = @{{
    gateway_token = $GATEWAY_TOKEN
    saas_url = $GATEWAY_URL
    db_database = $selectedDatabase
    db_host = $DB_HOST
    db_port = $DB_PORT
    use_windows_auth = $true
    db_driver = "ODBC Driver 17 for SQL Server"
}}

# Convert to JSON and save without BOM
$jsonContent = $config | ConvertTo-Json -Depth 10
[System.IO.File]::WriteAllText($configPath, $jsonContent, [System.Text.UTF8Encoding]::new($false))
Write-Host "      Saved to: $configPath" -ForegroundColor Green

# Download gateway agent executable
Write-Host ""
Write-Host "[4/5] Downloading Gateway Agent Service..." -ForegroundColor Yellow

$downloadUrl = "$SERVER_URL/api/gateway/download-agent-exe"
try {{
    # Stop and remove existing service if any
    $existingService = Get-Service -Name $SERVICE_NAME -ErrorAction SilentlyContinue
    if ($existingService) {{
        Write-Host "      Stopping existing service..." -ForegroundColor Cyan
        Stop-Service -Name $SERVICE_NAME -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
        sc.exe delete $SERVICE_NAME | Out-Null
        Start-Sleep -Seconds 1
    }}

    # Download with progress
    Write-Host "      Downloading from: $downloadUrl" -ForegroundColor Gray
    $webClient = New-Object System.Net.WebClient
    $webClient.DownloadFile($downloadUrl, $exePath)
    Write-Host "      Downloaded successfully!" -ForegroundColor Green
}} catch {{
    Write-Host "      Download failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "      Please contact support or download manually." -ForegroundColor Yellow
    pause
    exit 1
}}

# Install as Windows Service
Write-Host ""
Write-Host "[5/5] Installing Windows Service..." -ForegroundColor Yellow

try {{
    # Install the service using the EXE's built-in installer
    Write-Host "      Installing service..." -ForegroundColor Cyan
    $installResult = & $exePath install 2>&1

    if ($LASTEXITCODE -ne 0) {{
        # Try using sc.exe as fallback
        Write-Host "      Using sc.exe for installation..." -ForegroundColor Cyan
        sc.exe create $SERVICE_NAME binPath= "`"$exePath`"" start= delayed-auto DisplayName= "$SERVICE_DISPLAY"
        sc.exe description $SERVICE_NAME "Connects your local SQL Server database to OryggiAI cloud platform for natural language querying."
        sc.exe failure $SERVICE_NAME reset= 86400 actions= restart/5000/restart/10000/restart/30000
    }}

    # Start the service
    Write-Host "      Starting service..." -ForegroundColor Cyan
    Start-Service -Name $SERVICE_NAME -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3

    # Verify service is running
    $service = Get-Service -Name $SERVICE_NAME -ErrorAction SilentlyContinue
    if ($service -and $service.Status -eq "Running") {{
        Write-Host "      Service is running!" -ForegroundColor Green
    }} else {{
        Write-Host "      Service installed but not running yet." -ForegroundColor Yellow
        Write-Host "      Check logs at: $logsDir\\gateway-service.log" -ForegroundColor Gray
    }}

}} catch {{
    Write-Host "      Service installation error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "      Manual installation:" -ForegroundColor Yellow
    Write-Host "        $exePath install" -ForegroundColor White
    Write-Host "        $exePath start" -ForegroundColor White
}}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  INSTALLATION COMPLETE!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Gateway Agent Service installed!" -ForegroundColor Cyan
Write-Host ""
Write-Host "Details:" -ForegroundColor Yellow
Write-Host "  Executable: $exePath" -ForegroundColor White
Write-Host "  Config:     $configPath" -ForegroundColor White
Write-Host "  Logs:       $logsDir\\gateway-service.log" -ForegroundColor White
Write-Host "  Database:   $selectedDatabase" -ForegroundColor White
Write-Host ""
Write-Host "The service will:" -ForegroundColor Cyan
Write-Host "  - Start automatically when Windows boots" -ForegroundColor White
Write-Host "  - Run silently in the background" -ForegroundColor White
Write-Host "  - Auto-restart if it crashes" -ForegroundColor White
Write-Host "  - Connect to OryggiAI using Windows Authentication" -ForegroundColor White
Write-Host ""
Write-Host "Manage the service:" -ForegroundColor Yellow
Write-Host "  View status:  Get-Service $SERVICE_NAME" -ForegroundColor Gray
Write-Host "  Stop:         Stop-Service $SERVICE_NAME" -ForegroundColor Gray
Write-Host "  Start:        Start-Service $SERVICE_NAME" -ForegroundColor Gray
Write-Host "  Uninstall:    $exePath remove" -ForegroundColor Gray
Write-Host ""
Write-Host "Your database should appear as 'Online' in OryggiAI dashboard!" -ForegroundColor Green
Write-Host ""
pause
'''
    from fastapi.responses import Response
    return Response(
        content=script_content,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": "attachment; filename=setup-oryggi-gateway-native.ps1"
        }
    )


@router.get("/download-agent-exe")
async def download_agent_exe():
    """
    Download the Gateway Agent executable (Windows Service version).

    This endpoint serves the pre-built OryggiGatewayService.exe for the
    PowerShell installer script to download automatically.

    Returns:
        The gateway agent service executable file
    """
    from fastapi.responses import FileResponse

    # Check multiple possible locations for the service exe
    base_path = Path(__file__).parent.parent.parent
    possible_paths = [
        # Service version (preferred)
        base_path / "static" / "OryggiGatewayService.exe",
        base_path / "oryggi-gateway-agent" / "dist" / "OryggiGatewayService.exe",
        # Legacy GUI version (fallback)
        base_path / "static" / "OryggiAI-Gateway.exe",
        base_path / "oryggi-gateway-agent" / "dist" / "OryggiAI-Gateway.exe",
        # Server deployment paths
        Path("C:/Users/sudo/Downloads/OryggiAI_Clean_Package/OryggiAI_ChatbotService/AI_ChatbotService/static/OryggiGatewayService.exe"),
        Path("C:/OryggiAI/OryggiGatewayService.exe"),
    ]

    for exe_path in possible_paths:
        if exe_path.exists():
            filename = "OryggiGatewayService.exe" if "Service" in str(exe_path) else "OryggiAI-Gateway.exe"
            return FileResponse(
                path=str(exe_path),
                filename=filename,
                media_type="application/octet-stream",
            )

    # If exe not found, return error
    raise HTTPException(
        status_code=404,
        detail="Gateway Agent executable not found. Please contact support."
    )


@router.get("/download-zero-config-installer")
async def download_zero_config_installer(
    gateway_token: str = Query(..., description="Gateway token to embed"),
    db_database: str = Query("", description="Database name (optional)"),
    db: Session = Depends(get_platform_db),
):
    """
    Download the Zero-Config Gateway Agent Installer.

    This endpoint returns a ZIP file containing:
    1. OryggiAI-Gateway-Launcher.exe - Small launcher that auto-runs installer
    2. gateway-launch-config.json - Pre-filled configuration with your token

    Customer just extracts and double-clicks - NO PowerShell, NO commands!

    The launcher will:
    - Download the full installer automatically
    - Run it with pre-filled token and database
    - Handle admin privileges automatically
    - Provide GUI progress feedback

    Args:
        gateway_token: The gateway token from generate-token endpoint
        db_database: Optional database name to pre-select

    Returns:
        ZIP file for download
    """
    import hashlib
    import zipfile
    import io
    import json

    # Validate gateway_token format
    if not gateway_token or not gateway_token.startswith("gw_"):
        raise HTTPException(
            status_code=400,
            detail="Invalid gateway token format. Token must start with 'gw_'"
        )

    # Look up database configuration from gateway token
    db_host = "localhost"
    db_port = 1433

    try:
        token_hash = hashlib.sha256(gateway_token.encode()).hexdigest()
        api_key = db.query(ApiKey).filter(ApiKey.key_hash == token_hash).first()

        if api_key:
            tenant_db = db.query(TenantDatabase).filter(
                TenantDatabase.gateway_api_key_id == api_key.id
            ).first()

            if tenant_db:
                db_host = tenant_db.host or "localhost"
                db_port = tenant_db.port or 1433
                if not db_database:
                    db_database = tenant_db.database_name or ""
                logger.info(f"Found database config for zero-config installer: host={db_host}, port={db_port}, db={db_database}")
    except Exception as e:
        logger.warning(f"Could not look up database from token: {e}. Using defaults.")

    # Get gateway WebSocket URL from settings
    settings = get_settings()
    gateway_ws_url = settings.gateway_ws_url

    # Derive base URL
    base_url = gateway_ws_url.replace("ws://", "http://").replace("wss://", "https://")
    base_url = base_url.rsplit("/api/gateway", 1)[0]

    # Create configuration JSON
    config = {
        "gateway_token": gateway_token,
        "database_name": db_database,
        "gateway_url": gateway_ws_url,
        "db_host": db_host,
        "db_port": db_port,
        "server_url": base_url,
        "installer_filename": "OryggiAI-Gateway-Setup.exe"
    }

    config_json = json.dumps(config, indent=2)

    # Find the launcher executable
    base_path = Path(__file__).parent.parent.parent
    possible_launcher_paths = [
        base_path / "static" / "OryggiAI-Gateway-Launcher.exe",
        base_path / "oryggi-gateway-agent" / "dist" / "OryggiAI-Gateway-Launcher.exe",
        Path("C:/OryggiAI/OryggiAI-Gateway-Launcher.exe"),
    ]

    launcher_path = None
    for path in possible_launcher_paths:
        if path.exists():
            launcher_path = path
            break

    if not launcher_path:
        # Launcher not built yet - return instructions
        raise HTTPException(
            status_code=404,
            detail="Zero-config launcher not available. Please use the PowerShell installer or build the launcher first."
        )

    # Create ZIP file in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Add launcher executable
        zip_file.write(launcher_path, "OryggiAI-Gateway-Launcher.exe")

        # Add configuration file
        zip_file.writestr("gateway-launch-config.json", config_json)

        # Add README
        readme_content = """OryggiAI Gateway Agent - Zero Config Installer
=============================================

Instructions:
1. Extract all files to a folder
2. Double-click "OryggiAI-Gateway-Launcher.exe"
3. Follow the installation wizard
4. Done! Your database will appear online in OryggiAI dashboard.

Configuration has been pre-filled with your gateway token.

Need help? Visit https://oryggi.ai/support
"""
        zip_file.writestr("README.txt", readme_content)

    zip_buffer.seek(0)

    from fastapi.responses import Response
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": "attachment; filename=OryggiAI-Gateway-Installer.zip"
        }
    )


@router.get("/download-installer-exe")
async def download_installer_exe():
    """
    Download the Inno Setup installer executable.

    This is the main installer that the launcher downloads.
    Returns the OryggiAI-Gateway-Setup.exe file.
    """
    from fastapi.responses import FileResponse

    base_path = Path(__file__).parent.parent.parent
    possible_paths = [
        base_path / "static" / "OryggiAI-Gateway-Setup.exe",
        base_path / "oryggi-gateway-agent" / "Output" / "OryggiAI-Gateway-Setup.exe",
        Path("C:/OryggiAI/OryggiAI-Gateway-Setup.exe"),
    ]

    for exe_path in possible_paths:
        if exe_path.exists():
            return FileResponse(
                path=str(exe_path),
                filename="OryggiAI-Gateway-Setup.exe",
                media_type="application/octet-stream",
            )

    raise HTTPException(
        status_code=404,
        detail="Gateway installer not found. Please build it first with Inno Setup."
    )
