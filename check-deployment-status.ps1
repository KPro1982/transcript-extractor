# Quick deployment status checker
Write-Host "╔════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║   Railway Deployment Status Check         ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

Write-Host "Recent commits:" -ForegroundColor Yellow
git log --oneline -3
Write-Host ""

Write-Host "Checking Railway worker status..." -ForegroundColor Yellow
Write-Host "(This will show recent logs from the worker)" -ForegroundColor Gray
Write-Host ""

# Try to get worker logs
railway logs --service worker --tail 30

Write-Host ""
Write-Host "════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "What to look for:" -ForegroundColor Yellow
Write-Host "  ✅ Recent startup messages = Deployment complete" -ForegroundColor Green
Write-Host "  ⏳ Old timestamps = Deployment still in progress" -ForegroundColor Yellow
Write-Host "  ❌ Error messages = Deployment failed" -ForegroundColor Red
Write-Host ""
Write-Host "If deployment is complete, run:" -ForegroundColor Cyan
Write-Host "  python test-railway-upload.py" -ForegroundColor White
Write-Host ""











