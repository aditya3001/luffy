#!/usr/bin/env python3
"""
Migration Script: Add service_id to indexing_metadata table

This script updates the indexing_metadata table to support multi-service architecture:
1. Renames columns to match new schema
2. Adds service_id column with foreign key
3. Changes primary key from repository to id (UUID)
4. Migrates existing data to new schema

Run this script once to migrate the database.
"""

import sys
import os
from pathlib import Path
import uuid
import logging

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, text
from src.config.settings import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def migrate_indexing_metadata():
    """Migrate indexing_metadata table to support multi-service architecture"""
    
    engine = create_engine(settings.database_url)
    
    with engine.connect() as conn:
        try:
            logger.info("Starting indexing_metadata migration...")
            
            # Check if migration is needed
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'indexing_metadata' 
                AND column_name = 'service_id'
            """))
            
            if result.fetchone():
                logger.info("✅ Migration already applied - service_id column exists")
                return
            
            logger.info("📋 Creating backup of existing data...")
            
            # Get existing data
            result = conn.execute(text("""
                SELECT * FROM indexing_metadata
            """))
            existing_data = result.fetchall()
            logger.info(f"Found {len(existing_data)} existing records")
            
            # Get default service (first service or create one)
            result = conn.execute(text("""
                SELECT id FROM services ORDER BY created_at LIMIT 1
            """))
            default_service = result.fetchone()
            
            if not default_service:
                logger.warning("⚠️  No services found, creating default service...")
                default_service_id = 'default-service'
                conn.execute(text("""
                    INSERT INTO services (id, name, description, is_active, created_at, updated_at)
                    VALUES (:id, :name, :description, true, NOW(), NOW())
                """), {
                    'id': default_service_id,
                    'name': 'Default Service',
                    'description': 'Auto-created during indexing_metadata migration'
                })
                conn.commit()
            else:
                default_service_id = default_service[0]
            
            logger.info(f"Using default service: {default_service_id}")
            
            # Step 1: Rename table to backup
            logger.info("📦 Creating backup table...")
            conn.execute(text("""
                ALTER TABLE indexing_metadata RENAME TO indexing_metadata_backup
            """))
            conn.commit()
            
            # Step 2: Create new table with updated schema
            logger.info("🔨 Creating new table with updated schema...")
            conn.execute(text("""
                CREATE TABLE indexing_metadata (
                    id VARCHAR PRIMARY KEY,
                    service_id VARCHAR NOT NULL REFERENCES services(id) ON DELETE CASCADE,
                    repository VARCHAR NOT NULL,
                    commit_sha VARCHAR,
                    indexed_at TIMESTAMP,
                    files_indexed INTEGER DEFAULT 0,
                    code_blocks_created INTEGER DEFAULT 0,
                    indexing_mode VARCHAR,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """))
            conn.commit()
            
            # Step 3: Create index on service_id
            logger.info("📇 Creating index on service_id...")
            conn.execute(text("""
                CREATE INDEX idx_indexing_metadata_service_id ON indexing_metadata(service_id)
            """))
            conn.commit()
            
            # Step 4: Migrate data
            logger.info("📊 Migrating existing data...")
            for row in existing_data:
                new_id = str(uuid.uuid4())
                conn.execute(text("""
                    INSERT INTO indexing_metadata (
                        id, service_id, repository, commit_sha, indexed_at,
                        files_indexed, code_blocks_created, indexing_mode,
                        created_at, updated_at
                    ) VALUES (
                        :id, :service_id, :repository, :commit_sha, :indexed_at,
                        :files_indexed, :code_blocks_created, :indexing_mode,
                        :created_at, :updated_at
                    )
                """), {
                    'id': new_id,
                    'service_id': default_service_id,
                    'repository': row[0],  # repository (old PK)
                    'commit_sha': row[1],  # last_indexed_commit -> commit_sha
                    'indexed_at': row[2],  # last_indexed_at -> indexed_at
                    'files_indexed': row[3] or 0,  # total_files_indexed -> files_indexed
                    'code_blocks_created': row[4] or 0,  # total_blocks_indexed -> code_blocks_created
                    'indexing_mode': row[5] or 'incremental',
                    'created_at': row[6],
                    'updated_at': row[7]
                })
            conn.commit()
            
            logger.info(f"✅ Migrated {len(existing_data)} records")
            
            # Step 5: Drop backup table
            logger.info("🗑️  Dropping backup table...")
            conn.execute(text("""
                DROP TABLE indexing_metadata_backup
            """))
            conn.commit()
            
            logger.info("✅ Migration completed successfully!")
            logger.info("")
            logger.info("Summary:")
            logger.info(f"  - Migrated {len(existing_data)} indexing metadata records")
            logger.info(f"  - All records assigned to service: {default_service_id}")
            logger.info(f"  - New schema: id (PK), service_id (FK), repository, commit_sha, indexed_at")
            logger.info(f"  - Old columns renamed: last_indexed_commit → commit_sha, last_indexed_at → indexed_at")
            logger.info(f"  - Old columns renamed: total_files_indexed → files_indexed, total_blocks_indexed → code_blocks_created")
            
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            logger.error("Rolling back changes...")
            conn.rollback()
            
            # Try to restore from backup if it exists
            try:
                conn.execute(text("""
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'indexing_metadata_backup'
                """))
                if conn.fetchone():
                    logger.info("Restoring from backup...")
                    conn.execute(text("DROP TABLE IF EXISTS indexing_metadata"))
                    conn.execute(text("ALTER TABLE indexing_metadata_backup RENAME TO indexing_metadata"))
                    conn.commit()
                    logger.info("✅ Restored from backup")
            except Exception as restore_error:
                logger.error(f"Failed to restore from backup: {restore_error}")
            
            raise


if __name__ == '__main__':
    try:
        migrate_indexing_metadata()
        sys.exit(0)
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)
