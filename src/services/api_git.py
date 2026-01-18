"""
Git integration API endpoints.

Provides endpoints for:
- Viewing recent commits
- Getting blame information for exceptions
- Correlating exceptions with code changes
- Viewing file history
"""
import logging
from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.services.git_service import git_service
from src.storage.database import get_db
from src.storage.models import CodeChange, ExceptionBlame, ExceptionCluster

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/git", tags=["git"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class CommitInfo(BaseModel):
    """Commit information"""
    sha: str
    short_sha: str
    author: str
    author_email: Optional[str] = None
    message: str
    summary: str
    committed_date: datetime
    files_changed: int = 0
    insertions: int = 0
    deletions: int = 0


class BlameInfo(BaseModel):
    """Blame information for a line of code"""
    line_number: Optional[int] = None
    line_content: Optional[str] = None
    commit_sha: str
    short_sha: str
    author: str
    author_email: Optional[str] = None
    committed_date: datetime
    message: str


class FileChange(BaseModel):
    """File change details"""
    file_path: str
    change_type: str  # A=added, D=deleted, M=modified, R=renamed
    insertions: int = 0
    deletions: int = 0


class CommitDiff(BaseModel):
    """Commit diff information"""
    commit_sha: str
    files_changed: List[FileChange]
    total_files: int


class ExceptionCorrelation(BaseModel):
    """Correlation between exception and code changes"""
    exception_timestamp: datetime
    lookback_hours: int
    stack_trace_blame: List[BlameInfo]
    recent_changes_count: int
    relevant_changes: List[dict]
    suspect_commits: List[str]


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/commits", response_model=List[CommitInfo])
async def get_recent_commits(
    since_hours: int = Query(default=168, ge=1, le=720, description="Hours to look back (default: 7 days)"),
    max_count: int = Query(default=100, ge=1, le=500, description="Maximum number of commits")
):
    """
    Get recent commits from the repository.
    
    Args:
        since_hours: Look back this many hours (default: 168 = 7 days)
        max_count: Maximum number of commits to return
        
    Returns:
        List of recent commits
    """
    try:
        since = datetime.now() - timedelta(hours=since_hours)
        commits = git_service.get_recent_commits(since=since, max_count=max_count)
        return commits
    except Exception as e:
        logger.error(f"Error getting recent commits: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/commits/{commit_sha}", response_model=CommitInfo)
async def get_commit_details(commit_sha: str):
    """
    Get detailed information about a specific commit.
    
    Args:
        commit_sha: Full or short commit SHA
        
    Returns:
        Commit details
    """
    try:
        commit_info = git_service.get_commit_info(commit_sha)
        if not commit_info:
            raise HTTPException(status_code=404, detail="Commit not found")
        return commit_info
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting commit details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/commits/{commit_sha}/diff", response_model=CommitDiff)
async def get_commit_diff(commit_sha: str):
    """
    Get diff for a specific commit.
    
    Args:
        commit_sha: Full or short commit SHA
        
    Returns:
        Commit diff with file changes
    """
    try:
        diff_info = git_service.get_commit_diff(commit_sha)
        if not diff_info:
            raise HTTPException(status_code=404, detail="Commit not found or diff unavailable")
        return diff_info
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting commit diff: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/blame/{file_path:path}")
async def get_file_blame(
    file_path: str,
    line_number: Optional[int] = Query(default=None, ge=1, description="Specific line number")
):
    """
    Get blame information for a file or specific line.
    
    Args:
        file_path: Relative path to file from repo root
        line_number: Optional specific line number
        
    Returns:
        Blame information
    """
    try:
        blame_info = git_service.get_file_blame(file_path, line_number)
        if not blame_info:
            raise HTTPException(status_code=404, detail="File not found or blame unavailable")
        return blame_info
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting blame: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{file_path:path}", response_model=List[CommitInfo])
async def get_file_history(
    file_path: str,
    max_count: int = Query(default=50, ge=1, le=200, description="Maximum number of commits")
):
    """
    Get commit history for a specific file.
    
    Args:
        file_path: Relative path to file from repo root
        max_count: Maximum number of commits
        
    Returns:
        List of commits that modified this file
    """
    try:
        history = git_service.get_file_history(file_path, max_count)
        return history
    except Exception as e:
        logger.error(f"Error getting file history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/correlate/{cluster_id}", response_model=ExceptionCorrelation)
async def correlate_exception_with_changes(
    cluster_id: str,
    lookback_hours: int = Query(default=24, ge=1, le=168, description="Hours to look back for changes")
):
    """
    Correlate an exception cluster with recent code changes.
    
    This analyzes the stack trace and identifies which recent commits
    may have introduced the bug.
    
    Args:
        cluster_id: Exception cluster ID
        lookback_hours: How far back to look for changes (default: 24 hours)
        
    Returns:
        Correlation analysis with suspect commits
    """
    try:
        # Get cluster from database
        db = next(get_db())
        try:
            cluster = db.query(ExceptionCluster).filter(
                ExceptionCluster.cluster_id == cluster_id
            ).first()
            
            if not cluster:
                raise HTTPException(status_code=404, detail="Cluster not found")
            
            # Convert stack trace from JSON to string
            stack_trace_str = "\n".join([
                f'File "{frame.get("file", "")}", line {frame.get("line", 0)}'
                for frame in cluster.stack_trace or []
            ])
            
            # Perform correlation
            correlation = git_service.correlate_exception_with_changes(
                exception_timestamp=cluster.last_seen,
                stack_trace=stack_trace_str,
                lookback_hours=lookback_hours
            )
            
            # Store blame information in database
            for blame in correlation['stack_trace_blame']:
                if 'commit_sha' in blame:
                    exception_blame = ExceptionBlame(
                        id=f"{cluster_id}_{blame['commit_sha'][:8]}_{blame.get('line_number', 0)}",
                        cluster_id=cluster_id,
                        commit_sha=blame['commit_sha'],
                        file_path=blame.get('original_path', ''),
                        line_number=blame.get('line_number'),
                        blame_author=blame.get('author'),
                        blame_date=blame.get('committed_date'),
                        blame_message=blame.get('message'),
                        confidence_score=0.8 if blame.get('line_number') else 0.5,
                        time_delta_hours=(cluster.last_seen - blame.get('committed_date')).total_seconds() / 3600 if blame.get('committed_date') else None,
                        is_direct_cause=True,
                        analysis=correlation
                    )
                    db.merge(exception_blame)
            
            db.commit()
            
            return correlation
            
        finally:
            db.close()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error correlating exception with changes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/changes", response_model=List[CommitInfo])
async def get_changes_in_timeframe(
    start_hours_ago: int = Query(default=24, ge=1, le=720, description="Start time (hours ago)"),
    end_hours_ago: int = Query(default=0, ge=0, le=720, description="End time (hours ago)")
):
    """
    Get all code changes in a specific timeframe.
    
    Args:
        start_hours_ago: Start of timeframe (hours ago)
        end_hours_ago: End of timeframe (hours ago, 0 = now)
        
    Returns:
        List of changes with file details
    """
    try:
        start_time = datetime.now() - timedelta(hours=start_hours_ago)
        end_time = datetime.now() - timedelta(hours=end_hours_ago) if end_hours_ago > 0 else datetime.now()
        
        changes = git_service.get_changes_in_timeframe(start_time, end_time)
        return changes
    except Exception as e:
        logger.error(f"Error getting changes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_git_stats():
    """
    Get Git repository statistics.
    
    Returns:
        Repository statistics
    """
    try:
        current_commit = git_service.get_current_commit()
        recent_commits = git_service.get_recent_commits(max_count=100)
        
        # Calculate statistics
        total_authors = len(set(c['author'] for c in recent_commits))
        total_files_changed = sum(c.get('files_changed', 0) for c in recent_commits)
        total_insertions = sum(c.get('insertions', 0) for c in recent_commits)
        total_deletions = sum(c.get('deletions', 0) for c in recent_commits)
        
        return {
            'current_commit': current_commit,
            'current_commit_short': current_commit[:8] if current_commit else None,
            'recent_commits_count': len(recent_commits),
            'unique_authors': total_authors,
            'total_files_changed': total_files_changed,
            'total_insertions': total_insertions,
            'total_deletions': total_deletions,
            'repository_path': str(git_service.repo_path),
            'branch': git_service.branch
        }
    except Exception as e:
        logger.error(f"Error getting Git stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
