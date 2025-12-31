$services = Get-Service | Where-Object { $_.Name -like 'MSSQL*' -and $_.Status -eq 'Stopped' }
foreach ($svc in $services) {
    Write-Host "Starting: $($svc.Name)"
    Start-Service $svc.Name
}
Start-Sleep -Seconds 3
Get-Service 'MSSQL*' | Format-Table Name, Status
