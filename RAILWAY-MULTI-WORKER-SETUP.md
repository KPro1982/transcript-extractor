# Railway Multi-Worker Setup Guide

## Current Status

✅ **Local `.env` configured with 3 API keys**
- All 3 keys are now in `backend/.env`
- Local testing ready

## Railway Deployment Steps

### Overview

You need to create **3 separate worker services** in Railway, each with its own `WORKER_ID` and `OPENAI_API_KEY`.

### Step 1: Create Worker Service 1 (Worker 0)

1. Go to Railway dashboard
2. Click **"+ New Service"**
3. Select your repository
4. Name it: **`worker-0`** or **`depodigest-worker-0`**
5. Set build configuration:
   - **Root Directory**: `backend`
   - **Dockerfile Path**: `backend/Dockerfile`
   - **Start Command**: `PYTHONPATH=/app celery -A workers.celery_app worker --loglevel=info --concurrency=4`

6. Set environment variables:
```bash
WORKER_ID=0
OPENAI_API_KEY=<your-first-key>  # Use Key 1 from your .env file

# Also copy these from your existing worker service:
DATABASE_URL=<from-postgresql-plugin>
PERSISTENT_DATABASE_URL=<from-postgresql-plugin>
REDIS_URL=<from-redis-plugin>
GOOGLE_CLIENT_ID=<your-value>
GOOGLE_CLIENT_SECRET=<your-value>
JWT_SECRET_KEY=<your-value>
WORKERS_COUNT=4
FRONTEND_URL=<your-frontend-url>
MAX_CONCURRENT_AI_REQUESTS=50
CACHE_TTL_DAYS=30
LOG_LEVEL=INFO
OPENAI_RPM=500
OPENAI_TPM=200000
ENABLE_CHUNKING=true
CHUNKING_THRESHOLD=500
MAX_CHUNKS=3
```

### Step 2: Create Worker Service 2 (Worker 1)

1. Click **"+ New Service"** again
2. Name it: **`worker-1`** or **`depodigest-worker-1`**
3. Same build configuration as Worker 1
4. Set environment variables (SAME as Worker 1, except):
```bash
WORKER_ID=1
OPENAI_API_KEY=<your-second-key>  # Use Key 2 from your .env file

# (Copy all other env vars from Worker 1)
```

### Step 3: Create Worker Service 3 (Worker 2)

1. Click **"+ New Service"** again
2. Name it: **`worker-2`** or **`depodigest-worker-2`**
3. Same build configuration as Worker 1
4. Set environment variables (SAME as Worker 1, except):
```bash
WORKER_ID=2
OPENAI_API_KEY=<your-third-key>  # Use Key 3 from your .env file

# (Copy all other env vars from Worker 1)
```

### Step 4: Update Backend Service

Add these environment variables to your **backend service**:
```bash
OPENAI_API_KEY_1=<your-first-key>   # Copy from backend/.env
OPENAI_API_KEY_2=<your-second-key>  # Copy from backend/.env
OPENAI_API_KEY_3=<your-third-key>   # Copy from backend/.env
ENABLE_CHUNKING=true
CHUNKING_THRESHOLD=500
MAX_CHUNKS=3
```

## Step 5: Deploy

1. Commit and push changes to `dev` branch (already done!)
2. Railway will auto-deploy all services
3. Wait for all services to be healthy

## Step 6: Verify Setup

### Check Worker Logs

Look for these messages in each worker service:

**Worker 0:**
```
✅ OpenAI provider initialized (Worker 0) with key: sk-proj-mPDj...FNYA
```

**Worker 1:**
```
✅ OpenAI provider initialized (Worker 1) with key: sk-proj-bBks...QQgA
```

**Worker 2:**
```
✅ OpenAI provider initialized (Worker 2) with key: sk-proj-EHpP...BP4A
```

### Test Chunking

1. Upload a large document (>100 pages)
2. Check backend logs for:
```
Chunking enabled: 1500 pairs, 3 keys available
Optimal chunks: 3 (pages=300, keys=3)
Created chunk 0: pages 1-100, worker 0
Created chunk 1: pages 101-200, worker 1
Created chunk 2: pages 201-300, worker 2
```

3. Check worker logs - should see parallel processing:
```
Worker 0: Chunk 0: Processing pages 1-100
Worker 1: Chunk 1: Processing pages 101-200
Worker 2: Chunk 2: Processing pages 201-300
```

4. Verify completion:
```
Chunk 0 complete: 500 items in 120s
Chunk 1 complete: 500 items in 118s
Chunk 2 complete: 500 items in 125s
Parent job completed: 1500 items processed
```

## Expected Performance

### Before (1 worker, 1 key):
- 1000 Q&A pairs: ~6-8 minutes
- Rate limit: 500 RPM, 200k TPM

### After (3 workers, 3 keys):
- 1000 Q&A pairs: ~2-3 minutes
- Rate limit: 1500 RPM, 600k TPM
- **Speed improvement: ~3×**

## Troubleshooting

### Issue: Workers using same key

**Symptoms:** Logs show same key for all workers
**Fix:** 
- Verify each worker service has unique `WORKER_ID`
- Verify each has different `OPENAI_API_KEY`
- Restart worker services

### Issue: Chunking not triggering

**Symptoms:** Large documents still use single worker
**Fix:**
- Check `ENABLE_CHUNKING=true` in backend
- Verify `OPENAI_API_KEY_1`, `_2`, `_3` set in backend
- Check document has >500 Q&A pairs (>100 pages)

### Issue: Chunks failing

**Symptoms:** Chunks show "failed" status
**Fix:**
- Check API key validity on OpenAI dashboard
- Verify rate limits not exceeded
- Check worker logs for specific errors
- Ensure sufficient API quota on all 3 keys

### Issue: Database connection errors

**Symptoms:** Workers can't connect to DB
**Fix:**
- Verify `DATABASE_URL` and `PERSISTENT_DATABASE_URL` in all worker services
- Check PostgreSQL plugins are attached
- Restart worker services

## Monitoring

### Railway Dashboard

Monitor these metrics:
- CPU usage across all 3 workers
- Memory usage
- Network traffic
- Deployment status

### OpenAI Dashboard

Check each API key:
- Usage per key (should be roughly equal)
- Rate limit status
- Billing per key

### Application Logs

Watch for:
- Chunk creation messages
- Worker assignment
- Processing times
- Error messages

## Cost Tracking

### Per-Key Usage

Track costs separately for each key:
- Key 1: Worker 0 processing
- Key 2: Worker 1 processing  
- Key 3: Worker 2 processing

### Total Cost

- 3× keys = 3× potential cost
- BUT: Cache hit rate 80-90% reduces actual cost
- Large docs process 3× faster = better user experience
- Cost per document remains similar (distributed across keys)

## Rollback Plan

If issues occur:

1. **Disable chunking temporarily:**
   - Set `ENABLE_CHUNKING=false` in backend
   - Redeploy backend service
   - System falls back to single-worker mode

2. **Remove worker services:**
   - Delete worker-1 and worker-2 services
   - Keep only worker-0
   - System works with single worker

3. **Revert code:**
   - Checkout previous commit before multi-worker
   - Push to `dev` branch
   - Railway auto-deploys old version

## Success Checklist

- [ ] 3 worker services created in Railway
- [ ] Each worker has unique `WORKER_ID` (0, 1, 2)
- [ ] Each worker has different `OPENAI_API_KEY`
- [ ] Backend has all 3 keys configured
- [ ] All services deployed and healthy
- [ ] Worker logs show correct key assignment
- [ ] Test upload shows chunking enabled
- [ ] Parallel processing visible in logs
- [ ] Processing time reduced by ~3×
- [ ] Results merge correctly
- [ ] No errors in logs

## Next Steps

1. **Complete Railway setup** (Steps 1-5 above)
2. **Test with large document** (>100 pages)
3. **Monitor performance** improvement
4. **Track costs** across all 3 keys
5. **Celebrate 3× speedup!** 🚀

---

**Status:** Configuration ready - Deploy to Railway to activate 3× speed!

