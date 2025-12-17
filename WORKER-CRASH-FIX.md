# Worker Crash Fix - HTTP/2 Dependency

## ✅ Fix Applied

**File:** `backend/requirements.txt`  
**Change:** Updated `httpx==0.26.0` to `httpx[http2]==0.26.0`

## Problem

The worker service was crashing on startup with:
```
ImportError: Using http2=True, but the 'h2' package is not installed. 
Make sure to install httpx using `pip install httpx[http2]`.
```

## Root Cause

The `base_provider.py` file uses `httpx.AsyncClient(http2=True)` to enable HTTP/2 for better performance, but the `requirements.txt` only installed `httpx` without the `[http2]` extra, which includes the `h2` package needed for HTTP/2 support.

## Solution

Updated `requirements.txt` line 34:
- **Before:** `httpx==0.26.0`
- **After:** `httpx[http2]==0.26.0`

This installs both `httpx` and the `h2` package required for HTTP/2 support.

## Next Steps

1. **Commit the change:**
   ```bash
   git add backend/requirements.txt
   git commit -m "Fix: Add httpx[http2] dependency for HTTP/2 support"
   git push
   ```

2. **Railway will automatically:**
   - Detect the change
   - Rebuild the Docker image
   - Install the updated dependencies including `h2`
   - Redeploy the worker service

3. **Verify the fix:**
   - Check Railway logs after deployment
   - Worker should start successfully without the ImportError
   - Health checks should pass

## Expected Result

After deployment, the worker logs should show:
- ✅ Successful Celery worker startup
- ✅ No ImportError about missing `h2` package
- ✅ Worker ready to process tasks

## Related Files

- `backend/services/ai_providers/base_provider.py` - Uses `http2=True` (line 34)
- `backend/requirements.txt` - Now includes `httpx[http2]` (line 34)

