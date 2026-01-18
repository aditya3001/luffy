"""
Database migration script for on-demand code indexing.

This script:
1. Removes code_indexing_interval_hours column from services table
2. Adds new columns for on-demand indexing status tracking:
   - code_indexing_status (not_indexed, indexing, completed, failed)
   - code_indexing_trigger (exception_detected, pre_rca, manual, webhook)
   - last_indexed_commit (Git commit SHA)
   - code_indexing_error (error message if failed)
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text, inspect
from src.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration():
    """Run the database migration"""
    logger.info("Starting on-demand code indexing migration...")
    
    # Create engine
    engine = create_engine(settings.database_url)
    
    with engine.connect() as conn:
        # Start transaction
        trans = conn.begin()
        
        try:
            # Check if services table exists
            inspector = inspect(engine)
            if 'services' not in inspector.get_table_names():
                logger.error("Services table does not exist. Please run service migration first.")
                return False
            
            # Get existing columns
            existing_columns = [col['name'] for col in inspector.get_columns('services')]
            logger.info(f"Existing columns: {existing_columns}")
            
            # 1. Remove code_indexing_interval_hours if it exists
            if 'code_indexing_interval_hours' in existing_columns:
                logger.info("Removing code_indexing_interval_hours column...")
                conn.execute(text("""
                    ALTER TABLE services 
                    DROP COLUMN IF EXISTS code_indexing_interval_hours
                """))
                logger.info("✓ Removed code_indexing_interval_hours")
            else:
                logger.info("code_indexing_interval_hours column does not exist, skipping removal")
            
            # 2. Add code_indexing_status column
            if 'code_indexing_status' not in existing_columns:
                logger.info("Adding code_indexing_status column...")
                conn.execute(text("""
                    ALTER TABLE services 
                    ADD COLUMN code_indexing_status VARCHAR DEFAULT 'not_indexed'
                """))
                logger.info("✓ Added code_indexing_status")
            else:
                logger.info("code_indexing_status column already exists")
            
            # 3. Add code_indexing_trigger column
            if 'code_indexing_trigger' not in existing_columns:
                logger.info("Adding code_indexing_trigger column...")
                conn.execute(text("""
                    ALTER TABLE services 
                    ADD COLUMN code_indexing_trigger VARCHAR
                """))
                logger.info("✓ Added code_indexing_trigger")
            else:
                logger.info("code_indexing_trigger column already exists")
            
            # 4. Add last_indexed_commit column
            if 'last_indexed_commit' not in existing_columns:
                logger.info("Adding last_indexed_commit column...")
                conn.execute(text("""
                    ALTER TABLE services 
                    ADD COLUMN last_indexed_commit VARCHAR
                """))
                logger.info("✓ Added last_indexed_commit")
            else:
                logger.info("last_indexed_commit column already exists")
            
            # 5. Add code_indexing_error column
            if 'code_indexing_error' not in existing_columns:
                logger.info("Adding code_indexing_error column...")
                conn.execute(text("""
                    ALTER TABLE services 
                    ADD COLUMN code_indexing_error TEXT
                """))
                logger.info("✓ Added code_indexing_error")
            else:
                logger.info("code_indexing_error column already exists")
            
            # 6. Update existing services to have 'not_indexed' status
            logger.info("Updating existing services to 'not_indexed' status...")
            result = conn.execute(text("""
                UPDATE services 
                SET code_indexing_status = 'not_indexed'
                WHERE code_indexing_status IS NULL
            """))
            logger.info(f"✓ Updated {result.rowcount} services")
            
            # Commit transaction
            trans.commit()
            logger.info("✅ Migration completed successfully!")
            
            # Show final schema
            inspector = inspect(engine)
            final_columns = [col['name'] for col in inspector.get_columns('services')]
            logger.info(f"\nFinal services table columns: {final_columns}")
            
            return True
            
        except Exception as e:
            trans.rollback()
            logger.error(f"❌ Migration failed: {e}", exc_info=True)
            return False


def verify_migration():
    """Verify the migration was successful"""
    logger.info("\nVerifying migration...")
    
    engine = create_engine(settings.database_url)
    inspector = inspect(engine)
    
    required_columns = [
        'code_indexing_status',
        'code_indexing_trigger',
        'last_indexed_commit',
        'code_indexing_error'
    ]
    
    existing_columns = [col['name'] for col in inspector.get_columns('services')]
    
    missing_columns = [col for col in required_columns if col not in existing_columns]
    
    if missing_columns:
        logger.error(f"❌ Missing columns: {missing_columns}")
        return False
    
    # Check that old column is removed
    if 'code_indexing_interval_hours' in existing_columns:
        logger.warning("⚠️ Old column code_indexing_interval_hours still exists")
    
    logger.info("✅ All required columns present")
    
    # Check data
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT 
                id, 
                name, 
                code_indexing_status,
                code_indexing_enabled,
                last_code_indexing,
                last_indexed_commit
            FROM services 
            LIMIT 5
        """))
        
        rows = result.fetchall()
        if rows:
            logger.info(f"\nSample services ({len(rows)} rows):")
            for row in rows:
                logger.info(f"  - {row[1]}: status={row[2]}, enabled={row[3]}, last_indexed={row[4]}, commit={row[5]}")
        else:
            logger.info("No services found in database")
    
    return True


if __name__ == "__main__":
    logger.info("=" * 80)
    logger.info("On-Demand Code Indexing Migration")
    logger.info("=" * 80)
    
    # Run migration
    success = run_migration()
    
    if success:
        # Verify migration
        verify_migration()
        logger.info("\n" + "=" * 80)
        logger.info("Migration completed successfully!")
        logger.info("=" * 80)
        logger.info("\nNext steps:")
        logger.info("1. Restart your application")
        logger.info("2. Code indexing will now be triggered on-demand when exceptions are detected")
        logger.info("3. Use POST /api/v1/code-indexing/services/{service_id}/trigger for manual indexing")
        logger.info("4. Check GET /api/v1/code-indexing/services/{service_id}/status for indexing status")
    else:
        logger.error("\n" + "=" * 80)
        logger.error("Migration failed! Please check the errors above.")
        logger.error("=" * 80)
        sys.exit(1)
