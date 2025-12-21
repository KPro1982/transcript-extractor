# Quick Setup Checklist

## ✅ Pre-Setup (You already have these)
- [x] Google OAuth credentials configured
- [x] Account with danieljcravens@gmail.com

## 🚀 Setup Steps

### 1. Update Environment Variables

Add these to your `.env` file:

```bash
# Database URLs (Docker will use these)
DATABASE_URL=postgresql://postgres:postgres@db:5432/depodigest_ephemeral
PERSISTENT_DATABASE_URL=postgresql://postgres:postgres@db_persistent:5432/depodigest_persistent

# Google OAuth (you have these)
GOOGLE_CLIENT_ID=your_google_client_id_here
GOOGLE_CLIENT_SECRET=your_google_client_secret_here
GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/google/callback

# JWT Secret (generate a random string)
JWT_SECRET_KEY=change-this-to-a-secure-random-string-in-production

# Admin Email (your email)
ADMIN_EMAIL=danieljcravens@gmail.com

# SendGrid (optional - for email notifications)
SENDGRID_API_KEY=your_sendgrid_key_here
NOTIFICATION_FROM_EMAIL=notifications@depodigest.com

# Existing variables (keep your current values)
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
# ... other existing variables
```

### 2. Install New Backend Dependencies

```bash
cd backend
pip install authlib==1.3.0 itsdangerous==2.1.2 sendgrid==6.11.0
# Or simply:
pip install -r requirements.txt
```

### 3. Restart Docker Services

```bash
docker-compose down
docker-compose up -d
```

This will:
- Create the new persistent database container
- Initialize both databases with required tables
- Start backend with new auth endpoints
- Start frontend with new auth components

### 4. Verify Setup

1. **Check databases are running:**
   ```bash
   docker ps
   ```
   You should see:
   - `depodigest-db-ephemeral` (port 5432)
   - `depodigest-db-persistent` (port 5433)
   - `depodigest-redis`
   - `depodigest-backend`
   - `depodigest-frontend`
   - `depodigest-worker`

2. **Check backend logs:**
   ```bash
   docker logs depodigest-backend
   ```
   Should show:
   - "Ephemeral database initialized"
   - "Persistent database initialized"
   - "Redis cache connected"

3. **Check frontend:**
   Open `http://localhost:3000/login`
   Should see Google sign-in button

### 5. First Login

1. Go to `http://localhost:3000/login`
2. Click "Sign in with Google"
3. Authorize with your Google account (danieljcravens@gmail.com)
4. You'll be redirected to the home page
5. Check user menu (top right) - should show your profile
6. Click user menu → should see "Admin Panel" option

### 6. Test Features

**As Admin:**
- ✅ Access `/admin` - Admin dashboard
- ✅ Access `/admin/chats` - Bug reports (should be empty)
- ✅ Access `/admin/feedback` - Learning feedback (should be empty)

**As User:**
- ✅ Upload page gear icon - Opens settings modal
- ✅ Results page brain icon - Opens learning feedback modal
- ✅ Floating bug report button - Create bug/feature request

### 7. Optional: Configure SendGrid

If you want email notifications:

1. Sign up for SendGrid (free tier available)
2. Create an API key
3. Add to `.env`: `SENDGRID_API_KEY=your_key`
4. Restart backend: `docker-compose restart backend`

Without SendGrid:
- Everything works fine
- Emails just won't be sent (you'll see warnings in logs)
- In-app notifications still work

## 🔧 Troubleshooting

### "Database connection failed"
- Check both databases are running: `docker ps`
- Check environment variables in docker-compose.yml
- Restart: `docker-compose restart backend worker`

### "OAuth error" or "Invalid redirect URI"
- Verify Google Cloud Console redirect URIs include:
  - `http://localhost:8000/api/auth/google/callback`
  - `http://localhost:3000/auth/callback`
- Check GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env

### "Not authenticated" errors
- Clear browser localStorage
- Login again
- Check browser console for errors

### "No admin access"
- Verify your email is danieljcravens@gmail.com
- Check ADMIN_EMAIL in .env matches
- Logout and login again

## 📝 Notes

- **For now:** Assume all users are you (single-user mode works perfectly)
- **For beta:** Will need to add user_id to job tracking and document ownership
- **Email notifications:** Optional but recommended for production
- **JWT Secret:** Change to a long random string for production

## 🎉 You're Ready!

Once you see the login page and can sign in with Google, all features are ready to use!





