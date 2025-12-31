@echo off
REM Build Script for OryggiAI Gateway Agent
REM Creates a standalone Windows executable (.EXE)

echo ============================================
echo OryggiAI Gateway Agent - Build Script
echo ============================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    exit /b 1
)

REM Create virtual environment if not exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -q websockets pyodbc PyYAML pyinstaller

REM Build the EXE
echo.
echo Building executable...
echo.
pyinstaller OryggiGatewayAgent.spec --clean

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Build failed!
    exit /b 1
)

echo.
echo ============================================
echo BUILD SUCCESSFUL!
echo ============================================
echo.
echo Executable location:
echo   dist\OryggiGatewayAgent.exe
echo.
echo File size:
dir /b dist\OryggiGatewayAgent.exe

echo.
echo To distribute:
echo   1. Copy dist\OryggiGatewayAgent.exe
echo   2. Users just need to double-click to run!
echo.
pause
