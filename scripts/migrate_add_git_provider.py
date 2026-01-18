#!/usr/bin/env python3
"""
Migration script to add git_provider column to services table.
This supports GitHub, GitLab, and Bitbucket providers for code indexing.
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from src.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate():
    """Add git_provider column to services table"""
    try:
        # Create database engine
        engine = create_engine(settings.DATABASE_URL)
        
        with engine.connect() as conn:
            # Check if column already exists
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='services' AND column_name='git_provider'
            """))
            
            if result.fetchone():
                logger.info("✅ Column 'git_provider' already exists in services table")
                return
            
            # Add git_provider column
            logger.info("Adding 'git_provider' column to services table...")
            conn.execute(text("""
                ALTER TABLE services 
                ADD COLUMN git_provider VARCHAR
            """))
            conn.commit()
            
            logger.info("✅ Successfully added 'git_provider' column")
            
            # Try to infer git_provider from repository_url for existing services
            # Note: Only GitHub and GitLab are currently supported
            logger.info("Inferring git_provider from repository_url for existing services...")
            conn.execute(text("""
                UPDATE services 
                SET git_provider = CASE
                    WHEN repository_url LIKE '%github.com%' THEN 'github'
                    WHEN repository_url LIKE '%gitlab.com%' THEN 'gitlab'
                    ELSE NULL
                END
                WHERE repository_url IS NOT NULL
            """))
            conn.commit()
            
            # Warn about unsupported providers
            result = conn.execute(text("""
                SELECT COUNT(*) as count
                FROM services
                WHERE repository_url IS NOT NULL
                  AND git_provider IS NULL
            """))
            unsupported_count = result.fetchone()[0]
            if unsupported_count > 0:
                logger.warning(
                    f"⚠️  {unsupported_count} service(s) have repository URLs that could not be mapped to a provider. "
                    f"Only GitHub and GitLab are currently supported. "
                    f"Bitbucket support is planned for a future release."
                )
            
            # Count updated services
            result = conn.execute(text("""
                SELECT 
                    git_provider, 
                    COUNT(*) as count 
                FROM services 
                WHERE git_provider IS NOT NULL
                GROUP BY git_provider
            """))
            
            logger.info("Updated services:")
            for row in result:
                logger.info(f"  - {row[0]}: {row[1]} service(s)")
            
            logger.info("✅ Migration completed successfully!")
            
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Migration: Add git_provider column to services table")
    logger.info("=" * 60)
    migrate()
