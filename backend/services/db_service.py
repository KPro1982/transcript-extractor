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
                case_name TEXT,
                case_number VARCHAR(100),
                deposition_date VARCHAR(50),
                attorneys TEXT[],
                witness_name VARCHAR(255),
                created_at TIMESTAMP DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_documents_file_hash ON documents(file_hash);
            
            -- Add case info columns if they don't exist (migration)
            DO $$ 
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'documents' AND column_name = 'case_name'
                ) THEN
                    ALTER TABLE documents ADD COLUMN case_name TEXT;
                END IF;
                
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'documents' AND column_name = 'case_number'
                ) THEN
                    ALTER TABLE documents ADD COLUMN case_number VARCHAR(100);
                END IF;
                
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'documents' AND column_name = 'deposition_date'
                ) THEN
                    ALTER TABLE documents ADD COLUMN deposition_date VARCHAR(50);
                END IF;
                
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'documents' AND column_name = 'attorneys'
                ) THEN
                    ALTER TABLE documents ADD COLUMN attorneys TEXT[];
                END IF;
                
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'documents' AND column_name = 'witness_name'
                ) THEN
                    ALTER TABLE documents ADD COLUMN witness_name VARCHAR(255);
                END IF;
            END $$;
            
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
                topics TEXT[] DEFAULT ARRAY['Other']::TEXT[],
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
            
            -- Migrate topic column from VARCHAR to TEXT[] array (migration)
            DO $$ 
            BEGIN
                -- Check if topic is still VARCHAR (not yet migrated)
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'final_qa_items' 
                    AND column_name = 'topic' 
                    AND data_type = 'character varying'
                ) THEN
                    -- Migrate existing data to array format
                    ALTER TABLE final_qa_items 
                    ALTER COLUMN topic TYPE TEXT[] 
                    USING CASE 
                        WHEN topic IS NULL OR topic = '' THEN ARRAY['Other']::TEXT[]
                        ELSE ARRAY[topic]::TEXT[]
                    END;
                    
                    -- Set default for new rows
                    ALTER TABLE final_qa_items 
                    ALTER COLUMN topic SET DEFAULT ARRAY['Other']::TEXT[];
                    
                    RAISE NOTICE 'Migrated topic column to TEXT[] array';
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
            
            -- People mentioned in depositions
            CREATE TABLE IF NOT EXISTS people_mentioned (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
                normalized_name VARCHAR(255) NOT NULL,
                display_name VARCHAR(255) NOT NULL,
                role VARCHAR(50),
                context TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(document_id, normalized_name)
            );
            
            CREATE INDEX IF NOT EXISTS idx_people_mentioned_document ON people_mentioned(document_id);
            CREATE INDEX IF NOT EXISTS idx_people_mentioned_normalized ON people_mentioned(normalized_name);
            
            -- Junction table linking Q&A items to people mentioned
            CREATE TABLE IF NOT EXISTS qa_people (
                qa_item_id UUID REFERENCES final_qa_items(id) ON DELETE CASCADE,
                people_id UUID REFERENCES people_mentioned(id) ON DELETE CASCADE,
                mention_context TEXT,
                PRIMARY KEY (qa_item_id, people_id)
            );
            
            CREATE INDEX IF NOT EXISTS idx_qa_people_qa ON qa_people(qa_item_id);
            CREATE INDEX IF NOT EXISTS idx_qa_people_person ON qa_people(people_id);
            
            CREATE TABLE IF NOT EXISTS processing_jobs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
                status VARCHAR(50) NOT NULL,
                progress INT DEFAULT 0,
                error_message TEXT,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW(),
                num_chunks INT DEFAULT 1,
                is_chunked BOOLEAN DEFAULT FALSE
            );
            
            CREATE INDEX IF NOT EXISTS idx_processing_jobs_document_id ON processing_jobs(document_id);
            CREATE INDEX IF NOT EXISTS idx_processing_jobs_status ON processing_jobs(status);
            
            -- Add num_chunks column if it doesn't exist (migration)
            DO $$ 
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'processing_jobs' AND column_name = 'num_chunks'
                ) THEN
                    ALTER TABLE processing_jobs ADD COLUMN num_chunks INT DEFAULT 1;
                END IF;
            END $$;
            
            -- Add is_chunked column if it doesn't exist (migration)
            DO $$ 
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'processing_jobs' AND column_name = 'is_chunked'
                ) THEN
                    ALTER TABLE processing_jobs ADD COLUMN is_chunked BOOLEAN DEFAULT FALSE;
                END IF;
            END $$;
            
            -- Chunk jobs table for multi-worker parallel processing
            CREATE TABLE IF NOT EXISTS chunk_jobs (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                parent_job_id UUID REFERENCES processing_jobs(id) ON DELETE CASCADE,
                document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
                chunk_index INT NOT NULL,
                worker_id INT,
                first_page INT NOT NULL,
                last_page INT,
                status VARCHAR(50) NOT NULL,
                progress INT DEFAULT 0,
                error_message TEXT,
                items_processed INT DEFAULT 0,
                retry_count INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT NOW(),
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                UNIQUE(parent_job_id, chunk_index)
            );
            
            -- Add retry_count column if it doesn't exist (for existing databases)
            DO $$ 
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'chunk_jobs' AND column_name = 'retry_count'
                ) THEN
                    ALTER TABLE chunk_jobs ADD COLUMN retry_count INT DEFAULT 0;
                END IF;
            END $$;
            
            CREATE INDEX IF NOT EXISTS idx_chunk_jobs_parent ON chunk_jobs(parent_job_id);
            CREATE INDEX IF NOT EXISTS idx_chunk_jobs_status ON chunk_jobs(status);
            CREATE INDEX IF NOT EXISTS idx_chunk_jobs_document ON chunk_jobs(document_id);
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
            
            -- Bug report chat messages table (for admin-user communication)
            -- Rename old chat_messages table if it exists
            DO $$ 
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'chat_messages' 
                    AND NOT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'bug_report_messages'
                    )
                ) THEN
                    ALTER TABLE chat_messages RENAME TO bug_report_messages;
                    ALTER INDEX IF EXISTS idx_chat_messages_bug_report_id RENAME TO idx_bug_report_messages_bug_report_id;
                    ALTER INDEX IF EXISTS idx_chat_messages_sender_id RENAME TO idx_bug_report_messages_sender_id;
                END IF;
            END $$;
            
            CREATE TABLE IF NOT EXISTS bug_report_messages (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                bug_report_id UUID REFERENCES bug_reports(id) ON DELETE CASCADE,
                sender_id UUID REFERENCES users(id) ON DELETE CASCADE,
                message TEXT NOT NULL,
                screenshot_url VARCHAR(500),
                is_admin_message BOOLEAN DEFAULT FALSE,
                read_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_bug_report_messages_bug_report_id ON bug_report_messages(bug_report_id);
            CREATE INDEX IF NOT EXISTS idx_bug_report_messages_sender_id ON bug_report_messages(sender_id);
            
            -- Chat sessions table (for chat-with-depo feature)
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                document_id UUID NOT NULL,  -- References ephemeral DB documents table
                title VARCHAR(255) DEFAULT 'New Chat',
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_chat_sessions_user ON chat_sessions(user_id);
            CREATE INDEX IF NOT EXISTS idx_chat_sessions_document ON chat_sessions(document_id);
            CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated ON chat_sessions(user_id, updated_at DESC);
            
            -- Chat messages table (for chat-with-depo feature)
            CREATE TABLE IF NOT EXISTS depo_chat_messages (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
                role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                citations JSONB,  -- Array of {qa_item_id, page, line, text_snippet}
                created_at TIMESTAMP DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_depo_chat_messages_session ON depo_chat_messages(session_id);
            CREATE INDEX IF NOT EXISTS idx_depo_chat_messages_created ON depo_chat_messages(session_id, created_at ASC);
            
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
            
            -- Migration: Rename old columns to new schema if they exist
            DO $$ 
            BEGIN
                -- Check if old column exists and rename
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'processing_metrics' AND column_name = 'total_qa_pairs'
                ) THEN
                    ALTER TABLE processing_metrics RENAME COLUMN total_qa_pairs TO total_pages;
                END IF;
                
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'processing_metrics' AND column_name = 'avg_time_per_qa'
                ) THEN
                    ALTER TABLE processing_metrics RENAME COLUMN avg_time_per_qa TO avg_time_per_page;
                END IF;
            END $$;
        """)
        
        logger.info("Persistent database tables initialized")








