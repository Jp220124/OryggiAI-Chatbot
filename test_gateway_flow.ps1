# Complete Gateway Agent Test Flow
$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  REAL USER TEST - Gateway Agent Flow" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Login
Write-Host "[Step 1] Logging in..." -ForegroundColor Yellow
$loginBody = @{
    email = "critic2024@test.com"
    password = "Critic@2024"
} | ConvertTo-Json

$loginResponse = Invoke-RestMethod -Uri "http://103.197.77.163:9000/api/auth/login" -Method Post -Body $loginBody -ContentType "application/json"
$token = $loginResponse.tokens.access_token
Write-Host "         Logged in as: $($loginResponse.user.full_name)" -ForegroundColor Green

# Step 2: Get databases
Write-Host ""
Write-Host "[Step 2] Getting databases..." -ForegroundColor Yellow
$headers = @{ Authorization = "Bearer $token" }
$databases = Invoke-RestMethod -Uri "http://103.197.77.163:9000/api/tenant/databases" -Method Get -Headers $headers
Write-Host "         Found $($databases.Count) database(s):" -ForegroundColor Green
foreach ($db in $databases) {
    Write-Host "           - $($db.name) ($($db.host):$($db.port))" -ForegroundColor White
}

# Step 3: Generate gateway token
Write-Host ""
Write-Host "[Step 3] Generating gateway token..." -ForegroundColor Yellow
$dbId = $databases[0].id
$tokenResponse = Invoke-RestMethod -Uri "http://103.197.77.163:9000/api/gateway/databases/$dbId/generate-token" -Method Post -Headers $headers
Write-Host "         Token Response: $($tokenResponse | ConvertTo-Json -Depth 3)" -ForegroundColor Gray
$gatewayToken = $tokenResponse.token
if (-not $gatewayToken) { $gatewayToken = $tokenResponse.gateway_token }
Write-Host "         Gateway Token: $gatewayToken" -ForegroundColor Green

# Step 4: Download installer
Write-Host ""
Write-Host "[Step 4] Downloading installer from website..." -ForegroundColor Yellow
$installerUrl = "http://103.197.77.163:9000/api/gateway/download-native-installer?gateway_token=$gatewayToken&db_database=$($databases[0].database_name)"
$installerPath = "$env:TEMP\setup-oryggi-gateway-native.ps1"
Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath -UseBasicParsing
$fileSize = (Get-Item $installerPath).Length
Write-Host "         Downloaded: $installerPath ($fileSize bytes)" -ForegroundColor Green

# Step 5: Show installer contents (first 50 lines)
Write-Host ""
Write-Host "[Step 5] Installer content preview:" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Gray
Get-Content $installerPath | Select-Object -First 50 | ForEach-Object { Write-Host $_ -ForegroundColor DarkGray }
Write-Host "..." -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Gray

# Step 6: Verify key elements in installer
Write-Host ""
Write-Host "[Step 6] Verifying installer content..." -ForegroundColor Yellow
$content = Get-Content $installerPath -Raw

if ($content -match "GATEWAY_TOKEN.*=.*`"$gatewayToken`"") {
    Write-Host "         [OK] Gateway token embedded correctly" -ForegroundColor Green
} else {
    Write-Host "         [FAIL] Gateway token NOT found!" -ForegroundColor Red
}

if ($content -match "download-agent-exe") {
    Write-Host "         [OK] Downloads exe from server" -ForegroundColor Green
} else {
    Write-Host "         [FAIL] No exe download URL found!" -ForegroundColor Red
}

if ($content -match "INSTALLATION COMPLETE") {
    Write-Host "         [OK] Has completion message" -ForegroundColor Green
} else {
    Write-Host "         [FAIL] No completion message!" -ForegroundColor Red
}

if ($content -match "Do you want to start") {
    Write-Host "         [OK] Prompts to start agent" -ForegroundColor Green
} else {
    Write-Host "         [FAIL] No start prompt!" -ForegroundColor Red
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  TEST COMPLETE" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Installer saved to: $installerPath" -ForegroundColor Cyan
Write-Host "To test the actual installer, run:" -ForegroundColor Cyan
Write-Host "  powershell -ExecutionPolicy Bypass -File `"$installerPath`"" -ForegroundColor White
