"""
Database Migration: Add Git Access Token Fields

Adds git_access_token, git_token_expires_at, and git_token_last_validated fields
to the services table for secure Git authentication.

Run this migration before using the new Git access token feature.
"""

import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine, text
from src.config import settings

def run_migration():
    """Run the migration to add Git access token fields"""
    
    print("=" * 80)
    print("Git Access Token Migration")
    print("=" * 80)
    print()
    
    # Create engine
    engine = create_engine(settings.DATABASE_URL)
    
    print(f"Connected to database: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else 'local'}")
    print()
    
    with engine.connect() as conn:
        # Check if columns already exist
        print("Checking existing schema...")
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'services' 
            AND column_name IN ('git_access_token', 'git_token_expires_at', 'git_token_last_validated')
        """))
        existing_columns = [row[0] for row in result]
        
        if len(existing_columns) == 3:
            print("✅ All columns already exist. No migration needed.")
            return
        
        print(f"Found {len(existing_columns)} of 3 columns. Adding missing columns...")
        print()
        
        # Add git_access_token column
        if 'git_access_token' not in existing_columns:
            print("Adding git_access_token column...")
            conn.execute(text("""
                ALTER TABLE services 
                ADD COLUMN git_access_token VARCHAR
            """))
            conn.commit()
            print("✅ Added git_access_token column")
        else:
            print("⏭️  git_access_token column already exists")
        
        # Add git_token_expires_at column
        if 'git_token_expires_at' not in existing_columns:
            print("Adding git_token_expires_at column...")
            conn.execute(text("""
                ALTER TABLE services 
                ADD COLUMN git_token_expires_at TIMESTAMP
            """))
            conn.commit()
            print("✅ Added git_token_expires_at column")
        else:
            print("⏭️  git_token_expires_at column already exists")
        
        # Add git_token_last_validated column
        if 'git_token_last_validated' not in existing_columns:
            print("Adding git_token_last_validated column...")
            conn.execute(text("""
                ALTER TABLE services 
                ADD COLUMN git_token_last_validated TIMESTAMP
            """))
            conn.commit()
            print("✅ Added git_token_last_validated column")
        else:
            print("⏭️  git_token_last_validated column already exists")
        
        print()
        print("=" * 80)
        print("Migration completed successfully!")
        print("=" * 80)
        print()
        print("Next steps:")
        print("1. Configure Git access token in Settings page for each service")
        print("2. Code indexing will use the token for authentication")
        print("3. Token expiry warnings will appear 7 days before expiration")
        print()

def rollback_migration():
    """Rollback the migration (remove added columns)"""
    
    print("=" * 80)
    print("Git Access Token Migration Rollback")
    print("=" * 80)
    print()
    
    response = input("Are you sure you want to rollback? This will remove all Git token data. (yes/no): ")
    if response.lower() != 'yes':
        print("Rollback cancelled.")
        return
    
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        print("Removing git_access_token column...")
        try:
            conn.execute(text("ALTER TABLE services DROP COLUMN git_access_token"))
            conn.commit()
            print("✅ Removed git_access_token column")
        except Exception as e:
            print(f"⚠️  Column might not exist: {e}")
        
        print("Removing git_token_expires_at column...")
        try:
            conn.execute(text("ALTER TABLE services DROP COLUMN git_token_expires_at"))
            conn.commit()
            print("✅ Removed git_token_expires_at column")
        except Exception as e:
            print(f"⚠️  Column might not exist: {e}")
        
        print("Removing git_token_last_validated column...")
        try:
            conn.execute(text("ALTER TABLE services DROP COLUMN git_token_last_validated"))
            conn.commit()
            print("✅ Removed git_token_last_validated column")
        except Exception as e:
            print(f"⚠️  Column might not exist: {e}")
        
        print()
        print("Rollback completed.")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate database for Git access token support')
    parser.add_argument('--rollback', action='store_true', help='Rollback the migration')
    args = parser.parse_args()
    
    try:
        if args.rollback:
            rollback_migration()
        else:
            run_migration()
    except Exception as e:
        print()
        print("=" * 80)
        print("❌ Migration failed!")
        print("=" * 80)
        print(f"Error: {e}")
        print()
        import traceback
        traceback.print_exc()
        sys.exit(1)
