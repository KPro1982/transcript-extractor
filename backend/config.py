"""Configuration management for DepoDigest backend."""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Databases
    # Ephemeral database for transcripts (can be cleared without losing user data)
    database_url: str = "postgresql://postgres:postgres@localhost:5432/depodigest_ephemeral"
    # Persistent database for users, auth, feedback, settings
    persistent_database_url: str = "postgresql://postgres:postgres@localhost:5432/depodigest_persistent"
    
    # Redis
    redis_url: str = "redis://localhost:6379"
    
    # AI Provider Keys
    openai_api_key: Optional[str] = None
    openai_api_key_1: Optional[str] = None  # Multi-key support for parallel processing
    openai_api_key_2: Optional[str] = None
    openai_api_key_3: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    
    # Worker Configuration (for multi-worker chunking)
    worker_id: int = 0  # 0-based worker index (set via WORKER_ID env var)
    
    # Cloud Storage
    s3_bucket: str = "depodigest-uploads"
    s3_region: str = "us-east-1"
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    
    # Google OAuth
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"
    
    # JWT Authentication
    jwt_secret_key: str = "change-this-secret-key-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24  # 24 hours
    jwt_refresh_token_expire_days: int = 30
    
    # Admin
    admin_email: str = "danieljcravens@gmail.com"
    
    # Email Notifications
    sendgrid_api_key: Optional[str] = None
    notification_from_email: str = "notifications@depodigest.com"
    
    # Server Configuration
    api_host: str = "0.0.0.0"
    api_port: int = int(os.environ.get("PORT", 8000))  # Railway sets PORT dynamically
    workers_count: int = 4
    
    # CORS
    frontend_url: str = "http://localhost:3000"
    allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "https://frontend-production-e051f.up.railway.app",
        "https://backend-production-e4c7.up.railway.app"  # Allow backend itself for health checks
    ]
    
    # Monitoring
    sentry_dsn: Optional[str] = None
    log_level: str = "INFO"
    
    # Performance Tuning
    max_concurrent_ai_requests: int = 50
    ai_request_timeout: int = 60
    cache_ttl_days: int = 30
    
    # Rate Limiting
    openai_rpm: int = 500  # Requests per minute
    openai_tpm: int = 200000  # Tokens per minute
    
    # Document Chunking (for multi-worker parallel processing)
    enable_chunking: bool = True  # Enable/disable document chunking
    chunking_threshold: int = 500  # Min Q&A pairs to trigger chunking
    max_chunks: int = 3  # Maximum number of chunks per document
    
    @property
    def assigned_openai_key(self) -> Optional[str]:
        """Get the API key assigned to this worker based on worker_id.
        
        Returns the appropriate API key for this worker, enabling multiple
        workers to use different keys for parallel processing without rate limit conflicts.
        """
        # If specific keys are set, use them based on worker_id
        key_map = {
            0: self.openai_api_key_1 or self.openai_api_key,
            1: self.openai_api_key_2 or self.openai_api_key,
            2: self.openai_api_key_3 or self.openai_api_key,
        }
        assigned_key = key_map.get(self.worker_id, self.openai_api_key)
        
        # Fallback to default key if assigned key is None
        return assigned_key or self.openai_api_key
    
    @property
    def available_worker_keys(self) -> int:
        """Count how many unique API keys are available for workers."""
        keys = [
            self.openai_api_key_1 or self.openai_api_key,
            self.openai_api_key_2,
            self.openai_api_key_3
        ]
        unique_keys = set(k for k in keys if k)
        return len(unique_keys)
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()

