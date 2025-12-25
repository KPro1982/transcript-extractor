# Redeploy worker to Railway with the latest fix
Write-Host "Redeploying Worker to Railway..." -ForegroundColor Cyan
Write-Host ""

# Ensure we're on the right branch
Write-Host "Step 1: Checking git status" -ForegroundColor Yellow
git status

Write-Host "`nStep 2: Pushing latest changes to Railway" -ForegroundColor Yellow
Write-Host "Making sure remote has latest code..." -ForegroundColor Gray
git push origin dev

Write-Host "`nStep 3: Triggering Railway worker redeploy" -ForegroundColor Yellow
Write-Host "Running: railway up --service worker" -ForegroundColor Gray
railway up --service worker

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "Worker redeployment triggered!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Wait 1-2 minutes for deployment to complete" -ForegroundColor Gray
Write-Host "2. Run: python test-railway-upload.py" -ForegroundColor Gray
Write-Host "3. Or manually upload PDF at: https://frontend-production-e051f.up.railway.app" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Green











