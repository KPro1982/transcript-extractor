# Railway Deployment Guide - New Features

## 🔄 Railway Branch Configuration

**CRITICAL**: Railway is configured to monitor the `dev` branch, not `master`.

- **Development**: Push to `dev` branch → Railway auto-rebuilds and deploys
- **Production**: Merge `dev` → `master` for release (but Railway doesn't auto-deploy from master)

**After each refactor or fix:**
1. Commit changes to `dev` branch
2. Push to trigger Railway rebuild
3. Monitor Railway dashboard for deployment status

```bash
git checkout dev
git add .
git commit -m "Your commit message"
git push origin dev
```

---

## 🎯 Overview

Based on your current Railway setup, you need to make these changes:

1. **Add a second PostgreSQL database** (for persistent user/auth/feedback data)
2. **Update environment variables** for all services
3. **Update database connection strings**

---

## 📋 Step-by-Step Railway Changes

### Step 1: Add Second PostgreSQL Database

**Current State:** You have one Postgres service (ephemeral data)

**Action Required:** Add a second Postgres service for persistent data

1. In Railway dashboard, click **"+ New"** → **"Database"** → **"Add PostgreSQL"**
2. Name it: **`depodigest-persistent`**
3. Railway will automatically create:
   - A new PostgreSQL instance
   - Environment variables: `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`
   - A volume for persistent storage

**Important:** Railway will generate connection variables. You can reference them using Railway's variable syntax:
- `${{depodigest-persistent.PGHOST}}`
- `${{depodigest-persistent.PGPORT}}` 
- `${{depodigest-persistent.PGUSER}}`
- `${{depodigest-persistent.PGPASSWORD}}`
- `${{depodigest-persistent.PGDATABASE}}`

---

### Step 2: Update Environment Variables

You need to add/update environment variables for **Backend**, **Worker**, and **Frontend** services.

#### 🔧 Backend Service Environment Variables

Go to **Backend** service → **Variables** tab → Add/Update:

**Existing Variables (keep these):**
```
# Ephemeral Database - Use Railway's DATABASE_URL from depodigest-ephemeral service
DATABASE_URL=${{depodigest-ephemeral.DATABASE_URL}}

REDIS_URL=[existing-redis-connection]
OPENAI_API_KEY=[your-key]
ANTHROPIC_API_KEY=[your-key]
FRONTEND_URL=https://frontend-production-e051f.up.railway.app
```

**NEW Variables to Add:**

```bash
# Persistent Database - Use Railway's DATABASE_URL from depodigest-persistent service
PERSISTENT_DATABASE_URL=${{depodigest-persistent.DATABASE_URL}}

# Google OAuth
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=https://backend-production-e4c7.up.railway.app/api/auth/google/callback

# JWT Authentication
JWT_SECRET_KEY=generate-a-long-random-string-here-min-32-chars
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=1440
JWT_REFRESH_TOKEN_EXPIRE_DAYS=30

# Admin Email
ADMIN_EMAIL=danieljcravens@gmail.com

# Email Notifications (Optional)
SENDGRID_API_KEY=your_sendgrid_api_key
NOTIFICATION_FROM_EMAIL=notifications@depodigest.com
```

**Railway Variable Reference Syntax:**
Railway allows referencing other services' variables. The easiest way is to use the `DATABASE_URL` variable that Railway automatically provides:

**For Ephemeral Database:**
```
DATABASE_URL=${{depodigest-ephemeral.DATABASE_URL}}
```

**For Persistent Database:**
```
PERSISTENT_DATABASE_URL=${{depodigest-persistent.DATABASE_URL}}
```

**Alternative:** If you need to construct the connection string manually, Railway also provides individual variables:
- `${{depodigest-ephemeral.PGDATABASE}}`
- `${{depodigest-ephemeral.PGUSER}}`
- `${{depodigest-ephemeral.PGPASSWORD}}`
- `${{depodigest-ephemeral.PGHOST}}`
- `${{depodigest-ephemeral.PGPORT}}`

But using `DATABASE_URL` is simpler and recommended!

#### 🔧 Worker Service Environment Variables

Go to **Worker** service → **Variables** tab → Add/Update:

**Copy ALL the same variables from Backend:**
- All database URLs (both ephemeral and persistent)
- All OAuth/JWT variables
- All API keys
- Admin email

**Why?** Workers need access to persistent DB for user settings when processing documents.

#### 🔧 Frontend Service Environment Variables

Go to **Frontend** service → **Variables** tab → Add/Update:

**Existing Variables (keep these):**
```
NEXT_PUBLIC_API_URL=https://backend-production-e4c7.up.railway.app
NEXT_PUBLIC_WS_URL=wss://backend-production-e4c7.up.railway.app
```

**No new frontend variables needed** - authentication is handled via API calls.

---

### Step 3: Update Google Cloud Console OAuth Settings

**Critical:** Update your Google OAuth redirect URIs:

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Navigate to **APIs & Services** → **Credentials**
3. Find your OAuth 2.0 Client ID
4. Add these **Authorized redirect URIs**:
   ```
   https://backend-production-e4c7.up.railway.app/api/auth/google/callback
   http://localhost:8000/api/auth/google/callback  (for local dev)
   ```

5. Add these **Authorized JavaScript origins**:
   ```
   https://frontend-production-e051f.up.railway.app
   https://backend-production-e4c7.up.railway.app
   http://localhost:3000  (for local dev)
   http://localhost:8000  (for local dev)
   ```

---

### Step 4: Generate JWT Secret Key

**Important:** Use a secure random string for production!

**Option 1: Using Python**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Option 2: Using OpenSSL**
```bash
openssl rand -base64 32
```

**Option 3: Online Generator**
- Use a secure password generator (32+ characters)
- Example: `kX9#mP2$vL8@nQ5!wR3&tY7*uI1^oE4%`

**Copy the generated string** and add it as `JWT_SECRET_KEY` in Railway.

---

### Step 5: Verify Database Connections

After adding the persistent database, verify both databases are accessible:

**Check Backend Logs:**
1. Go to **Backend** service → **Deployments** → Latest deployment → **View Logs**
2. Look for:
   ```
   Ephemeral database pool initialized
   Persistent database pool initialized
   ```

**If you see errors:**
- Check `PERSISTENT_DATABASE_URL` is correctly formatted
- Verify `depodigest-persistent` service is running
- Verify `depodigest-ephemeral` service is running
- Check Railway variable references use exact service names: `depodigest-ephemeral` and `depodigest-persistent`

---

### Step 6: Redeploy Services

After updating environment variables:

1. **Backend:** Should auto-redeploy when variables change, or manually trigger redeploy
2. **Worker:** Should auto-redeploy when variables change, or manually trigger redeploy  
3. **Frontend:** No changes needed, but can redeploy to ensure fresh build

**To manually redeploy:**
- Go to service → **Settings** → **Redeploy** (or push a new commit)

---

## 🔍 Railway-Specific Considerations

### Database Naming Convention

Railway will auto-generate database names. Your setup should be:

**Ephemeral Database (existing):**
- Service name: `depodigest-ephemeral`
- Used for: Documents, Q/A pairs, summaries
- Connection: `DATABASE_URL`

**Persistent Database (new):**
- Service name: `depodigest-persistent`
- Used for: Users, auth, bug reports, feedback, settings
- Connection: `PERSISTENT_DATABASE_URL`

### Variable Reference Syntax

Railway supports referencing other services' variables:

**Example for Persistent Database (Recommended - using DATABASE_URL):**
```
PERSISTENT_DATABASE_URL=${{depodigest-persistent.DATABASE_URL}}
```

**Example for Ephemeral Database (Recommended - using DATABASE_URL):**
```
DATABASE_URL=${{depodigest-ephemeral.DATABASE_URL}}
```

**How to Add Variable References in Railway:**
1. Go to **Backend** service → **Variables** tab
2. Click **"New Variable"** button
3. For **Key**, enter: `DATABASE_URL` (or `PERSISTENT_DATABASE_URL`)
4. For **Value**, click the **"{}"** icon (Raw Editor) or type: `${{depodigest-ephemeral.DATABASE_URL}}`
5. Railway will show a dropdown of available services - select the correct one
6. Click **"Add"**

**To verify service names:**
1. Go to each database service in Railway (`depodigest-ephemeral` and `depodigest-persistent`)
2. Click **Variables** tab
3. You'll see `DATABASE_URL` variable available
4. Railway will show the service name when you reference it from another service

### Health Checks

Your existing health checks should continue working:
- **Backend:** `/health` endpoint (already configured)
- **Frontend:** `/` endpoint (already configured)
- **Worker:** No HTTP endpoint needed

---

## ✅ Verification Checklist

After making changes, verify:

- [ ] Second PostgreSQL database created and running
- [ ] `PERSISTENT_DATABASE_URL` set in Backend service
- [ ] `PERSISTENT_DATABASE_URL` set in Worker service
- [ ] Google OAuth variables set (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`)
- [ ] `GOOGLE_REDIRECT_URI` points to Railway backend URL
- [ ] `JWT_SECRET_KEY` set (long random string)
- [ ] `ADMIN_EMAIL` set to `danieljcravens@gmail.com`
- [ ] Google Cloud Console redirect URIs updated
- [ ] All services redeployed successfully
- [ ] Backend logs show both databases initialized
- [ ] Can access `/login` page on frontend
- [ ] Can sign in with Google OAuth

---

## 🚨 Common Issues & Solutions

### Issue: "Database connection failed"
**Solution:**
- Check `PERSISTENT_DATABASE_URL` and `DATABASE_URL` are set correctly
- Verify variable references use Railway syntax: `${{depodigest-persistent.DATABASE_URL}}`
- Verify `depodigest-persistent` service is running
- Verify `depodigest-ephemeral` service is running
- Check Railway variable references use exact service names: `depodigest-ephemeral` and `depodigest-persistent`
- Ensure variable syntax is correct: `${{ServiceName.VariableName}}` (with double curly braces)
- In Railway, use the **"{}" Raw Editor** button to see available variable references

### Issue: "OAuth redirect URI mismatch"
**Solution:**
- Verify `GOOGLE_REDIRECT_URI` matches exactly what's in Google Cloud Console
- Check for trailing slashes
- Ensure using HTTPS for production URLs

### Issue: "JWT token invalid"
**Solution:**
- Verify `JWT_SECRET_KEY` is set and same across all services
- Check token hasn't expired (default 24 hours)
- Clear browser localStorage and login again

### Issue: "Admin access denied"
**Solution:**
- Verify `ADMIN_EMAIL` exactly matches your Google email
- Check email is lowercase
- Logout and login again after setting `ADMIN_EMAIL`

---

## 📝 Quick Reference: Railway Service Names

Based on your screenshot and database naming, your services are:
- **Frontend:** `frontend-production-e051f`
- **Backend:** `backend-production-e4c7`
- **Worker:** `Worker` (or similar)
- **Postgres (Ephemeral):** `depodigest-ephemeral` (existing)
- **Postgres (Persistent):** `depodigest-persistent` (NEW - you'll create this)
- **Redis:** `Redis` (existing)

Use these exact names when referencing variables: `${{depodigest-ephemeral.VariableName}}` and `${{depodigest-persistent.VariableName}}`

---

## 🎯 Next Steps After Railway Setup

1. **Test Login:** Go to your frontend URL → `/login` → Sign in with Google
2. **Verify Admin:** Check user menu shows "Admin Panel" option
3. **Test Features:** Try bug report button, settings modal, learning feedback
4. **Check Logs:** Monitor backend logs for any errors

Once Railway is configured, all features will work exactly like local development!

