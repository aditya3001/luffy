#!/usr/bin/env python3
"""
Database Migration: Add Git API Configuration Fields to Service Model

This migration adds the following fields to the services table:
- git_provider (String): 'github' or 'gitlab'
- repository_owner (String): GitHub org/user or GitLab namespace
- repository_name (String): Repository name
- access_token_encrypted (String): Encrypted API access token

These fields enable API-based code indexing without local repository clones.

Usage:
    python scripts/migrate_git_api_fields.py
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.storage.database import get_db
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate():
    """Add Git API configuration fields to services table"""
    
    logger.info("Starting migration: Add Git API fields to services table")
    
    with get_db() as db:
        try:
            # Check if columns already exist
            result = db.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'services' 
                AND column_name IN ('git_provider', 'repository_owner', 'repository_name', 'access_token_encrypted')
            """))
            existing_columns = {row[0] for row in result}
            
            # Add git_provider column
            if 'git_provider' not in existing_columns:
                logger.info("Adding column: git_provider")
                db.execute(text("""
                    ALTER TABLE services 
                    ADD COLUMN git_provider VARCHAR
                """))
                logger.info("✓ Added git_provider column")
            else:
                logger.info("✓ Column git_provider already exists")
            
            # Add repository_owner column
            if 'repository_owner' not in existing_columns:
                logger.info("Adding column: repository_owner")
                db.execute(text("""
                    ALTER TABLE services 
                    ADD COLUMN repository_owner VARCHAR
                """))
                logger.info("✓ Added repository_owner column")
            else:
                logger.info("✓ Column repository_owner already exists")
            
            # Add repository_name column
            if 'repository_name' not in existing_columns:
                logger.info("Adding column: repository_name")
                db.execute(text("""
                    ALTER TABLE services 
                    ADD COLUMN repository_name VARCHAR
                """))
                logger.info("✓ Added repository_name column")
            else:
                logger.info("✓ Column repository_name already exists")
            
            # Add access_token_encrypted column
            if 'access_token_encrypted' not in existing_columns:
                logger.info("Adding column: access_token_encrypted")
                db.execute(text("""
                    ALTER TABLE services 
                    ADD COLUMN access_token_encrypted VARCHAR
                """))
                logger.info("✓ Added access_token_encrypted column")
            else:
                logger.info("✓ Column access_token_encrypted already exists")
            
            # Commit changes
            db.commit()
            logger.info("✓ Migration completed successfully")
            
            # Show summary
            logger.info("\n" + "="*60)
            logger.info("Migration Summary:")
            logger.info("="*60)
            logger.info("Added columns to 'services' table:")
            logger.info("  - git_provider (VARCHAR)")
            logger.info("  - repository_owner (VARCHAR)")
            logger.info("  - repository_name (VARCHAR)")
            logger.info("  - access_token_encrypted (VARCHAR)")
            logger.info("\nThese fields enable API-based code indexing.")
            logger.info("="*60)
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            db.rollback()
            raise


def verify_migration():
    """Verify that migration was successful"""
    
    logger.info("\nVerifying migration...")
    
    with get_db() as db:
        try:
            # Check all columns exist
            result = db.execute(text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'services' 
                AND column_name IN ('git_provider', 'repository_owner', 'repository_name', 'access_token_encrypted')
                ORDER BY column_name
            """))
            
            columns = list(result)
            
            if len(columns) == 4:
                logger.info("✓ All columns verified:")
                for col_name, data_type, is_nullable in columns:
                    logger.info(f"  - {col_name} ({data_type}, nullable: {is_nullable})")
                return True
            else:
                logger.error(f"✗ Expected 4 columns, found {len(columns)}")
                return False
                
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return False


def show_example_usage():
    """Show example of how to use new fields"""
    
    logger.info("\n" + "="*60)
    logger.info("Example Usage:")
    logger.info("="*60)
    
    example = """
# Configure service for API-based code indexing

from src.storage.database import get_db
from src.storage.models import Service
from src.utils.encryption import encrypt_token

with get_db() as db:
    service = db.query(Service).filter(Service.id == 'my-service').first()
    
    # Set Git API configuration
    service.git_provider = 'github'  # or 'gitlab'
    service.repository_owner = 'myorg'
    service.repository_name = 'myrepo'
    service.git_branch = 'main'
    
    # Encrypt and store access token
    token = 'ghp_your_github_token_here'
    service.access_token_encrypted = encrypt_token(token)
    
    db.commit()

# Now code indexing will use GitHub API instead of local clone
"""
    
    logger.info(example)
    logger.info("="*60)


if __name__ == '__main__':
    try:
        # Run migration
        migrate()
        
        # Verify migration
        if verify_migration():
            logger.info("\n✓ Migration completed and verified successfully!")
            
            # Show example usage
            show_example_usage()
            
            sys.exit(0)
        else:
            logger.error("\n✗ Migration verification failed!")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"\n✗ Migration failed: {e}")
        sys.exit(1)
