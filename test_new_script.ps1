# OryggiAI Gateway Agent - TRUE Zero Config Installer
# This script runs NATIVELY on Windows - NO DOCKER REQUIRED!
# Uses Windows Authentication - NO SQL PASSWORD NEEDED!
# Downloads and runs the gateway agent AUTOMATICALLY!

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  OryggiAI Gateway Agent" -ForegroundColor Cyan
Write-Host "  ONE-CLICK SETUP" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Configuration (pre-filled from your dashboard!)
$GATEWAY_TOKEN = "gw_test123"
$GATEWAY_URL = "ws://103.197.77.163:9000/api/gateway/ws"
$DB_DATABASE = ""
$SERVER_URL = "http://103.197.77.163:9000"

# Installation directory
$installDir = "$env:ProgramData\OryggiAI"
$configPath = "$installDir\gateway-config.json"
$exePath = "$installDir\OryggiAI-Gateway.exe"

# Create installation directory
Write-Host "[1/4] Creating installation directory..." -ForegroundColor Yellow
New-Item -ItemType Directory -Path $installDir -Force | Out-Null
Write-Host "      Done!" -ForegroundColor Green

# Discover SQL Server databases using Windows Authentication
Write-Host ""
Write-Host "[2/4] Discovering SQL Server databases..." -ForegroundColor Yellow

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

# Save configuration
Write-Host ""
Write-Host "[3/4] Saving configuration..." -ForegroundColor Yellow

$config = @{
    gateway_token = $GATEWAY_TOKEN
    saas_url = $GATEWAY_URL
    db_database = $selectedDatabase
    db_host = "localhost"
    db_port = 1433
    use_windows_auth = $true
    db_driver = "ODBC Driver 17 for SQL Server"
} | ConvertTo-Json -Depth 10

$config | Out-File $configPath -Encoding UTF8
Write-Host "      Saved to: $configPath" -ForegroundColor Green

# Download gateway agent executable
Write-Host ""
Write-Host "[4/4] Downloading Gateway Agent..." -ForegroundColor Yellow

$downloadUrl = "$SERVER_URL/api/gateway/download-agent-exe"
try {
    # Check if already downloaded
    if (Test-Path $exePath) {
        Write-Host "      Gateway Agent already exists, updating..." -ForegroundColor Cyan
    }

    # Download with progress
    $webClient = New-Object System.Net.WebClient
    $webClient.DownloadFile($downloadUrl, $exePath)
    Write-Host "      Downloaded successfully!" -ForegroundColor Green
} catch {
    Write-Host "      Download failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "      The gateway agent executable is not yet available on the server." -ForegroundColor Yellow
    Write-Host "      Your configuration has been saved. Once the executable is available," -ForegroundColor Yellow
    Write-Host "      run this script again or download manually from the dashboard." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "      Configuration saved to: $configPath" -ForegroundColor Gray
    pause
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  INSTALLATION COMPLETE!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Gateway Agent installed to: $exePath" -ForegroundColor Cyan
Write-Host "Configuration saved to: $configPath" -ForegroundColor Cyan
Write-Host "Database: $selectedDatabase" -ForegroundColor Cyan
Write-Host ""

# Ask user if they want to start the agent now
Write-Host "Do you want to start the Gateway Agent now? (Y/N)" -ForegroundColor Yellow
$startNow = Read-Host "Choice"

if ($startNow -eq "Y" -or $startNow -eq "y") {
    Write-Host ""
    Write-Host "Starting Gateway Agent..." -ForegroundColor Green
    Write-Host "Your database will appear as 'Online' in OryggiAI within seconds!" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Press Ctrl+C to stop the agent." -ForegroundColor Yellow
    Write-Host ""

    # Run the gateway agent
    & $exePath --config $configPath
} else {
    Write-Host ""
    Write-Host "To start the Gateway Agent later, run:" -ForegroundColor Cyan
    Write-Host "  $exePath" -ForegroundColor White
    Write-Host ""
    Write-Host "Or create a Windows Service for auto-start:" -ForegroundColor Cyan
    Write-Host "  sc create OryggiGateway binPath= `"$exePath --config $configPath`"" -ForegroundColor White
    Write-Host ""
}

pause
