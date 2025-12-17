# Restart Frontend to Pick Up New Environment Variables

Write-Host "Restarting Frontend..." -ForegroundColor Green

# Find and stop the frontend process
$frontendProcess = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess | Select-Object -First 1

if ($frontendProcess) {
    Write-Host "Stopping existing frontend (PID: $frontendProcess)..." -ForegroundColor Yellow
    Stop-Process -Id $frontendProcess -Force
    Start-Sleep -Seconds 2
}

# Start the frontend
Write-Host "Starting frontend with Railway backend..." -ForegroundColor Green
Write-Host "Backend URL: https://backend-production-e4c7.up.railway.app" -ForegroundColor Cyan
Write-Host ""

Set-Location -Path "$PSScriptRoot\frontend"
npm run dev

