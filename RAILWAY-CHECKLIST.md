# Railway Deployment Checklist

Use this checklist to ensure your Railway deployment is complete and production-ready.

## 📋 Pre-Deployment

### GitHub Repository
- [ ] Code is pushed to GitHub
- [ ] `.env` files are in `.gitignore`
- [ ] `Dockerfile` exists in `backend/` directory
- [ ] `Dockerfile` exists in `frontend/` directory
- [ ] All sensitive data removed from code

### API Keys & Credentials
- [ ] OpenAI API key obtained (required)
- [ ] Anthropic API key obtained (optional)
- [ ] AWS credentials ready if using S3 (recommended)
- [ ] Sentry DSN ready if using error tracking (optional)

### Railway Account
- [ ] Railway account created at https://railway.app
- [ ] Credit card added (for production usage)
- [ ] Railway CLI installed: `npm install -g @railway/cli`
- [ ] Logged in to CLI: `railway login`

## 🚂 Railway Setup

### Project Creation
- [ ] New Railway project created
- [ ] GitHub repository connected
- [ ] Project name set appropriately

### Database Services
- [ ] PostgreSQL database added
- [ ] PostgreSQL is healthy (check status indicator)
- [ ] Redis database added
- [ ] Redis is healthy (check status indicator)
- [ ] Noted that `DATABASE_URL` and `REDIS_URL` are auto-set

## 🔧 Backend Service

### Configuration
- [ ] Backend service created from GitHub repo
- [ ] Root directory set to `backend`
- [ ] Dockerfile detected automatically

### Environment Variables
- [ ] `OPENAI_API_KEY` set
- [ ] `API_HOST=0.0.0.0` set
- [ ] `API_PORT=8000` set
- [ ] `WORKERS_COUNT=4` set
- [ ] `LOG_LEVEL=INFO` set
- [ ] `MAX_CONCURRENT_AI_REQUESTS=50` set (optional)
- [ ] `ANTHROPIC_API_KEY` set (if using Claude)
- [ ] `S3_BUCKET` set (if using S3)
- [ ] `AWS_ACCESS_KEY_ID` set (if using S3)
- [ ] `AWS_SECRET_ACCESS_KEY` set (if using S3)
- [ ] `SENTRY_DSN` set (if using Sentry)

### Deployment
- [ ] Backend deployed successfully
- [ ] Build logs reviewed (no errors)
- [ ] Deployment logs reviewed (no errors)
- [ ] Backend URL copied (e.g., `https://backend-production-xxxx.up.railway.app`)
- [ ] Health check passing: `/health` endpoint returns 200

### Networking
- [ ] Public domain generated
- [ ] Custom domain configured (optional)
- [ ] Health check path set to `/health`

## 👷 Worker Service

### Configuration
- [ ] Worker service created from GitHub repo
- [ ] Root directory set to `backend`
- [ ] Custom start command set: `celery -A workers.celery_app worker --loglevel=info --concurrency=4`

### Environment Variables
- [ ] All backend variables copied
- [ ] `BACKEND_URL` set to backend's public URL

### Deployment
- [ ] Worker deployed successfully
- [ ] Worker logs show Celery started
- [ ] Worker logs show connection to Redis
- [ ] No errors in worker logs

## 🎨 Frontend Service

### Configuration
- [ ] Frontend service created from GitHub repo
- [ ] Root directory set to `frontend`
- [ ] Dockerfile detected automatically

### Environment Variables
- [ ] `NEXT_PUBLIC_API_URL` set to backend URL (https://)
- [ ] `NEXT_PUBLIC_WS_URL` set to backend WebSocket URL (wss://)

### Deployment
- [ ] Frontend deployed successfully
- [ ] Build logs reviewed (Next.js build successful)
- [ ] Frontend URL copied (e.g., `https://frontend-production-xxxx.up.railway.app`)
- [ ] Frontend loads in browser

### Networking
- [ ] Public domain generated
- [ ] Custom domain configured (optional)

## 🔄 Cross-Service Configuration

### Backend Update
- [ ] `FRONTEND_URL` added to backend environment variables
- [ ] Backend redeployed with new variable
- [ ] CORS working correctly (no console errors)

### Service Dependencies
- [ ] Backend depends on PostgreSQL (implicitly via env vars)
- [ ] Backend depends on Redis (implicitly via env vars)
- [ ] Worker depends on Redis (implicitly via env vars)
- [ ] Frontend depends on Backend (via API calls)

## ✅ Validation

### Automated Testing
- [ ] Validation script installed: `pip install httpx`
- [ ] Validation script executed successfully
- [ ] All health checks passed
- [ ] No errors in validation output

### Manual Testing

#### Backend
- [ ] `/health` endpoint returns 200 OK
- [ ] `/health/detailed` shows all services healthy
- [ ] API docs accessible at `/docs`
- [ ] Database connection confirmed
- [ ] Redis connection confirmed

#### Frontend
- [ ] Homepage loads without errors
- [ ] No console errors in browser DevTools
- [ ] Upload page accessible
- [ ] UI renders correctly

#### End-to-End
- [ ] Can upload a PDF document
- [ ] Upload progress shows correctly
- [ ] Processing starts automatically
- [ ] Real-time progress updates work (WebSocket)
- [ ] Results display correctly
- [ ] Can download results

### Performance Testing
- [ ] Upload a small test file (< 10 pages)
- [ ] Processing completes in reasonable time
- [ ] Upload a larger file (50+ pages)
- [ ] Worker processes the job successfully
- [ ] Check backend response times (should be < 1000ms)

## 🔒 Security

### Environment Variables
- [ ] No sensitive data in code
- [ ] All API keys in environment variables only
- [ ] `.env` files not committed to git
- [ ] Environment variables not logged

### CORS Configuration
- [ ] Backend accepts requests from frontend URL only
- [ ] No CORS errors in browser console
- [ ] WebSocket connections work

### Network Security
- [ ] All services use HTTPS (automatic with Railway)
- [ ] WebSocket uses WSS (secure)
- [ ] Database connections encrypted (automatic with Railway)

### Access Control
- [ ] Railway project access limited to team members
- [ ] GitHub repository access controlled
- [ ] API keys have appropriate permissions

## 📊 Monitoring Setup

### Railway Monitoring
- [ ] Metrics enabled for all services
- [ ] Resource usage reviewed
- [ ] No memory leaks detected
- [ ] CPU usage reasonable

### Logging
- [ ] Log level set appropriately (INFO for production)
- [ ] Logs accessible in Railway dashboard
- [ ] Critical errors identifiable
- [ ] Log retention configured

### Error Tracking (Optional)
- [ ] Sentry configured
- [ ] Sentry receiving events
- [ ] Alerts configured
- [ ] Team members added to Sentry

### Uptime Monitoring (Optional)
- [ ] External uptime monitor configured
- [ ] Health check URLs monitored
- [ ] Alert notifications configured

## 📈 Performance Optimization

### Resource Allocation
- [ ] Backend resources appropriate for load
- [ ] Worker resources sufficient for PDF processing
- [ ] Frontend resources adequate
- [ ] Database size appropriate

### Scaling Configuration
- [ ] Worker replicas set if needed (1-3)
- [ ] Auto-restart policies configured
- [ ] Resource limits set appropriately

### Caching
- [ ] Redis cache working (check logs)
- [ ] Cache hit rate monitored
- [ ] Cache TTL configured (30 days default)

## 💰 Cost Management

### Railway Plan
- [ ] Appropriate plan selected (Hobby vs Team)
- [ ] Usage limits understood
- [ ] Billing alerts configured

### Resource Optimization
- [ ] Unnecessary services removed
- [ ] Resources sized appropriately
- [ ] Auto-sleep disabled for production

### API Usage
- [ ] OpenAI rate limits configured
- [ ] API usage monitored
- [ ] Cache reducing API calls effectively

## 📚 Documentation

### Internal Documentation
- [ ] Deployment documented
- [ ] Service URLs documented
- [ ] Environment variables documented
- [ ] Troubleshooting steps documented

### Team Access
- [ ] Railway access shared with team
- [ ] GitHub access configured
- [ ] API key access managed securely
- [ ] Runbook created for common issues

## 🚀 Go Live

### Pre-Launch
- [ ] All checklist items above completed
- [ ] Full end-to-end test successful
- [ ] Team trained on monitoring
- [ ] Rollback plan documented

### Launch
- [ ] Users directed to production URL
- [ ] Monitoring during initial usage
- [ ] Support channels ready
- [ ] Incident response plan ready

### Post-Launch
- [ ] Monitor for first 24 hours
- [ ] Review logs for errors
- [ ] Check performance metrics
- [ ] Collect user feedback

## 🎯 Optional Enhancements

### Custom Domains
- [ ] Custom domain purchased
- [ ] DNS configured
- [ ] SSL certificate validated
- [ ] Domain working correctly

### CI/CD
- [ ] Automatic deployments on push to main
- [ ] Preview environments for PRs
- [ ] Automated tests in CI pipeline

### Advanced Features
- [ ] Multiple environments (staging, production)
- [ ] Feature flags configured
- [ ] A/B testing setup
- [ ] Analytics integrated

---

## ✨ Deployment Complete!

Once all required items are checked:
- ✅ Your application is production-ready
- ✅ All services are healthy and monitored
- ✅ Security best practices followed
- ✅ Ready to serve users!

**Need Help?**
- 📖 See [RAILWAY-DEPLOYMENT.md](RAILWAY-DEPLOYMENT.md)
- 🔍 Run validation: `python validate-railway-deployment.py`
- 💬 Railway Discord: https://discord.gg/railway

