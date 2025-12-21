# Quick script to check Railway worker logs for the recent upload issue
Write-Host "Fetching Railway Worker Logs..." -ForegroundColor Cyan
Write-Host "Looking for recent processing attempts and errors..." -ForegroundColor Yellow
Write-Host ""

# Get worker logs
Write-Host "Running: railway logs --service worker" -ForegroundColor Gray
railway logs --service worker --tail 100

Write-Host "`n" 
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "If you see the 'pages' error above:" -ForegroundColor Yellow
Write-Host "  - This means the old buggy code is still running" -ForegroundColor Red
Write-Host "  - Need to redeploy worker with latest fix" -ForegroundColor Red
Write-Host ""
Write-Host "If you see successful Q&A extraction:" -ForegroundColor Yellow  
Write-Host "  - The fix is working!" -ForegroundColor Green
Write-Host "  - Check if results saved to database" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan










