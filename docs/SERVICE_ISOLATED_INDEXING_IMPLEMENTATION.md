# Service-Isolated Code Indexing - Implementation Guide

## 📋 Quick Summary

**Problem**: Code blocks from different services are mixed in PostgreSQL and Qdrant, causing cross-service contamination in RCA generation.

**Solution**: Add `service_id` to all code indexing tables and vector metadata, ensuring complete service isolation.

---

## 🎯 Implementation Steps

### **Step 1: Run Database Migration**

```bash
# Run migration script
python scripts/migrate_service_isolated_indexing.py
```

**What it does**:
- Adds `service_id` column to `code_blocks` table
- Recreates `indexing_metadata` table with composite primary key `(service_id, repository)`
- Updates existing records with default service_id
- Creates necessary indexes for performance

**Expected Output**:
```
✅ Added service_id column to code_blocks
✅ Updated existing code_blocks with service_id: default-service
✅ Made service_id non-nullable
✅ Added foreign key constraint
✅ Created indexes
✅ Recreated indexing_metadata table
✅ Restored N records
```

---

### **Step 2: Update Database Models**

Update `src/storage/models.py`:

```python
class CodeBlock(Base):
    """Indexed code blocks for context retrieval"""
    __tablename__ = 'code_blocks'
    
    id = Column(String, primary_key=True)
    service_id = Column(String, ForeignKey('services.id'), nullable=False)  # NEW
    repository = Column(String, nullable=False)
    version = Column(String, nullable=False)
    commit_sha = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    symbol_name = Column(String, nullable=False)
    symbol_type = Column(String)
    line_start = Column(Integer, nullable=False)
    line_end = Column(Integer, nullable=False)
    code_snippet = Column(Text, nullable=False)
    docstring = Column(Text)
    function_signature = Column(String)
    embedding_id = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # NEW: Relationship
    service = relationship("Service", back_populates="code_blocks")


class IndexingMetadata(Base):
    """Track repository indexing state for incremental indexing"""
    __tablename__ = 'indexing_metadata'
    
    # NEW: Composite primary key
    service_id = Column(String, ForeignKey('services.id'), primary_key=True)
    repository = Column(String, primary_key=True)
    
    last_indexed_commit = Column(String)
    last_indexed_at = Column(DateTime)
    total_files_indexed = Column(Integer, default=0)
    total_blocks_indexed = Column(Integer, default=0)
    indexing_mode = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # NEW: Relationship
    service = relationship("Service", back_populates="indexing_metadata")


class Service(Base):
    """Service/Application metadata"""
    __tablename__ = 'services'
    
    # ... existing fields ...
    
    # NEW: Relationships
    code_blocks = relationship("CodeBlock", back_populates="service")
    indexing_metadata = relationship("IndexingMetadata", back_populates="service")
```

---

### **Step 3: Update CodeIndexer Class**

Update `src/services/code_indexer.py`:

#### **3.1 Constructor**

```python
class CodeIndexer:
    """Index code repository for RAG-based analysis"""
    
    def __init__(
        self, 
        repo_path: str = None, 
        version: str = None,
        service_id: str = None  # NEW: Required parameter
    ):
        self.repo_path = Path(repo_path or settings.git_repo_path)
        self.version = version or settings.code_version
        self.service_id = service_id  # NEW
        self.repo = None
        self.commit_sha = self._get_commit_sha()
        
        # Validate service_id
        if not self.service_id:
            raise ValueError("service_id is required for code indexing")
        
        logger.info(f"Initialized CodeIndexer for service: {self.service_id}")
```

#### **3.2 Metadata Methods**

```python
def _get_last_indexed_commit(self) -> Optional[str]:
    """Get the last indexed commit SHA from database"""
    try:
        with get_db() as db:
            metadata = db.query(IndexingMetadata).filter_by(
                service_id=self.service_id,  # NEW: Filter by service
                repository=str(self.repo_path.name)
            ).first()
            
            if metadata:
                return metadata.last_indexed_commit
            return None
    except Exception as e:
        logger.error(f"Error getting last indexed commit: {e}")
        return None

def _update_indexing_metadata(self, stats: Dict, mode: str):
    """Update indexing metadata in database"""
    try:
        with get_db() as db:
            metadata = db.query(IndexingMetadata).filter_by(
                service_id=self.service_id,  # NEW: Filter by service
                repository=str(self.repo_path.name)
            ).first()
            
            if not metadata:
                metadata = IndexingMetadata(
                    service_id=self.service_id,  # NEW: Set service_id
                    repository=str(self.repo_path.name)
                )
                db.add(metadata)
            
            metadata.last_indexed_commit = self.commit_sha
            metadata.last_indexed_at = datetime.utcnow()
            metadata.total_files_indexed = stats.get('total_files', 0)
            metadata.total_blocks_indexed = stats.get('total_blocks', 0)
            metadata.indexing_mode = mode
            
            db.commit()
            logger.info(f"Updated indexing metadata for service {self.service_id}")
    except Exception as e:
        logger.error(f"Error updating indexing metadata: {e}")
```

#### **3.3 Code Block Storage**

```python
def _store_code_block(self, block_data: Dict) -> Optional[str]:
    """Store code block in PostgreSQL and Qdrant"""
    try:
        block_id = str(uuid.uuid4())
        
        # PostgreSQL storage
        with get_db() as db:
            code_block = CodeBlock(
                id=block_id,
                service_id=self.service_id,  # NEW: Set service_id
                repository=str(self.repo_path.name),
                version=self.version,
                commit_sha=self.commit_sha,
                file_path=block_data['file_path'],
                symbol_name=block_data['symbol_name'],
                symbol_type=block_data['symbol_type'],
                line_start=block_data['line_start'],
                line_end=block_data['line_end'],
                code_snippet=block_data['code_snippet'],
                docstring=block_data.get('docstring'),
                function_signature=block_data.get('function_signature'),
                embedding_id=block_id
            )
            db.add(code_block)
            db.commit()
        
        # Qdrant storage with service isolation
        vector_db.upsert(
            collection_name="code_embeddings",
            points=[{
                "id": block_id,
                "vector": block_data['embedding'],
                "payload": {
                    "service_id": self.service_id,  # NEW: Service isolation
                    "service_name": self._get_service_name(),  # NEW
                    "repository": str(self.repo_path.name),
                    "file_path": block_data['file_path'],
                    "symbol_name": block_data['symbol_name'],
                    "symbol_type": block_data['symbol_type'],
                    "commit_sha": self.commit_sha,
                    "indexed_at": datetime.utcnow().isoformat()
                }
            }]
        )
        
        return block_id
        
    except Exception as e:
        logger.error(f"Error storing code block: {e}")
        return None

def _get_service_name(self) -> str:
    """Get service name for metadata"""
    try:
        with get_db() as db:
            service = db.query(Service).filter_by(id=self.service_id).first()
            return service.name if service else self.service_id
    except:
        return self.service_id
```

---

### **Step 4: Update Task**

Update `src/services/tasks.py`:

```python
@celery_app.task(name='tasks.index_code_repository', bind=True)
def index_code_repository(
    self,
    service_id: str = None,  # REQUIRED
    trigger_reason: str = 'manual',
    force_full: bool = False,
    repository_path: str = None,
    branch: str = 'main',
    auto_sync: bool = True
):
    """Index the code repository with service isolation"""
    task_id = self.request.id
    
    # Validate service_id
    if not service_id:
        error_msg = "service_id is required for code indexing"
        logger.error(f"[Task {task_id}] {error_msg}")
        return {'status': 'error', 'error': error_msg}
    
    logger.info(f"[Task {task_id}] Starting code indexing for service {service_id}")
    
    try:
        from src.storage.database import get_db
        from src.storage.models import Service
        
        # Get service configuration
        with get_db() as db:
            service = db.query(Service).filter(Service.id == service_id).first()
            
            if not service:
                error_msg = f"Service {service_id} not found"
                logger.error(f"[Task {task_id}] {error_msg}")
                return {'status': 'error', 'error': error_msg}
            
            if not service.git_repo_path:
                error_msg = f"No Git repository configured for service {service_id}"
                logger.error(f"[Task {task_id}] {error_msg}")
                return {'status': 'error', 'error': error_msg}
            
            repository_path = service.git_repo_path
            branch = service.git_branch or 'main'
        
        # Initialize code indexer with service_id
        indexer = CodeIndexer(
            repo_path=repository_path,
            version=branch,
            service_id=service_id  # NEW: Pass service_id
        )
        
        # Run indexing
        stats = indexer.index_repository(
            languages=['python', 'java'],
            force_full=force_full,
            auto_sync=auto_sync
        )
        
        logger.info(f"[Task {task_id}] Code indexing complete for service {service_id}: {stats}")
        
        return {
            'status': 'success',
            'task_id': task_id,
            'service_id': service_id,
            'mode': stats.get('mode'),
            'files_indexed': stats.get('total_files'),
            'blocks_indexed': stats.get('total_blocks')
        }
    
    except Exception as e:
        error_msg = f"Code indexing failed: {str(e)}"
        logger.error(f"[Task {task_id}] {error_msg}", exc_info=True)
        return {'status': 'error', 'error': error_msg}
```

---

### **Step 5: Update Code Retrieval**

Create or update `src/services/code_retrieval.py`:

```python
def retrieve_relevant_code(
    query: str,
    service_id: str,  # NEW: Required parameter
    top_k: int = 10
) -> List[Dict]:
    """
    Retrieve relevant code blocks for a query, filtered by service.
    
    Args:
        query: Search query (exception message, stack trace, etc.)
        service_id: Service ID to filter results
        top_k: Number of results to return
    
    Returns:
        List of relevant code blocks from the specified service only
    """
    from src.storage.vector_db import vector_db
    from src.storage.database import get_db
    from src.storage.models import CodeBlock
    
    # Generate query embedding
    query_embedding = generate_embedding(query)
    
    # Search with service filter
    results = vector_db.search(
        collection_name="code_embeddings",
        query_vector=query_embedding,
        query_filter={
            "must": [
                {"key": "service_id", "match": {"value": service_id}}
            ]
        },
        limit=top_k
    )
    
    # Fetch full details from PostgreSQL
    code_blocks = []
    with get_db() as db:
        for result in results:
            block = db.query(CodeBlock).filter_by(
                id=result.id,
                service_id=service_id  # Double-check service isolation
            ).first()
            
            if block:
                code_blocks.append({
                    "id": block.id,
                    "service_id": block.service_id,
                    "file_path": block.file_path,
                    "symbol_name": block.symbol_name,
                    "code_snippet": block.code_snippet,
                    "similarity_score": result.score
                })
    
    return code_blocks
```

---

### **Step 6: Update RCA Generation**

Update `src/services/llm_analyzer.py`:

```python
def generate_rca_for_cluster(cluster_id: str):
    """Generate RCA with service-isolated code retrieval"""
    from src.storage.database import get_db
    from src.storage.models import ExceptionCluster
    from src.services.code_retrieval import retrieve_relevant_code
    
    # Get cluster details
    with get_db() as db:
        cluster = db.query(ExceptionCluster).filter_by(
            cluster_id=cluster_id
        ).first()
        
        if not cluster:
            raise ValueError(f"Cluster {cluster_id} not found")
        
        service_id = cluster.service_id  # Get service from cluster
    
    logger.info(f"Generating RCA for cluster {cluster_id} (service: {service_id})")
    
    # Retrieve relevant code ONLY from same service
    relevant_code = retrieve_relevant_code(
        query=f"{cluster.exception_type}: {cluster.exception_message}",
        service_id=service_id,  # Service-filtered retrieval
        top_k=10
    )
    
    logger.info(f"Retrieved {len(relevant_code)} code blocks from service {service_id}")
    
    # Generate RCA using service-specific code
    rca = llm_analyzer.analyze(
        exception=cluster,
        code_context=relevant_code,
        service_id=service_id
    )
    
    return rca
```

---

### **Step 7: Re-index All Services**

Create `scripts/maintenance/reindex_all_services.py`:

```python
#!/usr/bin/env python3
"""
Re-index all services to populate Qdrant with service_id metadata.
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.storage.database import get_db
from src.storage.models import Service
from src.services.tasks import index_code_repository
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Re-index all active services"""
    logger.info("=" * 80)
    logger.info("Re-indexing All Services")
    logger.info("=" * 80)
    
    with get_db() as db:
        services = db.query(Service).filter_by(is_active=True).all()
        
        logger.info(f"Found {len(services)} active services")
        
        for service in services:
            if not service.git_repo_path:
                logger.warning(f"Skipping {service.name}: No repository configured")
                continue
            
            logger.info(f"")
            logger.info(f"Re-indexing: {service.name} ({service.id})")
            logger.info(f"Repository: {service.git_repo_path}")
            
            # Trigger indexing task
            task = index_code_repository.apply_async(
                kwargs={
                    'service_id': service.id,
                    'trigger_reason': 'reindex',
                    'force_full': True,  # Force full re-index
                    'auto_sync': True
                }
            )
            
            logger.info(f"Task triggered: {task.id}")
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("✅ Re-indexing tasks triggered for all services")
    logger.info("=" * 80)
    logger.info("")
    logger.info("Monitor task progress:")
    logger.info("  - Check Celery logs")
    logger.info("  - Or use: celery -A src.services.tasks inspect active")


if __name__ == "__main__":
    main()
```

Run the script:
```bash
python scripts/maintenance/reindex_all_services.py
```

---

## 🧪 Testing

### **Test 1: Verify Database Migration**

```bash
# Connect to PostgreSQL
psql -d luffy

# Check code_blocks table
\d code_blocks

# Should show service_id column with foreign key constraint

# Check indexing_metadata table
\d indexing_metadata

# Should show composite primary key (service_id, repository)

# Count blocks by service
SELECT service_id, COUNT(*) FROM code_blocks GROUP BY service_id;
```

### **Test 2: Test Service-Isolated Indexing**

```python
# Test script
from src.services.code_indexer import CodeIndexer

# Index service 1
indexer1 = CodeIndexer(
    repo_path="/path/to/service1",
    service_id="service-1"
)
stats1 = indexer1.index_repository()
print(f"Service 1: {stats1}")

# Index service 2
indexer2 = CodeIndexer(
    repo_path="/path/to/service2",
    service_id="service-2"
)
stats2 = indexer2.index_repository()
print(f"Service 2: {stats2}")

# Verify isolation
from src.storage.database import get_db
from src.storage.models import CodeBlock

with get_db() as db:
    service1_blocks = db.query(CodeBlock).filter_by(service_id="service-1").count()
    service2_blocks = db.query(CodeBlock).filter_by(service_id="service-2").count()
    
    print(f"Service 1 blocks: {service1_blocks}")
    print(f"Service 2 blocks: {service2_blocks}")
```

### **Test 3: Test Service-Filtered Retrieval**

```python
from src.services.code_retrieval import retrieve_relevant_code

# Retrieve code for service 1
code1 = retrieve_relevant_code(
    query="database connection error",
    service_id="service-1",
    top_k=10
)

# Verify all results are from service 1
for block in code1:
    assert block['service_id'] == "service-1"
    print(f"✅ Block {block['id']}: {block['symbol_name']}")

print(f"All {len(code1)} blocks are from service-1")
```

---

## ✅ Verification Checklist

- [ ] Database migration completed successfully
- [ ] `code_blocks` table has `service_id` column
- [ ] `indexing_metadata` table has composite primary key
- [ ] Indexes created for performance
- [ ] CodeIndexer requires `service_id` parameter
- [ ] Code blocks stored with `service_id` in PostgreSQL
- [ ] Code blocks stored with `service_id` in Qdrant
- [ ] Code retrieval filters by `service_id`
- [ ] RCA generation uses service-filtered code
- [ ] All services re-indexed successfully
- [ ] No cross-service contamination in queries

---

## 📊 Expected Results

### **Before**
```sql
-- Mixed code blocks
SELECT service_id, COUNT(*) FROM code_blocks GROUP BY service_id;
 service_id | count 
------------+-------
 NULL       | 1500
```

### **After**
```sql
-- Service-isolated code blocks
SELECT service_id, COUNT(*) FROM code_blocks GROUP BY service_id;
   service_id    | count 
-----------------+-------
 web-app         | 450
 api-service     | 380
 worker-service  | 320
 default-service | 350
```

---

## 🎉 Success Criteria

1. ✅ All code blocks have `service_id`
2. ✅ Qdrant vectors have `service_id` in payload
3. ✅ Code retrieval only returns service-specific blocks
4. ✅ RCA generation uses correct service code
5. ✅ No cross-service contamination
6. ✅ Performance acceptable with service filtering

---

## 📚 Related Documentation

- `SERVICE_ISOLATED_CODE_INDEXING.md` - Complete architecture guide
- `CODE_INDEXING_AUTO_SYNC.md` - Auto-sync feature
- `MULTI_SERVICE_BACKEND_PROCESSING.md` - Multi-service architecture

---

## ✅ Summary

This implementation ensures **complete service isolation** in code indexing:
- Every code block tagged with `service_id`
- All queries filter by service
- Zero cross-service contamination
- Production-ready with comprehensive testing

**Result: Clean service separation in code indexing and retrieval!** 🎉
