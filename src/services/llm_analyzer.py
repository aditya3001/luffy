"""
LLM-based Root Cause Analysis service.
Uses RAG (Retrieval-Augmented Generation) with code context.
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
from src.storage.models import CodeBlock
import time

logger = logging.getLogger(__name__)

# Initialize LLM client based on provider
if settings.llm_provider == 'openai':
    try:
        from openai import OpenAI
        from openai import APIError, RateLimitError, Timeout
        llm_client = OpenAI(api_key=settings.openai_api_key)
        logger.info(f"openai key {settings.openai_api_key}")
    except ImportError:
        logger.info("OpenAI library not installed")

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


class LLMAnalyzer:
    """Generate Root Cause Analysis using LLM"""
    
    def __init__(self):
        self.client = llm_client
        self.model = settings.llm_model
        self.temperature = settings.llm_temperature
        self.max_tokens = settings.llm_max_tokens
    
    def analyze_cluster(self, cluster_id: str) -> Optional[str]:
        """
        Perform RCA on an exception cluster.
        
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
            
            # Eagerly load stack_trace before session closes to avoid detached instance error
            stack_trace = cluster.stack_trace
            cluster_data = {
                'cluster_id': cluster.cluster_id,
                'exception_type': cluster.exception_type,
                'exception_message': cluster.exception_message,
                'stack_trace': stack_trace,
                'first_seen': cluster.first_seen,
                'last_seen': cluster.last_seen
            }
        
        # Retrieve relevant code context (using extracted data, not the detached object)
        code_context = self._retrieve_code_context(cluster_data)
        
        # Build prompt
        prompt = self._build_prompt(cluster_data, code_context)
        print("prompt : ",prompt)
        # Call LLM
        try:
            response = self._call_llm(prompt)
            print("llm_response : ",response)
            rca_data = self._parse_llm_response(response)
            print("rca_data : ",rca_data)
            
            if not rca_data:
                logger.error("Failed to parse LLM response")
                return None
            
            # Store RCA result
            rca_id = self._store_rca_result(cluster_id, rca_data, response)
            
            # Update cluster
            with get_db() as db:
                cluster = db.query(ExceptionCluster).filter_by(cluster_id=cluster_id).first()
                if cluster:
                    cluster.has_rca = True
                    cluster.rca_generated_at = datetime.utcnow()
                    db.commit()
            
            logger.info(f"Generated RCA for cluster {cluster_id}: {rca_id}")
            return rca_id
        
        except Exception as e:
            logger.error(f"Error generating RCA: {e}")
            return None
    
    def _retrieve_code_context(self, cluster_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Retrieve relevant code blocks using vector search"""
        # print("_retrieve_code_context")
        code_context = []
        logger.info(f"cluster.stack_trace : {cluster_data}")

        # Extract stack frames
        stack_frames = cluster_data.get('stack_trace') or []
        
        # Search for each stack frame
        for frame in stack_frames[:5]:  # Top 5 frames
            file_path = frame.get('file', '')
            symbol = frame.get('symbol', '')
            
            # Build search query
            query = f"{symbol} {file_path}"
            print("search_code_blocks query : ",query)
            
            try:
                results = vector_db.search_code_blocks(
                    query_text=query,
                    top_k=7
                )
                code_context.extend(results)
            except Exception as e:
                logger.error(f"Error searching code blocks: {e}")
        
        print("search_code_blocks results : ",results)
        # Deduplicate by ID
        seen_ids = set()
        unique_context = []
        for item in code_context:
            if item['id'] not in seen_ids:
                seen_ids.add(item['id'])
                unique_context.append(item)
        
        return unique_context[:10]  # Limit to top 10 blocks
    
    def _build_prompt(
        self,
        cluster_data: Dict[str, Any],
        code_context: List[Dict[str, Any]]
    ) -> str:
        """Build prompt for LLM"""
        
        # System prompt
        system_prompt = """You are an expert SRE and senior software engineer. 
Analyze production exceptions to identify the root cause, involved parameters, and propose fixes.
Return your analysis as valid JSON matching this schema:

{
  "likely_root_cause": {
    "file_path": "path/to/file.py",
    "symbol": "function_name",
    "line_range": [start, end],
    "confidence": 0.0-1.0,
    "explanation": "detailed explanation"
  },
  "supporting_evidence": [
    {
      "file_path": "...",
      "code_snippet": "...",
      "relevance": "..."
    }
  ],
  "involved_parameters": [
    {
      "name": "parameter_name",
      "value": "value",
      "issue": "why this is problematic"
    }
  ],
  "fix_suggestions": [
    "specific fix suggestion"
  ],
  "tests_to_add": [
    "test case description"
  ]
}"""
        
        # Context prompt
        context_parts = [
            f"Service: {cluster_data.get('service_id', 'unknown')}",
            f"Exception Type: {cluster_data.get('exception_type', 'unknown')}",
            f"Exception Message: {cluster_data.get('exception_message', 'unknown')}",
            f"Frequency: {cluster_data.get('frequency_24h', 0)} occurrences in 24h",
            ""
        ]
        
        # Add stack trace
        stack_trace = cluster_data.get('stack_trace')
        if stack_trace:
            context_parts.append("Stack Trace:")
            for i, frame in enumerate(stack_trace[:10], 1):
                context_parts.append(
                    f"{i}. {frame.get('file', 'unknown')}:{frame.get('line', '?')} "
                    f"in {frame.get('symbol', 'unknown')}"
                )
            context_parts.append("")
        
        # Add code context
        if code_context:
            context_parts.append("Relevant Code Blocks:")
            for i, block in enumerate(code_context[:2], 1):
                block_id = block.get('id')
                metadata = block.get('metadata', {})

                # Fetch actual code snippet from database
                code_block_info = self._fetch_code_block_info(block_id)
                code_snippet = code_block_info['code_snippet']
                context_parts.append(f"\n--- Block {i} ({metadata.get('name', 'unknown')}) ---")
                context_parts.append(f"File: {code_block_info.get('file_path', 'unknown')}")
                context_parts.append(f"Lines: {metadata.get('start_line', '?')}-{metadata.get('end_line', '?')}")
                context_parts.append(f"Type: {metadata.get('type', 'unknown')}")

                if code_snippet:
                    context_parts.append("Code:")
                    context_parts.append("```")
                    context_parts.append(code_snippet)
                    context_parts.append("```")
                else:
                    context_parts.append("Code: (unavailable)")
                
                context_parts.append("")
        
        # User prompt
        user_prompt = "\n".join(context_parts)
        user_prompt += "\n\nAnalyze this exception and provide your findings in JSON format."
        
        # Combine for models that need single prompt
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        return full_prompt

    def _call_llm(self, prompt: str) -> Dict[str, Any]:
        """Call LLM API with retry, error handling, and timing."""
        
        if settings.llm_provider != 'openai':
            raise ValueError("Currently only OpenAI provider is supported.")
        
        logger.info(f"🧠 Using OpenAI LLM client: {llm_client}, model: {self.model}")
        
        retries = 3
        backoff = 2  # seconds

        for attempt in range(1, retries + 1):
            start_time = time.time()
            try:
                response = llm_client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are an expert SRE analyzing production exceptions."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    response_format={"type": "json_object"}
                )
                
                elapsed = time.time() - start_time
                content = response.choices[0].message.content
                tokens_used = response.usage.total_tokens

                logger.info(
                    f"✅ LLM call successful in {elapsed:.2f}s | tokens_used={tokens_used}"
                )

                return {
                    "content": content,
                    "tokens_used": tokens_used,
                    "model": self.model,
                    "elapsed_sec": elapsed,
                }

            except RateLimitError as e:
                logger.warning(f"⚠️ Rate limit hit (attempt {attempt}/{retries}): {e}")
            except Timeout as e:
                logger.warning(f"⏳ Timeout (attempt {attempt}/{retries}): {e}")
            except APIError as e:
                logger.error(f"❌ API error (attempt {attempt}/{retries}): {e}")
            except Exception as e:
                logger.exception(f"💥 Unexpected error during LLM call (attempt {attempt}/{retries}): {e}")

            # If not returned yet, retry after backoff
            if attempt < retries:
                sleep_time = backoff * attempt
                logger.info(f"🔁 Retrying in {sleep_time}s...")
                time.sleep(sleep_time)
        
        logger.error("❌ All retry attempts failed for LLM call.")
        return {"content": None, "error": "LLM request failed after retries"}

        
    
    def _parse_llm_response(self, response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse LLM JSON response"""
        try:
            content = response.get('content', '{}')
            data = json.loads(content)
            
            # Validate required fields
            if 'likely_root_cause' not in data:
                logger.error("LLM response missing 'likely_root_cause'")
                return None
            
            return data
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {e}")
            return None
    
    def _store_rca_result(
        self,
        cluster_id: str,
        rca_data: Dict[str, Any],
        llm_response: Dict[str, Any]
    ) -> str:
        """Store RCA result in database"""
        
        rca_id = f"rca_{uuid.uuid4().hex[:12]}"
        
        root_cause = rca_data.get('likely_root_cause', {})
        
        with get_db() as db:
            rca = RCAResult(
                id=rca_id,
                cluster_id=cluster_id,
                root_cause_file=root_cause.get('file_path'),
                root_cause_symbol=root_cause.get('symbol'),
                root_cause_line_start=root_cause.get('line_range', [0, 0])[0],
                root_cause_line_end=root_cause.get('line_range', [0, 0])[1],
                confidence_score=root_cause.get('confidence', 0.0),
                explanation=root_cause.get('explanation', ''),
                involved_parameters=rca_data.get('involved_parameters', []),
                fix_suggestions=rca_data.get('fix_suggestions', []),
                tests_to_add=rca_data.get('tests_to_add', []),
                supporting_evidence=rca_data.get('supporting_evidence', []),
                llm_model=llm_response.get('model'),
                llm_tokens_used=llm_response.get('tokens_used', 0),
                llm_cost=0.0  # Calculate based on model pricing
            )
            db.add(rca)
        
        return rca_id
    
    def get_rca_result(self, cluster_id: str) -> Optional[Dict[str, Any]]:
        """Get RCA result for a cluster"""
        with get_db() as db:
            rca = db.query(RCAResult).filter_by(cluster_id=cluster_id).first()
            
            if not rca:
                return None
            
            return {
                'rca_id': rca.id,
                'cluster_id': rca.cluster_id,
                'root_cause': {
                    'file': rca.root_cause_file,
                    'symbol': rca.root_cause_symbol,
                    'line_range': [rca.root_cause_line_start, rca.root_cause_line_end],
                    'confidence': rca.confidence_score,
                    'explanation': rca.explanation
                },
                'involved_parameters': rca.involved_parameters,
                'fix_suggestions': rca.fix_suggestions,
                'tests_to_add': rca.tests_to_add,
                'supporting_evidence': rca.supporting_evidence,
                'created_at': rca.created_at.isoformat()
            }

    from typing import Optional, Dict, Any

    def _fetch_code_block_info(self, block_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch code snippet and metadata from database by block ID.

        Returns:
            {
                "code_snippet": str,
                "file_path": str,
                "symbol_type": str
            }
            or None if not found
        """
        logger.info(f"block_id present is {block_id}")

        try:
            with get_db() as db:
                code_block = (
                    db.query(CodeBlock)
                    .filter(CodeBlock.id == block_id)
                    .first()
                )

                if not code_block:
                    return None

                return {
                    "code_snippet": code_block.code_snippet,
                    "file_path": code_block.file_path,
                    "symbol_type": code_block.symbol_type,
                }

        except Exception as e:
            logger.error(
                f"Error fetching code snippet for block {block_id}: {e}",
                exc_info=True
            )
            return None

