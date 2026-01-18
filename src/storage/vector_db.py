"""
Vector database client for code and log embeddings.
Supports Qdrant and FAISS.
"""
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer
import logging
from src.config import settings

logger = logging.getLogger(__name__)


class VectorDatabase:
    """Vector database client wrapper"""
    
    def __init__(self):
        self.db_type = settings.vector_db_type
        self.embedding_model = SentenceTransformer(settings.embedding_model)
        self.dimension = settings.embedding_dimension
        
        if self.db_type == 'qdrant':
            self.client = QdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
                api_key=settings.qdrant_api_key if settings.qdrant_api_key else None
            )
        else:
            raise NotImplementedError(f"Vector DB type '{self.db_type}' not implemented")
    
    def init_collections(self):
        """Initialize vector database collections"""
        collections = ['code_embeddings', 'log_embeddings']
        
        for collection_name in collections:
            try:
                self.client.get_collection(collection_name)
                logger.info(f"Collection '{collection_name}' already exists")
            except Exception:
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(size=self.dimension, distance=Distance.COSINE)
                )
                logger.info(f"Created collection '{collection_name}'")
    
    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for text"""
        return self.embedding_model.encode(text).tolist()
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        return self.embedding_model.encode(texts).tolist()
    
    def insert_code_block(
        self,
        code_id: str,
        code_text: str,
        metadata: Dict[str, Any]
    ) -> str:
        """Insert code block with embedding"""
        logger.info("Creating embeddings")
        embedding = self.embed_text(code_text)
        logger.info(f"Embedding length: {len(embedding)}")

        point = PointStruct(
            id=code_id,
            vector=embedding,
            payload=metadata
        )
        self.client.upsert(
            collection_name='code_embeddings',
            points=[point]
        )
        
        logger.debug(f"Inserted code block: {code_id}")
        return code_id
    
    def search_code_blocks(
        self,
        query_text: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar code blocks.
        
        Args:
            query_text: Query text (e.g., stack frame or exception message)
            top_k: Number of results to return
            filters: Optional filters (e.g., {'file_path': 'handlers/user.py'})
        
        Returns:
            List of matching code blocks with scores
        """
        query_vector = self.embed_text(query_text)
        
        # Build filters if provided
        search_filter = None
        if filters:
            conditions = []
            for key, value in filters.items():
                conditions.append(
                    FieldCondition(key=key, match=MatchValue(value=value))
                )
            if conditions:
                search_filter = Filter(must=conditions)
        
        results = self.client.search(
            collection_name='code_embeddings',
            query_vector=query_vector,
            limit=top_k,
            query_filter=search_filter
        )
        
        return [
            {
                'id': hit.id,
                'score': hit.score,
                'metadata': hit.payload
            }
            for hit in results
        ]
    
    def insert_log_embedding(
        self,
        log_id: str,
        log_text: str,
        metadata: Dict[str, Any]
    ) -> str:
        """Insert log entry with embedding for clustering"""
        embedding = self.embed_text(log_text)
        
        point = PointStruct(
            id=log_id,
            vector=embedding,
            payload=metadata
        )
        
        self.client.upsert(
            collection_name='log_embeddings',
            points=[point]
        )
        
        logger.debug(f"Inserted log embedding: {log_id}")
        return log_id
    
    def find_similar_logs(
        self,
        log_text: str,
        top_k: int = 10,
        threshold: float = 0.85
    ) -> List[Dict[str, Any]]:
        """Find similar log entries for clustering"""
        query_vector = self.embed_text(log_text)
        
        results = self.client.search(
            collection_name='log_embeddings',
            query_vector=query_vector,
            limit=top_k,
            score_threshold=threshold
        )
        
        return [
            {
                'id': hit.id,
                'score': hit.score,
                'metadata': hit.payload
            }
            for hit in results
        ]


# Global vector database instance
vector_db = VectorDatabase()
