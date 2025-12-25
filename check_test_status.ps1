# Quick status check for running test
Write-Host "Checking test status..." -ForegroundColor Cyan

# Check if Python test process is running
$processes = Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*run_test_20min*" }

if ($processes) {
    Write-Host "`n✓ Test is running!" -ForegroundColor Green
    Write-Host "  Process ID: $($processes.Id)" -ForegroundColor Gray
    Write-Host "  Started: $($processes.StartTime)" -ForegroundColor Gray
    Write-Host "  CPU Time: $($processes.CPU)" -ForegroundColor Gray
    Write-Host "  Memory: $([math]::Round($processes.WorkingSet64/1MB, 2)) MB" -ForegroundColor Gray
} else {
    Write-Host "`n✗ Test process not found" -ForegroundColor Yellow
    Write-Host "  The test may have completed or not started yet." -ForegroundColor Gray
}

# Check for log files or recent output
Write-Host "`nChecking for test artifacts..." -ForegroundColor Cyan
if (Test-Path "artifacts/diagnostics") {
    Write-Host "✓ Artifacts directory exists" -ForegroundColor Green
    Get-ChildItem "artifacts/diagnostics" -ErrorAction SilentlyContinue | Select-Object -First 5 | Format-Table Name, LastWriteTime
} else {
    Write-Host "⚠ No artifacts directory found" -ForegroundColor Yellow
}

Write-Host "`nTo view live output, check the terminal where the test was started." -ForegroundColor Cyan













