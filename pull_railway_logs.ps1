# Pull Railway logs for backend service to diagnose crashes
Write-Host "Pulling Railway logs for backend service..." -ForegroundColor Cyan

# Try to get logs from Railway
Write-Host "`nAttempting to pull logs via Railway CLI..." -ForegroundColor Yellow

# Method 1: Try to get logs directly
$logs = railway logs --tail 500 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "`n=== RAILWAY LOGS ===" -ForegroundColor Green
    $logs | Out-File -FilePath "railway_backend_logs.txt" -Encoding UTF8
    $logs
    
    Write-Host "`nLogs saved to: railway_backend_logs.txt" -ForegroundColor Green
    
    # Analyze for common crash patterns
    Write-Host "`n=== ANALYZING FOR CRASH PATTERNS ===" -ForegroundColor Cyan
    
    $errorPatterns = @(
        "ModuleNotFoundError",
        "ImportError", 
        "AttributeError",
        "NameError",
        "TypeError",
        "ValueError",
        "KeyError",
        "ConnectionError",
        "TimeoutError",
        "PermissionError",
        "FileNotFoundError",
        "OSError",
        "MemoryError",
        "SyntaxError",
        "IndentationError",
        "cannot import",
        "No module named",
        "PYTHONPATH",
        "Traceback",
        "Exception",
        "Error",
        "Failed",
        "Crash",
        "Killed",
        "OOM",
        "Out of memory"
    )
    
    $foundErrors = @()
    foreach ($pattern in $errorPatterns) {
        $matches = Select-String -Path "railway_backend_logs.txt" -Pattern $pattern -CaseSensitive:$false
        if ($matches) {
            $foundErrors += $matches
        }
    }
    
    if ($foundErrors.Count -gt 0) {
        Write-Host "`nFound $($foundErrors.Count) potential error patterns:" -ForegroundColor Red
        $foundErrors | Select-Object -First 20 | ForEach-Object {
            Write-Host "  Line $($_.LineNumber): $($_.Line.Trim())" -ForegroundColor Yellow
        }
    } else {
        Write-Host "`nNo obvious error patterns found in logs." -ForegroundColor Yellow
        Write-Host "Check railway_backend_logs.txt for full details." -ForegroundColor Gray
    }
    
} else {
    Write-Host "`nFailed to pull logs via CLI. Error:" -ForegroundColor Red
    $logs
    
    Write-Host "`nAlternative: Please run manually:" -ForegroundColor Yellow
    Write-Host "  1. Go to Railway dashboard: https://railway.app" -ForegroundColor Gray
    Write-Host "  2. Select your project: Depodigest 2.0" -ForegroundColor Gray
    Write-Host "  3. Click on 'backend-production-e4c7' service" -ForegroundColor Gray
    Write-Host "  4. Go to 'Deployments' tab" -ForegroundColor Gray
    Write-Host "  5. Click on latest deployment" -ForegroundColor Gray
    Write-Host "  6. View 'Logs' section" -ForegroundColor Gray
    Write-Host "`nOr run: railway logs --tail 500" -ForegroundColor Cyan
}

