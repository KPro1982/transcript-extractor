# Backend Crash Diagnosis

## Issue
Backend service crashes every few seconds on Railway deployment.

## Common Causes & Solutions

### 1. PYTHONPATH Not Set
**Symptom:** `ModuleNotFoundError` or `ImportError`  
**Solution:** Ensure Railway has `PYTHONPATH=/app` set in environment variables

### 2. Missing Environment Variables
**Symptom:** Connection errors to database/Redis  
**Solution:** Verify these are set in Railway:
- `DATABASE_URL` (auto-set by Railway PostgreSQL)
- `REDIS_URL` (auto-set by Railway Redis)
- `OPENAI_API_KEY` (required)

### 3. Database Connection Failure
**Symptom:** `asyncpg.exceptions.InvalidPasswordError` or connection timeout  
**Solution:** 
- Verify PostgreSQL service is running
- Check DATABASE_URL format: `postgresql://user:pass@host:port/dbname`
- Ensure database is accessible from backend service

### 4. Redis Connection Failure  
**Symptom:** `redis.exceptions.ConnectionError`  
**Solution:**
- Verify Redis service is running
- Check REDIS_URL format: `redis://host:port`
- Ensure Redis is accessible from backend service

### 5. Import Errors
**Symptom:** `ModuleNotFoundError: No module named 'config'` or similar  
**Solution:**
- Set `PYTHONPATH=/app` in Railway environment variables
- Verify Dockerfile sets `ENV PYTHONPATH=/app`
- Check that start command uses correct working directory

### 6. Port Binding Issues
**Symptom:** `Address already in use` or port conflicts  
**Solution:**
- Ensure backend uses port 8000 (Railway default)
- Check no other service uses same port

### 7. Memory Issues
**Symptom:** `Killed` or `OOM` (Out of Memory)  
**Solution:**
- Increase Railway service memory allocation
- Reduce worker concurrency
- Check for memory leaks

## Railway-Specific Fixes

### Fix 1: Update Railway Start Command
In Railway dashboard for backend service:
```
uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1
```

### Fix 2: Set Environment Variables
Ensure these are set in Railway backend service:
```
PYTHONPATH=/app
DATABASE_URL=<auto-set by Railway>
REDIS_URL=<auto-set by Railway>
OPENAI_API_KEY=<your-key>
LOG_LEVEL=INFO
```

### Fix 3: Verify Service Dependencies
In Railway, ensure backend service has:
- PostgreSQL service as dependency
- Redis service as dependency

## Diagnostic Steps

1. **Check Railway Logs:**
   ```bash
   railway logs --tail 500
   ```

2. **Run Import Check Locally:**
   ```bash
   python scripts/diagnostics/check_imports.py
   ```

3. **Test Backend Startup Locally:**
   ```bash
   cd backend
   export PYTHONPATH=/app
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

4. **Check Railway Service Status:**
   - Go to Railway dashboard
   - Check backend service logs
   - Look for error patterns in last deployment

## Most Likely Causes (Based on Common Patterns)

1. **PYTHONPATH not set** - 40% probability
2. **Database connection failure** - 25% probability  
3. **Redis connection failure** - 20% probability
4. **Missing environment variables** - 10% probability
5. **Other (syntax error, memory, etc.)** - 5% probability

## Quick Fix Script

Run this to check Railway configuration:
```bash
railway variables
railway logs --tail 100
```








