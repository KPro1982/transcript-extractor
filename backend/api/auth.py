"""Authentication API endpoints."""
import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Response, Request
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from jose import JWTError, jwt
from pydantic import BaseModel

from config import settings
from services.db_service import persistent_db_service

logger = logging.getLogger(__name__)

router = APIRouter()

# OAuth configuration
oauth = OAuth()
oauth.register(
    name='google',
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)


class User(BaseModel):
    """User model."""
    id: str
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None
    is_admin: bool = False


class TokenResponse(BaseModel):
    """Token response model."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: User


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def create_refresh_token(data: dict):
    """Create JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt


async def get_current_user(request: Request) -> User:
    """Get current user from JWT token."""
    # Get token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = auth_header.replace("Bearer ", "")
    
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Fetch user from database
        user_data = await persistent_db_service.fetchrow(
            "SELECT id, email, name, picture, is_admin FROM users WHERE id = $1",
            user_id
        )
        
        if not user_data:
            raise HTTPException(status_code=401, detail="User not found")
        
        return User(
            id=str(user_data['id']),
            email=user_data['email'],
            name=user_data['name'],
            picture=user_data['picture'],
            is_admin=user_data['is_admin']
        )
    
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Require admin user."""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.get("/google/login")
async def google_login(request: Request):
    """Initiate Google OAuth login."""
    redirect_uri = settings.google_redirect_uri
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/google/callback")
async def google_callback(request: Request):
    """Handle Google OAuth callback."""
    try:
        # Get token from Google
        token = await oauth.google.authorize_access_token(request)
        user_info = token.get('userinfo')
        
        if not user_info:
            raise HTTPException(status_code=400, detail="Failed to get user info from Google")
        
        email = user_info.get('email')
        google_id = user_info.get('sub')
        name = user_info.get('name')
        picture = user_info.get('picture')
        
        if not email or not google_id:
            raise HTTPException(status_code=400, detail="Invalid user info from Google")
        
        # Check if user exists, otherwise create
        user_data = await persistent_db_service.fetchrow(
            "SELECT id, email, name, picture, is_admin FROM users WHERE google_id = $1",
            google_id
        )
        
        is_admin = email == settings.admin_email
        
        if not user_data:
            # Create new user
            user_data = await persistent_db_service.fetchrow(
                """
                INSERT INTO users (email, google_id, name, picture, is_admin, last_login)
                VALUES ($1, $2, $3, $4, $5, NOW())
                RETURNING id, email, name, picture, is_admin
                """,
                email, google_id, name, picture, is_admin
            )
            logger.info(f"Created new user: {email} (admin={is_admin})")
        else:
            # Update last login and admin status (in case admin email changed)
            await persistent_db_service.execute(
                """
                UPDATE users 
                SET last_login = NOW(), name = $2, picture = $3, is_admin = $4
                WHERE id = $1
                """,
                user_data['id'], name, picture, is_admin
            )
            logger.info(f"User logged in: {email}")
        
        user_id = str(user_data['id'])
        
        # Create tokens
        access_token = create_access_token(data={"sub": user_id, "email": email})
        refresh_token = create_refresh_token(data={"sub": user_id})
        
        # Store refresh token in database
        expires_at = datetime.utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days)
        await persistent_db_service.execute(
            """
            INSERT INTO sessions (user_id, refresh_token, expires_at)
            VALUES ($1, $2, $3)
            """,
            user_id, refresh_token, expires_at
        )
        
        # Redirect to frontend with tokens in query params (frontend will store in localStorage)
        frontend_url = settings.frontend_url
        return RedirectResponse(
            url=f"{frontend_url}/auth/callback?access_token={access_token}&refresh_token={refresh_token}"
        )
    
    except Exception as e:
        logger.error(f"Google OAuth callback error: {e}", exc_info=True)
        frontend_url = settings.frontend_url
        return RedirectResponse(url=f"{frontend_url}/login?error=authentication_failed")


@router.get("/me", response_model=User)
async def get_me(user: User = Depends(get_current_user)):
    """Get current user information."""
    return user


@router.post("/logout")
async def logout(user: User = Depends(get_current_user)):
    """Logout user and invalidate refresh tokens."""
    await persistent_db_service.execute(
        "DELETE FROM sessions WHERE user_id = $1",
        user.id
    )
    return {"message": "Logged out successfully"}


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: str):
    """Refresh access token using refresh token."""
    try:
        # Verify refresh token
        payload = jwt.decode(refresh_token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Check if refresh token exists in database
        session = await persistent_db_service.fetchrow(
            """
            SELECT user_id, expires_at FROM sessions 
            WHERE refresh_token = $1 AND expires_at > NOW()
            """,
            refresh_token
        )
        
        if not session:
            raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
        
        # Get user data
        user_data = await persistent_db_service.fetchrow(
            "SELECT id, email, name, picture, is_admin FROM users WHERE id = $1",
            user_id
        )
        
        if not user_data:
            raise HTTPException(status_code=401, detail="User not found")
        
        user = User(
            id=str(user_data['id']),
            email=user_data['email'],
            name=user_data['name'],
            picture=user_data['picture'],
            is_admin=user_data['is_admin']
        )
        
        # Create new access token
        new_access_token = create_access_token(data={"sub": user.id})
        
        return TokenResponse(
            access_token=new_access_token,
            refresh_token=refresh_token,  # Reuse the same refresh token
            user=user
        )
    
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/dev/bypass-admin")
async def bypass_login_admin():
    """
    Development bypass: Login as admin without OAuth.
    Creates/updates admin user and returns tokens.
    """
    try:
        admin_email = settings.admin_email
        
        # Check if admin user exists
        user_data = await persistent_db_service.fetchrow(
            "SELECT id, email, name, picture, is_admin FROM users WHERE email = $1",
            admin_email
        )
        
        if not user_data:
            # Create admin user
            user_data = await persistent_db_service.fetchrow(
                """
                INSERT INTO users (email, google_id, name, is_admin, last_login)
                VALUES ($1, $2, $3, $4, NOW())
                RETURNING id, email, name, picture, is_admin
                """,
                admin_email,
                f"dev-admin-{admin_email}",
                "Admin User (Dev)",
                True
            )
        else:
            # Update last login
            await persistent_db_service.execute(
                "UPDATE users SET last_login = NOW() WHERE id = $1",
                user_data['id']
            )
        
        user = User(
            id=str(user_data['id']),
            email=user_data['email'],
            name=user_data['name'] or 'Admin User',
            picture=user_data['picture'],
            is_admin=True
        )
        
        # Create tokens
        access_token = create_access_token(data={"sub": user.id})
        refresh_token = create_refresh_token(data={"sub": user.id})
        
        # Store refresh token
        await persistent_db_service.execute(
            """
            INSERT INTO sessions (user_id, refresh_token, expires_at)
            VALUES ($1, $2, NOW() + INTERVAL '30 days')
            """,
            user.id,
            refresh_token
        )
        
        logger.info(f"Dev bypass login as admin: {admin_email}")
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=user
        )
    
    except Exception as e:
        logger.error(f"Dev bypass admin login failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create dev admin session: {str(e)}")


@router.get("/dev/bypass-user")
async def bypass_login_user():
    """
    Development bypass: Login as regular user without OAuth.
    Creates/updates user and returns tokens.
    """
    try:
        test_email = "user@depodigest.net"
        
        # Check if user exists
        user_data = await persistent_db_service.fetchrow(
            "SELECT id, email, name, picture, is_admin FROM users WHERE email = $1",
            test_email
        )
        
        if not user_data:
            # Create test user
            user_data = await persistent_db_service.fetchrow(
                """
                INSERT INTO users (email, google_id, name, is_admin, last_login)
                VALUES ($1, $2, $3, $4, NOW())
                RETURNING id, email, name, picture, is_admin
                """,
                test_email,
                f"dev-user-{test_email}",
                "Test User (Dev)",
                False
            )
        else:
            # Update last login
            await persistent_db_service.execute(
                "UPDATE users SET last_login = NOW() WHERE id = $1",
                user_data['id']
            )
        
        user = User(
            id=str(user_data['id']),
            email=user_data['email'],
            name=user_data['name'] or 'Test User',
            picture=user_data['picture'],
            is_admin=False
        )
        
        # Create tokens
        access_token = create_access_token(data={"sub": user.id})
        refresh_token = create_refresh_token(data={"sub": user.id})
        
        # Store refresh token
        await persistent_db_service.execute(
            """
            INSERT INTO sessions (user_id, refresh_token, expires_at)
            VALUES ($1, $2, NOW() + INTERVAL '30 days')
            """,
            user.id,
            refresh_token
        )
        
        logger.info(f"Dev bypass login as user: {test_email}")
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=user
        )
    
    except Exception as e:
        logger.error(f"Dev bypass user login failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create dev user session: {str(e)}")
        
        # Check if refresh token exists in database
        session = await persistent_db_service.fetchrow(
            "SELECT user_id, expires_at FROM sessions WHERE refresh_token = $1",
            refresh_token
        )
        
        if not session:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        
        if session['expires_at'] < datetime.utcnow():
            # Token expired, delete it
            await persistent_db_service.execute(
                "DELETE FROM sessions WHERE refresh_token = $1",
                refresh_token
            )
            raise HTTPException(status_code=401, detail="Refresh token expired")
        
        # Get user
        user_data = await persistent_db_service.fetchrow(
            "SELECT id, email, name, picture, is_admin FROM users WHERE id = $1",
            user_id
        )
        
        if not user_data:
            raise HTTPException(status_code=401, detail="User not found")
        
        # Create new tokens
        new_access_token = create_access_token(data={"sub": user_id, "email": user_data['email']})
        new_refresh_token = create_refresh_token(data={"sub": user_id})
        
        # Replace old refresh token with new one
        expires_at = datetime.utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days)
        await persistent_db_service.execute(
            """
            UPDATE sessions 
            SET refresh_token = $2, expires_at = $3
            WHERE refresh_token = $1
            """,
            refresh_token, new_refresh_token, expires_at
        )
        
        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            user=User(
                id=str(user_data['id']),
                email=user_data['email'],
                name=user_data['name'],
                picture=user_data['picture'],
                is_admin=user_data['is_admin']
            )
        )
    
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

