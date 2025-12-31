"""
OryggiAI Gateway Agent - Launcher Generator

This module generates small, token-embedded launcher executables that:
1. Can be downloaded from the dashboard with pre-filled configuration
2. Download the main installer (or have it embedded)
3. Run the installer with all parameters pre-filled
4. Provide a completely automatic, zero-config installation experience

Usage:
    from launcher_generator import generate_launcher

    launcher_bytes = generate_launcher(
        gateway_token="gw_xxx",
        database_name="MyDB",
        gateway_url="wss://api.oryggi.ai/api/gateway/ws",
        db_host="localhost",
        db_port=1433
    )

    # Return as download response
    return Response(content=launcher_bytes, media_type="application/octet-stream")
"""

import os
import sys
import tempfile
import subprocess
import shutil
from pathlib import Path
from typing import Optional
import base64
import zlib


def generate_launcher_script(
    gateway_token: str,
    database_name: str = "",
    gateway_url: str = "wss://api.oryggi.ai/api/gateway/ws",
    db_host: str = "localhost",
    db_port: int = 1433,
    server_base_url: str = "https://api.oryggi.ai"
) -> str:
    """
    Generate a Python launcher script with embedded configuration.

    This script will:
    1. Download the main installer from the server
    2. Run it with pre-filled parameters
    3. Show progress to the user
    """

    script = f'''#!/usr/bin/env python3
"""
OryggiAI Gateway Agent Launcher
Auto-generated with embedded configuration
"""

import os
import sys
import tempfile
import subprocess
import urllib.request
import ctypes
import tkinter as tk
from tkinter import ttk, messagebox
import threading

# ============================================================================
# EMBEDDED CONFIGURATION (Pre-filled from your OryggiAI Dashboard)
# ============================================================================
GATEWAY_TOKEN = "{gateway_token}"
DATABASE_NAME = "{database_name}"
GATEWAY_URL = "{gateway_url}"
DB_HOST = "{db_host}"
DB_PORT = {db_port}
SERVER_URL = "{server_base_url}"
INSTALLER_URL = f"{{SERVER_URL}}/api/gateway/download-installer-exe"

# ============================================================================
# Check Admin Rights
# ============================================================================
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1
    )

# ============================================================================
# Progress Window
# ============================================================================
class InstallerLauncher:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("OryggiAI Gateway Agent Setup")
        self.root.geometry("450x200")
        self.root.resizable(False, False)

        # Center window
        self.root.eval('tk::PlaceWindow . center')

        # Icon (if available)
        try:
            self.root.iconbitmap(default='')
        except:
            pass

        # Header
        header = tk.Label(
            self.root,
            text="OryggiAI Gateway Agent",
            font=("Segoe UI", 14, "bold")
        )
        header.pack(pady=(20, 5))

        # Subheader
        subheader = tk.Label(
            self.root,
            text="Preparing installation...",
            font=("Segoe UI", 10),
            fg="gray"
        )
        subheader.pack(pady=(0, 15))

        # Progress bar
        self.progress = ttk.Progressbar(
            self.root,
            length=350,
            mode='indeterminate'
        )
        self.progress.pack(pady=10)

        # Status label
        self.status = tk.Label(
            self.root,
            text="Initializing...",
            font=("Segoe UI", 9)
        )
        self.status.pack(pady=10)

        # Start installation in background thread
        self.progress.start(10)
        thread = threading.Thread(target=self.run_installation, daemon=True)
        thread.start()

    def update_status(self, text):
        self.root.after(0, lambda: self.status.config(text=text))

    def show_error(self, message):
        self.root.after(0, lambda: messagebox.showerror("Installation Error", message))
        self.root.after(0, self.root.destroy)

    def installation_complete(self):
        self.root.after(0, self.root.destroy)

    def run_installation(self):
        try:
            # Step 1: Download installer
            self.update_status("Downloading installer...")

            installer_path = os.path.join(tempfile.gettempdir(), "OryggiAI-Gateway-Setup.exe")

            try:
                urllib.request.urlretrieve(INSTALLER_URL, installer_path)
            except Exception as e:
                self.show_error(f"Failed to download installer:\\n{{str(e)}}")
                return

            # Step 2: Build command line arguments
            self.update_status("Starting installation wizard...")

            args = [installer_path]

            # Add token parameter
            if GATEWAY_TOKEN:
                args.append(f"/token={{GATEWAY_TOKEN}}")

            # Add database parameter
            if DATABASE_NAME:
                args.append(f"/database={{DATABASE_NAME}}")

            # Add other parameters
            args.append(f"/dbhost={{DB_HOST}}")
            args.append(f"/dbport={{DB_PORT}}")
            args.append(f"/gateway_url={{GATEWAY_URL}}")

            # Step 3: Run installer
            self.update_status("Launching installer...")

            try:
                # Run installer (it will handle its own UI)
                process = subprocess.Popen(args)

                # Close our window - installer takes over
                self.installation_complete()

                # Wait for installer to complete (optional)
                # process.wait()

            except Exception as e:
                self.show_error(f"Failed to start installer:\\n{{str(e)}}")
                return

        except Exception as e:
            self.show_error(f"Unexpected error:\\n{{str(e)}}")

    def run(self):
        self.root.mainloop()

# ============================================================================
# Main Entry Point
# ============================================================================
def main():
    # Check for admin rights
    if not is_admin():
        # Re-launch with admin rights
        run_as_admin()
        sys.exit(0)

    # Run the launcher GUI
    app = InstallerLauncher()
    app.run()

if __name__ == "__main__":
    main()
'''

    return script


def generate_launcher_exe(
    gateway_token: str,
    database_name: str = "",
    gateway_url: str = "wss://api.oryggi.ai/api/gateway/ws",
    db_host: str = "localhost",
    db_port: int = 1433,
    server_base_url: str = "https://api.oryggi.ai"
) -> Optional[bytes]:
    """
    Generate a standalone launcher executable with embedded configuration.

    Uses PyInstaller to create a small .exe that downloads and runs the main installer.

    Returns:
        bytes: The executable file content, or None if generation fails
    """

    # Create temporary directory for build
    temp_dir = tempfile.mkdtemp(prefix="oryggi_launcher_")

    try:
        # Generate the launcher script
        script_content = generate_launcher_script(
            gateway_token=gateway_token,
            database_name=database_name,
            gateway_url=gateway_url,
            db_host=db_host,
            db_port=db_port,
            server_base_url=server_base_url
        )

        # Write script to temp file
        script_path = os.path.join(temp_dir, "launcher.py")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script_content)

        # Create PyInstaller spec file for small output
        spec_content = f'''
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['{script_path.replace(os.sep, "/")}'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['tkinter', 'tkinter.ttk'],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=['numpy', 'pandas', 'matplotlib', 'scipy', 'PIL', 'cv2'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='OryggiAI-Gateway-Launcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=True,  # Request admin rights
    uac_uiaccess=False,
)
'''

        spec_path = os.path.join(temp_dir, "launcher.spec")
        with open(spec_path, "w", encoding="utf-8") as f:
            f.write(spec_content)

        # Run PyInstaller
        result = subprocess.run(
            [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", spec_path],
            cwd=temp_dir,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            print(f"PyInstaller failed: {result.stderr}")
            return None

        # Read the generated executable
        exe_path = os.path.join(temp_dir, "dist", "OryggiAI-Gateway-Launcher.exe")
        if os.path.exists(exe_path):
            with open(exe_path, "rb") as f:
                return f.read()
        else:
            print("Executable not found after build")
            return None

    except Exception as e:
        print(f"Error generating launcher: {e}")
        return None

    finally:
        # Cleanup temp directory
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass


def generate_batch_launcher(
    gateway_token: str,
    database_name: str = "",
    gateway_url: str = "wss://api.oryggi.ai/api/gateway/ws",
    db_host: str = "localhost",
    db_port: int = 1433,
    server_base_url: str = "https://api.oryggi.ai"
) -> str:
    """
    Generate a simple batch file launcher (alternative to .exe).

    This is faster to generate but requires the user to run it.
    Can be wrapped in a self-extracting archive for better UX.
    """

    batch_content = f'''@echo off
setlocal EnableDelayedExpansion

:: OryggiAI Gateway Agent - Auto Installer
:: Configuration is pre-filled from your dashboard

title OryggiAI Gateway Agent Setup

:: Check for admin rights
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

:: Configuration
set "GATEWAY_TOKEN={gateway_token}"
set "DATABASE_NAME={database_name}"
set "GATEWAY_URL={gateway_url}"
set "DB_HOST={db_host}"
set "DB_PORT={db_port}"
set "SERVER_URL={server_base_url}"

echo.
echo ========================================
echo   OryggiAI Gateway Agent Setup
echo ========================================
echo.

:: Create temp directory
set "TEMP_DIR=%TEMP%\\OryggiAI_Setup"
if not exist "%TEMP_DIR%" mkdir "%TEMP_DIR%"

:: Download installer
echo Downloading installer...
set "INSTALLER_PATH=%TEMP_DIR%\\OryggiAI-Gateway-Setup.exe"
powershell -Command "Invoke-WebRequest -Uri '%SERVER_URL%/api/gateway/download-installer-exe' -OutFile '%INSTALLER_PATH%'"

if not exist "%INSTALLER_PATH%" (
    echo ERROR: Failed to download installer
    pause
    exit /b 1
)

:: Build arguments
set "ARGS=/token=%GATEWAY_TOKEN%"
if not "%DATABASE_NAME%"=="" set "ARGS=%ARGS% /database=%DATABASE_NAME%"
set "ARGS=%ARGS% /dbhost=%DB_HOST% /dbport=%DB_PORT%"
set "ARGS=%ARGS% /gateway_url=%GATEWAY_URL%"

:: Run installer
echo Starting installation...
start "" "%INSTALLER_PATH%" %ARGS%

:: Cleanup will happen automatically when installer completes
exit /b 0
'''

    return batch_content


# ============================================================================
# Alternative: PowerShell-based Launcher (Most Reliable)
# ============================================================================

def generate_powershell_launcher(
    gateway_token: str,
    database_name: str = "",
    gateway_url: str = "wss://api.oryggi.ai/api/gateway/ws",
    db_host: str = "localhost",
    db_port: int = 1433,
    server_base_url: str = "https://api.oryggi.ai"
) -> str:
    """
    Generate a PowerShell-based launcher that's wrapped in a small .exe.

    This approach creates a small VBScript wrapper that runs PowerShell
    without showing a console window.
    """

    ps_script = f'''
# OryggiAI Gateway Agent - Silent Launcher
$ErrorActionPreference = "Stop"

# Configuration (pre-filled from dashboard)
$config = @{{
    GatewayToken = "{gateway_token}"
    DatabaseName = "{database_name}"
    GatewayUrl = "{gateway_url}"
    DbHost = "{db_host}"
    DbPort = {db_port}
    ServerUrl = "{server_base_url}"
}}

# Download and run installer
$installerUrl = "$($config.ServerUrl)/api/gateway/download-installer-exe"
$installerPath = "$env:TEMP\\OryggiAI-Gateway-Setup.exe"

# Progress form
Add-Type -AssemblyName System.Windows.Forms
$form = New-Object System.Windows.Forms.Form
$form.Text = "OryggiAI Gateway Agent"
$form.Size = New-Object System.Drawing.Size(400, 150)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedDialog"
$form.MaximizeBox = $false

$label = New-Object System.Windows.Forms.Label
$label.Text = "Downloading installer..."
$label.Location = New-Object System.Drawing.Point(20, 30)
$label.Size = New-Object System.Drawing.Size(360, 20)
$form.Controls.Add($label)

$progress = New-Object System.Windows.Forms.ProgressBar
$progress.Style = "Marquee"
$progress.Location = New-Object System.Drawing.Point(20, 60)
$progress.Size = New-Object System.Drawing.Size(350, 25)
$form.Controls.Add($progress)

$form.Show()
[System.Windows.Forms.Application]::DoEvents()

try {{
    # Download
    Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath -UseBasicParsing

    $label.Text = "Starting installation..."
    [System.Windows.Forms.Application]::DoEvents()

    # Build arguments
    $args = @(
        "/token=$($config.GatewayToken)"
    )
    if ($config.DatabaseName) {{
        $args += "/database=$($config.DatabaseName)"
    }}
    $args += "/dbhost=$($config.DbHost)"
    $args += "/dbport=$($config.DbPort)"
    $args += "/gateway_url=$($config.GatewayUrl)"

    # Launch installer
    Start-Process -FilePath $installerPath -ArgumentList $args

    $form.Close()
}}
catch {{
    $form.Close()
    [System.Windows.Forms.MessageBox]::Show(
        "Failed to download installer: $($_.Exception.Message)",
        "Error",
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error
    )
}}
'''

    return ps_script


def generate_vbs_wrapper(ps_script: str) -> str:
    """
    Generate a VBScript wrapper that runs PowerShell hidden.

    This creates a .vbs file that can be double-clicked to run
    PowerShell without showing a console window.
    """

    # Encode PowerShell script for embedding
    encoded = base64.b64encode(ps_script.encode('utf-16-le')).decode('ascii')

    vbs_content = f'''
' OryggiAI Gateway Agent Launcher
' Double-click this file to install

Set shell = CreateObject("WScript.Shell")

' Check for admin
If Not WScript.Arguments.Named.Exists("elevated") Then
    ' Re-launch as admin
    Set objShell = CreateObject("Shell.Application")
    objShell.ShellExecute "wscript.exe", Chr(34) & WScript.ScriptFullName & Chr(34) & " /elevated", "", "runas", 1
    WScript.Quit
End If

' Run PowerShell hidden
psCommand = "powershell.exe -NoProfile -ExecutionPolicy Bypass -EncodedCommand {encoded}"
shell.Run psCommand, 0, True
'''

    return vbs_content


# ============================================================================
# Test
# ============================================================================

if __name__ == "__main__":
    # Test launcher generation
    print("Testing launcher generation...")

    # Test batch file generation
    batch = generate_batch_launcher(
        gateway_token="gw_test123",
        database_name="TestDB",
        server_base_url="http://localhost:3000"
    )
    print("Batch launcher generated successfully")
    print(batch[:500] + "...")

    # Test PowerShell generation
    ps = generate_powershell_launcher(
        gateway_token="gw_test123",
        database_name="TestDB",
        server_base_url="http://localhost:3000"
    )
    print("\nPowerShell launcher generated successfully")

    print("\nDone!")
