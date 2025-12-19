"""Database service and connection management."""
import logging
from typing import Optional
import asyncpg
from asyncpg.pool import Pool

from config import settings

logger = logging.getLogger(__name__)


class DatabaseService:
    """PostgreSQL database connection manager."""
    
    def __init__(self):
        self.pool: Optional[Pool] = None
    
    async def init_pool(self):
        """Initialize database connection pool."""
        self.pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=2,
            max_size=10,
            command_timeout=60
        )
        logger.info("Database pool initialized")
    
    async def close_pool(self):
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Database pool closed")
    
    async def execute(self, query: str, *args):
        """Execute a query."""
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)
    
    async def fetch(self, query: str, *args):
        """Fetch multiple rows."""
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)
    
    async def fetchrow(self, query: str, *args):
        """Fetch single row."""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)
    
    async def fetchval(self, query: str, *args):
        """Fetch single value."""
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)


# Global database service
db_service = DatabaseService()


async def init_db():
    """Initialize database connection and create tables if needed."""
    await db_service.init_pool()
    
    # Create tables if they don't exist
    async with db_service.pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                filename VARCHAR(255) NOT NULL,
                file_hash VARCHAR(64) UNIQUE NOT NULL,
                s3_key VARCHAR(500) NOT NULL,
                total_pages INT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_documents_file_hash ON documents(file_hash);
            
            CREATE TABLE IF NOT EXISTS qa_items (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
                page_number INT NOT NULL,
                line_number INT NOT NULL,
                pdf_page_index INT,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                summary TEXT,
                topic VARCHAR(255),
                created_at TIMESTAMP DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_qa_items_document_id ON qa_items(document_id);
            
            -- Add pdf_page_index column if it doesn't exist (migration)
            DO $$ 
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'qa_items' AND column_name = 'pdf_page_index'
                ) THEN
                    ALTER TABLE qa_items ADD COLUMN pdf_page_index INT;
                END IF;
            END $$;
            
            -- Add answer_end_page column if it doesn't exist (migration)
            DO $$ 
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'qa_items' AND column_name = 'answer_end_page'
                ) THEN
                    ALTER TABLE qa_items ADD COLUMN answer_end_page INT;
                END IF;
            END $$;
            
            -- Add answer_end_line column if it doesn't exist (migration)
            DO $$ 
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'qa_items' AND column_name = 'answer_end_line'
                ) THEN
                    ALTER TABLE qa_items ADD COLUMN answer_end_line INT;
                END IF;
            END $$;
            
            -- Add is_final column if it doesn't exist (migration)
            DO $$ 
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'qa_items' AND column_name = 'is_final'
                ) THEN
                    ALTER TABLE qa_items ADD COLUMN is_final BOOLEAN DEFAULT TRUE;
                END IF;
            END $$;
            
            -- Create index on is_final AFTER column is added (migration)
            CREATE INDEX IF NOT EXISTS idx_qa_items_is_final ON qa_items(document_id, is_final);
            
            CREATE TABLE IF NOT EXISTS summary_cache (
                content_hash VARCHAR(64) PRIMARY KEY,
                summary TEXT NOT NULL,
                topic VARCHAR(255),
                created_at TIMESTAMP DEFAULT NOW(),
                last_accessed TIMESTAMP DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_summary_cache_last_accessed ON summary_cache(last_accessed);
            
            CREATE TABLE IF NOT EXISTS processing_jobs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
                status VARCHAR(50) NOT NULL,
                progress INT DEFAULT 0,
                error_message TEXT,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        
        logger.info("Database tables initialized")







