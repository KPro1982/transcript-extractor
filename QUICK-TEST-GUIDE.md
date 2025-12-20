# Quick Railway Deployment Test Guide

## 🎯 Goal
Verify that the `pages` variable fix is deployed and working on Railway.

---

## ⚡ Quick Test (2 minutes)

### Step 1: Check Current Worker Status

```powershell
# Get recent worker logs to see if fix is deployed
railway logs --service worker --tail 50
```

**Look for:**
- ❌ `NameError: name 'pages' is not defined` → Need to redeploy
- ✅ `Document processing complete` → Fix is working!

---

### Step 2A: If Fix NOT Deployed - Redeploy Worker

```powershell
# Ensure latest code is pushed
git status
git log --oneline -3

# Redeploy worker to Railway
railway up --service worker

# Wait 1-2 minutes for deployment
```

---

### Step 2B: If Fix Already Deployed - Test Upload

```powershell
# Install dependencies if needed
pip install websocket-client requests

# Run automated test
python test-railway-upload.py
```

**Test will:**
1. Check backend health ✅
2. Check frontend accessibility ✅
3. Upload PDF ✅
4. Monitor WebSocket updates ✅
5. Verify results in database ✅

**Expected time:** 2-3 minutes

---

## 📊 What Success Looks Like

### Worker Logs (Good)
```
[INFO] Task process_document[abc123] received
[INFO] Retrieved PDF from Redis: 666785 bytes
[INFO] Page 1: 25 lines, 5 Q&A pairs found
[INFO] Extraction complete: 35 pages, 127 Q&A pairs
[INFO] Document processing complete: Working transcript.pdf
```

### Worker Logs (Bad - Need Redeploy)
```
[ERROR] Document processing failed: name 'pages' is not defined
Traceback (most recent call last):
  File "backend/workers/tasks.py", line 285
    "pages_processed": len(pages),
                           ^^^^^
NameError: name 'pages' is not defined
```

### Frontend (Success)
- Progress bar reaches 100%
- Shows "Processing complete!"
- Displays Q&A pairs
- No error messages

---

## 🔧 Manual Test (If Automated Test Fails)

### 1. Open Frontend
```
https://frontend-production-e051f.up.railway.app
```

### 2. Upload Test PDF
File: `Transcripts/Working transcript.pdf`

### 3. Watch Logs in Real-Time
```powershell
# In separate terminal
railway logs --service worker --follow
```

### 4. Verify Results
```powershell
# Check backend health
curl https://backend-production-e4c7.up.railway.app/api/health

# If you got document_id from upload, check Q&A items:
curl https://backend-production-e4c7.up.railway.app/api/documents/{document_id}/qa
```

---

## 🚨 Troubleshooting

### Issue: Railway command fails
```powershell
# Link to correct project
railway link

# Select: "beautiful-delight" project
# Environment: "production"
```

### Issue: Worker still shows old code
```powershell
# Force rebuild and redeploy
railway up --service worker --force

# Or via Railway dashboard:
# 1. Go to Railway dashboard
# 2. Click "worker" service
# 3. Click "Deploy" button
# 4. Select "Redeploy"
```

### Issue: Test PDF not found
```powershell
# List available test PDFs
Get-ChildItem -Recurse -Filter "*.pdf" -Path Transcripts/

# Update test script with correct path
# Edit line 12 in test-railway-upload.py
```

### Issue: Python dependencies missing
```powershell
# Install test dependencies
pip install websocket-client requests
```

---

## 📝 All Available Commands

### Check Status
```powershell
railway status                          # Show current project/service
railway logs --service backend          # Backend logs
railway logs --service worker           # Worker logs
railway logs --service frontend         # Frontend logs
```

### Deploy Services
```powershell
railway up --service backend            # Deploy backend
railway up --service worker             # Deploy worker
railway up --service frontend           # Deploy frontend
railway up                              # Deploy all (use carefully!)
```

### Check Environment
```powershell
railway variables --service backend     # Show backend env vars
railway variables --service worker      # Show worker env vars
```

### Git Operations
```powershell
git status                              # Check current status
git log --oneline -5                    # Show recent commits
git push origin dev                     # Push to remote
```

---

## 🎯 Expected Timeline

| Step | Duration | Action |
|------|----------|--------|
| Check logs | 30 sec | See if fix deployed |
| Redeploy (if needed) | 1-2 min | Railway builds & deploys |
| Run test | 2-3 min | Upload + processing |
| **Total** | **3-5 min** | **Complete verification** |

---

## ✅ Success Checklist

- [ ] Railway worker logs show no `pages` error
- [ ] Automated test completes successfully
- [ ] Frontend shows 100% progress
- [ ] Q&A pairs display in UI
- [ ] Backend API returns Q&A items
- [ ] No errors in Railway logs

When all checked ✅ → **Deployment is working!** 🎉

---

## 📞 Quick Reference

**Frontend:** https://frontend-production-e051f.up.railway.app  
**Backend API:** https://backend-production-e4c7.up.railway.app  
**Backend Health:** https://backend-production-e4c7.up.railway.app/api/health  

**Test Script:** `python test-railway-upload.py`  
**Worker Logs:** `railway logs --service worker --tail 50`  
**Redeploy:** `railway up --service worker`

---

**Start Here:** Run `railway logs --service worker --tail 50` to check current status!






