"""Main FastAPI application entry point."""
# Deploy trigger: Dec 25, 2025 - Contradiction detection MVP deployment
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.responses import JSONResponse

from config import settings
from api import health, documents, jobs, websocket, cache, auth, bug_reports, learning_feedback, user_settings, chat, reports, claims, contradictions
from services.cache_service import cache_service
from services.db_service import init_db, init_persistent_db

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting DepoDigest API server...")
    
    # Initialize ephemeral database (transcripts)
    await init_db()
    logger.info("Ephemeral database initialized")
    
    # Initialize persistent database (users, auth, feedback)
    await init_persistent_db()
    logger.info("Persistent database initialized")
    
    # Initialize cache
    await cache_service.connect()
    logger.info("Redis cache connected")
    
    yield
    
    # Cleanup
    await cache_service.disconnect()
    logger.info("Application shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="DepoDigest API",
    description="High-performance deposition summarization API",
    version="2.0.0",
    lifespan=lifespan
)

# CORS configuration
# Combine allowed origins with frontend URL, ensuring no duplicates
cors_origins = list(set(settings.allowed_origins + [settings.frontend_url]))
# Filter out None/empty values and ensure trailing slashes are handled
cors_origins = [origin.rstrip('/') for origin in cors_origins if origin]
logger.info(f"Configuring CORS with origins: {cors_origins}")
logger.info(f"Frontend URL from settings: {settings.frontend_url}")

# Add SessionMiddleware (required for OAuth)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.jwt_secret_key
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,  # Cache preflight requests for 1 hour
)

# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(bug_reports.router, prefix="/api", tags=["bug-reports"])
app.include_router(learning_feedback.router, prefix="/api", tags=["learning-feedback"])
app.include_router(user_settings.router, prefix="/api", tags=["user-settings"])
app.include_router(cache.router, prefix="/api", tags=["cache"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(reports.router)
app.include_router(claims.router, tags=["claims"])
app.include_router(contradictions.router, tags=["contradictions"])
app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(websocket.router, prefix="/ws", tags=["websocket"])


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level=settings.log_level.lower()
    )


