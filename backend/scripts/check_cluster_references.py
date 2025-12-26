#!/usr/bin/env python3
"""
Check for cluster_jobs table references in the database and rename back to chunk_jobs if needed.

This script checks if the database has a cluster_jobs table (from the cluster rename)
and renames it back to chunk_jobs to match the rolled-back code.
"""

import asyncio
import asyncpg
import os
import sys
from pathlib import Path

# Add parent directory to path to import config
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings


async def check_and_fix_cluster_references():
    """Check for cluster_jobs table and rename to chunk_jobs if it exists."""
    
    # Connect to ephemeral database
    conn = await asyncpg.connect(settings.DATABASE_URL)
    
    try:
        # Check if cluster_jobs table exists
        cluster_table_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'cluster_jobs'
            )
        """)
        
        # Check if chunk_jobs table exists
        chunk_table_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'chunk_jobs'
            )
        """)
        
        print(f"cluster_jobs table exists: {cluster_table_exists}")
        print(f"chunk_jobs table exists: {chunk_table_exists}")
        
        if cluster_table_exists and not chunk_table_exists:
            print("\n⚠️  Found cluster_jobs table but no chunk_jobs table!")
            print("Renaming cluster_jobs → chunk_jobs...")
            
            # Rename the table
            await conn.execute("ALTER TABLE cluster_jobs RENAME TO chunk_jobs")
            
            # Rename indexes
            try:
                await conn.execute("ALTER INDEX IF EXISTS idx_cluster_jobs_parent RENAME TO idx_chunk_jobs_parent")
            except Exception as e:
                print(f"  Note: Could not rename idx_cluster_jobs_parent: {e}")
            
            try:
                await conn.execute("ALTER INDEX IF EXISTS idx_cluster_jobs_status RENAME TO idx_chunk_jobs_status")
            except Exception as e:
                print(f"  Note: Could not rename idx_cluster_jobs_status: {e}")
            
            try:
                await conn.execute("ALTER INDEX IF EXISTS idx_cluster_jobs_document RENAME TO idx_chunk_jobs_document")
            except Exception as e:
                print(f"  Note: Could not rename idx_cluster_jobs_document: {e}")
            
            print("✅ Successfully renamed cluster_jobs → chunk_jobs")
            
        elif cluster_table_exists and chunk_table_exists:
            print("\n⚠️  Both cluster_jobs and chunk_jobs tables exist!")
            print("This is unexpected. Checking data...")
            
            cluster_count = await conn.fetchval("SELECT COUNT(*) FROM cluster_jobs")
            chunk_count = await conn.fetchval("SELECT COUNT(*) FROM chunk_jobs")
            
            print(f"  cluster_jobs rows: {cluster_count}")
            print(f"  chunk_jobs rows: {chunk_count}")
            
            if cluster_count > 0 and chunk_count == 0:
                print("  Migrating data from cluster_jobs to chunk_jobs...")
                await conn.execute("""
                    INSERT INTO chunk_jobs 
                    SELECT * FROM cluster_jobs
                """)
                print("  ✅ Data migrated")
                print("  Dropping cluster_jobs table...")
                await conn.execute("DROP TABLE cluster_jobs CASCADE")
                print("  ✅ cluster_jobs table dropped")
            elif cluster_count == 0:
                print("  cluster_jobs is empty, dropping it...")
                await conn.execute("DROP TABLE cluster_jobs CASCADE")
                print("  ✅ cluster_jobs table dropped")
            else:
                print("  ⚠️  Both tables have data - manual intervention needed!")
                
        elif not cluster_table_exists and chunk_table_exists:
            print("\n✅ Database is correct: chunk_jobs exists, no cluster_jobs")
            
        else:
            print("\n✅ No tables found (database may be empty or not initialized)")
        
        # Check for any cluster-related column names
        print("\nChecking for cluster-related column names...")
        cluster_columns = await conn.fetch("""
            SELECT table_name, column_name 
            FROM information_schema.columns 
            WHERE column_name LIKE '%cluster%'
            AND table_schema = 'public'
        """)
        
        if cluster_columns:
            print(f"⚠️  Found {len(cluster_columns)} columns with 'cluster' in name:")
            for row in cluster_columns:
                print(f"  - {row['table_name']}.{row['column_name']}")
        else:
            print("✅ No columns with 'cluster' in name found")
        
        # Check for cluster references in data
        print("\nChecking for 'cluster' string references in data...")
        tables_to_check = ['processing_jobs', 'chunk_jobs']
        
        for table in tables_to_check:
            if await conn.fetchval(f"""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = '{table}'
                )
            """):
                # Check error_message column if it exists
                has_error_col = await conn.fetchval(f"""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = '{table}' AND column_name = 'error_message'
                    )
                """)
                
                if has_error_col:
                    cluster_refs = await conn.fetch(f"""
                        SELECT id, error_message 
                        FROM {table} 
                        WHERE error_message LIKE '%cluster%'
                        LIMIT 10
                    """)
                    
                    if cluster_refs:
                        print(f"⚠️  Found {len(cluster_refs)} rows in {table} with 'cluster' in error_message")
                        for row in cluster_refs[:5]:
                            print(f"  - ID: {row['id']}, Error: {row['error_message'][:100]}")
                    else:
                        print(f"✅ No 'cluster' references in {table}.error_message")
        
    finally:
        await conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Checking for cluster_jobs references in database")
    print("=" * 60)
    asyncio.run(check_and_fix_cluster_references())
    print("\n" + "=" * 60)
    print("Check complete!")
    print("=" * 60)

