#!/bin/bash

# Railway Deployment Script for DepoDigest
# This script helps automate the deployment process using Railway CLI

set -e

echo "🚂 DepoDigest Railway Deployment Script"
echo "========================================"
echo ""

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "❌ Railway CLI is not installed."
    echo "📦 Install it with: npm install -g @railway/cli"
    exit 1
fi

echo "✅ Railway CLI is installed"
echo ""

# Check if logged in
echo "🔑 Checking Railway authentication..."
if ! railway whoami &> /dev/null; then
    echo "❌ Not logged in to Railway"
    echo "🔐 Please run: railway login"
    exit 1
fi

echo "✅ Authenticated with Railway"
echo ""

# Function to check if a service exists
check_service() {
    local service_name=$1
    railway service list | grep -q "$service_name"
}

# Function to create and configure a service
create_service() {
    local service_name=$1
    local root_dir=$2
    local dockerfile=$3
    
    echo "📦 Creating service: $service_name"
    railway service create "$service_name"
    railway service "$service_name"
    
    if [ -n "$root_dir" ]; then
        railway config set rootDirectory "$root_dir"
    fi
    
    if [ -n "$dockerfile" ]; then
        railway config set dockerfile "$dockerfile"
    fi
    
    echo "✅ Service $service_name created"
}

# Main deployment flow
echo "🎯 Starting deployment process..."
echo ""

# Step 1: Create or link project
echo "1️⃣ Setting up Railway project..."
if [ ! -f "railway.json" ]; then
    echo "Creating new Railway project..."
    railway init
else
    echo "Using existing Railway project"
fi
echo ""

# Step 2: Add PostgreSQL
echo "2️⃣ Setting up PostgreSQL..."
echo "Please add PostgreSQL through the Railway dashboard:"
echo "   Dashboard → New → Database → PostgreSQL"
echo ""
read -p "Press Enter after you've added PostgreSQL..."
echo ""

# Step 3: Add Redis
echo "3️⃣ Setting up Redis..."
echo "Please add Redis through the Railway dashboard:"
echo "   Dashboard → New → Database → Redis"
echo ""
read -p "Press Enter after you've added Redis..."
echo ""

# Step 4: Deploy Backend
echo "4️⃣ Deploying Backend Service..."
echo ""
echo "📝 Required environment variables for Backend:"
echo "   - OPENAI_API_KEY"
echo "   - ANTHROPIC_API_KEY (optional)"
echo "   - FRONTEND_URL (will set after frontend deployment)"
echo "   - API_HOST=0.0.0.0"
echo "   - API_PORT=8000"
echo "   - WORKERS_COUNT=4"
echo "   - LOG_LEVEL=INFO"
echo ""
read -p "Have you set these variables in Railway dashboard? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Please set the environment variables in Railway dashboard and run this script again"
    exit 1
fi

# Deploy backend
cd backend
railway up --service backend
cd ..
echo "✅ Backend deployed"
echo ""

# Get backend URL
echo "📋 Please note your backend URL from Railway dashboard"
read -p "Enter your backend URL (e.g., https://backend-production-xxxx.up.railway.app): " BACKEND_URL
echo ""

# Step 5: Deploy Worker
echo "5️⃣ Deploying Worker Service..."
echo ""
echo "Setting custom start command for worker..."
echo "In Railway dashboard for worker service, set:"
echo "   Custom Start Command: celery -A workers.celery_app worker --loglevel=info --concurrency=4"
echo ""
echo "Also add environment variable:"
echo "   BACKEND_URL=$BACKEND_URL"
echo ""
read -p "Press Enter after you've configured the worker..."

cd backend
railway up --service worker
cd ..
echo "✅ Worker deployed"
echo ""

# Step 6: Deploy Frontend
echo "6️⃣ Deploying Frontend Service..."
echo ""
echo "📝 Required environment variables for Frontend:"
echo "   - NEXT_PUBLIC_API_URL=$BACKEND_URL"
echo "   - NEXT_PUBLIC_WS_URL=${BACKEND_URL/https/wss}"
echo ""
read -p "Have you set these variables in Railway dashboard? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Please set the environment variables and run this script again"
    exit 1
fi

cd frontend
railway up --service frontend
cd ..
echo "✅ Frontend deployed"
echo ""

# Get frontend URL
echo "📋 Please note your frontend URL from Railway dashboard"
read -p "Enter your frontend URL (e.g., https://frontend-production-xxxx.up.railway.app): " FRONTEND_URL
echo ""

# Step 7: Update backend with frontend URL
echo "7️⃣ Updating Backend with Frontend URL..."
echo "Please update the Backend service environment variable:"
echo "   FRONTEND_URL=$FRONTEND_URL"
echo ""
read -p "Press Enter after you've updated the backend environment variable..."
echo ""

# Final checks
echo "🎉 Deployment Complete!"
echo ""
echo "📍 Your services:"
echo "   Backend:  $BACKEND_URL"
echo "   Frontend: $FRONTEND_URL"
echo ""
echo "🔍 Next steps:"
echo "   1. Verify health check: $BACKEND_URL/health"
echo "   2. Test frontend: $FRONTEND_URL"
echo "   3. Monitor logs in Railway dashboard"
echo "   4. Upload a test PDF to verify end-to-end functionality"
echo ""
echo "📚 For detailed troubleshooting, see RAILWAY-DEPLOYMENT.md"
echo ""

