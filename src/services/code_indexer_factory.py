"""
Code Indexer Factory
Creates appropriate indexer based on configuration mode
"""
import logging
from typing import Dict, Any, Optional
from pathlib import Path

from src.config import settings
from src.services.code_indexer import CodeIndexer
from src.services.code_indexer_api import APICodeIndexer

logger = logging.getLogger(__name__)


class CodeIndexerFactory:
    """
    Factory to create appropriate code indexer based on mode
    
    Modes:
    - 'local': Clone repository to local filesystem (existing method)
    - 'api': Fetch files via GitHub/GitLab API (in-memory, no local storage)
    """
    
    @staticmethod
    def create_from_service(service_data: Dict[str, Any]):
        """
        Create code indexer from service configuration
        
        Args:
            service_data: Service database model or dict with configuration
                - use_api_mode: Boolean (True=API mode, False=Local mode)
                - repository_url: Git repository URL
                - git_branch: Branch name
                - git_repo_path: Local path (local mode only)
                - access_token: Access token for private repos
            
        Returns:
            CodeIndexer (local mode) or APICodeIndexer (API mode)
        """
        use_api_mode = service_data.get('use_api_mode', False)
        service_id = service_data.get('id')
        
        logger.info(f"Creating code indexer for service {service_id}: mode={'API' if use_api_mode else 'LOCAL'}")
        
        if use_api_mode:
            return CodeIndexerFactory._create_api_indexer(service_data)
        else:
            return CodeIndexerFactory._create_local_indexer(service_data)
    
    @staticmethod
    def _create_local_indexer(service_data: Dict[str, Any]) -> CodeIndexer:
        """
        Create local filesystem-based code indexer
        
        Reads files directly from git_repo_path (no Git operations).
        User is responsible for managing the repository (git clone/pull).
        
        Args:
            service_data: Service configuration with git_repo_path
            
        Returns:
            CodeIndexer instance
        """
        repo_path = service_data.get('git_repo_path')
        service_id = service_data.get('id')
        version = service_data.get('git_branch') or 'main'
        
        if not repo_path:
            raise ValueError(f"Local mode requires 'git_repo_path' for service {service_id}")
        
        logger.info(f"Creating LOCAL code indexer: repo_path={repo_path}, service_id={service_id}")
        
        return CodeIndexer(
            repo_path=repo_path,
            version=version,
            service_id=service_id
        )
    
    @staticmethod
    def _create_api_indexer(service_data: Dict[str, Any]) -> APICodeIndexer:
        """
        Create API-based code indexer
        
        Fetches files via Git API (GitHub/GitLab) using repository_url.
        Parses URL to extract owner and repo name.
        
        Args:
            service_data: Service configuration with repository_url and access_token
            
        Returns:
            APICodeIndexer instance
            
        Raises:
            ValueError: If required configuration is missing or URL cannot be parsed
        """
        import re
        
        service_id = service_data.get('id')
        repository_url = service_data.get('repository_url')
        git_branch = service_data.get('git_branch') or 'main'
        access_token = service_data.get('access_token')
        git_provider = service_data.get('git_provider')  # NEW: Use explicit provider
        
        # Validate required fields
        if not repository_url:
            raise ValueError(f"API mode requires 'repository_url' for service {service_id}")
        if not access_token:
            raise ValueError(f"API mode requires 'access_token' for service {service_id}")
        
        # Parse repository_url to extract owner and repo name
        # Supports: https://github.com/owner/repo.git, git@github.com:owner/repo.git
        repository_owner = None
        repository_name = None
        
        # Use explicit git_provider if provided, otherwise infer from URL (backward compatibility)
        if not git_provider:
            logger.warning(f"git_provider not set for service {service_id}, inferring from URL")
            if 'github.com' in repository_url:
                git_provider = 'github'
            elif 'gitlab.com' in repository_url:
                git_provider = 'gitlab'
            else:
                raise ValueError(
                    f"Could not infer Git provider from URL: {repository_url}. "
                    f"Please set git_provider explicitly. Supported providers: github, gitlab"
                )
        
        # Validate provider (Bitbucket not yet implemented in Git API client)
        if git_provider not in ['github', 'gitlab']:
            raise ValueError(
                f"Unsupported Git provider: {git_provider}. "
                f"Supported providers: github, gitlab. "
                f"Note: Bitbucket support is planned for future release."
            )
        
        # Extract owner and repo name
        match = re.search(r'[:/]([^/]+)/([^/\.]+)(?:\.git)?$', repository_url)
        if match:
            repository_owner = match.group(1)
            repository_name = match.group(2)
        else:
            raise ValueError(f"Could not parse repository URL: {repository_url}")
        
        logger.info(
            f"Creating API code indexer: provider={git_provider}, "
            f"repo={repository_owner}/{repository_name}, branch={git_branch}, "
            f"parsed from URL: {repository_url}"
        )
        
        return APICodeIndexer(
            git_provider=git_provider,
            repository_owner=repository_owner,
            repository_name=repository_name,
            branch=git_branch,
            access_token_encrypted=access_token,  # Pass access_token directly
            service_id=service_id
        )
    
    @staticmethod
    def create_from_log_source(log_source_data: Dict[str, Any]):
        """
        Create code indexer from log source configuration
        
        NOTE: LogSource doesn't have use_api_mode field.
        This method uses the service's configuration instead.
        For log source-based indexing, get the service first and use create_from_service().
        
        Args:
            log_source_data: LogSource database model or dict with configuration
            
        Returns:
            CodeIndexer instance (always local mode for log sources)
            
        Raises:
            ValueError: If required configuration is missing
        """
        service_id = log_source_data.get('service_id')
        git_repo_path = log_source_data.get('git_repo_path')
        
        logger.info(f"Creating LOCAL code indexer for log source {log_source_data.get('id')}")
        
        # Log sources always use local mode
        # For API mode, use create_from_service() with the service configuration
        if not git_repo_path:
            raise ValueError(
                f"Log source indexing requires 'git_repo_path'. "
                f"Please configure for log source {log_source_data.get('id')}"
            )
        
        # Normalize path
        repo_path = Path(git_repo_path).resolve()
        
        return CodeIndexer(
            repo_path=str(repo_path),
            version=log_source_data.get('git_branch') or 'main',
            service_id=service_id
        )


def get_code_indexer(
    service_data: Optional[Dict[str, Any]] = None,
    log_source_data: Optional[Dict[str, Any]] = None,
    mode: Optional[str] = None
):
    """
    Convenience function to get appropriate code indexer
    
    Args:
        service_data: Service configuration (optional)
        log_source_data: Log source configuration (optional)
        mode: Override indexing mode (optional)
        
    Returns:
        CodeIndexer or APICodeIndexer instance
        
    Raises:
        ValueError: If neither service_data nor log_source_data is provided
    """
    if log_source_data:
        return CodeIndexerFactory.create_from_log_source(log_source_data, mode)
    elif service_data:
        return CodeIndexerFactory.create_from_service(service_data, mode)
    else:
        raise ValueError("Either service_data or log_source_data must be provided")
