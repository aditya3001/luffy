# On-Demand Code Indexing - Implementation Guide

## 📚 Overview

This document outlines the approach for **on-demand code indexing** triggered during log processing, replacing scheduled/periodic code indexing. This ensures that service repositories are indexed accurately and timely when exceptions are detected, providing fresh context for RCA generation.

---

## 🎯 Problem Statement

### Current Approach (Scheduled Indexing):
- ❌ **Fixed intervals** - Indexes code every X hours regardless of need
- ❌ **Resource waste** - Indexes even when no changes occurred
- ❌ **Stale context** - May miss recent code changes between intervals
- ❌ **Delayed indexing** - New exceptions may not have latest code context
- ❌ **No correlation** - Indexing not tied to actual exception processing

### Desired Approach (On-Demand Indexing):
- ✅ **Event-driven** - Index when exceptions are detected
- ✅ **Resource efficient** - Only index when needed
- ✅ **Fresh context** - Always have latest code for RCA
- ✅ **Immediate indexing** - Code indexed before RCA generation
- ✅ **Correlated** - Indexing tied to exception processing flow

---

## 🔄 Proposed Approaches

### Approach 1: Index on Exception Detection (Recommended)

**Trigger Point:** When new exceptions are detected during log processing

**Flow:**
```
Log Processing → Exception Detection → Check Code Index Status → Index if Needed → Continue Processing
```

**Implementation:**

```python
# In tasks.py - fetch_and_process_logs task

@celery_app.task(name='tasks.fetch_and_process_logs', bind=True)
def fetch_and_process_logs(self, service_id: str = None, log_source_id: str = None):
    # ... existing log fetching code ...
    
    # After processing logs and detecting exceptions
    if total_stats['exceptions_found'] > 0:
        # Check if code indexing is needed
        if _should_index_code_for_service(service_id):
            logger.info(f"New exceptions detected, triggering code indexing for service {service_id}")
            
            # Trigger code indexing asynchronously
            index_code_repository.delay(
                service_id=service_id,
                trigger_reason='exception_detected',
                priority='high'
            )
    
    return total_stats


def _should_index_code_for_service(service_id: str) -> bool:
    """
    Determine if code indexing is needed for a service.
    
    Checks:
    1. Is repository configured?
    2. Has code changed since last index? (Git commit SHA)
    3. Is indexing already in progress?
    4. Time since last index (minimum interval to avoid spam)
    """
    with get_db() as db:
        service = db.query(Service).filter(Service.id == service_id).first()
        
        if not service or not service.git_repo_path:
            return False
        
        # Check if already indexing
        if _is_indexing_in_progress(service_id):
            logger.info(f"Code indexing already in progress for service {service_id}")
            return False
        
        # Check minimum interval (e.g., 5 minutes to avoid spam)
        if service.last_code_indexing:
            time_since_last = datetime.utcnow() - service.last_code_indexing
            if time_since_last < timedelta(minutes=5):
                logger.info(f"Code indexed recently for service {service_id}, skipping")
                return False
        
        # Check if code has changed (Git commit SHA)
        current_commit = _get_current_commit_sha(service.git_repo_path, service.git_branch)
        last_indexed_commit = _get_last_indexed_commit(service_id)
        
        if current_commit == last_indexed_commit:
            logger.info(f"Code unchanged for service {service_id}, skipping indexing")
            return False
        
        return True
```

**Pros:**
- ✅ **Immediate response** - Index as soon as exceptions appear
- ✅ **Fresh context** - Always have latest code for RCA
- ✅ **Automatic** - No manual intervention needed
- ✅ **Efficient** - Only index when exceptions occur

**Cons:**
- ⚠️ **Multiple triggers** - May trigger multiple times if many exceptions
- ⚠️ **Latency** - Adds indexing time to log processing pipeline

**Mitigation:**
- Use minimum interval check (5 minutes)
- Check if indexing already in progress
- Run indexing asynchronously (non-blocking)

---

### Approach 2: Index Before RCA Generation

**Trigger Point:** Before generating RCA for exception clusters

**Flow:**
```
Exception Clustering → RCA Trigger → Check Code Index → Index if Needed → Generate RCA
```

**Implementation:**

```python
# In tasks.py - generate_rca_for_clusters task

@celery_app.task(name='tasks.generate_rca_for_clusters', bind=True)
def generate_rca_for_clusters(self, service_id: str = None, cluster_id: str = None):
    """Generate RCA for exception clusters"""
    
    # Before generating RCA, ensure code is indexed
    if service_id:
        if _should_index_code_for_service(service_id):
            logger.info(f"Indexing code before RCA generation for service {service_id}")
            
            # Index synchronously (blocking) to ensure code is available for RCA
            result = index_code_repository_sync(
                service_id=service_id,
                trigger_reason='pre_rca_indexing'
            )
            
            if result['status'] != 'success':
                logger.error(f"Code indexing failed, proceeding with RCA anyway")
    
    # ... existing RCA generation code ...
    
    return rca_stats


def index_code_repository_sync(service_id: str, trigger_reason: str) -> Dict[str, Any]:
    """
    Synchronous code indexing (blocking).
    Used when we need to ensure code is indexed before proceeding.
    """
    from src.services.code_indexer import CodeIndexer
    
    with get_db() as db:
        service = db.query(Service).filter(Service.id == service_id).first()
        
        if not service or not service.git_repo_path:
            return {'status': 'skipped', 'reason': 'no_repo_configured'}
        
        try:
            indexer = CodeIndexer(
                repo_path=service.git_repo_path,
                version=service.git_branch or 'main'
            )
            
            stats = indexer.index_repository(
                languages=['python', 'java'],
                force_full=False  # Incremental by default
            )
            
            # Update service metadata
            db.query(Service).filter(Service.id == service_id).update({
                'last_code_indexing': datetime.utcnow(),
                'code_indexing_status': 'completed'
            })
            db.commit()
            
            return {
                'status': 'success',
                'stats': stats,
                'trigger_reason': trigger_reason
            }
            
        except Exception as e:
            logger.error(f"Code indexing failed: {e}")
            return {'status': 'error', 'error': str(e)}
```

**Pros:**
- ✅ **Guaranteed fresh code** - Always index before RCA
- ✅ **Synchronous** - Ensures code is available for RCA
- ✅ **Less frequent** - Only triggers when RCA is needed
- ✅ **Predictable** - Clear trigger point

**Cons:**
- ⚠️ **Blocking** - RCA generation waits for indexing
- ⚠️ **Latency** - Adds indexing time to RCA pipeline
- ⚠️ **Delayed RCA** - Users wait longer for RCA results

**Mitigation:**
- Use incremental indexing (fast)
- Cache indexing status
- Show "Indexing in progress" status to users

---

### Approach 3: Hybrid - Index on First Exception, Cache for Subsequent

**Trigger Point:** First exception detection + periodic refresh

**Flow:**
```
First Exception → Index Code → Cache Status → Subsequent Exceptions → Use Cached Code → Periodic Refresh
```

**Implementation:**

```python
# In tasks.py

def _should_index_code_for_service(service_id: str) -> bool:
    """
    Smart indexing decision based on:
    1. First exception for service (always index)
    2. Code changes detected (index)
    3. Time-based refresh (index every 1 hour)
    4. Manual trigger (index)
    """
    with get_db() as db:
        service = db.query(Service).filter(Service.id == service_id).first()
        
        if not service or not service.git_repo_path:
            return False
        
        # Check if this is the first exception for this service
        exception_count = db.query(ExceptionCluster).join(LogSource).filter(
            LogSource.service_id == service_id
        ).count()
        
        if exception_count == 0:
            logger.info(f"First exception for service {service_id}, triggering indexing")
            return True
        
        # Check if code has changed
        current_commit = _get_current_commit_sha(service.git_repo_path, service.git_branch)
        last_indexed_commit = _get_last_indexed_commit(service_id)
        
        if current_commit != last_indexed_commit:
            logger.info(f"Code changed for service {service_id}, triggering indexing")
            return True
        
        # Check time-based refresh (e.g., every 1 hour)
        if service.last_code_indexing:
            time_since_last = datetime.utcnow() - service.last_code_indexing
            if time_since_last >= timedelta(hours=1):
                logger.info(f"Periodic refresh due for service {service_id}")
                return True
        
        return False


# Cache indexing status in Redis
def _is_code_indexed_recently(service_id: str) -> bool:
    """Check if code was indexed recently (cached in Redis)"""
    from src.storage.redis_client import redis_client
    
    cache_key = f"code_indexed:{service_id}"
    cached = redis_client.get(cache_key)
    
    if cached:
        return True
    
    return False


def _mark_code_as_indexed(service_id: str, ttl: int = 3600):
    """Mark code as indexed in cache (1 hour TTL)"""
    from src.storage.redis_client import redis_client
    
    cache_key = f"code_indexed:{service_id}"
    redis_client.setex(cache_key, ttl, "1")
```

**Pros:**
- ✅ **Best of both worlds** - Immediate + periodic
- ✅ **Efficient** - Caches indexing status
- ✅ **Flexible** - Multiple trigger conditions
- ✅ **Smart** - Adapts to usage patterns

**Cons:**
- ⚠️ **Complex** - More logic to maintain
- ⚠️ **Cache dependency** - Requires Redis
- ⚠️ **Edge cases** - Cache invalidation issues

---

### Approach 4: Webhook-Based Indexing (Advanced)

**Trigger Point:** Git webhook on code push/merge

**Flow:**
```
Code Push → Git Webhook → API Endpoint → Trigger Indexing → Update Status
```

**Implementation:**

```python
# In api.py - Add webhook endpoint

@router.post("/webhooks/git/{service_id}")
async def handle_git_webhook(
    service_id: str,
    payload: Dict[str, Any],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Handle Git webhook for code changes.
    
    Supported platforms:
    - GitHub
    - GitLab
    - Bitbucket
    """
    logger.info(f"Received Git webhook for service {service_id}")
    
    # Validate service exists
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    # Parse webhook payload (GitHub example)
    if 'ref' in payload:  # GitHub push event
        branch = payload['ref'].split('/')[-1]
        
        # Check if this is the branch we're tracking
        if branch == service.git_branch:
            logger.info(f"Code pushed to tracked branch {branch}, triggering indexing")
            
            # Trigger indexing asynchronously
            background_tasks.add_task(
                index_code_repository.delay,
                service_id=service_id,
                trigger_reason='git_webhook',
                commit_sha=payload.get('after')
            )
            
            return {
                "status": "accepted",
                "message": "Code indexing triggered",
                "service_id": service_id
            }
    
    return {"status": "ignored", "reason": "not_tracked_branch"}


# Configure webhook in GitHub/GitLab:
# URL: https://your-domain.com/api/v1/webhooks/git/{service_id}
# Events: push, merge
# Secret: Optional for validation
```

**Pros:**
- ✅ **Real-time** - Index immediately on code push
- ✅ **Accurate** - Triggered by actual code changes
- ✅ **Efficient** - No polling or checking needed
- ✅ **Scalable** - Works for any number of services

**Cons:**
- ⚠️ **Setup required** - Need to configure webhooks
- ⚠️ **External dependency** - Relies on Git platform
- ⚠️ **Network dependency** - Webhook must reach server
- ⚠️ **Security** - Need to validate webhook authenticity

---

## 🏗️ Recommended Implementation Strategy

### Phase 1: Remove Scheduled Indexing ✅

**Step 1: Disable scheduled code indexing in ServiceScheduler**

```python
# In service_scheduler.py

def schedule_service_tasks(self) -> Dict[str, Any]:
    """Schedule tasks for all active services"""
    stats = {
        'services_processed': 0,
        'log_fetch_tasks_scheduled': 0,
        'rca_tasks_scheduled': 0,
        # Remove: 'code_indexing_tasks_scheduled': 0,
        'errors': []
    }
    
    try:
        with get_db() as db:
            services = db.query(Service).filter(Service.is_active == True).all()
            
            for service in services:
                try:
                    stats['services_processed'] += 1
                    
                    # Schedule log fetch tasks
                    if self._should_fetch_logs(service):
                        self._schedule_log_fetch(service)
                        stats['log_fetch_tasks_scheduled'] += 1
                    
                    # Schedule RCA generation
                    if self._should_generate_rca(service):
                        self._schedule_rca_generation(service)
                        stats['rca_tasks_scheduled'] += 1
                    
                    # REMOVED: Scheduled code indexing
                    # if self._should_index_code(service):
                    #     self._schedule_code_indexing(service)
                    #     stats['code_indexing_tasks_scheduled'] += 1
                    
                except Exception as e:
                    logger.error(f"Error scheduling tasks for service {service.id}: {e}")
                    stats['errors'].append(str(e))
    
    except Exception as e:
        logger.error(f"Error in service scheduler: {e}")
        stats['errors'].append(str(e))
    
    return stats
```

**Step 2: Remove code indexing interval from Service model**

```python
# In models.py - Service model

class Service(Base):
    __tablename__ = "services"
    
    # ... existing fields ...
    
    # REMOVE these fields:
    # code_indexing_interval_hours = Column(Integer, default=24)
    # last_code_indexing = Column(DateTime)
    
    # ADD new fields for on-demand indexing:
    code_indexing_status = Column(String, default='not_indexed')  # not_indexed, indexing, completed, failed
    code_indexing_trigger = Column(String)  # exception_detected, pre_rca, manual, webhook
    last_indexed_commit = Column(String)  # Git commit SHA
```

### Phase 2: Implement On-Demand Indexing ✅

**Recommended: Approach 1 + Approach 3 (Hybrid)**

**Step 1: Add indexing logic to log processing**

```python
# In tasks.py - fetch_and_process_logs

@celery_app.task(name='tasks.fetch_and_process_logs', bind=True)
def fetch_and_process_logs(self, service_id: str = None, log_source_id: str = None):
    # ... existing log processing code ...
    
    # After processing and detecting exceptions
    if total_stats['exceptions_found'] > 0 and service_id:
        # Check if code indexing is needed
        if _should_index_code_for_service(service_id):
            logger.info(f"Triggering code indexing for service {service_id}")
            
            # Mark as indexing in progress
            _mark_indexing_in_progress(service_id)
            
            # Trigger indexing asynchronously
            index_code_repository.apply_async(
                kwargs={
                    'service_id': service_id,
                    'trigger_reason': 'exception_detected',
                    'force_full': False
                },
                priority=7  # High priority
            )
    
    return total_stats
```

**Step 2: Add helper functions**

```python
# In tasks.py

def _should_index_code_for_service(service_id: str) -> bool:
    """Determine if code indexing is needed"""
    with get_db() as db:
        service = db.query(Service).filter(Service.id == service_id).first()
        
        if not service or not service.git_repo_path:
            return False
        
        # Check if already indexing
        if service.code_indexing_status == 'indexing':
            return False
        
        # Check minimum interval (5 minutes)
        if service.last_code_indexing:
            time_since_last = datetime.utcnow() - service.last_code_indexing
            if time_since_last < timedelta(minutes=5):
                return False
        
        # Check if code changed
        try:
            from src.services.code_indexer import CodeIndexer
            indexer = CodeIndexer(service.git_repo_path, service.git_branch)
            current_commit = indexer.commit_sha
            
            if current_commit == service.last_indexed_commit:
                logger.info(f"Code unchanged for service {service_id}")
                return False
        except Exception as e:
            logger.error(f"Error checking commit SHA: {e}")
            # Index anyway if we can't determine
            return True
        
        return True


def _mark_indexing_in_progress(service_id: str):
    """Mark service as currently indexing"""
    with get_db() as db:
        db.query(Service).filter(Service.id == service_id).update({
            'code_indexing_status': 'indexing',
            'updated_at': datetime.utcnow()
        })
        db.commit()


def _mark_indexing_complete(service_id: str, commit_sha: str):
    """Mark service indexing as complete"""
    with get_db() as db:
        db.query(Service).filter(Service.id == service_id).update({
            'code_indexing_status': 'completed',
            'last_code_indexing': datetime.utcnow(),
            'last_indexed_commit': commit_sha,
            'updated_at': datetime.utcnow()
        })
        db.commit()


def _mark_indexing_failed(service_id: str, error: str):
    """Mark service indexing as failed"""
    with get_db() as db:
        db.query(Service).filter(Service.id == service_id).update({
            'code_indexing_status': 'failed',
            'code_indexing_error': error,
            'updated_at': datetime.utcnow()
        })
        db.commit()
```

**Step 3: Update index_code_repository task**

```python
# In tasks.py

@celery_app.task(name='tasks.index_code_repository', bind=True)
def index_code_repository(
    self,
    service_id: str,
    trigger_reason: str = 'manual',
    force_full: bool = False
) -> Dict[str, Any]:
    """
    Index code repository for a service.
    
    Args:
        service_id: Service ID to index
        trigger_reason: Why indexing was triggered
        force_full: Force full indexing (default: incremental)
    """
    task_id = self.request.id
    logger.info(f"[Task {task_id}] Starting code indexing for service {service_id}")
    logger.info(f"[Task {task_id}] Trigger reason: {trigger_reason}")
    
    try:
        with get_db() as db:
            service = db.query(Service).filter(Service.id == service_id).first()
            
            if not service:
                error_msg = f"Service {service_id} not found"
                logger.error(f"[Task {task_id}] {error_msg}")
                return {'status': 'error', 'error': error_msg}
            
            if not service.git_repo_path:
                error_msg = f"No Git repository configured for service {service_id}"
                logger.error(f"[Task {task_id}] {error_msg}")
                _mark_indexing_failed(service_id, error_msg)
                return {'status': 'error', 'error': error_msg}
            
            # Initialize indexer
            from src.services.code_indexer import CodeIndexer
            indexer = CodeIndexer(
                repo_path=service.git_repo_path,
                version=service.git_branch or 'main'
            )
            
            # Index repository
            stats = indexer.index_repository(
                languages=['python', 'java'],
                force_full=force_full
            )
            
            # Mark as complete
            _mark_indexing_complete(service_id, indexer.commit_sha)
            
            logger.info(f"[Task {task_id}] Code indexing completed: {stats}")
            
            return {
                'status': 'success',
                'task_id': task_id,
                'service_id': service_id,
                'trigger_reason': trigger_reason,
                'stats': stats,
                'commit_sha': indexer.commit_sha
            }
            
    except Exception as e:
        error_msg = f"Code indexing failed: {str(e)}"
        logger.error(f"[Task {task_id}] {error_msg}", exc_info=True)
        _mark_indexing_failed(service_id, error_msg)
        
        return {
            'status': 'error',
            'task_id': task_id,
            'service_id': service_id,
            'error': error_msg
        }
```

### Phase 3: Add Manual Trigger (Optional) ✅

**Add API endpoint for manual indexing**

```python
# In api.py

@router.post("/services/{service_id}/index-code")
async def trigger_code_indexing(
    service_id: str,
    force_full: bool = False,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Manually trigger code indexing for a service.
    
    Args:
        service_id: Service ID to index
        force_full: Force full indexing (default: incremental)
    """
    # Validate service exists
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    if not service.git_repo_path:
        raise HTTPException(
            status_code=400,
            detail="No Git repository configured for this service"
        )
    
    # Check if already indexing
    if service.code_indexing_status == 'indexing':
        raise HTTPException(
            status_code=409,
            detail="Code indexing already in progress"
        )
    
    # Trigger indexing
    task = index_code_repository.apply_async(
        kwargs={
            'service_id': service_id,
            'trigger_reason': 'manual',
            'force_full': force_full
        }
    )
    
    return {
        "message": "Code indexing triggered",
        "service_id": service_id,
        "task_id": task.id,
        "force_full": force_full
    }


@router.get("/services/{service_id}/indexing-status")
async def get_indexing_status(
    service_id: str,
    db: Session = Depends(get_db)
):
    """Get code indexing status for a service"""
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    return {
        "service_id": service_id,
        "status": service.code_indexing_status,
        "last_indexed_at": service.last_code_indexing,
        "last_indexed_commit": service.last_indexed_commit,
        "git_repo_path": service.git_repo_path,
        "git_branch": service.git_branch
    }
```

---

## 📊 Comparison Matrix

| Approach | Trigger | Timing | Complexity | Resource Usage | Accuracy |
|----------|---------|--------|------------|----------------|----------|
| **Scheduled** | Time-based | Periodic | Low | High (wasteful) | Medium |
| **On Exception** | Exception detected | Immediate | Medium | Medium | High |
| **Before RCA** | RCA trigger | Delayed | Medium | Low | Very High |
| **Hybrid** | Multiple | Mixed | High | Low | Very High |
| **Webhook** | Git push | Real-time | High | Very Low | Perfect |

---

## ✅ Benefits of On-Demand Indexing

### 1. Resource Efficiency
- **No wasted indexing** - Only index when needed
- **Reduced CPU usage** - No periodic background jobs
- **Lower storage I/O** - Less frequent database writes
- **Better scalability** - Resources scale with actual usage

### 2. Accuracy
- **Fresh code context** - Always have latest code for RCA
- **No stale data** - Code indexed when actually needed
- **Commit-aware** - Track exact code version
- **Change detection** - Only index when code changes

### 3. User Experience
- **Faster RCA** - Code already indexed when needed
- **Better insights** - RCA based on current code
- **Predictable** - Clear trigger points
- **Transparent** - Users see indexing status

### 4. Operational
- **Easier debugging** - Clear cause-effect relationship
- **Better monitoring** - Track indexing per exception
- **Audit trail** - Know why indexing was triggered
- **Flexible** - Easy to add new triggers

---

## 🔧 Configuration

### Environment Variables

```bash
# Code indexing settings
CODE_INDEXING_MIN_INTERVAL_MINUTES=5  # Minimum time between indexing
CODE_INDEXING_TIMEOUT_SECONDS=300     # Max time for indexing task
CODE_INDEXING_RETRY_ATTEMPTS=3        # Retry failed indexing

# Trigger settings
INDEX_ON_EXCEPTION=true               # Trigger on exception detection
INDEX_BEFORE_RCA=false                # Trigger before RCA (optional)
INDEX_ON_FIRST_EXCEPTION=true         # Always index on first exception

# Cache settings (for hybrid approach)
CODE_INDEX_CACHE_TTL_SECONDS=3600     # Cache indexing status (1 hour)
```

### Service Configuration

```python
# In Service model
class Service(Base):
    # ... existing fields ...
    
    # Code indexing configuration
    git_repo_path = Column(String)
    git_branch = Column(String, default='main')
    code_indexing_enabled = Column(Boolean, default=True)
    code_indexing_status = Column(String, default='not_indexed')
    code_indexing_trigger = Column(String)
    last_code_indexing = Column(DateTime)
    last_indexed_commit = Column(String)
    code_indexing_error = Column(Text)
```

---

## 🐛 Troubleshooting

### Issue 1: Indexing Triggered Too Frequently

**Symptom:** Code indexing runs multiple times in short period

**Solution:**
- Increase `CODE_INDEXING_MIN_INTERVAL_MINUTES`
- Check commit SHA comparison logic
- Verify caching is working

### Issue 2: Indexing Never Triggers

**Symptom:** Exceptions detected but no indexing happens

**Solution:**
- Check `code_indexing_enabled` flag
- Verify `git_repo_path` is configured
- Check logs for errors in `_should_index_code_for_service`

### Issue 3: RCA Generated Without Fresh Code

**Symptom:** RCA uses old code context

**Solution:**
- Enable `INDEX_BEFORE_RCA` flag
- Use synchronous indexing before RCA
- Check indexing completion status

### Issue 4: Indexing Fails Silently

**Symptom:** Indexing status shows "failed" but no error

**Solution:**
- Check `code_indexing_error` field
- Review task logs
- Verify Git repository accessibility

---

## 📈 Monitoring & Metrics

### Key Metrics to Track

```python
# Metrics to collect

# Indexing frequency
- code_indexing_triggered_total (counter)
- code_indexing_trigger_reason (labels: exception, rca, manual, webhook)

# Indexing performance
- code_indexing_duration_seconds (histogram)
- code_indexing_files_processed (gauge)
- code_indexing_blocks_created (gauge)

# Indexing success
- code_indexing_success_total (counter)
- code_indexing_failure_total (counter)
- code_indexing_retry_total (counter)

# Resource usage
- code_indexing_cpu_usage (gauge)
- code_indexing_memory_usage (gauge)
- code_indexing_disk_io (gauge)
```

### Dashboard Queries

```sql
-- Indexing frequency by service
SELECT 
    service_id,
    COUNT(*) as indexing_count,
    AVG(duration_seconds) as avg_duration
FROM code_indexing_logs
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY service_id;

-- Indexing trigger reasons
SELECT 
    trigger_reason,
    COUNT(*) as count,
    AVG(duration_seconds) as avg_duration
FROM code_indexing_logs
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY trigger_reason;

-- Failed indexing attempts
SELECT 
    service_id,
    error_message,
    COUNT(*) as failure_count
FROM code_indexing_logs
WHERE status = 'failed'
    AND created_at > NOW() - INTERVAL '24 hours'
GROUP BY service_id, error_message;
```

---

## 🎯 Migration Checklist

### Pre-Migration
- [ ] Backup current indexing metadata
- [ ] Document current indexing intervals
- [ ] Review service configurations
- [ ] Test on-demand indexing in staging

### Migration Steps
- [ ] Remove scheduled indexing from `ServiceScheduler`
- [ ] Add new fields to `Service` model
- [ ] Run database migrations
- [ ] Implement `_should_index_code_for_service` logic
- [ ] Update `fetch_and_process_logs` task
- [ ] Update `index_code_repository` task
- [ ] Add manual trigger API endpoint
- [ ] Update monitoring dashboards

### Post-Migration
- [ ] Monitor indexing frequency
- [ ] Verify RCA quality
- [ ] Check resource usage
- [ ] Collect user feedback
- [ ] Optimize trigger conditions

---

## 🎓 Best Practices

### 1. Indexing Strategy
- ✅ Use incremental indexing by default
- ✅ Check commit SHA before indexing
- ✅ Set minimum interval to avoid spam
- ✅ Cache indexing status
- ✅ Handle failures gracefully

### 2. Performance
- ✅ Run indexing asynchronously
- ✅ Use high priority for exception-triggered indexing
- ✅ Limit concurrent indexing tasks
- ✅ Monitor indexing duration
- ✅ Optimize for large repositories

### 3. Reliability
- ✅ Retry failed indexing attempts
- ✅ Log all indexing events
- ✅ Track indexing status
- ✅ Alert on repeated failures
- ✅ Provide manual override

### 4. User Experience
- ✅ Show indexing status in UI
- ✅ Provide manual trigger button
- ✅ Display last indexed commit
- ✅ Show indexing progress
- ✅ Explain why indexing was triggered

---

## 🎯 Summary

**On-demand code indexing provides:**

1. **Efficiency** - Only index when needed, saving resources
2. **Accuracy** - Always have fresh code context for RCA
3. **Flexibility** - Multiple trigger points (exception, RCA, manual, webhook)
4. **Transparency** - Clear trigger reasons and status tracking
5. **Scalability** - Resources scale with actual usage
6. **Reliability** - Retry logic and error handling

**Recommended approach: Hybrid (Exception Detection + Smart Caching)**

This ensures code is indexed when exceptions occur, while avoiding redundant indexing through intelligent caching and commit SHA tracking.

**Result: Accurate, efficient, and timely code indexing that provides fresh context for high-quality RCA generation!** 🚀
