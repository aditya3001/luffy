#!/usr/bin/env python3
"""
Migration Script: Clean Code Indexing Architecture

This script migrates the Service model to the new clean architecture:
- Adds use_api_mode column (Boolean)
- Consolidates token fields into single access_token
- Removes unnecessary fields (git_provider, repository_owner, repository_name, etc.)

Run this script after updating the Service model in models.py
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text, inspect
from src.storage.database import get_db, engine
from src.storage.models import Service

def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table"""
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns

def migrate_database():
    """Migrate database to new clean architecture"""
    
    print("=" * 80)
    print("Code Indexing Clean Architecture Migration")
    print("=" * 80)
    print()
    
    with get_db() as db:
        # Step 1: Add use_api_mode column if it doesn't exist
        print("Step 1: Adding use_api_mode column...")
        if not column_exists('services', 'use_api_mode'):
            try:
                db.execute(text("""
                    ALTER TABLE services 
                    ADD COLUMN use_api_mode BOOLEAN DEFAULT FALSE
                """))
                db.commit()
                print("✅ Added use_api_mode column")
            except Exception as e:
                print(f"⚠️  Could not add use_api_mode column: {e}")
                print("   (Column may already exist)")
        else:
            print("✅ use_api_mode column already exists")
        
        # Step 2: Add access_token column if it doesn't exist
        print("\nStep 2: Adding access_token column...")
        if not column_exists('services', 'access_token'):
            try:
                db.execute(text("""
                    ALTER TABLE services 
                    ADD COLUMN access_token VARCHAR
                """))
                db.commit()
                print("✅ Added access_token column")
            except Exception as e:
                print(f"⚠️  Could not add access_token column: {e}")
                print("   (Column may already exist)")
        else:
            print("✅ access_token column already exists")
        
        # Step 3: Migrate existing data
        print("\nStep 3: Migrating existing service data...")
        services = db.query(Service).all()
        
        if not services:
            print("ℹ️  No services found to migrate")
        else:
            print(f"Found {len(services)} service(s) to migrate")
            
            for service in services:
                print(f"\n  Migrating service: {service.id} ({service.name})")
                
                # Determine use_api_mode based on existing configuration
                # If git_provider exists and is set, assume API mode
                if hasattr(service, 'git_provider') and service.git_provider:
                    service.use_api_mode = True
                    print(f"    ✅ Set use_api_mode=True (detected git_provider={service.git_provider})")
                else:
                    service.use_api_mode = False
                    print(f"    ✅ Set use_api_mode=False (no git_provider detected)")
                
                # Consolidate token fields
                # Priority: access_token_encrypted > git_access_token
                if hasattr(service, 'access_token') and not service.access_token:
                    if hasattr(service, 'access_token_encrypted') and service.access_token_encrypted:
                        service.access_token = service.access_token_encrypted
                        print(f"    ✅ Migrated access_token from access_token_encrypted")
                    elif hasattr(service, 'git_access_token') and service.git_access_token:
                        service.access_token = service.git_access_token
                        print(f"    ✅ Migrated access_token from git_access_token")
                    else:
                        print(f"    ℹ️  No token to migrate")
                else:
                    print(f"    ℹ️  access_token already set")
            
            db.commit()
            print(f"\n✅ Migrated {len(services)} service(s)")
        
        # Step 4: Drop old columns (optional - commented out for safety)
        print("\nStep 4: Removing old columns...")
        print("⚠️  Skipping column removal for safety")
        print("   To remove old columns manually, run:")
        print("   ALTER TABLE services DROP COLUMN git_provider;")
        print("   ALTER TABLE services DROP COLUMN repository_owner;")
        print("   ALTER TABLE services DROP COLUMN repository_name;")
        print("   ALTER TABLE services DROP COLUMN access_token_encrypted;")
        print("   ALTER TABLE services DROP COLUMN git_access_token;")
        print("   ALTER TABLE services DROP COLUMN git_token_expires_at;")
        print("   ALTER TABLE services DROP COLUMN git_token_last_validated;")
        
        # Uncomment below to automatically drop old columns (use with caution!)
        """
        old_columns = [
            'git_provider',
            'repository_owner', 
            'repository_name',
            'access_token_encrypted',
            'git_access_token',
            'git_token_expires_at',
            'git_token_last_validated'
        ]
        
        for column in old_columns:
            if column_exists('services', column):
                try:
                    db.execute(text(f"ALTER TABLE services DROP COLUMN {column}"))
                    db.commit()
                    print(f"✅ Dropped column: {column}")
                except Exception as e:
                    print(f"⚠️  Could not drop column {column}: {e}")
        """
        
        # Step 5: Verify migration
        print("\nStep 5: Verifying migration...")
        services = db.query(Service).all()
        
        success_count = 0
        for service in services:
            has_mode = hasattr(service, 'use_api_mode') and service.use_api_mode is not None
            has_url = service.repository_url is not None
            has_branch = service.git_branch is not None
            
            if service.use_api_mode:
                # API mode: requires repository_url
                if has_url:
                    success_count += 1
                    print(f"  ✅ {service.id}: API mode configured correctly")
                else:
                    print(f"  ⚠️  {service.id}: API mode but missing repository_url")
            else:
                # Local mode: requires git_repo_path
                if service.git_repo_path:
                    success_count += 1
                    print(f"  ✅ {service.id}: Local mode configured correctly")
                else:
                    print(f"  ⚠️  {service.id}: Local mode but missing git_repo_path")
        
        print(f"\n✅ Verification complete: {success_count}/{len(services)} service(s) configured correctly")
    
    print("\n" + "=" * 80)
    print("Migration Complete!")
    print("=" * 80)
    print("\nNext Steps:")
    print("1. Review the migration results above")
    print("2. Test code indexing for each service")
    print("3. If everything works, manually drop old columns (see Step 4 above)")
    print("4. Update frontend to use new fields")
    print()

def show_current_state():
    """Show current state of services"""
    print("\n" + "=" * 80)
    print("Current Service Configuration")
    print("=" * 80)
    
    with get_db() as db:
        services = db.query(Service).all()
        
        if not services:
            print("\nNo services found")
            return
        
        for service in services:
            print(f"\nService: {service.id} ({service.name})")
            print(f"  use_api_mode: {getattr(service, 'use_api_mode', 'N/A')}")
            print(f"  repository_url: {service.repository_url or 'Not set'}")
            print(f"  git_branch: {service.git_branch or 'Not set'}")
            print(f"  git_repo_path: {service.git_repo_path or 'Not set'}")
            print(f"  access_token: {'Set' if getattr(service, 'access_token', None) else 'Not set'}")
            
            # Show old fields if they exist
            if hasattr(service, 'git_provider') and service.git_provider:
                print(f"  [OLD] git_provider: {service.git_provider}")
            if hasattr(service, 'repository_owner') and service.repository_owner:
                print(f"  [OLD] repository_owner: {service.repository_owner}")
            if hasattr(service, 'repository_name') and service.repository_name:
                print(f"  [OLD] repository_name: {service.repository_name}")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate to clean code indexing architecture')
    parser.add_argument('--show', action='store_true', help='Show current service configuration')
    parser.add_argument('--migrate', action='store_true', help='Run migration')
    
    args = parser.parse_args()
    
    if args.show:
        show_current_state()
    elif args.migrate:
        confirm = input("This will modify the database. Continue? (yes/no): ")
        if confirm.lower() == 'yes':
            migrate_database()
        else:
            print("Migration cancelled")
    else:
        print("Usage:")
        print("  python scripts/migrate_clean_code_indexing.py --show     # Show current state")
        print("  python scripts/migrate_clean_code_indexing.py --migrate  # Run migration")
