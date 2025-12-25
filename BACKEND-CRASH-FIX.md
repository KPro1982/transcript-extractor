# Backend Crash Fix - PYTHONPATH Issue

## 🔴 Root Cause Identified

**Problem:** Backend crashes immediately on startup due to `ModuleNotFoundError`  
**Cause:** `PYTHONPATH` environment variable is not set in Railway  
**Impact:** All imports fail (`config`, `services.*`, `workers.*`, `api.*`)

## ✅ Solution

### Step 1: Set PYTHONPATH in Railway

1. Go to Railway Dashboard: https://railway.app
2. Select project: **Depodigest 2.0**
3. Click on service: **backend-production-e4c7** (or your backend service name)
4. Go to **Variables** tab
5. Click **+ New Variable**
6. Add:
   - **Name:** `PYTHONPATH`
   - **Value:** `/app`
7. Click **Add**

### Step 2: Verify Other Required Variables

Ensure these are also set:

- `DATABASE_URL` - Should be auto-set by Railway PostgreSQL service
- `REDIS_URL` - Should be auto-set by Railway Redis service  
- `OPENAI_API_KEY` - Your OpenAI API key
- `LOG_LEVEL` - Set to `INFO` (optional)

### Step 3: Redeploy

After adding `PYTHONPATH`:
1. Railway will automatically redeploy the service
2. Or manually trigger redeploy: **Deployments** → **Redeploy**

### Step 4: Verify Fix

Check logs to confirm startup:
```bash
railway logs --tail 50
```

You should see:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

## 🔍 Verification Commands

### Test Locally (Before Deploying)
```powershell
# Set PYTHONPATH
$env:PYTHONPATH = "C:\Users\Daniel Cravens\Desktop\Projects\PDF Reader\backend"

# Run import check
python scripts/diagnostics/check_imports.py

# Should show all [OK] messages
```

### Test Railway Configuration
```bash
# Check environment variables
railway variables

# Should show PYTHONPATH=/app
```

## 📋 Why This Happens

The backend code uses absolute imports like:
- `from config import settings`
- `from services.ai_service import ai_service`
- `from workers.tasks import process_document_task`

Python needs `PYTHONPATH=/app` to know that `/app` is the root directory for these imports.

The Dockerfile sets `ENV PYTHONPATH=/app`, but Railway may override environment variables, so it must be explicitly set in Railway's Variables.

## 🚨 Additional Checks

If crashes persist after setting PYTHONPATH:

1. **Check Database Connection:**
   ```bash
   railway logs | Select-String -Pattern "database|postgres|asyncpg"
   ```

2. **Check Redis Connection:**
   ```bash
   railway logs | Select-String -Pattern "redis|Redis"
   ```

3. **Check for Memory Issues:**
   ```bash
   railway logs | Select-String -Pattern "Killed|OOM|memory"
   ```

4. **Verify Start Command:**
   - Should be: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - Check in Railway: Service → Settings → Deploy → Start Command

## 📝 Quick Fix Script

Run this to verify Railway has PYTHONPATH:
```powershell
railway variables | Select-String -Pattern "PYTHONPATH"
```

If empty, add it via Railway dashboard as described above.

## ✅ Expected Result

After setting `PYTHONPATH=/app`:
- ✅ Backend starts successfully
- ✅ All imports work
- ✅ Health endpoint responds: `/health`
- ✅ Service stays online (no crashes)

---

**Status:** Ready to fix - Just add `PYTHONPATH=/app` in Railway Variables!













