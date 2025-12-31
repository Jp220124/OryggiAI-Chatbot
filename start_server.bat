@echo off
REM Startup script for Advance Chatbot with GTK3 support
REM Sets GTK3 path for WeasyPrint PDF generation

echo ========================================
echo Advance Chatbot - Starting Server
echo ========================================
echo.

REM Add GTK3 to PATH for this session
echo Adding GTK3 to PATH...
set "PATH=C:\Program Files\GTK3-Runtime Win64\bin;%PATH%"

REM Verify GTK3 is accessible
echo Verifying GTK3 installation...
if exist "C:\Program Files\GTK3-Runtime Win64\bin\libgobject-2.0-0.dll" (
    echo [OK] GTK3 DLL found
) else (
    echo [ERROR] GTK3 DLL not found!
    echo Please ensure GTK3-Runtime Win64 is installed.
    pause
    exit /b 1
)

echo.
echo Starting FastAPI server...
echo Press Ctrl+C to stop the server
echo.

REM Change to project directory
cd /d "D:\OryggiAI_Service\Advance_Chatbot"

REM Start the server
python -m app.main

pause
