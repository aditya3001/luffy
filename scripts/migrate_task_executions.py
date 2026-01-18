"""
Migration script to add task_executions table for tracking task runs.
This enables real-time monitoring of task execution history.
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
    """Add task_executions table"""
    engine = create_engine(settings.database_url)
    
    with engine.connect() as conn:
        # Create task_executions table
        logger.info("Creating task_executions table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS task_executions (
                id SERIAL PRIMARY KEY,
                service_id VARCHAR NOT NULL REFERENCES services(id) ON DELETE CASCADE,
                task_name VARCHAR NOT NULL,
                started_at TIMESTAMP NOT NULL DEFAULT NOW(),
                completed_at TIMESTAMP,
                status VARCHAR NOT NULL,
                error_message TEXT,
                stats JSONB,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        
        # Create indexes
        logger.info("Creating indexes...")
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_task_executions_service_task 
            ON task_executions(service_id, task_name)
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_task_executions_started 
            ON task_executions(started_at DESC)
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_task_executions_status 
            ON task_executions(status)
        """))
        
        conn.commit()
        logger.info("✅ Migration completed successfully!")
        
        # Show table info
        result = conn.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'task_executions'
            ORDER BY ordinal_position
        """))
        
        logger.info("\nTask Executions Table Schema:")
        for row in result:
            logger.info(f"  - {row[0]}: {row[1]}")

if __name__ == "__main__":
    try:
        migrate()
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        sys.exit(1)
