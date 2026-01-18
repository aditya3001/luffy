#!/usr/bin/env python3
"""
Database migration to add log_processing_enabled toggle to services table.

This migration:
1. Adds log_processing_enabled column (default True)
2. Sets all existing services to enabled (backward compatible)
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.storage.database import engine, get_db_dependency
from src.storage.models import Service
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate():
    """Run the migration"""
    logger.info("Starting migration: Add log_processing_enabled toggle")
    
    try:
        with engine.connect() as conn:
            # Check if column already exists
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='services' 
                AND column_name='log_processing_enabled'
            """))
            
            if result.fetchone():
                logger.info("✅ Column log_processing_enabled already exists, skipping")
                return
            
            # Add log_processing_enabled column
            logger.info("Adding log_processing_enabled column to services table...")
            conn.execute(text("""
                ALTER TABLE services 
                ADD COLUMN log_processing_enabled BOOLEAN DEFAULT TRUE
            """))
            conn.commit()
            logger.info("✅ Column added successfully")
            
            # Update existing services to enabled (backward compatible)
            logger.info("Setting all existing services to log_processing_enabled=TRUE...")
            conn.execute(text("""
                UPDATE services 
                SET log_processing_enabled = TRUE 
                WHERE log_processing_enabled IS NULL
            """))
            conn.commit()
            logger.info("✅ Existing services updated")
        
        # Verify migration
        db = next(get_db_dependency())
        try:
            services = db.query(Service).all()
            logger.info(f"\n📊 Migration Summary:")
            logger.info(f"   Total services: {len(services)}")
            enabled_count = sum(1 for s in services if s.log_processing_enabled)
            logger.info(f"   Log processing enabled: {enabled_count}")
            logger.info(f"   Log processing disabled: {len(services) - enabled_count}")
        finally:
            db.close()
        
        logger.info("\n✅ Migration completed successfully!")
        logger.info("\n📝 Next Steps:")
        logger.info("   1. Restart backend server: uvicorn src.services.api:app --reload")
        logger.info("   2. Restart Celery worker: celery -A src.services.tasks worker --loglevel=info")
        logger.info("   3. Restart Celery beat: celery -A src.services.tasks beat --loglevel=info")
        logger.info("   4. Use UI to toggle log processing per service")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    migrate()
