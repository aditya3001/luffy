"""
Database Migration: Remove Git/Code Indexing Fields from LogSource Table

Removes all Git and code indexing related fields from log_sources table.
These fields should only exist in the services table.

Fields to remove:
- code_indexing_enabled
- git_provider
- repository_url
- git_branch
- repository_owner
- repository_name
- repository_id
- access_token_encrypted
- token_status
- token_last_validated
- last_indexed_commit
- last_indexed_at
- indexing_status
- indexing_error

Run this migration after updating the models.py file.
"""

import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import create_engine, text
from src.config import settings

def run_migration():
    """Run the migration to remove Git fields from log_sources table"""
    
    print("=" * 80)
    print("Remove Git Fields from LogSource Migration")
    print("=" * 80)
    print()
    
    # Create engine
    engine = create_engine(settings.DATABASE_URL)
    
    print(f"Connected to database: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else 'local'}")
    print()
    
    columns_to_remove = [
        'code_indexing_enabled',
        'git_provider',
        'repository_url',
        'git_branch',
        'repository_owner',
        'repository_name',
        'repository_id',
        'access_token_encrypted',
        'token_status',
        'token_last_validated',
        'last_indexed_commit',
        'last_indexed_at',
        'indexing_status',
        'indexing_error'
    ]
    
    with engine.connect() as conn:
        # Check which columns exist
        print("Checking existing columns...")
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'log_sources'
        """))
        existing_columns = [row[0] for row in result]
        
        columns_to_drop = [col for col in columns_to_remove if col in existing_columns]
        
        if not columns_to_drop:
            print("✅ No Git-related columns found in log_sources table. Migration not needed.")
            return
        
        print(f"Found {len(columns_to_drop)} columns to remove:")
        for col in columns_to_drop:
            print(f"  - {col}")
        print()
        
        # Remove columns one by one
        for column in columns_to_drop:
            try:
                print(f"Removing {column} column...")
                conn.execute(text(f"""
                    ALTER TABLE log_sources 
                    DROP COLUMN IF EXISTS {column}
                """))
                conn.commit()
                print(f"✅ Removed {column} column")
            except Exception as e:
                print(f"❌ Error removing {column}: {e}")
                conn.rollback()
        
        print()
        print("=" * 80)
        print("Migration completed successfully!")
        print("=" * 80)
        print()
        print("Git and code indexing fields are now only in the services table.")
        print("LogSource table is now focused on log fetching configuration only.")

def rollback_migration():
    """Rollback the migration (add columns back)"""
    
    print("=" * 80)
    print("Rollback: Add Git Fields Back to LogSource")
    print("=" * 80)
    print()
    print("⚠️  WARNING: This will add Git fields back to log_sources table.")
    print()
    
    # Create engine
    engine = create_engine(settings.DATABASE_URL)
    
    print(f"Connected to database: {settings.DATABASE_URL.split('@')[1] if '@' in settings.DATABASE_URL else 'local'}")
    print()
    
    with engine.connect() as conn:
        try:
            print("Adding code_indexing_enabled column...")
            conn.execute(text("""
                ALTER TABLE log_sources 
                ADD COLUMN IF NOT EXISTS code_indexing_enabled BOOLEAN DEFAULT FALSE
            """))
            
            print("Adding git_provider column...")
            conn.execute(text("""
                ALTER TABLE log_sources 
                ADD COLUMN IF NOT EXISTS git_provider VARCHAR
            """))
            
            print("Adding repository_url column...")
            conn.execute(text("""
                ALTER TABLE log_sources 
                ADD COLUMN IF NOT EXISTS repository_url VARCHAR
            """))
            
            print("Adding git_branch column...")
            conn.execute(text("""
                ALTER TABLE log_sources 
                ADD COLUMN IF NOT EXISTS git_branch VARCHAR DEFAULT 'main'
            """))
            
            print("Adding repository_owner column...")
            conn.execute(text("""
                ALTER TABLE log_sources 
                ADD COLUMN IF NOT EXISTS repository_owner VARCHAR
            """))
            
            print("Adding repository_name column...")
            conn.execute(text("""
                ALTER TABLE log_sources 
                ADD COLUMN IF NOT EXISTS repository_name VARCHAR
            """))
            
            print("Adding repository_id column...")
            conn.execute(text("""
                ALTER TABLE log_sources 
                ADD COLUMN IF NOT EXISTS repository_id VARCHAR
            """))
            
            print("Adding access_token_encrypted column...")
            conn.execute(text("""
                ALTER TABLE log_sources 
                ADD COLUMN IF NOT EXISTS access_token_encrypted TEXT
            """))
            
            print("Adding token_status column...")
            conn.execute(text("""
                ALTER TABLE log_sources 
                ADD COLUMN IF NOT EXISTS token_status VARCHAR DEFAULT 'not_configured'
            """))
            
            print("Adding token_last_validated column...")
            conn.execute(text("""
                ALTER TABLE log_sources 
                ADD COLUMN IF NOT EXISTS token_last_validated TIMESTAMP
            """))
            
            print("Adding last_indexed_commit column...")
            conn.execute(text("""
                ALTER TABLE log_sources 
                ADD COLUMN IF NOT EXISTS last_indexed_commit VARCHAR
            """))
            
            print("Adding last_indexed_at column...")
            conn.execute(text("""
                ALTER TABLE log_sources 
                ADD COLUMN IF NOT EXISTS last_indexed_at TIMESTAMP
            """))
            
            print("Adding indexing_status column...")
            conn.execute(text("""
                ALTER TABLE log_sources 
                ADD COLUMN IF NOT EXISTS indexing_status VARCHAR DEFAULT 'not_started'
            """))
            
            print("Adding indexing_error column...")
            conn.execute(text("""
                ALTER TABLE log_sources 
                ADD COLUMN IF NOT EXISTS indexing_error TEXT
            """))
            
            conn.commit()
            
            print()
            print("=" * 80)
            print("Rollback completed successfully!")
            print("=" * 80)
            
        except Exception as e:
            print(f"❌ Error during rollback: {e}")
            conn.rollback()
            raise

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Remove Git fields from log_sources table')
    parser.add_argument('--rollback', action='store_true', help='Rollback the migration')
    
    args = parser.parse_args()
    
    if args.rollback:
        confirm = input("Are you sure you want to rollback? This will add Git fields back to log_sources. (yes/no): ")
        if confirm.lower() == 'yes':
            rollback_migration()
        else:
            print("Rollback cancelled.")
    else:
        run_migration()
