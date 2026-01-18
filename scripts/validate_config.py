#!/usr/bin/env python3
"""
Configuration Validation Script
Validates all service connections and environment variables before deployment.
"""
import sys
import os
from typing import List, Tuple

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.config.settings import Settings
from pydantic import ValidationError


def validate_environment() -> Tuple[bool, List[str]]:
    """
    Validate environment configuration.
    
    Returns:
        Tuple of (success: bool, errors: List[str])
    """
    errors = []
    
    try:
        settings = Settings()
        print("✓ Configuration loaded successfully")
        
        # Validate critical services
        print("\n=== Validating Service Connections ===")
        
        # Database
        if not settings.database_url or settings.database_url == 'postgresql://user:password@localhost:5432/observability':
            errors.append("❌ DATABASE_URL not configured or using default value")
        else:
            print(f"✓ Database URL configured: {settings.database_url.split('@')[1] if '@' in settings.database_url else 'configured'}")
        
        # Redis
        if not settings.redis_url or settings.redis_url == 'redis://localhost:6379/0':
            errors.append("❌ REDIS_URL not configured or using default value")
        else:
            print(f"✓ Redis URL configured: {settings.redis_url}")
        
        # Qdrant
        if not settings.qdrant_host:
            errors.append("❌ QDRANT_HOST not configured")
        else:
            print(f"✓ Qdrant configured: {settings.qdrant_host}:{settings.qdrant_port}")
        
        # LLM Provider
        print(f"\n=== LLM Configuration ===")
        print(f"Provider: {settings.llm_provider}")
        
        if settings.llm_provider == 'openai':
            if not settings.openai_api_key or settings.openai_api_key == '':
                errors.append("❌ OPENAI_API_KEY not configured")
            else:
                print(f"✓ OpenAI API key configured (length: {len(settings.openai_api_key)})")
        elif settings.llm_provider == 'anthropic':
            if not settings.anthropic_api_key or settings.anthropic_api_key == '':
                errors.append("❌ ANTHROPIC_API_KEY not configured")
            else:
                print(f"✓ Anthropic API key configured")
        
        # Log Source
        print(f"\n=== Log Source Configuration ===")
        print(f"Log Source: {settings.log_source}")
        
        if settings.log_source in ['opensearch', 'elasticsearch']:
            if not settings.elasticsearch_url:
                errors.append(f"❌ ELASTICSEARCH_URL not configured for {settings.log_source}")
            else:
                print(f"✓ Elasticsearch/OpenSearch URL: {settings.elasticsearch_url}")
                print(f"  Index pattern: {settings.elasticsearch_index}")
        
        # Storage Backend
        print(f"\n=== Storage Configuration ===")
        print(f"Storage Backend: {settings.storage_backend}")
        
        if settings.storage_backend == 's3':
            if not settings.s3_bucket:
                errors.append("❌ S3_BUCKET not configured")
            else:
                print(f"✓ S3 Bucket: {settings.s3_bucket}")
                print(f"  Region: {settings.s3_region}")
        elif settings.storage_backend == 'gcs':
            if not settings.gcs_bucket:
                errors.append("❌ GCS_BUCKET not configured")
            else:
                print(f"✓ GCS Bucket: {settings.gcs_bucket}")
        else:
            print(f"✓ Local storage path: {settings.local_storage_path}")
        
        # Feature Flags
        print(f"\n=== Feature Flags ===")
        print(f"Code Indexing: {'✓' if settings.enable_code_indexing else '✗'}")
        print(f"LLM Analysis: {'✓' if settings.enable_llm_analysis else '✗'}")
        print(f"Real-time Streaming: {'✓' if settings.enable_real_time_streaming else '✗'}")
        print(f"Feedback Loop: {'✓' if settings.enable_feedback_loop else '✗'}")
        print(f"GChat Notifications: {'✓' if settings.enable_gchat_notifications else '✗'}")
        
        if settings.enable_gchat_notifications:
            if not settings.gchat_webhook_url or 'SPACE_ID' in settings.gchat_webhook_url:
                errors.append("❌ GCHAT_WEBHOOK_URL not properly configured")
        
        # API Configuration
        print(f"\n=== API Configuration ===")
        print(f"Host: {settings.api_host}")
        print(f"Port: {settings.api_port}")
        print(f"Workers: {settings.api_workers}")
        print(f"Log Level: {settings.log_level}")
        
        # Processing Configuration
        print(f"\n=== Processing Configuration ===")
        print(f"Batch Size: {settings.batch_size}")
        print(f"Max Workers: {settings.max_workers}")
        print(f"Log Fetch Interval: {settings.log_fetch_interval}")
        print(f"Processing Log Levels: {settings.processing_log_levels}")
        
        # Summary
        print("\n" + "=" * 50)
        if errors:
            print("❌ Configuration validation FAILED")
            print(f"\nFound {len(errors)} error(s):")
            for error in errors:
                print(f"  {error}")
            return False, errors
        else:
            print("✓ All configuration checks passed!")
            return True, []
            
    except ValidationError as e:
        print("❌ Configuration validation FAILED")
        print("\nValidation Errors:")
        for error in e.errors():
            field = " -> ".join(str(x) for x in error['loc'])
            print(f"  ❌ {field}: {error['msg']}")
            errors.append(f"{field}: {error['msg']}")
        return False, errors
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        errors.append(f"Unexpected error: {str(e)}")
        return False, errors


def check_docker_environment():
    """Check if running in Docker environment."""
    print("\n=== Environment Check ===")
    is_docker = os.path.exists('/.dockerenv') or os.environ.get('RUNNING_IN_DOCKER') == 'true'
    
    if is_docker:
        print("✓ Running in Docker container")
    else:
        print("ℹ Running outside Docker")
    
    # Check for .env file
    env_file = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(env_file):
        print(f"✓ .env file found at: {env_file}")
    else:
        print("⚠ .env file not found - using environment variables only")
    
    return is_docker


def main():
    """Main validation function."""
    print("=" * 50)
    print("Luffy Configuration Validator")
    print("=" * 50)
    
    check_docker_environment()
    
    success, errors = validate_environment()
    
    if success:
        print("\n✓ Configuration is valid and ready for deployment!")
        sys.exit(0)
    else:
        print(f"\n❌ Configuration validation failed with {len(errors)} error(s)")
        print("\nPlease fix the errors above before deploying.")
        sys.exit(1)


if __name__ == "__main__":
    main()
