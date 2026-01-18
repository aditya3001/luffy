"""
Enhanced LLM-based Root Cause Analysis with Git integration.
Incorporates Git blame and change history into RCA generation.
"""
import json
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
from src.config import settings
from src.storage.vector_db import vector_db
from src.storage.database import get_db
from src.storage.models import RCAResult, ExceptionCluster
from src.services.git_service import git_service

logger = logging.getLogger(__name__)

# Initialize LLM client based on provider
if settings.llm_provider == 'openai':
    try:
        from openai import OpenAI
        llm_client = OpenAI(api_key=settings.openai_api_key)
    except ImportError:
        logger.warning("OpenAI library not installed")
        llm_client = None
elif settings.llm_provider == 'anthropic':
    try:
        from anthropic import Anthropic
        llm_client = Anthropic(api_key=settings.anthropic_api_key)
    except ImportError:
        logger.warning("Anthropic library not installed")
        llm_client = None
else:
    llm_client = None


class EnhancedLLMAnalyzer:
    """Generate Root Cause Analysis using LLM with Git context"""
    
    def __init__(self):
        self.client = llm_client
        self.model = settings.llm_model
        self.temperature = settings.llm_temperature
        self.max_tokens = settings.llm_max_tokens
    
    def analyze_cluster_with_git(self, cluster_id: str) -> Optional[str]:
        """
        Perform RCA on an exception cluster with Git blame information.
        
        Args:
            cluster_id: Cluster ID to analyze
        
        Returns:
            RCA result ID or None if analysis fails
        """
        if not self.client:
            logger.error("LLM client not initialized")
            return None
        
        # Get cluster details
        with get_db() as db:
            cluster = db.query(ExceptionCluster).filter_by(cluster_id=cluster_id).first()
            if not cluster:
                logger.error(f"Cluster not found: {cluster_id}")
                return None
            
            cluster_data = {
                'cluster_id': cluster.cluster_id,
                'exception_type': cluster.exception_type,
                'exception_message': cluster.exception_message,
                'stack_trace': cluster.stack_trace,
                'first_seen': cluster.first_seen,
                'last_seen': cluster.last_seen
            }
        
        # Retrieve code context
        code_context = self._retrieve_code_context(cluster_data)
        
        # Get Git blame and change correlation
        git_context = self._retrieve_git_context(cluster_data)
        
        # Build enhanced prompt with Git information
        prompt = self._build_enhanced_prompt(cluster_data, code_context, git_context)
        
        # Call LLM
        try:
            response = self._call_llm(prompt)
            rca_data = self._parse_llm_response(response)
            
            if not rca_data:
                logger.error("Failed to parse LLM response")
                return None
            
            # Enrich RCA data with Git information
            rca_data['git_context'] = git_context
            
            # Store RCA result
            rca_id = self._store_rca_result(cluster_id, rca_data, response)
            
            # Update cluster
            with get_db() as db:
                cluster = db.query(ExceptionCluster).filter_by(cluster_id=cluster_id).first()
                if cluster:
                    cluster.has_rca = True
                    cluster.rca_generated_at = datetime.utcnow()
                    db.commit()
            
            logger.info(f"Generated enhanced RCA for cluster {cluster_id}: {rca_id}")
            return rca_id
        
        except Exception as e:
            logger.error(f"Error generating RCA: {e}", exc_info=True)
            return None
    
    def _retrieve_code_context(self, cluster_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Retrieve relevant code blocks using vector search"""
        code_context = []
        stack_frames = cluster_data.get('stack_trace') or []
        
        for frame in stack_frames[:5]:
            file_path = frame.get('file', '')
            symbol = frame.get('symbol', '')
            query = f"{symbol} {file_path}"
            
            try:
                results = vector_db.search_code_blocks(query_text=query, top_k=5)
                code_context.extend(results)
            except Exception as e:
                logger.error(f"Error searching code blocks: {e}")
        
        # Deduplicate
        seen_ids = set()
        unique_context = []
        for item in code_context:
            if item['id'] not in seen_ids:
                seen_ids.add(item['id'])
                unique_context.append(item)
        
        return unique_context[:10]
    
    def _retrieve_git_context(self, cluster_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retrieve Git blame and change correlation for the exception.
        
        Returns:
            Dictionary with Git context including blame, recent changes, and suspects
        """
        git_context = {
            'blame_info': [],
            'recent_changes': [],
            'suspect_commits': [],
            'correlation_available': False
        }
        
        try:
            # Convert stack trace to string for blame analysis
            stack_frames = cluster_data.get('stack_trace') or []
            stack_trace_str = "\n".join([
                f'File "{frame.get("file", "")}", line {frame.get("line", 0)}'
                for frame in stack_frames
            ])
            
            if not stack_trace_str:
                return git_context
            
            # Get blame information for stack trace
            blame_results = git_service.analyze_stack_trace_blame(stack_trace_str)
            git_context['blame_info'] = blame_results
            
            # Correlate with recent changes
            exception_time = cluster_data.get('last_seen') or datetime.utcnow()
            correlation = git_service.correlate_exception_with_changes(
                exception_timestamp=exception_time,
                stack_trace=stack_trace_str,
                lookback_hours=48  # Look back 48 hours
            )
            
            git_context['recent_changes'] = correlation.get('relevant_changes', [])
            git_context['suspect_commits'] = correlation.get('suspect_commits', [])
            git_context['correlation_available'] = True
            
        except Exception as e:
            logger.error(f"Error retrieving Git context: {e}")
        
        return git_context
    
    def _build_enhanced_prompt(
        self, 
        cluster_data: Dict[str, Any], 
        code_context: List[Dict[str, Any]],
        git_context: Dict[str, Any]
    ) -> str:
        """Build enhanced prompt with Git information"""
        
        # Format stack trace
        stack_trace = cluster_data.get('stack_trace', [])
        stack_trace_str = "\n".join([
            f"  File \"{frame.get('file', 'unknown')}\", line {frame.get('line', 0)}, in {frame.get('symbol', 'unknown')}"
            for frame in stack_trace
        ])
        
        # Format code context
        code_context_str = ""
        for i, ctx in enumerate(code_context[:5], 1):
            code_context_str += f"\n--- Code Block {i} ---\n"
            code_context_str += f"File: {ctx.get('file_path', 'unknown')}\n"
            code_context_str += f"Symbol: {ctx.get('symbol_name', 'unknown')}\n"
            code_context_str += f"Lines: {ctx.get('line_start', 0)}-{ctx.get('line_end', 0)}\n"
            code_context_str += f"Code:\n{ctx.get('code_snippet', '')}\n"
        
        # Format Git context
        git_context_str = ""
        if git_context.get('correlation_available'):
            git_context_str += "\n=== GIT BLAME INFORMATION ===\n"
            
            for blame in git_context.get('blame_info', [])[:5]:
                git_context_str += f"\nFile: {blame.get('original_path', 'unknown')}\n"
                git_context_str += f"Line: {blame.get('line_number', 'N/A')}\n"
                git_context_str += f"Last Modified By: {blame.get('author', 'unknown')}\n"
                git_context_str += f"Commit: {blame.get('short_sha', 'unknown')}\n"
                git_context_str += f"Date: {blame.get('committed_date', 'unknown')}\n"
                git_context_str += f"Message: {blame.get('message', 'N/A')}\n"
            
            if git_context.get('suspect_commits'):
                git_context_str += "\n=== SUSPECT COMMITS (Recent changes to affected files) ===\n"
                for commit_sha in git_context['suspect_commits'][:3]:
                    git_context_str += f"- {commit_sha}\n"
                
                git_context_str += "\n=== RECENT RELEVANT CHANGES ===\n"
                for change in git_context.get('recent_changes', [])[:3]:
                    commit = change.get('commit', {})
                    file_change = change.get('file_change', {})
                    git_context_str += f"\nCommit: {commit.get('short_sha', 'unknown')}\n"
                    git_context_str += f"Author: {commit.get('author', 'unknown')}\n"
                    git_context_str += f"Date: {commit.get('committed_date', 'unknown')}\n"
                    git_context_str += f"Message: {commit.get('message', 'N/A')}\n"
                    git_context_str += f"File Changed: {file_change.get('file_path', 'unknown')}\n"
                    git_context_str += f"Change Type: {file_change.get('change_type', 'unknown')}\n"
        
        # Build the complete prompt
        prompt = f"""You are an expert software engineer performing Root Cause Analysis (RCA) on a production exception.

=== EXCEPTION DETAILS ===
Type: {cluster_data.get('exception_type', 'Unknown')}
Message: {cluster_data.get('exception_message', 'No message')}
First Seen: {cluster_data.get('first_seen', 'Unknown')}
Last Seen: {cluster_data.get('last_seen', 'Unknown')}

=== STACK TRACE ===
{stack_trace_str}

=== RELEVANT CODE CONTEXT ===
{code_context_str}

{git_context_str}

=== YOUR TASK ===
Analyze this exception and provide a comprehensive Root Cause Analysis. Pay special attention to:
1. The Git blame information showing who last modified the problematic lines
2. Recent commits that changed files in the stack trace
3. The timing between code changes and when the exception started appearing

Provide your analysis in the following JSON format:
{{
  "root_cause": {{
    "file": "path/to/file.py",
    "symbol": "function_or_class_name",
    "line_start": 123,
    "line_end": 130,
    "explanation": "Detailed explanation of what's causing the issue"
  }},
  "git_analysis": {{
    "likely_introduced_by": "commit_sha or 'unknown'",
    "author": "author name if known",
    "change_description": "What change likely introduced this bug"
  }},
  "involved_parameters": [
    {{"name": "param1", "value": "value1", "issue": "why this is problematic"}}
  ],
  "fix_suggestions": [
    {{"priority": "high", "description": "Specific fix recommendation", "code_example": "optional code snippet"}}
  ],
  "impact_analysis": {{
    "severity": "critical|high|medium|low",
    "affected_users": "description of impact",
    "business_impact": "business consequences"
  }},
  "prevention": [
    "How to prevent this in the future"
  ]
}}

Be specific, actionable, and reference the Git information when identifying the likely cause."""

        return prompt
    
    def _call_llm(self, prompt: str) -> str:
        """Call the LLM API"""
        if settings.llm_provider == 'openai':
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert software engineer specializing in debugging and root cause analysis."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            return response.choices[0].message.content
        
        elif settings.llm_provider == 'anthropic':
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        
        return ""
    
    def _parse_llm_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse LLM response into structured data"""
        try:
            # Try to extract JSON from response
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                return json.loads(json_str)
            
            return None
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            return None
    
    def _store_rca_result(self, cluster_id: str, rca_data: Dict[str, Any], raw_response: str) -> str:
        """Store RCA result in database"""
        rca_id = str(uuid.uuid4())
        
        root_cause = rca_data.get('root_cause', {})
        git_analysis = rca_data.get('git_analysis', {})
        
        rca_result = RCAResult(
            id=rca_id,
            cluster_id=cluster_id,
            root_cause_file=root_cause.get('file'),
            root_cause_symbol=root_cause.get('symbol'),
            root_cause_line_start=root_cause.get('line_start'),
            root_cause_line_end=root_cause.get('line_end'),
            confidence_score=0.85,
            explanation=root_cause.get('explanation', ''),
            involved_parameters=rca_data.get('involved_parameters', []),
            fix_suggestions=rca_data.get('fix_suggestions', []),
            supporting_evidence={
                'git_analysis': git_analysis,
                'impact_analysis': rca_data.get('impact_analysis', {}),
                'prevention': rca_data.get('prevention', []),
                'raw_response': raw_response
            },
            llm_model=self.model,
            llm_tokens_used=len(raw_response.split()),
            llm_cost=0.0
        )
        
        with get_db() as db:
            db.add(rca_result)
            db.commit()
        
        return rca_id


# Global instance
enhanced_analyzer = EnhancedLLMAnalyzer()
