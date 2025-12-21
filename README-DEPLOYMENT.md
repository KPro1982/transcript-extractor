# DepoDigest Deployment Guide

## Railway Setup

### 1. Create Railway Project

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login to Railway
railway login

# Create new project
railway init
```

### 2. Add Services

In Railway dashboard:

1. **PostgreSQL**
   - Click "+ New" → "Database" → "PostgreSQL"
   - Railway will automatically provision and set `DATABASE_URL`

2. **Redis**
   - Click "+ New" → "Database" → "Redis"
   - Railway will automatically set `REDIS_URL`

3. **Backend Service**
   - Click "+ New" → "GitHub Repo"
   - Select your repository
   - Set root directory: `/backend`
   - Deploy branch: `main`

4. **Worker Service**
   - Click "+ New" → "GitHub Repo"
   - Same repository
   - Set root directory: `/backend`
   - Override start command: `python -m workers.summarization_worker`

5. **Frontend Service**
   - Click "+ New" → "GitHub Repo"
   - Same repository
   - Set root directory: `/frontend`

### 3. Environment Variables

Set these in Railway dashboard for backend service:

```
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...
S3_BUCKET=depodigest-uploads
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
FRONTEND_URL=https://your-frontend.railway.app
```

### 4. AWS S3 Setup

```bash
# Install AWS CLI
aws configure

# Create S3 bucket
aws s3 mb s3://depodigest-uploads --region us-east-1

# Set CORS policy
aws s3api put-bucket-cors --bucket depodigest-uploads --cors-configuration file://s3-cors.json
```

Create `s3-cors.json`:
```json
{
  "CORSRules": [
    {
      "AllowedOrigins": ["*"],
      "AllowedMethods": ["GET", "PUT", "POST", "DELETE"],
      "AllowedHeaders": ["*"],
      "MaxAgeSeconds": 3000
    }
  ]
}
```

### 5. Deploy

```bash
# Push to main branch
git push origin main

# Railway will automatically deploy
```

## Local Development

See [README-LOCAL.md](README-LOCAL.md) for local setup instructions.

## Monitoring

- Railway provides automatic logging and metrics
- Add Sentry DSN for error tracking
- Use Railway's built-in monitoring dashboard












