#!/usr/bin/env python3
"""
Quick test to verify the API services endpoint fix
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.storage.models import Service
from src.services.api_services import ServiceResponse
from datetime import datetime

def test_service_response_mapping():
    """Test that ServiceResponse can be created from Service model"""
    
    # Create a mock service object with the actual model attributes
    class MockService:
        id = "test-service"
        name = "Test Service"
        description = "Test Description"
        version = "1.0.0"
        repository_url = "https://github.com/test/repo"
        git_branch = "main"
        git_repo_path = "/path/to/repo"
        access_token = "test_token_123"  # This is the correct attribute name
        is_active = True
        created_at = datetime.utcnow()
        updated_at = datetime.utcnow()
    
    service = MockService()
    
    # Try to create ServiceResponse - this should work now
    try:
        response = ServiceResponse(
            id=service.id,
            name=service.name,
            description=service.description,
            version=service.version,
            repository_url=service.repository_url,
            git_branch=service.git_branch,
            git_repo_path=service.git_repo_path,
            access_token=service.access_token,  # Fixed: was git_access_token
            is_active=service.is_active,
            log_sources_count=0,
            active_exceptions_count=0,
            created_at=service.created_at,
            updated_at=service.updated_at
        )
        print("✅ SUCCESS: ServiceResponse created successfully")
        print(f"   Service ID: {response.id}")
        print(f"   Service Name: {response.name}")
        print(f"   Access Token: {response.access_token[:10]}..." if response.access_token else "   Access Token: None")
        return True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False

if __name__ == "__main__":
    print("Testing API Services Fix...")
    print("-" * 50)
    success = test_service_response_mapping()
    print("-" * 50)
    sys.exit(0 if success else 1)
