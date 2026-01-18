#!/usr/bin/env python3
"""
Comprehensive Test Script for Code Indexing Flow

Tests both Local and API modes with various scenarios.
Updated to test new git_provider field and validation.
"""

import sys
import os
from pathlib import Path
import tempfile
import shutil

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.services.code_indexer_factory import CodeIndexerFactory
from src.services.code_indexer import CodeIndexer
from src.services.code_indexer_api import APICodeIndexer

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_test(name):
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}TEST: {name}{Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}")

def print_success(message):
    print(f"{Colors.GREEN}✅ {message}{Colors.END}")

def print_error(message):
    print(f"{Colors.RED}❌ {message}{Colors.END}")

def print_warning(message):
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.END}")

def test_local_mode_valid_path():
    """Test Local Mode with valid path"""
    print_test("Local Mode - Valid Path")
    
    # Create temporary directory with some files
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a simple Python file
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("def hello():\n    print('Hello')\n")
        
        try:
            service_data = {
                'id': 'test-service',
                'use_api_mode': False,
                'repository_url': 'https://github.com/test/repo.git',
                'git_branch': 'main',
                'git_repo_path': tmpdir,
                'access_token': None,
            }
            
            indexer = CodeIndexerFactory.create_from_service(service_data)
            
            assert isinstance(indexer, CodeIndexer), "Should create CodeIndexer"
            assert indexer.repo_path == Path(tmpdir).resolve(), "Path should be normalized"
            assert indexer.service_id == 'test-service', "Service ID should match"
            
            print_success("Created indexer successfully")
            print_success(f"  Indexer type: {type(indexer).__name__}")
            print_success(f"  Repo path: {indexer.repo_path}")
            print_success(f"  Commit SHA: {indexer.commit_sha}")
            
        except Exception as e:
            print_error(f"Failed: {e}")
            return False
    
    return True

def test_local_mode_invalid_path():
    """Test Local Mode with non-existent path"""
    print_test("Local Mode - Invalid Path (Should Fail)")
    
    try:
        service_data = {
            'id': 'test-service',
            'use_api_mode': False,
            'repository_url': 'https://github.com/test/repo.git',
            'git_branch': 'main',
            'git_repo_path': '/nonexistent/path/that/does/not/exist',
            'access_token': None,
        }
        
        indexer = CodeIndexerFactory.create_from_service(service_data)
        print_error("Should have raised ValueError for non-existent path")
        return False
        
    except ValueError as e:
        if "does not exist" in str(e):
            print_success(f"Correctly raised ValueError: {e}")
            return True
        else:
            print_error(f"Wrong error message: {e}")
            return False
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        return False

def test_local_mode_missing_path():
    """Test Local Mode without git_repo_path"""
    print_test("Local Mode - Missing Path (Should Fail)")
    
    try:
        service_data = {
            'id': 'test-service',
            'use_api_mode': False,
            'repository_url': 'https://github.com/test/repo.git',
            'git_branch': 'main',
            'git_repo_path': None,
            'access_token': None,
        }
        
        indexer = CodeIndexerFactory.create_from_service(service_data)
        print_error("Should have raised ValueError for missing path")
        return False
        
    except ValueError as e:
        if "requires 'git_repo_path'" in str(e):
            print_success(f"Correctly raised ValueError: {e}")
            return True
        else:
            print_error(f"Wrong error message: {e}")
            return False
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        return False

def test_api_mode_github():
    """Test API Mode with GitHub URL"""
    print_test("API Mode - GitHub URL")
    
    try:
        service_data = {
            'id': 'test-service',
            'use_api_mode': True,
            'repository_url': 'https://github.com/python/cpython.git',
            'git_provider': 'github',  # NEW: Explicit provider
            'git_branch': 'main',
            'access_token': 'fake_token_for_testing',
        }
        
        indexer = CodeIndexerFactory.create_from_service(service_data)
        
        assert isinstance(indexer, APICodeIndexer), "Should create APICodeIndexer"
        assert indexer.git_provider == 'github', "Should use explicit provider"
        assert indexer.repository_owner == 'python', "Should parse owner"
        assert indexer.repository_name == 'cpython', "Should parse repo name"
        
        print_success("Created API indexer successfully")
        print_success(f"  Indexer type: {type(indexer).__name__}")
        print_success(f"  Provider: {indexer.git_provider}")
        print_success(f"  Owner: {indexer.repository_owner}")
        print_success(f"  Repo: {indexer.repository_name}")
        print_success(f"  Branch: {indexer.branch}")
        
        return True
        
    except Exception as e:
        print_error(f"Failed: {e}")
        return False

def test_api_mode_gitlab():
    """Test API Mode with GitLab URL"""
    print_test("API Mode - GitLab URL")
    
    try:
        service_data = {
            'id': 'test-service',
            'use_api_mode': True,
            'repository_url': 'https://gitlab.com/gitlab-org/gitlab.git',
            'git_provider': 'gitlab',  # NEW: Explicit provider
            'git_branch': 'master',
            'access_token': 'fake_token_for_testing',
        }
        
        indexer = CodeIndexerFactory.create_from_service(service_data)
        
        assert isinstance(indexer, APICodeIndexer), "Should create APICodeIndexer"
        assert indexer.git_provider == 'gitlab', "Should use explicit provider"
        assert indexer.repository_owner == 'gitlab-org', "Should parse owner"
        assert indexer.repository_name == 'gitlab', "Should parse repo name"
        
        print_success("Created API indexer successfully")
        print_success(f"  Indexer type: {type(indexer).__name__}")
        print_success(f"  Provider: {indexer.git_provider}")
        print_success(f"  Owner: {indexer.repository_owner}")
        print_success(f"  Repo: {indexer.repository_name}")
        
        return True
        
    except Exception as e:
        print_error(f"Failed: {e}")
        return False

def test_api_mode_invalid_url():
    """Test API Mode with invalid URL"""
    print_test("API Mode - Invalid URL (Should Fail)")
    
    try:
        service_data = {
            'id': 'test-service',
            'use_api_mode': True,
            'repository_url': 'https://invalid-url.com/not-a-repo',
            'git_branch': 'main',
            'access_token': 'fake_token',
        }
        
        indexer = CodeIndexerFactory.create_from_service(service_data)
        print_error("Should have raised ValueError for invalid URL")
        return False
        
    except ValueError as e:
        if "Unsupported Git provider" in str(e) or "Could not parse" in str(e):
            print_success(f"Correctly raised ValueError: {e}")
            return True
        else:
            print_error(f"Wrong error message: {e}")
            return False
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        return False

def test_api_mode_missing_token():
    """Test API Mode without access token"""
    print_test("API Mode - Missing Token (Should Fail)")
    
    try:
        service_data = {
            'id': 'test-service',
            'use_api_mode': True,
            'repository_url': 'https://github.com/test/repo.git',
            'git_branch': 'main',
            'access_token': None,
        }
        
        indexer = CodeIndexerFactory.create_from_service(service_data)
        print_error("Should have raised ValueError for missing token")
        return False
        
    except ValueError as e:
        if "requires 'access_token'" in str(e):
            print_success(f"Correctly raised ValueError: {e}")
            return True
        else:
            print_error(f"Wrong error message: {e}")
            return False
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        return False

def test_api_mode_url_inference():
    """Test API Mode with URL inference (no explicit provider)"""
    print_test("API Mode - URL Inference (Backward Compatibility)")
    
    try:
        # Test GitHub URL inference
        service_data = {
            'id': 'test-service',
            'use_api_mode': True,
            'repository_url': 'https://github.com/test/repo.git',
            'git_provider': None,  # No explicit provider
            'git_branch': 'main',
            'access_token': 'fake_token',
        }
        
        indexer = CodeIndexerFactory.create_from_service(service_data)
        
        assert isinstance(indexer, APICodeIndexer), "Should create APICodeIndexer"
        assert indexer.git_provider == 'github', "Should infer GitHub from URL"
        
        print_success("URL inference works for GitHub")
        print_success(f"  Inferred provider: {indexer.git_provider}")
        
        # Test GitLab URL inference
        service_data['repository_url'] = 'https://gitlab.com/test/repo.git'
        indexer = CodeIndexerFactory.create_from_service(service_data)
        
        assert indexer.git_provider == 'gitlab', "Should infer GitLab from URL"
        print_success("URL inference works for GitLab")
        print_success(f"  Inferred provider: {indexer.git_provider}")
        
        return True
        
    except Exception as e:
        print_error(f"Failed: {e}")
        return False

def test_api_mode_bitbucket_rejected():
    """Test API Mode rejects Bitbucket (not yet implemented)"""
    print_test("API Mode - Bitbucket Rejected (Not Implemented)")
    
    try:
        service_data = {
            'id': 'test-service',
            'use_api_mode': True,
            'repository_url': 'https://bitbucket.org/test/repo.git',
            'git_provider': 'bitbucket',  # Explicitly set bitbucket
            'git_branch': 'main',
            'access_token': 'fake_token',
        }
        
        indexer = CodeIndexerFactory.create_from_service(service_data)
        print_error("Should have raised ValueError for Bitbucket")
        return False
        
    except ValueError as e:
        if "Unsupported Git provider" in str(e) and "bitbucket" in str(e).lower():
            print_success(f"Correctly rejected Bitbucket: {e}")
            return True
        else:
            print_error(f"Wrong error message: {e}")
            return False
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        return False

def test_api_mode_unsupported_url():
    """Test API Mode with unsupported URL (not GitHub/GitLab)"""
    print_test("API Mode - Unsupported URL (Should Fail)")
    
    try:
        service_data = {
            'id': 'test-service',
            'use_api_mode': True,
            'repository_url': 'https://bitbucket.org/test/repo.git',
            'git_provider': None,  # Will try to infer
            'git_branch': 'main',
            'access_token': 'fake_token',
        }
        
        indexer = CodeIndexerFactory.create_from_service(service_data)
        print_error("Should have raised ValueError for unsupported URL")
        return False
        
    except ValueError as e:
        if "Could not infer Git provider" in str(e) or "Unsupported" in str(e):
            print_success(f"Correctly rejected unsupported URL: {e}")
            return True
        else:
            print_error(f"Wrong error message: {e}")
            return False
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        return False

def test_path_normalization():
    """Test path normalization"""
    print_test("Path Normalization")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a subdirectory
        subdir = Path(tmpdir) / "subdir"
        subdir.mkdir()
        
        # Create a file
        (subdir / "test.py").write_text("print('test')")
        
        try:
            # Use relative path notation
            relative_path = str(subdir) + "/.."
            
            service_data = {
                'id': 'test-service',
                'use_api_mode': False,
                'repository_url': 'https://github.com/test/repo.git',
                'git_branch': 'main',
                'git_repo_path': relative_path,
                'access_token': None,
            }
            
            indexer = CodeIndexerFactory.create_from_service(service_data)
            
            # Should be normalized to tmpdir
            assert indexer.repo_path == Path(tmpdir).resolve(), "Path should be normalized"
            
            print_success("Path normalized correctly")
            print_success(f"  Input: {relative_path}")
            print_success(f"  Normalized: {indexer.repo_path}")
            
            return True
            
        except Exception as e:
            print_error(f"Failed: {e}")
            return False

def run_all_tests():
    """Run all tests"""
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}Code Indexing Flow - Comprehensive Test Suite{Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}")
    
    tests = [
        ("Local Mode - Valid Path", test_local_mode_valid_path),
        ("Local Mode - Invalid Path", test_local_mode_invalid_path),
        ("Local Mode - Missing Path", test_local_mode_missing_path),
        ("API Mode - GitHub", test_api_mode_github),
        ("API Mode - GitLab", test_api_mode_gitlab),
        ("API Mode - URL Inference", test_api_mode_url_inference),
        ("API Mode - Bitbucket Rejected", test_api_mode_bitbucket_rejected),
        ("API Mode - Unsupported URL", test_api_mode_unsupported_url),
        ("API Mode - Invalid URL", test_api_mode_invalid_url),
        ("API Mode - Missing Token", test_api_mode_missing_token),
        ("Path Normalization", test_path_normalization),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print_error(f"Test crashed: {e}")
            results.append((name, False))
    
    # Print summary
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BLUE}Test Summary{Colors.END}")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}\n")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        if result:
            print_success(f"{name}")
        else:
            print_error(f"{name}")
    
    print(f"\n{Colors.BLUE}{'='*80}{Colors.END}")
    if passed == total:
        print_success(f"All tests passed! ({passed}/{total})")
    else:
        print_error(f"Some tests failed: {passed}/{total} passed")
    print(f"{Colors.BLUE}{'='*80}{Colors.END}\n")
    
    return passed == total

if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
