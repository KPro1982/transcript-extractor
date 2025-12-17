# Railway Deployment Script for DepoDigest (PowerShell)
# This script helps automate the deployment process using Railway CLI

$ErrorActionPreference = "Stop"

Write-Host "🚂 DepoDigest Railway Deployment Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Railway CLI is installed
Write-Host "Checking for Railway CLI..." -ForegroundColor Yellow
try {
    railway --version | Out-Null
    Write-Host "✅ Railway CLI is installed" -ForegroundColor Green
} catch {
    Write-Host "❌ Railway CLI is not installed." -ForegroundColor Red
    Write-Host "📦 Install it with: npm install -g @railway/cli" -ForegroundColor Yellow
    exit 1
}
Write-Host ""

# Check if logged in
Write-Host "🔑 Checking Railway authentication..." -ForegroundColor Yellow
try {
    railway whoami | Out-Null
    Write-Host "✅ Authenticated with Railway" -ForegroundColor Green
} catch {
    Write-Host "❌ Not logged in to Railway" -ForegroundColor Red
    Write-Host "🔐 Please run: railway login" -ForegroundColor Yellow
    exit 1
}
Write-Host ""

# Main deployment flow
Write-Host "🎯 Starting deployment process..." -ForegroundColor Cyan
Write-Host ""

# Step 1: Create or link project
Write-Host "1️⃣ Setting up Railway project..." -ForegroundColor Yellow
if (-Not (Test-Path "railway.json")) {
    Write-Host "Creating new Railway project..." -ForegroundColor Yellow
    railway init
} else {
    Write-Host "Using existing Railway project" -ForegroundColor Green
}
Write-Host ""

# Step 2: Add PostgreSQL
Write-Host "2️⃣ Setting up PostgreSQL..." -ForegroundColor Yellow
Write-Host "Please add PostgreSQL through the Railway dashboard:" -ForegroundColor Cyan
Write-Host "   Dashboard → New → Database → PostgreSQL" -ForegroundColor White
Write-Host ""
Read-Host "Press Enter after you've added PostgreSQL"
Write-Host ""

# Step 3: Add Redis
Write-Host "3️⃣ Setting up Redis..." -ForegroundColor Yellow
Write-Host "Please add Redis through the Railway dashboard:" -ForegroundColor Cyan
Write-Host "   Dashboard → New → Database → Redis" -ForegroundColor White
Write-Host ""
Read-Host "Press Enter after you've added Redis"
Write-Host ""

# Step 4: Deploy Backend
Write-Host "4️⃣ Deploying Backend Service..." -ForegroundColor Yellow
Write-Host ""
Write-Host "📝 Required environment variables for Backend:" -ForegroundColor Cyan
Write-Host "   - OPENAI_API_KEY" -ForegroundColor White
Write-Host "   - ANTHROPIC_API_KEY (optional)" -ForegroundColor White
Write-Host "   - FRONTEND_URL (will set after frontend deployment)" -ForegroundColor White
Write-Host "   - API_HOST=0.0.0.0" -ForegroundColor White
Write-Host "   - API_PORT=8000" -ForegroundColor White
Write-Host "   - WORKERS_COUNT=4" -ForegroundColor White
Write-Host "   - LOG_LEVEL=INFO" -ForegroundColor White
Write-Host ""

$response = Read-Host "Have you set these variables in Railway dashboard? (y/n)"
if ($response -ne "y" -and $response -ne "Y") {
    Write-Host "Please set the environment variables in Railway dashboard and run this script again" -ForegroundColor Red
    exit 1
}

# Deploy backend
Write-Host "Deploying backend..." -ForegroundColor Yellow
Set-Location backend
railway up --service backend
Set-Location ..
Write-Host "✅ Backend deployed" -ForegroundColor Green
Write-Host ""

# Get backend URL
Write-Host "📋 Please note your backend URL from Railway dashboard" -ForegroundColor Cyan
$BACKEND_URL = Read-Host "Enter your backend URL (e.g., https://backend-production-xxxx.up.railway.app)"
Write-Host ""

# Step 5: Deploy Worker
Write-Host "5️⃣ Deploying Worker Service..." -ForegroundColor Yellow
Write-Host ""
Write-Host "Setting custom start command for worker..." -ForegroundColor Cyan
Write-Host "In Railway dashboard for worker service, set:" -ForegroundColor White
Write-Host "   Custom Start Command: celery -A workers.celery_app worker --loglevel=info --concurrency=4" -ForegroundColor White
Write-Host ""
Write-Host "Also add environment variable:" -ForegroundColor White
Write-Host "   BACKEND_URL=$BACKEND_URL" -ForegroundColor White
Write-Host ""
Read-Host "Press Enter after you've configured the worker"

Set-Location backend
railway up --service worker
Set-Location ..
Write-Host "✅ Worker deployed" -ForegroundColor Green
Write-Host ""

# Step 6: Deploy Frontend
Write-Host "6️⃣ Deploying Frontend Service..." -ForegroundColor Yellow
Write-Host ""
$WS_URL = $BACKEND_URL -replace "https", "wss"
Write-Host "📝 Required environment variables for Frontend:" -ForegroundColor Cyan
Write-Host "   - NEXT_PUBLIC_API_URL=$BACKEND_URL" -ForegroundColor White
Write-Host "   - NEXT_PUBLIC_WS_URL=$WS_URL" -ForegroundColor White
Write-Host ""

$response = Read-Host "Have you set these variables in Railway dashboard? (y/n)"
if ($response -ne "y" -and $response -ne "Y") {
    Write-Host "Please set the environment variables and run this script again" -ForegroundColor Red
    exit 1
}

Set-Location frontend
railway up --service frontend
Set-Location ..
Write-Host "✅ Frontend deployed" -ForegroundColor Green
Write-Host ""

# Get frontend URL
Write-Host "📋 Please note your frontend URL from Railway dashboard" -ForegroundColor Cyan
$FRONTEND_URL = Read-Host "Enter your frontend URL (e.g., https://frontend-production-xxxx.up.railway.app)"
Write-Host ""

# Step 7: Update backend with frontend URL
Write-Host "7️⃣ Updating Backend with Frontend URL..." -ForegroundColor Yellow
Write-Host "Please update the Backend service environment variable:" -ForegroundColor Cyan
Write-Host "   FRONTEND_URL=$FRONTEND_URL" -ForegroundColor White
Write-Host ""
Read-Host "Press Enter after you've updated the backend environment variable"
Write-Host ""

# Final checks
Write-Host "🎉 Deployment Complete!" -ForegroundColor Green
Write-Host ""
Write-Host "📍 Your services:" -ForegroundColor Cyan
Write-Host "   Backend:  $BACKEND_URL" -ForegroundColor White
Write-Host "   Frontend: $FRONTEND_URL" -ForegroundColor White
Write-Host ""
Write-Host "🔍 Next steps:" -ForegroundColor Cyan
Write-Host "   1. Verify health check: $BACKEND_URL/health" -ForegroundColor White
Write-Host "   2. Test frontend: $FRONTEND_URL" -ForegroundColor White
Write-Host "   3. Monitor logs in Railway dashboard" -ForegroundColor White
Write-Host "   4. Upload a test PDF to verify end-to-end functionality" -ForegroundColor White
Write-Host ""
Write-Host "📚 For detailed troubleshooting, see RAILWAY-DEPLOYMENT.md" -ForegroundColor Yellow
Write-Host ""

