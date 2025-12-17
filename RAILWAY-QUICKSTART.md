# Railway Quick Start Guide

Get DepoDigest deployed to Railway in under 30 minutes!

## 📋 Prerequisites

- [ ] Railway account (sign up at https://railway.app)
- [ ] GitHub repository with your code
- [ ] OpenAI API key (required)
- [ ] AWS S3 bucket (recommended for production)

## 🚀 Quick Deployment Steps

### Step 1: Create Railway Project (2 min)

1. Go to https://railway.app/new
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Choose your repository

### Step 2: Add Databases (3 min)

1. Click "+ New" → "Database" → "Add PostgreSQL"
2. Wait for provisioning (~30 seconds)
3. Click "+ New" → "Database" → "Add Redis"
4. Wait for provisioning (~30 seconds)

✅ Railway automatically sets `DATABASE_URL` and `REDIS_URL` for all services

### Step 3: Deploy Backend (8 min)

1. Click "+ New" → "GitHub Repo" → Select your repo
2. Configure:
   - **Service Name**: `backend`
   - **Root Directory**: `backend`
3. Add environment variables (Settings → Variables):

```env
# Required
OPENAI_API_KEY=sk-proj-your-key-here
API_HOST=0.0.0.0
API_PORT=8000
WORKERS_COUNT=4
LOG_LEVEL=INFO

# Optional but recommended
ANTHROPIC_API_KEY=sk-ant-your-key-here
S3_BUCKET=your-bucket-name
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
```

4. Click "Deploy"
5. Wait for deployment (~3 minutes)
6. **Copy the public URL** (e.g., `https://backend-production-xxxx.up.railway.app`)

### Step 4: Deploy Worker (5 min)

1. Click "+ New" → "GitHub Repo" → Select your repo
2. Configure:
   - **Service Name**: `worker`
   - **Root Directory**: `backend`
3. Go to Settings → Deploy
4. Set **Custom Start Command**:
   ```
   celery -A workers.celery_app worker --loglevel=info --concurrency=4
   ```
5. Add environment variables (copy from backend + add):
   ```env
   BACKEND_URL=https://your-backend-url.up.railway.app
   ```
6. Click "Deploy"

### Step 5: Deploy Frontend (8 min)

1. Click "+ New" → "GitHub Repo" → Select your repo
2. Configure:
   - **Service Name**: `frontend`
   - **Root Directory**: `frontend`
3. Add environment variables:
   ```env
   NEXT_PUBLIC_API_URL=https://your-backend-url.up.railway.app
   NEXT_PUBLIC_WS_URL=wss://your-backend-url.up.railway.app
   ```
4. Click "Deploy"
5. Wait for deployment (~3 minutes)
6. **Copy the public URL** (e.g., `https://frontend-production-xxxx.up.railway.app`)

### Step 6: Update Backend with Frontend URL (2 min)

1. Go to Backend service → Settings → Variables
2. Add/Update:
   ```env
   FRONTEND_URL=https://your-frontend-url.up.railway.app
   ```
3. Save (this triggers a redeploy)

## ✅ Verify Deployment

### 1. Check Backend Health

Visit: `https://your-backend-url.up.railway.app/health`

Expected response:
```json
{
  "status": "healthy",
  "service": "depodigest-api",
  "version": "2.0.0"
}
```

### 2. Test Frontend

Visit: `https://your-frontend-url.up.railway.app`

You should see the DepoDigest upload interface.

### 3. Run Automated Validation

Using Python:
```bash
pip install httpx
python validate-railway-deployment.py \
  --backend https://your-backend-url.up.railway.app \
  --frontend https://your-frontend-url.up.railway.app
```

Using PowerShell:
```powershell
.\validate-railway-deployment.ps1 `
  -BackendUrl "https://your-backend-url.up.railway.app" `
  -FrontendUrl "https://your-frontend-url.up.railway.app"
```

## 🎯 What's Deployed

Your Railway project now has **5 services**:

```
┌─────────────┐     ┌─────────┐
│ PostgreSQL  │────▶│ Backend │────┐
└─────────────┘     └─────────┘    │
                                   │
┌─────────────┐     ┌─────────┐   │     ┌──────────┐
│   Redis     │────▶│ Worker  │   ├────▶│ Frontend │
└─────────────┘     └─────────┘   │     └──────────┘
                                   │
                         User ─────┘
```

## 💰 Estimated Costs

**Hobby Plan** ($5/month + usage):
- PostgreSQL: ~$5/month
- Redis: ~$5/month
- Backend: ~$5-10/month
- Worker: ~$5-10/month
- Frontend: ~$3-5/month

**Total: ~$23-35/month** for a production-ready deployment

**Free Trial**: Railway offers $5 free credit per month on the trial plan.

## 🔧 Common Issues & Solutions

### Backend won't start
- ✅ Check logs: Backend service → Deployments → View logs
- ✅ Verify `DATABASE_URL` and `REDIS_URL` are set (automatic)
- ✅ Ensure `OPENAI_API_KEY` is valid

### Frontend can't connect to backend
- ✅ Verify `NEXT_PUBLIC_API_URL` is correct with `https://`
- ✅ Check `FRONTEND_URL` is set in backend
- ✅ Look for CORS errors in browser console

### Worker not processing jobs
- ✅ Check worker logs for errors
- ✅ Verify Redis connection
- ✅ Ensure custom start command is set correctly

### PDF uploads failing
- ✅ Configure S3 (Railway has ephemeral storage)
- ✅ Verify AWS credentials are correct
- ✅ Check S3 bucket CORS configuration

## 📈 Scaling for Production

### Increase Resources
1. Go to service → Settings → Resources
2. Recommended:
   - Backend: 2GB RAM, 2 vCPUs
   - Worker: 4GB RAM, 4 vCPUs
   - Frontend: 1GB RAM, 1 vCPU

### Add More Workers
1. Go to Worker service → Settings → Deploy
2. Increase "Replicas" to 2-3

### Add Custom Domain
1. Go to service → Settings → Networking
2. Click "Add Custom Domain"
3. Follow DNS configuration instructions

## 🔒 Security Checklist

- [x] All API keys are environment variables
- [x] `.env` files are in `.gitignore`
- [x] HTTPS enabled (automatic with Railway)
- [ ] CORS configured for your domain only (update in backend)
- [ ] S3 bucket has proper IAM policies
- [ ] Enable Sentry for error tracking
- [ ] Set up monitoring alerts

## 📚 Next Steps

1. **Configure Custom Domain**: Make your app accessible at your own domain
2. **Set up Monitoring**: Add Sentry DSN to environment variables
3. **Test Upload Workflow**: Upload a sample deposition transcript
4. **Review Logs**: Monitor for any errors or warnings
5. **Set up CI/CD**: Configure branch deployments and preview environments

## 🆘 Need Help?

- 📖 Full guide: See [RAILWAY-DEPLOYMENT.md](RAILWAY-DEPLOYMENT.md)
- 🐛 Issues: Check Railway logs and service health
- 💬 Support: Railway Discord at https://discord.gg/railway
- 📧 Project issues: Create an issue in your GitHub repository

---

**Congratulations! 🎉** Your DepoDigest app is now live on Railway!

