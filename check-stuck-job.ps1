# Quick script to check Railway worker logs for the stuck job
Write-Host "Checking Railway worker logs for the current processing job..." -ForegroundColor Cyan
Write-Host ""

# Get recent worker logs to see what's happening
railway logs --service worker --tail 100

Write-Host ""
Write-Host "========================================" -ForegroundColor Yellow
Write-Host "Look for:" -ForegroundColor Yellow
Write-Host "  1. Current batch being processed" -ForegroundColor Gray
Write-Host "  2. Any timeout or error messages" -ForegroundColor Gray
Write-Host "  3. OpenAI API rate limit errors" -ForegroundColor Gray
Write-Host "  4. Memory issues" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Yellow










