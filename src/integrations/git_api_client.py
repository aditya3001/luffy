"""
Git API clients for GitHub and GitLab
Fetches code via API without local repository clones
"""
import requests
import base64
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Raised when Git API authentication fails"""
    pass


class GitHubClient:
    """GitHub API client for code fetching"""
    
    def __init__(self, token: str, api_url: str = "https://api.github.com"):
        self.token = token
        self.api_url = api_url.rstrip('/')
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }
    
    def test_authentication(self) -> Dict:
        """Test if token is valid"""
        try:
            response = requests.get(
                f"{self.api_url}/user",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 401:
                raise AuthenticationError("Invalid or expired token")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"GitHub authentication test failed: {e}")
            raise AuthenticationError(str(e))
    
    def get_latest_commit(self, owner: str, repo: str, branch: str) -> str:
        """Get latest commit SHA for a branch"""
        try:
            response = requests.get(
                f"{self.api_url}/repos/{owner}/{repo}/commits/{branch}",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 401:
                raise AuthenticationError("Invalid or expired token")
            
            response.raise_for_status()
            return response.json()['sha']
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get latest commit: {e}")
            raise
    
    def get_repository_tree(self, owner: str, repo: str, branch: str) -> Dict:
        """Get repository file tree"""

        try:
            response = requests.get(
                f"{self.api_url}/repos/{owner}/{repo}/git/trees/{branch}",
                headers=self.headers,
                params={"recursive": "1"},
                timeout=30
            )


            if response.status_code == 401:
                raise AuthenticationError("Invalid or expired token")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get repository tree: {e}")
            raise
    
    def get_file_content(self, owner: str, repo: str, path: str, branch: str) -> Dict:
        """Get file content"""
        try:
            response = requests.get(
                f"{self.api_url}/repos/{owner}/{repo}/contents/{path}",
                headers=self.headers,
                params={"ref": branch},
                timeout=10
            )
            
            if response.status_code == 401:
                raise AuthenticationError("Invalid or expired token")
            
            response.raise_for_status()
            data = response.json()
            
            # Decode base64 content
            if 'content' in data:
                content = base64.b64decode(data['content']).decode('utf-8')
                data['decoded_content'] = content
            
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get file content for {path}: {e}")
            raise
    
    def test_connection(self, owner: str, repo: str) -> Dict:
        """Test repository access"""
        try:
            response = requests.get(
                f"{self.api_url}/repos/{owner}/{repo}",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 401:
                raise AuthenticationError("Invalid or expired token")
            
            if response.status_code == 404:
                raise ValueError(f"Repository {owner}/{repo} not found or no access")
            
            response.raise_for_status()
            repo_data = response.json()
            
            return {
                "status": "success",
                "repository": repo_data['full_name'],
                "default_branch": repo_data['default_branch'],
                "private": repo_data['private'],
                "access": "read-only"
            }
            
        except AuthenticationError:
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Connection test failed: {e}")
            raise
    
    def compare_commits(self, owner: str, repo: str, base: str, head: str) -> Dict:
        """
        Compare two commits and get changed files
        
        Args:
            owner: Repository owner
            repo: Repository name
            base: Base commit SHA
            head: Head commit SHA
            
        Returns:
            Dictionary with comparison data including 'files' array
        """
        try:
            response = requests.get(
                f"{self.api_url}/repos/{owner}/{repo}/compare/{base}...{head}",
                headers=self.headers,
                timeout=30
            )
            
            if response.status_code == 401:
                raise AuthenticationError("Invalid or expired token")
            
            if response.status_code == 404:
                raise ValueError(f"Commits not found or no access")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to compare commits: {e}")
            raise


class GitLabClient:
    """GitLab API client for code fetching"""
    
    def __init__(self, token: str, api_url: str = "https://gitlab.com/api/v4"):
        self.token = token
        self.api_url = api_url.rstrip('/')
        self.headers = {
            "PRIVATE-TOKEN": token
        }
    
    def test_authentication(self) -> Dict:
        """Test if token is valid"""
        try:
            response = requests.get(
                f"{self.api_url}/user",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 401:
                raise AuthenticationError("Invalid or expired token")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"GitLab authentication test failed: {e}")
            raise AuthenticationError(str(e))
    
    def get_project_id(self, owner: str, repo: str) -> str:
        """Get GitLab project ID from owner/repo"""
        project_path = f"{owner}/{repo}"
        try:
            response = requests.get(
                f"{self.api_url}/projects/{requests.utils.quote(project_path, safe='')}",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 401:
                raise AuthenticationError("Invalid or expired token")
            
            response.raise_for_status()
            return str(response.json()['id'])
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get project ID: {e}")
            raise
    
    def get_latest_commit(self, project_id: str, branch: str) -> str:
        """Get latest commit SHA for a branch"""
        try:
            response = requests.get(
                f"{self.api_url}/projects/{project_id}/repository/commits/{branch}",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 401:
                raise AuthenticationError("Invalid or expired token")
            
            response.raise_for_status()
            return response.json()['id']
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get latest commit: {e}")
            raise
    
    def get_repository_tree(self, project_id: str, branch: str) -> Dict:
        """Get repository file tree"""
        try:
            response = requests.get(
                f"{self.api_url}/projects/{project_id}/repository/tree",
                headers=self.headers,
                params={"ref": branch, "recursive": "true", "per_page": "100"},
                timeout=30
            )
            
            if response.status_code == 401:
                raise AuthenticationError("Invalid or expired token")
            
            response.raise_for_status()
            return {"tree": response.json()}
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get repository tree: {e}")
            raise
    
    def get_file_content(self, project_id: str, path: str, branch: str) -> Dict:
        """Get file content"""
        try:
            response = requests.get(
                f"{self.api_url}/projects/{project_id}/repository/files/{requests.utils.quote(path, safe='')}",
                headers=self.headers,
                params={"ref": branch},
                timeout=10
            )
            
            if response.status_code == 401:
                raise AuthenticationError("Invalid or expired token")
            
            response.raise_for_status()
            data = response.json()
            
            # Decode base64 content
            if 'content' in data:
                content = base64.b64decode(data['content']).decode('utf-8')
                data['decoded_content'] = content
            
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get file content for {path}: {e}")
            raise
    
    def test_connection(self, project_path: str) -> Dict:
        """Test project access"""
        try:
            response = requests.get(
                f"{self.api_url}/projects/{requests.utils.quote(project_path, safe='')}",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 401:
                raise AuthenticationError("Invalid or expired token")
            
            if response.status_code == 404:
                raise ValueError(f"Project {project_path} not found or no access")
            
            response.raise_for_status()
            project_data = response.json()
            
            return {
                "status": "success",
                "repository": project_data['path_with_namespace'],
                "default_branch": project_data['default_branch'],
                "private": project_data['visibility'] == 'private',
                "access": "read-only"
            }
            
        except AuthenticationError:
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Connection test failed: {e}")
            raise
    
    def compare_commits(self, project_id: str, base: str, head: str) -> Dict:
        """
        Compare two commits and get changed files
        
        Args:
            project_id: GitLab project ID
            base: Base commit SHA
            head: Head commit SHA
            
        Returns:
            Dictionary with comparison data including 'diffs' array
        """
        try:
            response = requests.get(
                f"{self.api_url}/projects/{project_id}/repository/compare",
                headers=self.headers,
                params={"from": base, "to": head},
                timeout=30
            )
            
            if response.status_code == 401:
                raise AuthenticationError("Invalid or expired token")
            
            if response.status_code == 404:
                raise ValueError(f"Commits not found or no access")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to compare commits: {e}")
            raise


class GitClientFactory:
    """Factory to create appropriate Git client"""
    
    @staticmethod
    def create(provider: str, token: str):
        """Create Git client based on provider"""
        if provider.lower() == 'github':
            return GitHubClient(token)
        elif provider.lower() == 'gitlab':
            return GitLabClient(token)
        else:
            raise ValueError(f"Unsupported Git provider: {provider}")
