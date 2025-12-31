# OryggiAI Gateway Agent - Zero Config Windows Service Installer
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
if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    Write-Host "Then run this script again." -ForegroundColor Yellow
    Write-Host ""
    pause
    exit 1
}

# Configuration (pre-filled from your dashboard!)
$GATEWAY_TOKEN = "gw_utuHoItsiH6ILn9vnydXxTSww-jqh0Dj52rQ2eEIiCM"
$GATEWAY_URL = "ws://103.197.77.163:3000/api/gateway/ws"
$DB_DATABASE = "ComplaintManagementDB"
$SERVER_URL = "http://103.197.77.163:3000"
$SERVICE_NAME = "OryggiGatewayAgent"
$SERVICE_DISPLAY = "OryggiAI Gateway Agent"

# Installation directory
$installDir = "$env:ProgramData\OryggiAI"
$configPath = "$installDir\gateway-config.json"
$exePath = "$installDir\OryggiGatewayService.exe"
$logsDir = "$installDir\logs"

# Create installation directories
Write-Host "[1/5] Creating installation directories..." -ForegroundColor Yellow
New-Item -ItemType Directory -Path $installDir -Force | Out-Null
New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
Write-Host "      Done!" -ForegroundColor Green

# Discover SQL Server databases using Windows Authentication
Write-Host ""
Write-Host "[2/5] Discovering SQL Server databases..." -ForegroundColor Yellow

$selectedDatabase = $DB_DATABASE
$connectionString = "Server=localhost;Database=master;Integrated Security=True;TrustServerCertificate=True;"

try {
    $connection = New-Object System.Data.SqlClient.SqlConnection($connectionString)
    $connection.Open()

    $command = $connection.CreateCommand()
    $command.CommandText = "SELECT name FROM sys.databases WHERE name NOT IN ('master','tempdb','model','msdb') ORDER BY name"
    $reader = $command.ExecuteReader()

    $databases = @()
    while ($reader.Read()) {
        $databases += $reader["name"]
    }
    $connection.Close()

    if ($databases.Count -gt 0) {
        Write-Host "      Found $($databases.Count) database(s):" -ForegroundColor Green
        for ($i = 0; $i -lt $databases.Count; $i++) {
            Write-Host "        [$($i+1)] $($databases[$i])" -ForegroundColor White
        }

        if (-not $selectedDatabase -or $selectedDatabase -eq "") {
            Write-Host ""
            $selection = Read-Host "      Select database number (1-$($databases.Count))"
            $selectedDatabase = $databases[[int]$selection - 1]
        }
        Write-Host ""
        Write-Host "      Selected: $selectedDatabase" -ForegroundColor Cyan
    } else {
        Write-Host "      No user databases found." -ForegroundColor Yellow
        $selectedDatabase = Read-Host "      Enter database name manually"
    }
} catch {
    Write-Host "      Could not auto-discover databases: $($_.Exception.Message)" -ForegroundColor Yellow
    if (-not $selectedDatabase) {
        $selectedDatabase = Read-Host "      Enter database name manually"
    }
}

# Save configuration (using ASCII to avoid BOM issues)
Write-Host ""
Write-Host "[3/5] Saving configuration..." -ForegroundColor Yellow

$config = @{
    gateway_token = $GATEWAY_TOKEN
    saas_url = $GATEWAY_URL
    db_database = $selectedDatabase
    db_host = "localhost"
    db_port = 1433
    use_windows_auth = $true
    db_driver = "ODBC Driver 17 for SQL Server"
}

# Convert to JSON and save without BOM
$jsonContent = $config | ConvertTo-Json -Depth 10
[System.IO.File]::WriteAllText($configPath, $jsonContent, [System.Text.UTF8Encoding]::new($false))
Write-Host "      Saved to: $configPath" -ForegroundColor Green

# Download gateway agent executable
Write-Host ""
Write-Host "[4/5] Downloading Gateway Agent Service..." -ForegroundColor Yellow

$downloadUrl = "$SERVER_URL/api/gateway/download-agent-exe"
try {
    # Stop and remove existing service if any
    $existingService = Get-Service -Name $SERVICE_NAME -ErrorAction SilentlyContinue
    if ($existingService) {
        Write-Host "      Stopping existing service..." -ForegroundColor Cyan
        Stop-Service -Name $SERVICE_NAME -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
        sc.exe delete $SERVICE_NAME | Out-Null
        Start-Sleep -Seconds 1
    }

    # Download with progress
    Write-Host "      Downloading from: $downloadUrl" -ForegroundColor Gray
    $webClient = New-Object System.Net.WebClient
    $webClient.DownloadFile($downloadUrl, $exePath)
    Write-Host "      Downloaded successfully!" -ForegroundColor Green
} catch {
    Write-Host "      Download failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "      Please contact support or download manually." -ForegroundColor Yellow
    pause
    exit 1
}

# Install as Windows Service
Write-Host ""
Write-Host "[5/5] Installing Windows Service..." -ForegroundColor Yellow

try {
    # Install the service using the EXE's built-in installer
    Write-Host "      Installing service..." -ForegroundColor Cyan
    $installResult = & $exePath install 2>&1

    if ($LASTEXITCODE -ne 0) {
        # Try using sc.exe as fallback
        Write-Host "      Using sc.exe for installation..." -ForegroundColor Cyan
        sc.exe create $SERVICE_NAME binPath= "`"$exePath`"" start= delayed-auto DisplayName= "$SERVICE_DISPLAY"
        sc.exe description $SERVICE_NAME "Connects your local SQL Server database to OryggiAI cloud platform for natural language querying."
        sc.exe failure $SERVICE_NAME reset= 86400 actions= restart/5000/restart/10000/restart/30000
    }

    # Start the service
    Write-Host "      Starting service..." -ForegroundColor Cyan
    Start-Service -Name $SERVICE_NAME -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3

    # Verify service is running
    $service = Get-Service -Name $SERVICE_NAME -ErrorAction SilentlyContinue
    if ($service -and $service.Status -eq "Running") {
        Write-Host "      Service is running!" -ForegroundColor Green
    } else {
        Write-Host "      Service installed but not running yet." -ForegroundColor Yellow
        Write-Host "      Check logs at: $logsDir\gateway-service.log" -ForegroundColor Gray
    }

} catch {
    Write-Host "      Service installation error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "      Manual installation:" -ForegroundColor Yellow
    Write-Host "        $exePath install" -ForegroundColor White
    Write-Host "        $exePath start" -ForegroundColor White
}

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
Write-Host "  Logs:       $logsDir\gateway-service.log" -ForegroundColor White
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
