# Railway Deployment Guide for DepoDigest

This guide will help you deploy the complete DepoDigest application (Backend, Frontend, Workers, PostgreSQL, and Redis) to Railway.

## Prerequisites

1. **Railway Account**: Sign up at https://railway.app
2. **GitHub Repository**: Your code must be in a GitHub repository
3. **Railway CLI** (optional but recommended):
   ```bash
   npm install -g @railway/cli
   railway login
   ```

## Architecture Overview

The application consists of 5 services on Railway:
- **PostgreSQL Database** (managed by Railway)
- **Redis** (managed by Railway)
- **Backend API** (FastAPI)
- **Celery Worker** (for async processing)
- **Frontend** (Next.js)

## Step-by-Step Deployment

### 1. Create Railway Project

1. Go to https://railway.app/new
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Authorize Railway to access your GitHub
5. Select your repository

### 2. Add PostgreSQL Database

1. In your Railway project dashboard, click "+ New"
2. Select "Database" → "Add PostgreSQL"
3. Railway will automatically:
   - Provision a PostgreSQL instance
   - Create a `DATABASE_URL` environment variable
   - This URL will be available to all services in your project

### 3. Add Redis Database

1. Click "+ New" again
2. Select "Database" → "Add Redis"
3. Railway will automatically:
   - Provision a Redis instance
   - Create a `REDIS_URL` environment variable

### 4. Deploy Backend Service

1. Click "+ New" → "GitHub Repo"
2. Select your repository
3. Configure the service:
   - **Name**: `backend`
   - **Root Directory**: `backend`
   - **Dockerfile Path**: Leave default (Railway will find `backend/Dockerfile`)
   
4. Add Environment Variables (in Railway dashboard):
   ```
   # API Keys (REQUIRED)
   OPENAI_API_KEY=your_openai_api_key_here
   ANTHROPIC_API_KEY=your_anthropic_key_here
   GOOGLE_API_KEY=your_google_key_here (optional)
   
   # Server Configuration
   API_HOST=0.0.0.0
   API_PORT=8000
   WORKERS_COUNT=4
   
   # Performance Tuning
   MAX_CONCURRENT_AI_REQUESTS=50
   CACHE_TTL_DAYS=30
   LOG_LEVEL=INFO
   
   # Rate Limiting
   OPENAI_RPM=500
   OPENAI_TPM=200000
   
   # Cloud Storage (Optional but recommended for production)
   S3_BUCKET=depodigest-uploads
   S3_REGION=us-east-1
   AWS_ACCESS_KEY_ID=your_aws_key
   AWS_SECRET_ACCESS_KEY=your_aws_secret
   
   # Monitoring (Optional)
   SENTRY_DSN=your_sentry_dsn
   ```

5. Railway Settings:
   - **Port**: 8000 (Railway will auto-detect this)
   - **Health Check Path**: `/health`
   - **Health Check Timeout**: 100 seconds

6. After variables are set, click "Deploy"

7. Once deployed, note the public URL (e.g., `https://backend-production-xxxx.up.railway.app`)

### 5. Deploy Celery Worker Service

1. Click "+ New" → "GitHub Repo"
2. Select your repository again
3. Configure the service:
   - **Name**: `worker`
   - **Root Directory**: `backend`
   - **Dockerfile Path**: `backend/Dockerfile`
   
4. Override the Start Command:
   - Go to Settings → Deploy
   - **Custom Start Command**: `celery -A workers.celery_app worker --loglevel=info --concurrency=4`

5. Add the same Environment Variables as the backend (copy them)
   - You can use Railway's "Copy from another service" feature

6. Important: Add this additional variable:
   ```
   BACKEND_URL=https://your-backend-url.up.railway.app
   ```

7. Click "Deploy"

### 6. Deploy Frontend Service

1. Click "+ New" → "GitHub Repo"
2. Select your repository
3. Configure the service:
   - **Name**: `frontend`
   - **Root Directory**: `frontend`
   - **Dockerfile Path**: `frontend/Dockerfile`

4. Add Environment Variables:
   ```
   # IMPORTANT: Use your actual backend URL from step 4
   NEXT_PUBLIC_API_URL=https://your-backend-url.up.railway.app
   NEXT_PUBLIC_WS_URL=wss://your-backend-url.up.railway.app
   ```

5. Railway Settings:
   - **Port**: 3000 (Railway will auto-detect this)

6. Click "Deploy"

7. Once deployed, note your frontend URL (e.g., `https://frontend-production-xxxx.up.railway.app`)

### 7. Update Backend with Frontend URL

1. Go back to your **Backend service**
2. Add/Update environment variable:
   ```
   FRONTEND_URL=https://your-frontend-url.up.railway.app
   ```
3. This will trigger a redeploy of the backend

### 8. Configure Custom Domain (Optional)

1. For Backend:
   - Go to Backend service → Settings → Networking
   - Click "Generate Domain" or "Add Custom Domain"
   - Example: `api.depodigest.com`

2. For Frontend:
   - Go to Frontend service → Settings → Networking
   - Click "Generate Domain" or "Add Custom Domain"
   - Example: `app.depodigest.com`

3. Update environment variables with new domains if using custom domains

## Service Dependencies

Railway will automatically handle service startup order based on environment variable references. The dependency graph should be:

```
PostgreSQL ────┐
               ├──→ Backend ──→ Frontend
Redis ─────────┤
               └──→ Worker
```

## Verifying Deployment

### 1. Check Backend Health

Visit: `https://your-backend-url.up.railway.app/health`

You should see:
```json
{
  "status": "healthy",
  "database": "connected",
  "redis": "connected"
}
```

### 2. Check Frontend

Visit: `https://your-frontend-url.up.railway.app`

You should see the DepoDigest upload interface.

### 3. Check Logs

In Railway dashboard:
- Click on each service
- View the "Deployments" tab
- Click on the latest deployment to see logs
- Ensure no errors are present

### 4. Test Upload Workflow

1. Go to your frontend URL
2. Upload a test PDF (deposition transcript)
3. Monitor the progress
4. Check worker logs for processing activity
5. Verify results appear correctly

## Environment Variables Reference

### Backend Service
```env
# Required
DATABASE_URL=<automatically set by Railway>
REDIS_URL=<automatically set by Railway>
OPENAI_API_KEY=sk-proj-...
FRONTEND_URL=https://your-frontend-url.up.railway.app

# Optional but Recommended
ANTHROPIC_API_KEY=sk-ant-...
S3_BUCKET=depodigest-uploads
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...

# Configuration
API_HOST=0.0.0.0
API_PORT=8000
WORKERS_COUNT=4
MAX_CONCURRENT_AI_REQUESTS=50
LOG_LEVEL=INFO
```

### Worker Service
```env
# Same as Backend, plus:
BACKEND_URL=https://your-backend-url.up.railway.app
```

### Frontend Service
```env
NEXT_PUBLIC_API_URL=https://your-backend-url.up.railway.app
NEXT_PUBLIC_WS_URL=wss://your-backend-url.up.railway.app
```

## Scaling & Performance

### Vertical Scaling (More Resources)
- Go to service → Settings → Resources
- Increase memory/CPU as needed
- Recommended for production:
  - Backend: 2GB RAM, 2 vCPUs
  - Worker: 4GB RAM, 4 vCPUs (for heavy PDF processing)
  - Frontend: 1GB RAM, 1 vCPU

### Horizontal Scaling (More Instances)
- Worker service can be replicated:
  - Go to Worker service → Settings → Deploy
  - Increase "Replicas" to 2-3 for better throughput

## AWS S3 Setup (Recommended for Production)

Railway's ephemeral storage is not suitable for file uploads. Use S3:

```bash
# Install AWS CLI
aws configure

# Create S3 bucket
aws s3 mb s3://depodigest-uploads --region us-east-1

# Set CORS policy
cat > s3-cors.json << 'EOF'
{
  "CORSRules": [
    {
      "AllowedOrigins": ["https://your-frontend-url.up.railway.app"],
      "AllowedMethods": ["GET", "PUT", "POST", "DELETE"],
      "AllowedHeaders": ["*"],
      "MaxAgeSeconds": 3000
    }
  ]
}
EOF

aws s3api put-bucket-cors --bucket depodigest-uploads --cors-configuration file://s3-cors.json
```

Then add S3 credentials to your Backend and Worker services.

## Troubleshooting

### Backend won't start
- Check logs for database connection errors
- Verify `DATABASE_URL` and `REDIS_URL` are set
- Ensure health check endpoint is accessible at `/health`

### Worker not processing jobs
- Check worker logs for errors
- Verify Redis connection
- Ensure Celery is connecting to the correct Redis URL
- Check if jobs are being created in the backend logs

### Frontend can't connect to backend
- Verify `NEXT_PUBLIC_API_URL` is correct and includes `https://`
- Check CORS settings in backend (should allow your frontend URL)
- Verify backend is running and accessible

### PDF uploads failing
- Check if S3 is configured correctly
- Verify AWS credentials have proper permissions
- Look for storage-related errors in backend logs

### Out of Memory Errors
- Increase service memory in Railway settings
- Consider adding replicas for worker service
- Check for memory leaks in logs

## Cost Optimization

Railway pricing is based on resource usage:
- Use the $5/month Hobby plan for development
- Scale to Team plan for production ($20/month + usage)
- Monitor usage in Railway dashboard
- Turn off unused services
- Use appropriate resource limits

## Monitoring & Maintenance

### Enable Sentry (Recommended)
1. Sign up at https://sentry.io
2. Create a new project
3. Copy the DSN
4. Add `SENTRY_DSN` to Backend and Worker environment variables

### Railway Built-in Monitoring
- View metrics in Railway dashboard
- Set up webhook alerts
- Monitor deployment history
- Track resource usage

### Regular Maintenance
- Monitor logs regularly
- Update dependencies periodically
- Review and optimize resource usage
- Test backup and recovery procedures
- Keep API keys secure and rotated

## Rolling Back

If a deployment fails:
1. Go to service → Deployments
2. Find a previous successful deployment
3. Click "Redeploy"
4. Railway will rollback to that version

## CI/CD

Railway automatically deploys when you push to your main branch. To customize:

1. **Branch-based Deployments**:
   - Go to service → Settings → Deploy
   - Change "Deploy Branch" to your preferred branch

2. **Manual Deployments**:
   - Disable automatic deployments
   - Use Railway CLI: `railway up`

3. **Preview Environments**:
   - Railway automatically creates preview environments for PRs
   - Great for testing before merging

## Security Checklist

- [ ] All API keys are set as environment variables (never in code)
- [ ] `.env` files are in `.gitignore`
- [ ] CORS is configured to allow only your frontend URL
- [ ] Database credentials are managed by Railway (never hardcoded)
- [ ] S3 bucket has proper IAM policies
- [ ] HTTPS is enabled (automatic with Railway)
- [ ] Health check endpoints don't expose sensitive data

## Support

- Railway Documentation: https://docs.railway.app
- Railway Discord: https://discord.gg/railway
- Project Issues: Create an issue in your GitHub repository

---

**Next Steps**: After deployment, proceed to testing your application thoroughly in the production environment.

