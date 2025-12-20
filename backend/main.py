"""Main FastAPI application entry point."""
# Deploy trigger: Dec 19, 2025 - Cache clearing on upload implemented
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.responses import JSONResponse

from config import settings
from api import health, documents, jobs, websocket, cache, auth, bug_reports, learning_feedback, user_settings
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
cors_origins = settings.allowed_origins + [settings.frontend_url]
logger.info(f"Configuring CORS with origins: {cors_origins}")

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
)

# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(bug_reports.router, prefix="/api", tags=["bug-reports"])
app.include_router(learning_feedback.router, prefix="/api", tags=["learning-feedback"])
app.include_router(user_settings.router, prefix="/api", tags=["user-settings"])
app.include_router(cache.router, prefix="/api", tags=["cache"])
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


