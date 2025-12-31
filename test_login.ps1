# Test login and get token
$body = @{
    email = "critic2024@test.com"
    password = "Critic@2024"
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Uri "http://103.197.77.163:9000/api/auth/login" -Method Post -Body $body -ContentType "application/json"
    Write-Host "Login successful!"
    Write-Host "Response: $($response | ConvertTo-Json -Depth 5)"

    if ($response.access_token) {
        $response.access_token | Out-File "auth_token.txt" -NoNewline
        Write-Host "Token saved to auth_token.txt"
    }
} catch {
    Write-Host "Login failed: $($_.Exception.Message)"
    Write-Host "Response: $($_.Exception.Response)"
}
