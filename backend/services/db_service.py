"""Database service and connection management."""
import logging
from typing import Optional
import asyncpg
from asyncpg.pool import Pool

from config import settings

logger = logging.getLogger(__name__)


class DatabaseService:
    """PostgreSQL database connection manager (Ephemeral - for transcripts)."""
    
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
        logger.info("Ephemeral database pool initialized")
    
    async def close_pool(self):
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Ephemeral database pool closed")
    
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


class PersistentDatabaseService:
    """PostgreSQL database connection manager (Persistent - for users, auth, feedback)."""
    
    def __init__(self):
        self.pool: Optional[Pool] = None
    
    async def init_pool(self):
        """Initialize persistent database connection pool."""
        self.pool = await asyncpg.create_pool(
            settings.persistent_database_url,
            min_size=2,
            max_size=10,
            command_timeout=60
        )
        logger.info("Persistent database pool initialized")
    
    async def close_pool(self):
        """Close persistent database connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Persistent database pool closed")
    
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


# Global database services
db_service = DatabaseService()
persistent_db_service = PersistentDatabaseService()


async def init_db():
    """Initialize ephemeral database connection and create tables if needed."""
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
                answer_end_page INT,
                answer_end_line INT,
                is_final BOOLEAN DEFAULT TRUE,
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
            -- Only create index if column exists
            DO $$ 
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'qa_items' AND column_name = 'is_final'
                ) THEN
                    CREATE INDEX IF NOT EXISTS idx_qa_items_is_final ON qa_items(document_id, is_final);
                END IF;
            END $$;
            
            -- Create separate table for final Q/A pairs (distinct from interim/variables)
            CREATE TABLE IF NOT EXISTS final_qa_items (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
                page_number INT NOT NULL,
                line_number INT NOT NULL,
                pdf_page_index INT,
                answer_end_page INT,
                answer_end_line INT,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                summary TEXT DEFAULT '',
                topic VARCHAR(255) DEFAULT 'Other',
                created_at TIMESTAMP DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_final_qa_items_document_id ON final_qa_items(document_id);
            CREATE INDEX IF NOT EXISTS idx_final_qa_items_page_line ON final_qa_items(document_id, page_number, line_number);
            
            -- Verify table was created
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'final_qa_items') THEN
                    RAISE NOTICE 'final_qa_items table exists';
                ELSE
                    RAISE EXCEPTION 'final_qa_items table was not created';
                END IF;
            END $$;
            
            -- Add event_date column if it doesn't exist (migration)
            DO $$ 
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'final_qa_items' AND column_name = 'event_date'
                ) THEN
                    ALTER TABLE final_qa_items ADD COLUMN event_date VARCHAR(50);
                END IF;
            END $$;
            
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
        
        logger.info("Ephemeral database tables initialized")


async def init_persistent_db():
    """Initialize persistent database connection and create tables if needed."""
    await persistent_db_service.init_pool()
    
    # Create persistent tables if they don't exist
    async with persistent_db_service.pool.acquire() as conn:
        await conn.execute("""
            -- Users table (from Google OAuth)
            CREATE TABLE IF NOT EXISTS users (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                email VARCHAR(255) UNIQUE NOT NULL,
                google_id VARCHAR(255) UNIQUE NOT NULL,
                name VARCHAR(255),
                picture VARCHAR(500),
                is_admin BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW(),
                last_login TIMESTAMP DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
            CREATE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id);
            
            -- Sessions table (JWT refresh tokens)
            CREATE TABLE IF NOT EXISTS sessions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                refresh_token VARCHAR(500) UNIQUE NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_refresh_token ON sessions(refresh_token);
            
            -- Bug reports table
            CREATE TABLE IF NOT EXISTS bug_reports (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                title VARCHAR(255) NOT NULL,
                type VARCHAR(50) NOT NULL, -- 'bug' or 'feature'
                status VARCHAR(50) DEFAULT 'open', -- 'open', 'in_progress', 'resolved', 'closed'
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_bug_reports_user_id ON bug_reports(user_id);
            CREATE INDEX IF NOT EXISTS idx_bug_reports_status ON bug_reports(status);
            
            -- Chat messages table
            CREATE TABLE IF NOT EXISTS chat_messages (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                bug_report_id UUID REFERENCES bug_reports(id) ON DELETE CASCADE,
                sender_id UUID REFERENCES users(id) ON DELETE CASCADE,
                message TEXT NOT NULL,
                screenshot_url VARCHAR(500),
                is_admin_message BOOLEAN DEFAULT FALSE,
                read_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_chat_messages_bug_report_id ON chat_messages(bug_report_id);
            CREATE INDEX IF NOT EXISTS idx_chat_messages_sender_id ON chat_messages(sender_id);
            
            -- Learning feedback table
            CREATE TABLE IF NOT EXISTS learning_feedback (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                ai_summary TEXT NOT NULL,
                user_summary TEXT NOT NULL,
                notes TEXT,
                document_filename VARCHAR(255),
                page_citation VARCHAR(50),
                status VARCHAR(50) DEFAULT 'pending', -- 'pending', 'reviewed', 'applied', 'rejected'
                reviewed_by UUID REFERENCES users(id),
                reviewed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_learning_feedback_user_id ON learning_feedback(user_id);
            CREATE INDEX IF NOT EXISTS idx_learning_feedback_status ON learning_feedback(status);
            
            -- User prompt settings table
            CREATE TABLE IF NOT EXISTS user_prompt_settings (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID REFERENCES users(id) ON DELETE CASCADE UNIQUE,
                preset_options JSONB DEFAULT '{}',
                custom_instructions TEXT,
                updated_at TIMESTAMP DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_user_prompt_settings_user_id ON user_prompt_settings(user_id);
            
            -- Notifications table
            CREATE TABLE IF NOT EXISTS notifications (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                type VARCHAR(50) NOT NULL, -- 'bug_report', 'chat_message', 'learning_feedback'
                title VARCHAR(255) NOT NULL,
                message TEXT NOT NULL,
                link VARCHAR(500),
                read_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications(user_id);
            CREATE INDEX IF NOT EXISTS idx_notifications_read_at ON notifications(user_id, read_at);
            
            -- Processing metrics table (for time estimates)
            CREATE TABLE IF NOT EXISTS processing_metrics (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                total_pages INT NOT NULL,
                total_processing_time_seconds FLOAT NOT NULL,
                avg_time_per_page FLOAT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_processing_metrics_created_at ON processing_metrics(created_at DESC);
        """)
        
        logger.info("Persistent database tables initialized")








