"""
Git integration service for tracking code changes and correlating with exceptions.

This module provides:
- Git repository analysis (commits, diffs, blame)
- Change tracking and history
- Correlation between code changes and exceptions
- Blame analysis for exception stack traces
"""
import os
import logging
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime, timedelta
import subprocess
import re

try:
    import git
    from git import Repo, GitCommandError
    GIT_PYTHON_AVAILABLE = True
except ImportError:
    GIT_PYTHON_AVAILABLE = False
    logging.warning("GitPython not installed. Install with: pip install GitPython")

from src.config import settings
from src.storage.database import get_db
from src.storage.models import CodeChange, ExceptionBlame

logger = logging.getLogger(__name__)


class GitService:
    """Service for Git repository operations and change tracking"""
    
    def __init__(self, repo_path: str = None, branch: str = None):
        """
        Initialize Git service.
        
        Args:
            repo_path: Path to Git repository
            branch: Branch to track (default: main)
        """
        self.repo_path = Path(repo_path or settings.git_repo_path)
        self.branch = branch or settings.git_branch
        self.repo = None
        
        if GIT_PYTHON_AVAILABLE:
            try:
                self.repo = Repo(self.repo_path)
                logger.info(f"Git repository initialized: {self.repo_path}")
            except Exception as e:
                logger.error(f"Failed to initialize Git repository: {e}")
        else:
            logger.warning("GitPython not available, using subprocess fallback")
    
    def get_current_commit(self) -> Optional[str]:
        """
        Get current commit SHA.
        
        Returns:
            Commit SHA or None
        """
        if self.repo:
            try:
                return self.repo.head.commit.hexsha
            except Exception as e:
                logger.error(f"Error getting current commit: {e}")
        
        # Fallback to subprocess
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            logger.error(f"Error getting commit via subprocess: {e}")
        
        return None
    
    def get_commit_info(self, commit_sha: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a commit.
        
        Args:
            commit_sha: Commit SHA
            
        Returns:
            Commit information dictionary
        """
        if self.repo:
            try:
                commit = self.repo.commit(commit_sha)
                return {
                    'sha': commit.hexsha,
                    'short_sha': commit.hexsha[:8],
                    'author': commit.author.name,
                    'author_email': commit.author.email,
                    'committer': commit.committer.name,
                    'committer_email': commit.committer.email,
                    'message': commit.message.strip(),
                    'summary': commit.summary,
                    'committed_date': datetime.fromtimestamp(commit.committed_date),
                    'authored_date': datetime.fromtimestamp(commit.authored_date),
                    'parents': [p.hexsha for p in commit.parents],
                    'stats': commit.stats.total
                }
            except Exception as e:
                logger.error(f"Error getting commit info: {e}")
        
        return None
    
    def get_recent_commits(self, since: datetime = None, max_count: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent commits.
        
        Args:
            since: Get commits since this date (default: last 7 days)
            max_count: Maximum number of commits
            
        Returns:
            List of commit information
        """
        if since is None:
            since = datetime.now() - timedelta(days=7)
        
        commits = []
        
        if self.repo:
            try:
                for commit in self.repo.iter_commits(self.branch, max_count=max_count):
                    commit_date = datetime.fromtimestamp(commit.committed_date)
                    if commit_date < since:
                        break
                    
                    commits.append({
                        'sha': commit.hexsha,
                        'short_sha': commit.hexsha[:8],
                        'author': commit.author.name,
                        'author_email': commit.author.email,
                        'message': commit.message.strip(),
                        'summary': commit.summary,
                        'committed_date': commit_date,
                        'files_changed': len(commit.stats.files),
                        'insertions': commit.stats.total['insertions'],
                        'deletions': commit.stats.total['deletions']
                    })
            except Exception as e:
                logger.error(f"Error getting recent commits: {e}")
        
        return commits
    
    def get_file_history(self, file_path: str, max_count: int = 50) -> List[Dict[str, Any]]:
        """
        Get commit history for a specific file.
        
        Args:
            file_path: Relative path to file from repo root
            max_count: Maximum number of commits
            
        Returns:
            List of commits that modified this file
        """
        commits = []
        
        if self.repo:
            try:
                for commit in self.repo.iter_commits(self.branch, paths=file_path, max_count=max_count):
                    commits.append({
                        'sha': commit.hexsha,
                        'short_sha': commit.hexsha[:8],
                        'author': commit.author.name,
                        'message': commit.summary,
                        'committed_date': datetime.fromtimestamp(commit.committed_date)
                    })
            except Exception as e:
                logger.error(f"Error getting file history for {file_path}: {e}")
        
        return commits
    
    def get_file_blame(self, file_path: str, line_number: int = None) -> Optional[Dict[str, Any]]:
        """
        Get blame information for a file or specific line.
        
        Args:
            file_path: Relative path to file from repo root
            line_number: Specific line number (1-indexed)
            
        Returns:
            Blame information
        """
        if not self.repo:
            return None
        
        try:
            blame = self.repo.blame(self.branch, file_path)
            
            if line_number is not None:
                # Get blame for specific line
                for commit, lines in blame:
                    for line_num, line_content in enumerate(lines, start=1):
                        if line_num == line_number:
                            return {
                                'line_number': line_number,
                                'line_content': line_content,
                                'commit_sha': commit.hexsha,
                                'short_sha': commit.hexsha[:8],
                                'author': commit.author.name,
                                'author_email': commit.author.email,
                                'committed_date': datetime.fromtimestamp(commit.committed_date),
                                'message': commit.summary
                            }
            else:
                # Get blame for entire file
                blame_info = []
                for commit, lines in blame:
                    blame_info.append({
                        'commit_sha': commit.hexsha,
                        'short_sha': commit.hexsha[:8],
                        'author': commit.author.name,
                        'committed_date': datetime.fromtimestamp(commit.committed_date),
                        'message': commit.summary,
                        'line_count': len(lines)
                    })
                return {'file_path': file_path, 'blame': blame_info}
        
        except Exception as e:
            logger.error(f"Error getting blame for {file_path}: {e}")
        
        return None
    
    def get_commit_diff(self, commit_sha: str) -> Optional[Dict[str, Any]]:
        """
        Get diff for a commit.
        
        Args:
            commit_sha: Commit SHA
            
        Returns:
            Diff information
        """
        if not self.repo:
            return None
        
        try:
            commit = self.repo.commit(commit_sha)
            
            # Get parent commit for diff
            if commit.parents:
                parent = commit.parents[0]
                diff = parent.diff(commit, create_patch=True)
            else:
                # First commit, diff against empty tree
                diff = commit.diff(None, create_patch=True)
            
            files_changed = []
            for diff_item in diff:
                files_changed.append({
                    'file_path': diff_item.b_path or diff_item.a_path,
                    'change_type': diff_item.change_type,  # A=added, D=deleted, M=modified, R=renamed
                    'old_path': diff_item.a_path,
                    'new_path': diff_item.b_path,
                    'diff': diff_item.diff.decode('utf-8', errors='ignore') if diff_item.diff else None,
                    'insertions': diff_item.diff.decode('utf-8', errors='ignore').count('\n+') if diff_item.diff else 0,
                    'deletions': diff_item.diff.decode('utf-8', errors='ignore').count('\n-') if diff_item.diff else 0
                })
            
            return {
                'commit_sha': commit_sha,
                'files_changed': files_changed,
                'total_files': len(files_changed)
            }
        
        except Exception as e:
            logger.error(f"Error getting diff for commit {commit_sha}: {e}")
        
        return None
    
    def analyze_stack_trace_blame(self, stack_trace: str) -> List[Dict[str, Any]]:
        """
        Analyze stack trace and get blame information for each file/line.
        
        Args:
            stack_trace: Exception stack trace
            
        Returns:
            List of blame information for each stack frame
        """
        blame_results = []
        
        # Parse stack trace to extract file paths and line numbers
        # Pattern: File "path/to/file.py", line 123
        pattern = r'File "([^"]+)", line (\d+)'
        matches = re.findall(pattern, stack_trace)
        
        for file_path, line_number in matches:
            # Convert to relative path from repo root
            try:
                abs_path = Path(file_path)
                if abs_path.is_absolute():
                    rel_path = abs_path.relative_to(self.repo_path)
                else:
                    rel_path = Path(file_path)
                
                blame_info = self.get_file_blame(str(rel_path), int(line_number))
                if blame_info:
                    blame_info['original_path'] = file_path
                    blame_results.append(blame_info)
            except Exception as e:
                logger.debug(f"Could not get blame for {file_path}:{line_number}: {e}")
        
        return blame_results
    
    def get_changes_in_timeframe(self, start_time: datetime, end_time: datetime = None) -> List[Dict[str, Any]]:
        """
        Get all code changes in a specific timeframe.
        
        Args:
            start_time: Start of timeframe
            end_time: End of timeframe (default: now)
            
        Returns:
            List of changes with file details
        """
        if end_time is None:
            end_time = datetime.now()
        
        changes = []
        
        if self.repo:
            try:
                for commit in self.repo.iter_commits(self.branch):
                    commit_date = datetime.fromtimestamp(commit.committed_date)
                    
                    if commit_date < start_time:
                        break
                    
                    if commit_date <= end_time:
                        # Get files changed in this commit
                        diff_info = self.get_commit_diff(commit.hexsha)
                        if diff_info:
                            changes.append({
                                'commit_sha': commit.hexsha,
                                'short_sha': commit.hexsha[:8],
                                'author': commit.author.name,
                                'message': commit.summary,
                                'committed_date': commit_date,
                                'files_changed': diff_info['files_changed']
                            })
            except Exception as e:
                logger.error(f"Error getting changes in timeframe: {e}")
        
        return changes
    
    def correlate_exception_with_changes(
        self, 
        exception_timestamp: datetime,
        stack_trace: str,
        lookback_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Correlate an exception with recent code changes.
        
        Args:
            exception_timestamp: When the exception occurred
            stack_trace: Exception stack trace
            lookback_hours: How far back to look for changes
            
        Returns:
            Correlation analysis
        """
        start_time = exception_timestamp - timedelta(hours=lookback_hours)
        
        # Get blame information for stack trace
        blame_results = self.analyze_stack_trace_blame(stack_trace)
        
        # Get recent changes
        recent_changes = self.get_changes_in_timeframe(start_time, exception_timestamp)
        
        # Find changes that affected files in the stack trace
        relevant_changes = []
        stack_files = set()
        
        for blame in blame_results:
            if 'original_path' in blame:
                stack_files.add(blame['original_path'])
        
        for change in recent_changes:
            for file_change in change['files_changed']:
                # Check if this change affected a file in the stack trace
                if any(stack_file.endswith(file_change['file_path']) for stack_file in stack_files):
                    relevant_changes.append({
                        'commit': change,
                        'file_change': file_change,
                        'relevance': 'high'  # File directly in stack trace
                    })
        
        return {
            'exception_timestamp': exception_timestamp,
            'lookback_hours': lookback_hours,
            'stack_trace_blame': blame_results,
            'recent_changes_count': len(recent_changes),
            'relevant_changes': relevant_changes,
            'suspect_commits': [c['commit']['short_sha'] for c in relevant_changes]
        }
    
    def index_repository_with_git_metadata(self) -> Dict[str, Any]:
        """
        Index repository with Git metadata for each code block.
        
        Returns:
            Indexing statistics
        """
        from src.services.code_indexer import CodeIndexer
        
        stats = {
            'files_indexed': 0,
            'commits_tracked': 0,
            'changes_recorded': 0
        }
        
        # Get current commit
        current_commit = self.get_current_commit()
        if not current_commit:
            logger.error("Could not get current commit")
            return stats
        
        # Index code with Git metadata
        indexer = CodeIndexer(repo_path=str(self.repo_path), version=current_commit[:8])
        index_stats = indexer.index_repository()
        stats['files_indexed'] = index_stats.get('total_files', 0)
        
        # Track recent commits in database
        db = next(get_db())
        try:
            recent_commits = self.get_recent_commits(max_count=100)
            stats['commits_tracked'] = len(recent_commits)
            
            for commit_info in recent_commits:
                # Store commit in database
                code_change = CodeChange(
                    commit_sha=commit_info['sha'],
                    author=commit_info['author'],
                    author_email=commit_info['author_email'],
                    message=commit_info['message'],
                    committed_date=commit_info['committed_date'],
                    files_changed=commit_info['files_changed'],
                    insertions=commit_info['insertions'],
                    deletions=commit_info['deletions']
                )
                db.merge(code_change)
                stats['changes_recorded'] += 1
            
            db.commit()
        except Exception as e:
            logger.error(f"Error tracking commits: {e}")
            db.rollback()
        finally:
            db.close()
        
        return stats


# Global instance
git_service = GitService()
