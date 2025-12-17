# Get Railway logs and analyze for crash causes
Write-Host "Fetching Railway backend logs..." -ForegroundColor Cyan

# Set PYTHONPATH for import check
$env:PYTHONPATH = "C:\Users\Daniel Cravens\Desktop\Projects\PDF Reader\backend"

Write-Host "`n=== Running Import Check ===" -ForegroundColor Yellow
python scripts/diagnostics/check_imports.py

Write-Host "`n=== Attempting to Get Railway Logs ===" -ForegroundColor Yellow
Write-Host "Note: You may need to select the correct project interactively" -ForegroundColor Gray

# Try to get logs - user may need to select project
railway logs --tail 200 > railway_logs_raw.txt 2>&1

if (Test-Path railway_logs_raw.txt) {
    Write-Host "`n=== Analyzing Logs for Errors ===" -ForegroundColor Cyan
    
    $logContent = Get-Content railway_logs_raw.txt -Raw
    
    # Look for common error patterns
    $errorPatterns = @{
        "ImportError" = "Module import failed"
        "ModuleNotFoundError" = "Module not found - PYTHONPATH issue"
        "ConnectionError" = "Database/Redis connection failed"
        "asyncpg" = "PostgreSQL connection issue"
        "redis" = "Redis connection issue"
        "Traceback" = "Python exception occurred"
        "Exception" = "Exception raised"
        "Error" = "General error"
        "Failed" = "Operation failed"
        "Killed" = "Process killed (OOM?)"
        "OOM" = "Out of memory"
        "timeout" = "Connection timeout"
        "refused" = "Connection refused"
    }
    
    $foundIssues = @()
    foreach ($pattern in $errorPatterns.Keys) {
        if ($logContent -match $pattern) {
            $foundIssues += [PSCustomObject]@{
                Pattern = $pattern
                Issue = $errorPatterns[$pattern]
            }
        }
    }
    
    if ($foundIssues.Count -gt 0) {
        Write-Host "`nFound potential issues:" -ForegroundColor Red
        $foundIssues | Format-Table -AutoSize
        
        Write-Host "`nFull log saved to: railway_logs_raw.txt" -ForegroundColor Green
        Write-Host "`nLast 50 lines of log:" -ForegroundColor Yellow
        Get-Content railway_logs_raw.txt -Tail 50
    } else {
        Write-Host "`nNo obvious error patterns found." -ForegroundColor Yellow
        Write-Host "Full log saved to: railway_logs_raw.txt" -ForegroundColor Green
        Write-Host "`nLast 30 lines:" -ForegroundColor Yellow
        Get-Content railway_logs_raw.txt -Tail 30
    }
} else {
    Write-Host "`nCould not fetch logs automatically." -ForegroundColor Red
    Write-Host "Please:" -ForegroundColor Yellow
    Write-Host "1. Go to Railway dashboard" -ForegroundColor Gray
    Write-Host "2. Select 'Depodigest 2.0' project" -ForegroundColor Gray
    Write-Host "3. Click on 'backend-production-e4c7' service" -ForegroundColor Gray
    Write-Host "4. View logs in the 'Deployments' tab" -ForegroundColor Gray
}

