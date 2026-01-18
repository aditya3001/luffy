"""
Migration script to add log fetch duration fields to services table.
Adds support for configurable OpenSearch query time ranges (days, hours, minutes).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from src.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    """Add log fetch duration fields to services table"""
    engine = create_engine(settings.database_url)
    
    with engine.connect() as conn:
        logger.info("Adding log fetch duration fields to services table...")
        
        # Rename log_fetch_interval_minutes to log_fetch_duration_minutes
        try:
            conn.execute(text("""
                ALTER TABLE services 
                RENAME COLUMN log_fetch_interval_minutes TO log_fetch_duration_minutes
            """))
            logger.info("✅ Renamed log_fetch_interval_minutes to log_fetch_duration_minutes")
        except Exception as e:
            logger.warning(f"Column may already be renamed: {e}")
        
        # Add log_fetch_duration_hours field
        try:
            conn.execute(text("""
                ALTER TABLE services 
                ADD COLUMN IF NOT EXISTS log_fetch_duration_hours INTEGER
            """))
            logger.info("✅ Added log_fetch_duration_hours column")
        except Exception as e:
            logger.warning(f"log_fetch_duration_hours column may already exist: {e}")
        
        # Add log_fetch_duration_days field
        try:
            conn.execute(text("""
                ALTER TABLE services 
                ADD COLUMN IF NOT EXISTS log_fetch_duration_days INTEGER
            """))
            logger.info("✅ Added log_fetch_duration_days column")
        except Exception as e:
            logger.warning(f"log_fetch_duration_days column may already exist: {e}")
        
        conn.commit()
        logger.info("✅ Migration completed successfully!")
        
        # Show updated schema
        result = conn.execute(text("""
            SELECT column_name, data_type, column_default
            FROM information_schema.columns 
            WHERE table_name = 'services'
            AND column_name LIKE '%duration%'
            ORDER BY ordinal_position
        """))
        
        logger.info("\nLog Fetch Duration Columns:")
        for row in result:
            logger.info(f"  - {row[0]}: {row[1]} (default: {row[2]})")

if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        sys.exit(1)
