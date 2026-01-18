#!/usr/bin/env python3
"""
Migration script to add service_id to code indexing tables.

This script:
1. Adds service_id column to code_blocks table
2. Recreates indexing_metadata table with composite primary key
3. Updates existing records with default service_id
4. Creates necessary indexes
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.storage.database import get_db, engine
from src.storage.models import Service
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_code_blocks_table():
    """Add service_id to code_blocks table"""
    logger.info("Migrating code_blocks table...")
    
    with engine.connect() as conn:
        # Check if column exists
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='code_blocks' AND column_name='service_id'
        """))
        
        if result.fetchone():
            logger.info("service_id column already exists in code_blocks")
            return
        
        # Add service_id column (nullable initially)
        conn.execute(text("""
            ALTER TABLE code_blocks 
            ADD COLUMN service_id VARCHAR
        """))
        conn.commit()
        logger.info("✅ Added service_id column to code_blocks")
        
        # Get default service or create one
        with get_db() as db:
            default_service = db.query(Service).first()
            
            if not default_service:
                logger.warning("No services found, creating default service")
                default_service = Service(
                    id='default-service',
                    name='Default Service',
                    description='Default service for existing code blocks'
                )
                db.add(default_service)
                db.commit()
            
            default_service_id = default_service.id
        
        # Update existing records
        conn.execute(text(f"""
            UPDATE code_blocks 
            SET service_id = '{default_service_id}' 
            WHERE service_id IS NULL
        """))
        conn.commit()
        logger.info(f"✅ Updated existing code_blocks with service_id: {default_service_id}")
        
        # Make column non-nullable
        conn.execute(text("""
            ALTER TABLE code_blocks 
            ALTER COLUMN service_id SET NOT NULL
        """))
        conn.commit()
        logger.info("✅ Made service_id non-nullable")
        
        # Add foreign key constraint
        conn.execute(text("""
            ALTER TABLE code_blocks 
            ADD CONSTRAINT fk_code_blocks_service 
            FOREIGN KEY (service_id) REFERENCES services(id)
        """))
        conn.commit()
        logger.info("✅ Added foreign key constraint")
        
        # Create indexes
        conn.execute(text("""
            CREATE INDEX idx_code_blocks_service_id ON code_blocks(service_id)
        """))
        conn.execute(text("""
            CREATE INDEX idx_code_blocks_service_repo 
            ON code_blocks(service_id, repository)
        """))
        conn.commit()
        logger.info("✅ Created indexes")


def migrate_indexing_metadata_table():
    """Recreate indexing_metadata table with composite primary key"""
    logger.info("Migrating indexing_metadata table...")
    
    with engine.connect() as conn:
        # Backup existing data
        result = conn.execute(text("SELECT * FROM indexing_metadata"))
        existing_data = result.fetchall()
        logger.info(f"Backing up {len(existing_data)} existing records")
        
        # Drop and recreate table
        conn.execute(text("DROP TABLE IF EXISTS indexing_metadata"))
        conn.commit()
        
        conn.execute(text("""
            CREATE TABLE indexing_metadata (
                service_id VARCHAR NOT NULL,
                repository VARCHAR NOT NULL,
                last_indexed_commit VARCHAR,
                last_indexed_at TIMESTAMP,
                total_files_indexed INTEGER DEFAULT 0,
                total_blocks_indexed INTEGER DEFAULT 0,
                indexing_mode VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (service_id, repository),
                FOREIGN KEY (service_id) REFERENCES services(id)
            )
        """))
        conn.commit()
        logger.info("✅ Recreated indexing_metadata table")
        
        # Restore data with default service_id
        if existing_data:
            with get_db() as db:
                default_service = db.query(Service).first()
                default_service_id = default_service.id if default_service else 'default-service'
            
            for row in existing_data:
                conn.execute(text("""
                    INSERT INTO indexing_metadata 
                    (service_id, repository, last_indexed_commit, last_indexed_at, 
                     total_files_indexed, total_blocks_indexed, indexing_mode, 
                     created_at, updated_at)
                    VALUES (:service_id, :repository, :last_indexed_commit, :last_indexed_at,
                            :total_files_indexed, :total_blocks_indexed, :indexing_mode,
                            :created_at, :updated_at)
                """), {
                    'service_id': default_service_id,
                    'repository': row[0],  # Old primary key
                    'last_indexed_commit': row[1],
                    'last_indexed_at': row[2],
                    'total_files_indexed': row[3],
                    'total_blocks_indexed': row[4],
                    'indexing_mode': row[5],
                    'created_at': row[6],
                    'updated_at': row[7]
                })
            conn.commit()
            logger.info(f"✅ Restored {len(existing_data)} records")


def update_qdrant_metadata():
    """Update Qdrant vectors with service_id metadata"""
    logger.info("Updating Qdrant metadata...")
    logger.info("⚠️  Manual step required:")
    logger.info("   1. Re-index all code repositories to add service_id to Qdrant")
    logger.info("   2. Or run: python scripts/maintenance/reindex_all_services.py")


def print_summary():
    """Print migration summary and next steps"""
    logger.info("")
    logger.info("=" * 80)
    logger.info("MIGRATION SUMMARY")
    logger.info("=" * 80)
    
    with get_db() as db:
        # Count code blocks by service
        services = db.query(Service).all()
        
        logger.info("")
        logger.info("Code Blocks by Service:")
        for service in services:
            from src.storage.models import CodeBlock
            count = db.query(CodeBlock).filter_by(service_id=service.id).count()
            logger.info(f"  - {service.name} ({service.id}): {count} blocks")
        
        # Count indexing metadata
        from src.storage.models import IndexingMetadata
        metadata_count = db.query(IndexingMetadata).count()
        logger.info(f"")
        logger.info(f"Indexing Metadata Records: {metadata_count}")


def main():
    """Run all migrations"""
    logger.info("=" * 80)
    logger.info("Starting Service-Isolated Code Indexing Migration")
    logger.info("=" * 80)
    logger.info("")
    
    try:
        migrate_code_blocks_table()
        logger.info("")
        
        migrate_indexing_metadata_table()
        logger.info("")
        
        update_qdrant_metadata()
        logger.info("")
        
        print_summary()
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("✅ Migration completed successfully!")
        logger.info("=" * 80)
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Update CodeIndexer to require service_id parameter")
        logger.info("2. Re-index all service repositories to populate Qdrant with service_id")
        logger.info("3. Test code retrieval with service filtering")
        logger.info("4. Verify RCA generation uses correct service code")
        logger.info("")
        logger.info("To re-index all services:")
        logger.info("  python scripts/maintenance/reindex_all_services.py")
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}", exc_info=True)
        logger.error("")
        logger.error("Migration rolled back. Please fix the error and try again.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
