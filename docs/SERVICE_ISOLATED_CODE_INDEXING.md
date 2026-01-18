# Service-Isolated Code Indexing Architecture

## 📋 Problem Statement

**Current Issue**: Code indexing doesn't differentiate between services, causing:
- ❌ Code blocks from different services mixed in PostgreSQL and Qdrant
- ❌ No way to query code specific to a service
- ❌ RCA generation may retrieve code from wrong service
- ❌ Cross-service contamination in vector search
- ❌ No service-specific indexing metadata tracking

**Required**: Complete service isolation in code indexing pipeline.

---

## 🎯 Solution Overview

### **Core Principle**: Every code block must be tagged with `service_id`

**Isolation Points**:
1. **PostgreSQL**: Add `service_id` to `code_blocks` and `indexing_metadata` tables
2. **Qdrant**: Add `service_id` to vector metadata for filtering
3. **Indexing Pipeline**: Pass `service_id` through entire workflow
4. **Retrieval Pipeline**: Filter by `service_id` in all queries
5. **RCA Generation**: Only retrieve code from same service as exception

---

## 🗄️ Database Schema Changes

### **1. CodeBlock Table Enhancement**

```python
class CodeBlock(Base):
    """Indexed code blocks for context retrieval"""
    __tablename__ = 'code_blocks'
    
    id = Column(String, primary_key=True)
    
    # NEW: Service isolation
    service_id = Column(String, ForeignKey('services.id'), nullable=False)
    
    # Existing fields
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
```

**Index for Performance**:
```sql
CREATE INDEX idx_code_blocks_service_id ON code_blocks(service_id);
CREATE INDEX idx_code_blocks_service_repo ON code_blocks(service_id, repository);
```

### **2. IndexingMetadata Table Enhancement**

```python
class IndexingMetadata(Base):
    """Track repository indexing state for incremental indexing"""
    __tablename__ = 'indexing_metadata'
    
    # NEW: Composite primary key
    service_id = Column(String, ForeignKey('services.id'), primary_key=True)
    repository = Column(String, primary_key=True)
    
    # Existing fields
    last_indexed_commit = Column(String)
    last_indexed_at = Column(DateTime)
    total_files_indexed = Column(Integer, default=0)
    total_blocks_indexed = Column(Integer, default=0)
    indexing_mode = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # NEW: Relationship
    service = relationship("Service", back_populates="indexing_metadata")
```

**Composite Primary Key**: `(service_id, repository)` allows same repository for different services.

### **3. Service Model Enhancement**

```python
class Service(Base):
    """Service/Application metadata"""
    __tablename__ = 'services'
    
    # ... existing fields ...
    
    # NEW: Relationships
    code_blocks = relationship("CodeBlock", back_populates="service")
    indexing_metadata = relationship("IndexingMetadata", back_populates="service")
```

---

## 🔧 Qdrant Vector Database Changes

### **Current Structure** (WRONG)
```python
# No service isolation
vector_db.upsert(
    collection_name="code_embeddings",
    points=[{
        "id": block_id,
        "vector": embedding,
        "payload": {
            "repository": "my-repo",
            "file_path": "src/main.py",
            "symbol_name": "process_data"
        }
    }]
)
```

### **Enhanced Structure** (CORRECT)
```python
# With service isolation
vector_db.upsert(
    collection_name="code_embeddings",
    points=[{
        "id": block_id,
        "vector": embedding,
        "payload": {
            "service_id": "web-app",           # NEW: Service isolation
            "service_name": "Web Application",  # NEW: For readability
            "repository": "my-repo",
            "file_path": "src/main.py",
            "symbol_name": "process_data",
            "commit_sha": "abc123",
            "indexed_at": "2024-12-11T22:00:00Z"
        }
    }]
)
```

### **Service-Filtered Search**
```python
# Search only within specific service
results = vector_db.search(
    collection_name="code_embeddings",
    query_vector=query_embedding,
    query_filter={
        "must": [
            {"key": "service_id", "match": {"value": "web-app"}}
        ]
    },
    limit=10
)
```

---

## 🔄 Code Indexer Changes

### **1. Constructor Enhancement**

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
        self.service_id = service_id  # NEW: Store service_id
        self.repo = None
        self.commit_sha = self._get_commit_sha()
        
        # Validate service_id
        if not self.service_id:
            raise ValueError("service_id is required for code indexing")
```

### **2. Metadata Tracking Enhancement**

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
    except Exception as e:
        logger.error(f"Error updating indexing metadata: {e}")
```

### **3. Code Block Storage Enhancement**

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
                    "service_name": self._get_service_name(),  # NEW: For readability
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

## 🔍 Code Retrieval Changes

### **1. Vector Search Enhancement**

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

### **2. RCA Generation Enhancement**

```python
def generate_rca_for_cluster(cluster_id: str):
    """Generate RCA with service-isolated code retrieval"""
    
    # Get cluster details
    with get_db() as db:
        cluster = db.query(ExceptionCluster).filter_by(
            cluster_id=cluster_id
        ).first()
        
        if not cluster:
            raise ValueError(f"Cluster {cluster_id} not found")
        
        service_id = cluster.service_id  # Get service from cluster
    
    # Retrieve relevant code ONLY from same service
    relevant_code = retrieve_relevant_code(
        query=f"{cluster.exception_type}: {cluster.exception_message}",
        service_id=service_id,  # Service-filtered retrieval
        top_k=10
    )
    
    # Generate RCA using service-specific code
    rca = llm_analyzer.analyze(
        exception=cluster,
        code_context=relevant_code,
        service_id=service_id
    )
    
    return rca
```

---

## 📋 Migration Script

### **Database Migration**

```python
#!/usr/bin/env python3
"""
Migration script to add service_id to code indexing tables.

This script:
1. Adds service_id column to code_blocks table
2. Recreates indexing_metadata table with composite primary key
3. Updates existing records with default service_id
4. Creates necessary indexes
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.storage.database import get_db, engine
from src.storage.models import Service
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_code_blocks_table():
    """Add service_id to code_blocks table"""
    logger.info("Migrating code_blocks table...")
    
    with engine.connect() as conn:
        # Check if column exists
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='code_blocks' AND column_name='service_id'
        """))
        
        if result.fetchone():
            logger.info("service_id column already exists in code_blocks")
            return
        
        # Add service_id column (nullable initially)
        conn.execute(text("""
            ALTER TABLE code_blocks 
            ADD COLUMN service_id VARCHAR
        """))
        conn.commit()
        logger.info("✅ Added service_id column to code_blocks")
        
        # Get default service or create one
        with get_db() as db:
            default_service = db.query(Service).first()
            
            if not default_service:
                logger.warning("No services found, creating default service")
                default_service = Service(
                    id='default-service',
                    name='Default Service',
                    description='Default service for existing code blocks'
                )
                db.add(default_service)
                db.commit()
            
            default_service_id = default_service.id
        
        # Update existing records
        conn.execute(text(f"""
            UPDATE code_blocks 
            SET service_id = '{default_service_id}' 
            WHERE service_id IS NULL
        """))
        conn.commit()
        logger.info(f"✅ Updated existing code_blocks with service_id: {default_service_id}")
        
        # Make column non-nullable
        conn.execute(text("""
            ALTER TABLE code_blocks 
            ALTER COLUMN service_id SET NOT NULL
        """))
        conn.commit()
        logger.info("✅ Made service_id non-nullable")
        
        # Add foreign key constraint
        conn.execute(text("""
            ALTER TABLE code_blocks 
            ADD CONSTRAINT fk_code_blocks_service 
            FOREIGN KEY (service_id) REFERENCES services(id)
        """))
        conn.commit()
        logger.info("✅ Added foreign key constraint")
        
        # Create index
        conn.execute(text("""
            CREATE INDEX idx_code_blocks_service_id ON code_blocks(service_id)
        """))
        conn.execute(text("""
            CREATE INDEX idx_code_blocks_service_repo 
            ON code_blocks(service_id, repository)
        """))
        conn.commit()
        logger.info("✅ Created indexes")


def migrate_indexing_metadata_table():
    """Recreate indexing_metadata table with composite primary key"""
    logger.info("Migrating indexing_metadata table...")
    
    with engine.connect() as conn:
        # Backup existing data
        result = conn.execute(text("SELECT * FROM indexing_metadata"))
        existing_data = result.fetchall()
        logger.info(f"Backing up {len(existing_data)} existing records")
        
        # Drop and recreate table
        conn.execute(text("DROP TABLE IF EXISTS indexing_metadata"))
        conn.commit()
        
        conn.execute(text("""
            CREATE TABLE indexing_metadata (
                service_id VARCHAR NOT NULL,
                repository VARCHAR NOT NULL,
                last_indexed_commit VARCHAR,
                last_indexed_at TIMESTAMP,
                total_files_indexed INTEGER DEFAULT 0,
                total_blocks_indexed INTEGER DEFAULT 0,
                indexing_mode VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (service_id, repository),
                FOREIGN KEY (service_id) REFERENCES services(id)
            )
        """))
        conn.commit()
        logger.info("✅ Recreated indexing_metadata table")
        
        # Restore data with default service_id
        if existing_data:
            with get_db() as db:
                default_service = db.query(Service).first()
                default_service_id = default_service.id if default_service else 'default-service'
            
            for row in existing_data:
                conn.execute(text("""
                    INSERT INTO indexing_metadata 
                    (service_id, repository, last_indexed_commit, last_indexed_at, 
                     total_files_indexed, total_blocks_indexed, indexing_mode, 
                     created_at, updated_at)
                    VALUES (:service_id, :repository, :last_indexed_commit, :last_indexed_at,
                            :total_files_indexed, :total_blocks_indexed, :indexing_mode,
                            :created_at, :updated_at)
                """), {
                    'service_id': default_service_id,
                    'repository': row[0],  # Old primary key
                    'last_indexed_commit': row[1],
                    'last_indexed_at': row[2],
                    'total_files_indexed': row[3],
                    'total_blocks_indexed': row[4],
                    'indexing_mode': row[5],
                    'created_at': row[6],
                    'updated_at': row[7]
                })
            conn.commit()
            logger.info(f"✅ Restored {len(existing_data)} records")


def update_qdrant_metadata():
    """Update Qdrant vectors with service_id metadata"""
    logger.info("Updating Qdrant metadata...")
    logger.info("⚠️  Manual step required:")
    logger.info("   1. Re-index all code repositories to add service_id to Qdrant")
    logger.info("   2. Or run: python scripts/maintenance/reindex_all_services.py")


def main():
    """Run all migrations"""
    logger.info("=" * 80)
    logger.info("Starting Service-Isolated Code Indexing Migration")
    logger.info("=" * 80)
    
    try:
        migrate_code_blocks_table()
        migrate_indexing_metadata_table()
        update_qdrant_metadata()
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("✅ Migration completed successfully!")
        logger.info("=" * 80)
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Re-index all service repositories to populate Qdrant with service_id")
        logger.info("2. Test code retrieval with service filtering")
        logger.info("3. Verify RCA generation uses correct service code")
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

---

## 🧪 Testing Strategy

### **1. Unit Tests**

```python
def test_service_isolated_indexing():
    """Test that code indexing is service-isolated"""
    
    # Index service 1
    indexer1 = CodeIndexer(
        repo_path="/path/to/service1",
        service_id="service-1"
    )
    stats1 = indexer1.index_repository()
    
    # Index service 2
    indexer2 = CodeIndexer(
        repo_path="/path/to/service2",
        service_id="service-2"
    )
    stats2 = indexer2.index_repository()
    
    # Verify PostgreSQL isolation
    with get_db() as db:
        service1_blocks = db.query(CodeBlock).filter_by(
            service_id="service-1"
        ).count()
        
        service2_blocks = db.query(CodeBlock).filter_by(
            service_id="service-2"
        ).count()
        
        assert service1_blocks > 0
        assert service2_blocks > 0
        assert service1_blocks != service2_blocks  # Different counts
    
    # Verify Qdrant isolation
    results1 = vector_db.search(
        collection_name="code_embeddings",
        query_vector=[0.1] * 768,
        query_filter={"must": [{"key": "service_id", "match": {"value": "service-1"}}]},
        limit=100
    )
    
    results2 = vector_db.search(
        collection_name="code_embeddings",
        query_vector=[0.1] * 768,
        query_filter={"must": [{"key": "service_id", "match": {"value": "service-2"}}]},
        limit=100
    )
    
    # Verify no cross-contamination
    for result in results1:
        assert result.payload['service_id'] == "service-1"
    
    for result in results2:
        assert result.payload['service_id'] == "service-2"


def test_service_filtered_retrieval():
    """Test that code retrieval is service-filtered"""
    
    # Retrieve code for service 1
    code1 = retrieve_relevant_code(
        query="database connection error",
        service_id="service-1",
        top_k=10
    )
    
    # Verify all results are from service 1
    for block in code1:
        assert block['service_id'] == "service-1"
    
    # Retrieve code for service 2
    code2 = retrieve_relevant_code(
        query="database connection error",
        service_id="service-2",
        top_k=10
    )
    
    # Verify all results are from service 2
    for block in code2:
        assert block['service_id'] == "service-2"
    
    # Verify different results
    code1_ids = {block['id'] for block in code1}
    code2_ids = {block['id'] for block in code2}
    assert code1_ids.isdisjoint(code2_ids)  # No overlap
```

### **2. Integration Tests**

```python
def test_end_to_end_service_isolation():
    """Test complete pipeline with service isolation"""
    
    # 1. Index code for service
    indexer = CodeIndexer(
        repo_path="/path/to/service",
        service_id="test-service"
    )
    indexer.index_repository()
    
    # 2. Create exception cluster for service
    cluster = create_test_cluster(service_id="test-service")
    
    # 3. Generate RCA
    rca = generate_rca_for_cluster(cluster.cluster_id)
    
    # 4. Verify RCA only used code from same service
    # (Check logs or add instrumentation)
    
    # 5. Verify no code from other services was retrieved
    with get_db() as db:
        other_service_blocks = db.query(CodeBlock).filter(
            CodeBlock.service_id != "test-service"
        ).all()
        
        # Ensure none of these blocks were used in RCA
        for block in other_service_blocks:
            assert block.id not in rca.supporting_evidence
```

---

## 📊 Implementation Checklist

### **Phase 1: Database Schema** ✅
- [ ] Add `service_id` to `CodeBlock` model
- [ ] Update `IndexingMetadata` with composite primary key
- [ ] Add relationships to `Service` model
- [ ] Create migration script
- [ ] Run migration on development database
- [ ] Verify schema changes

### **Phase 2: Code Indexer** ✅
- [ ] Add `service_id` parameter to `CodeIndexer.__init__()`
- [ ] Update `_get_last_indexed_commit()` with service filter
- [ ] Update `_update_indexing_metadata()` with service_id
- [ ] Update `_store_code_block()` with service_id
- [ ] Add service_id to Qdrant payload
- [ ] Add validation for required service_id

### **Phase 3: Code Retrieval** ✅
- [ ] Update `retrieve_relevant_code()` with service filter
- [ ] Add Qdrant service filtering
- [ ] Add PostgreSQL service filtering
- [ ] Update RCA generation to use service-filtered retrieval

### **Phase 4: Task Integration** ✅
- [ ] Ensure `index_code_repository` task passes service_id
- [ ] Update API endpoints to require service_id
- [ ] Update all task calls with service_id

### **Phase 5: Testing** ✅
- [ ] Write unit tests for service isolation
- [ ] Write integration tests for end-to-end pipeline
- [ ] Test with multiple services
- [ ] Verify no cross-contamination
- [ ] Performance testing with service filters

### **Phase 6: Re-indexing** ✅
- [ ] Create re-indexing script for all services
- [ ] Run re-indexing for existing services
- [ ] Verify Qdrant metadata updated
- [ ] Clean up old non-service-tagged data

### **Phase 7: Documentation** ✅
- [ ] Update API documentation
- [ ] Update architecture documentation
- [ ] Create migration guide
- [ ] Update deployment guide

---

## 🎯 Expected Outcomes

### **Before (Current State)**
```
PostgreSQL code_blocks:
- service_id: NULL
- Mixed code from all services

Qdrant vectors:
- No service_id in payload
- Cross-service contamination in search

RCA Generation:
- May retrieve code from wrong service
- Incorrect context for analysis
```

### **After (Service-Isolated)**
```
PostgreSQL code_blocks:
- service_id: "web-app" (required)
- Clean service separation

Qdrant vectors:
- service_id: "web-app" in payload
- Service-filtered search

RCA Generation:
- Only retrieves code from same service
- Accurate context for analysis
```

---

## 🚀 Benefits

1. **Complete Isolation**: Each service's code is completely isolated
2. **Accurate RCA**: RCA uses only relevant service code
3. **Multi-Tenant Ready**: Can support multiple teams/services
4. **Performance**: Faster queries with service filtering
5. **Data Integrity**: No cross-service contamination
6. **Scalability**: Easy to add new services
7. **Debugging**: Clear service attribution for all code blocks

---

## ⚠️ Important Notes

1. **Breaking Change**: Requires re-indexing all repositories
2. **Downtime**: Brief downtime during migration
3. **Storage**: Slightly increased metadata storage
4. **Queries**: All queries must include service_id filter
5. **Backward Compatibility**: Old code without service_id will be assigned to default service

---

## 📚 Related Documentation

- `CODE_INDEXING_AUTO_SYNC.md` - Auto-sync feature
- `MULTI_SERVICE_BACKEND_PROCESSING.md` - Multi-service architecture
- `GIT_INTEGRATION_GUIDE.md` - Git integration
- `CODE_REPOSITORY_ACCESS_COMPARISON.md` - Repository access approaches

---

## ✅ Summary

This architecture ensures **complete service isolation** in code indexing by:
- Adding `service_id` to all code blocks (PostgreSQL + Qdrant)
- Filtering all queries by service
- Ensuring RCA only uses service-specific code
- Providing clear service attribution
- Enabling multi-tenant deployments

**Result: Zero cross-service contamination in code indexing and retrieval!**
