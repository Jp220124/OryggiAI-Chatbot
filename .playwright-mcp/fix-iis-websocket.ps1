# Fix IIS/ARR WebSocket Proxy Configuration
# Run this as Administrator on the VM

$ErrorActionPreference = "Stop"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  IIS/ARR WebSocket Proxy Fix" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# 1. Check if running as admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: Please run this script as Administrator!" -ForegroundColor Red
    exit 1
}

# 2. Enable WebSocket Protocol in IIS (if not already enabled)
Write-Host "[1/5] Checking WebSocket Protocol..." -ForegroundColor Yellow
$wsFeature = Get-WindowsFeature -Name Web-WebSockets -ErrorAction SilentlyContinue
if ($wsFeature -and $wsFeature.InstallState -ne "Installed") {
    Write-Host "      Installing WebSocket Protocol..." -ForegroundColor Cyan
    Install-WindowsFeature -Name Web-WebSockets
    Write-Host "      Done!" -ForegroundColor Green
} else {
    Write-Host "      WebSocket Protocol already installed" -ForegroundColor Green
}

# 3. Update ARR proxy settings for WebSocket
Write-Host ""
Write-Host "[2/5] Configuring ARR Proxy for WebSocket..." -ForegroundColor Yellow

$appHostConfig = "$env:SystemRoot\System32\inetsrv\config\applicationHost.config"
[xml]$config = Get-Content $appHostConfig

# Find or create proxy element
$webFarms = $config.SelectSingleNode("//webFarms")
if (-not $webFarms) {
    Write-Host "      Creating webFarms section..." -ForegroundColor Cyan
    $webFarms = $config.CreateElement("webFarms")
    $config.configuration.AppendChild($webFarms)
}

# Update system.webServer/proxy settings
$proxy = $config.SelectSingleNode("//system.webServer/proxy")
if ($proxy) {
    # Set HTTP/1.1 for WebSocket support
    $proxy.SetAttribute("httpVersion", "Http11")
    # Disable response buffering for WebSocket
    $proxy.SetAttribute("responseBufferLimit", "0")
    # Preserve host header
    $proxy.SetAttribute("preserveHostHeader", "true")
    # Enable reverse rewrite
    $proxy.SetAttribute("reverseRewriteHostInResponseHeaders", "true")
    Write-Host "      Updated ARR proxy settings" -ForegroundColor Green
} else {
    Write-Host "      ARR proxy settings not found - please enable ARR first" -ForegroundColor Yellow
}

$config.Save($appHostConfig)

# 4. Update web.config with WebSocket-specific rules
Write-Host ""
Write-Host "[3/5] Updating web.config for WebSocket..." -ForegroundColor Yellow

$webConfigPath = "C:\inetpub\wwwroot\web.config"
$webConfig = @"
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <system.webServer>
        <webSocket enabled="true" pingInterval="00:00:30" receiveBufferLimit="4194304" />
        <serverRuntime enabled="true" frequentHitThreshold="1" frequentHitTimePeriod="00:00:01" />
        <rewrite>
            <rules>
                <clear />
                <rule name="WebSocketRule" stopProcessing="true">
                    <match url="^api/gateway/ws$" />
                    <conditions logicalGrouping="MatchAll">
                        <add input="{HTTP_UPGRADE}" pattern="websocket" ignoreCase="true" />
                    </conditions>
                    <action type="Rewrite" url="http://localhost:3000/api/gateway/ws" />
                </rule>
                <rule name="ReverseProxy" stopProcessing="true">
                    <match url="(.*)" />
                    <conditions>
                        <add input="{REQUEST_URI}" pattern="^/dashboard" negate="true" />
                    </conditions>
                    <action type="Rewrite" url="http://localhost:3000/{R:1}" />
                </rule>
            </rules>
        </rewrite>
    </system.webServer>
</configuration>
"@

$webConfig | Out-File $webConfigPath -Encoding UTF8 -Force
Write-Host "      Updated web.config" -ForegroundColor Green

# 5. Add WebSocket server variables to URL Rewrite allowed list
Write-Host ""
Write-Host "[4/5] Adding WebSocket server variables..." -ForegroundColor Yellow

# Reload config
[xml]$config = Get-Content $appHostConfig

$rewrite = $config.SelectSingleNode("//rewrite")
if (-not $rewrite) {
    $rewrite = $config.CreateElement("rewrite")
    $config.configuration.SelectSingleNode("//system.webServer").AppendChild($rewrite)
}

$allowedVars = $rewrite.SelectSingleNode("allowedServerVariables")
if (-not $allowedVars) {
    $allowedVars = $config.CreateElement("allowedServerVariables")
    $rewrite.AppendChild($allowedVars)
}

# Add WebSocket-related variables
$varsToAdd = @(
    "HTTP_SEC_WEBSOCKET_KEY",
    "HTTP_SEC_WEBSOCKET_VERSION",
    "HTTP_SEC_WEBSOCKET_EXTENSIONS",
    "HTTP_SEC_WEBSOCKET_PROTOCOL",
    "HTTP_UPGRADE",
    "HTTP_CONNECTION",
    "HTTP_X_FORWARDED_FOR",
    "HTTP_X_FORWARDED_PROTO"
)

foreach ($var in $varsToAdd) {
    $existing = $allowedVars.SelectSingleNode("add[@name='$var']")
    if (-not $existing) {
        $newVar = $config.CreateElement("add")
        $newVar.SetAttribute("name", $var)
        $allowedVars.AppendChild($newVar) | Out-Null
    }
}

$config.Save($appHostConfig)
Write-Host "      Added WebSocket server variables" -ForegroundColor Green

# 6. Restart IIS
Write-Host ""
Write-Host "[5/5] Restarting IIS..." -ForegroundColor Yellow
iisreset /restart
Write-Host "      IIS restarted" -ForegroundColor Green

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  IIS WebSocket Proxy Fix Complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Test WebSocket connection with:" -ForegroundColor Cyan
Write-Host "  wscat -c ws://localhost:9000/api/gateway/ws" -ForegroundColor White
Write-Host ""
