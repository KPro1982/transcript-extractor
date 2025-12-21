# Worker Start Command Fix - Context & Instructions

## Problem Summary

**Issue:** Worker containers fail to start with error:
```
The executable `pythonpath=/app` could not be found.
```

**Root Cause:** Railway is trying to execute `PYTHONPATH=/app` as a command, but it's an environment variable assignment, not an executable.

**Status:**
- ✅ **worker-2**: Fixed (code updated in `railway.worker.toml`)
- ❌ **worker-0**: Needs manual fix in Railway UI
- ❌ **worker-1**: Needs manual fix in Railway UI

## Why This Happened

The start command was set to:
```
PYTHONPATH=/app celery -A workers.celery_app worker --loglevel=info --concurrency=4
```

Railway interprets the start command as an executable, not a shell command. When it sees `PYTHONPATH=/app`, it tries to execute it as a program, which fails.

## Solution

**PYTHONPATH is already set in the Dockerfile** (line 35: `ENV PYTHONPATH=/app`), so we don't need it in the start command.

**Correct Start Command:**
```
celery -A workers.celery_app worker --loglevel=info --concurrency=4
```

## Files Already Fixed

1. ✅ `railway.worker.toml` - Updated start command (affects new deployments)
2. ✅ `backend/Dockerfile` - Already has `ENV PYTHONPATH=/app` (line 35)

## What Needs to Be Done

### For Existing Railway Services (worker-0 and worker-1)

These services were created manually in Railway UI, so they need to be updated there:

#### Step 1: Fix worker-0

1. Go to Railway dashboard
2. Open **worker-0** service
3. Go to **Settings** → **Deploy** (or **Variables** tab)
4. Find **Start Command** field
5. **Current (WRONG):**
   ```
   PYTHONPATH=/app celery -A workers.celery_app worker --loglevel=info --concurrency=4
   ```
6. **Change to (CORRECT):**
   ```
   celery -A workers.celery_app worker --loglevel=info --concurrency=4
   ```
7. Save changes
8. Service will auto-redeploy

#### Step 2: Fix worker-1

1. Go to Railway dashboard
2. Open **worker-1** service
3. Go to **Settings** → **Deploy** (or **Variables** tab)
4. Find **Start Command** field
5. **Current (WRONG):**
   ```
   PYTHONPATH=/app celery -A workers.celery_app worker --loglevel=info --concurrency=4
   ```
6. **Change to (CORRECT):**
   ```
   celery -A workers.celery_app worker --loglevel=info --concurrency=4
   ```
7. Save changes
8. Service will auto-redeploy

## Verification

After fixing both services, check logs:

**Expected Success Logs:**
```
celery@hostname v5.3.6 (singularity)
...
[INFO/MainProcess] Connected to redis://...
[INFO/MainProcess] mingle: searching for neighbors
[INFO/MainProcess] mingle: all alone
[INFO/MainProcess] celery@hostname ready.
```

**If Still Failing:**
- Check that Root Directory is set to `backend`
- Verify Dockerfile Path is `backend/Dockerfile` (or just `Dockerfile` if Root Directory is set)
- Ensure all environment variables are set correctly

## Technical Details

### Why PYTHONPATH is in Dockerfile

The Dockerfile sets:
```dockerfile
ENV PYTHONPATH=/app
```

This ensures Python can find modules in `/app` directory. This is the correct way to set environment variables in Docker.

### Why Not in Start Command

Railway's start command is executed directly, not through a shell. So:
- ❌ `PYTHONPATH=/app celery ...` → Railway tries to execute `PYTHONPATH=/app` as a program
- ✅ `celery ...` → Railway executes celery directly, PYTHONPATH from Dockerfile is used

### Alternative Solutions (if needed)

If for some reason PYTHONPATH wasn't set in Dockerfile, you could:
1. Set it as an environment variable in Railway UI (not in start command)
2. Use a shell wrapper: `sh -c "PYTHONPATH=/app celery ..."`

But since it's already in Dockerfile, the simplest fix is to remove it from start command.

## Summary for New Agent

**Context:**
- Multi-worker parallel processing implementation
- 3 worker services: worker-0, worker-1, worker-2
- worker-2 fixed via code (`railway.worker.toml`)
- worker-0 and worker-1 need manual Railway UI fix

**Action Required:**
1. Update start command in Railway UI for worker-0
2. Update start command in Railway UI for worker-1
3. Remove `PYTHONPATH=/app` prefix from start command
4. Keep: `celery -A workers.celery_app worker --loglevel=info --concurrency=4`

**Why:**
- PYTHONPATH already set in Dockerfile
- Railway executes start command directly (not via shell)
- Environment variable assignments don't work in Railway start commands

**Files Changed:**
- `railway.worker.toml` - Fixed (for future deployments)
- Railway UI - Needs manual update for existing services

**Verification:**
- Check worker logs show Celery starting successfully
- No "executable not found" errors
- Workers connect to Redis and start processing

