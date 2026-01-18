# Dynamic Celery Beat Scheduling via UI

## 🎯 **Goal**

Enable users to configure Celery Beat task schedules through the UI without code changes.

---

## 🏗️ **Architecture Options**

### **Option 1: SQLAlchemy Beat Scheduler (Recommended)**

Use a custom database-backed scheduler that reads schedules from PostgreSQL.

**Pros:**
- ✅ No additional dependencies
- ✅ Works with existing SQLAlchemy models
- ✅ Full control over implementation
- ✅ UI can directly update database

**Cons:**
- ❌ Need to implement custom scheduler
- ❌ More code to maintain

### **Option 2: Django-Celery-Beat (Alternative)**

Use the popular `django-celery-beat` package (works with SQLAlchemy too).

**Pros:**
- ✅ Battle-tested solution
- ✅ Built-in admin interface
- ✅ Well documented

**Cons:**
- ❌ Requires Django (you're using FastAPI)
- ❌ Overkill for simple use case

### **Option 3: Redis-Based Scheduler**

Store schedules in Redis and use `celery-redbeat`.

**Pros:**
- ✅ Fast and lightweight
- ✅ Easy to implement
- ✅ No database changes

**Cons:**
- ❌ Schedules not persisted in main database
- ❌ Additional dependency

---

## ✅ **Recommended: Custom SQLAlchemy Scheduler**

Let's implement a custom database-backed Celery Beat scheduler.

---

## 📊 **Database Schema**

### **New Table: `task_schedules`**

```python
# src/storage/models.py

class TaskSchedule(Base):
    __tablename__ = 'task_schedules'
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    service_id = Column(String, ForeignKey('services.id'), nullable=False)
    
    # Task Configuration
    task_name = Column(String, nullable=False)  # 'fetch_logs', 'generate_rca', 'index_code'
    task_path = Column(String, nullable=False)  # 'src.services.tasks.fetch_and_process_logs'
    
    # Schedule Configuration
    schedule_type = Column(String, default='cron')  # 'cron' or 'interval'
    cron_expression = Column(String)  # '*/15 * * * *' (every 15 minutes)
    interval_seconds = Column(Integer)  # Alternative: 900 (15 minutes)
    
    # Status
    enabled = Column(Boolean, default=True)
    last_run = Column(DateTime)
    next_run = Column(DateTime)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    service = relationship("Service", back_populates="task_schedules")
```

### **Update Service Model**

```python
# src/storage/models.py

class Service(Base):
    # ... existing fields ...
    
    # Relationship
    task_schedules = relationship("TaskSchedule", back_populates="service", cascade="all, delete-orphan")
```

---

## 🔧 **Custom Celery Beat Scheduler**

### **File: `src/services/database_scheduler.py`**

```python
"""
Custom Celery Beat Scheduler that reads schedules from database.
"""
from celery.beat import Scheduler, ScheduleEntry
from celery.schedules import crontab, schedule
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from src.storage.database import SessionLocal
from src.storage.models import TaskSchedule
import logging

logger = logging.getLogger(__name__)


class DatabaseScheduleEntry(ScheduleEntry):
    """Schedule entry that reads from database"""
    
    def __init__(self, task_schedule: TaskSchedule, app=None):
        self.task_schedule_id = task_schedule.id
        self.service_id = task_schedule.service_id
        
        # Parse schedule
        if task_schedule.schedule_type == 'cron':
            schedule_obj = self._parse_cron(task_schedule.cron_expression)
        else:
            schedule_obj = schedule(run_every=timedelta(seconds=task_schedule.interval_seconds))
        
        super().__init__(
            name=f"{task_schedule.task_name}_{task_schedule.service_id}",
            task=task_schedule.task_path,
            schedule=schedule_obj,
            args=(task_schedule.service_id,),  # Pass service_id to task
            kwargs={},
            options={'queue': 'default'},
            app=app,
        )
    
    def _parse_cron(self, cron_expr: str):
        """Parse cron expression like '*/15 * * * *'"""
        parts = cron_expr.split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: {cron_expr}")
        
        minute, hour, day_of_month, month, day_of_week = parts
        
        return crontab(
            minute=minute,
            hour=hour,
            day_of_month=day_of_month,
            month_of_year=month,
            day_of_week=day_of_week,
        )


class DatabaseScheduler(Scheduler):
    """Celery Beat Scheduler that reads from PostgreSQL database"""
    
    def __init__(self, *args, **kwargs):
        self.db: Session = SessionLocal()
        super().__init__(*args, **kwargs)
        logger.info("DatabaseScheduler initialized")
    
    def setup_schedule(self):
        """Load schedules from database"""
        self.merge_inplace(self.get_from_database())
    
    def get_from_database(self):
        """Fetch all enabled schedules from database"""
        schedules = {}
        
        try:
            task_schedules = self.db.query(TaskSchedule).filter(
                TaskSchedule.enabled == True
            ).all()
            
            for task_schedule in task_schedules:
                entry = DatabaseScheduleEntry(task_schedule, app=self.app)
                schedules[entry.name] = entry
                logger.info(f"Loaded schedule: {entry.name} - {task_schedule.cron_expression}")
        
        except Exception as e:
            logger.error(f"Error loading schedules from database: {e}")
        
        return schedules
    
    def tick(self, *args, **kwargs):
        """Override tick to reload schedules periodically"""
        # Reload schedules every 60 seconds to pick up changes
        if not hasattr(self, '_last_reload') or \
           (datetime.utcnow() - self._last_reload).seconds > 60:
            logger.info("Reloading schedules from database...")
            self.setup_schedule()
            self._last_reload = datetime.utcnow()
        
        return super().tick(*args, **kwargs)
    
    def close(self):
        """Close database connection"""
        self.db.close()
        super().close()
```

---

## ⚙️ **Celery Configuration**

### **File: `src/services/celery_config.py`**

```python
"""
Celery configuration with database scheduler.
"""
from celery import Celery
from src.config import settings

app = Celery('luffy')

# Use database scheduler
app.conf.update(
    broker_url=settings.redis_url,
    result_backend=settings.redis_url,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Use custom database scheduler
    beat_scheduler='src.services.database_scheduler:DatabaseScheduler',
    
    # Beat schedule sync interval (check database every 60 seconds)
    beat_max_loop_interval=60,
)

# Import tasks
app.autodiscover_tasks(['src.services'])
```

---

## 🔌 **API Endpoints**

### **File: `src/services/api_task_scheduling.py`**

```python
"""
API endpoints for managing Celery Beat schedules.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from src.storage.database import get_db
from src.storage.models import TaskSchedule, Service
import uuid

router = APIRouter(prefix="/api/v1/task-scheduling", tags=["Task Scheduling"])


class TaskScheduleRequest(BaseModel):
    task_name: str = Field(..., description="Task name: 'fetch_logs', 'generate_rca', 'index_code'")
    schedule_type: str = Field(default='cron', description="'cron' or 'interval'")
    cron_expression: Optional[str] = Field(None, description="Cron expression: '*/15 * * * *'")
    interval_seconds: Optional[int] = Field(None, description="Interval in seconds: 900")
    enabled: bool = Field(default=True)


class TaskScheduleResponse(BaseModel):
    id: str
    service_id: str
    task_name: str
    task_path: str
    schedule_type: str
    cron_expression: Optional[str]
    interval_seconds: Optional[int]
    enabled: bool
    last_run: Optional[datetime]
    next_run: Optional[datetime]
    created_at: datetime
    updated_at: datetime


# Task name to path mapping
TASK_PATHS = {
    'fetch_logs': 'src.services.tasks.fetch_and_process_logs',
    'generate_rca': 'src.services.tasks.generate_rca_for_clusters',
    'index_code': 'src.services.tasks.index_code_repository',
}


@router.get("/services/{service_id}/schedules", response_model=List[TaskScheduleResponse])
def get_service_schedules(
    service_id: str,
    db: Session = Depends(get_db)
):
    """Get all task schedules for a service"""
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    schedules = db.query(TaskSchedule).filter(
        TaskSchedule.service_id == service_id
    ).all()
    
    return schedules


@router.post("/services/{service_id}/schedules", response_model=TaskScheduleResponse)
def create_task_schedule(
    service_id: str,
    request: TaskScheduleRequest,
    db: Session = Depends(get_db)
):
    """Create a new task schedule"""
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    # Validate task name
    if request.task_name not in TASK_PATHS:
        raise HTTPException(status_code=400, detail=f"Invalid task name: {request.task_name}")
    
    # Validate schedule
    if request.schedule_type == 'cron' and not request.cron_expression:
        raise HTTPException(status_code=400, detail="cron_expression required for cron schedule")
    if request.schedule_type == 'interval' and not request.interval_seconds:
        raise HTTPException(status_code=400, detail="interval_seconds required for interval schedule")
    
    # Create schedule
    schedule = TaskSchedule(
        id=str(uuid.uuid4()),
        service_id=service_id,
        task_name=request.task_name,
        task_path=TASK_PATHS[request.task_name],
        schedule_type=request.schedule_type,
        cron_expression=request.cron_expression,
        interval_seconds=request.interval_seconds,
        enabled=request.enabled,
    )
    
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    
    return schedule


@router.put("/schedules/{schedule_id}", response_model=TaskScheduleResponse)
def update_task_schedule(
    schedule_id: str,
    request: TaskScheduleRequest,
    db: Session = Depends(get_db)
):
    """Update an existing task schedule"""
    schedule = db.query(TaskSchedule).filter(TaskSchedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    # Update fields
    if request.schedule_type:
        schedule.schedule_type = request.schedule_type
    if request.cron_expression:
        schedule.cron_expression = request.cron_expression
    if request.interval_seconds:
        schedule.interval_seconds = request.interval_seconds
    if request.enabled is not None:
        schedule.enabled = request.enabled
    
    schedule.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(schedule)
    
    return schedule


@router.delete("/schedules/{schedule_id}")
def delete_task_schedule(
    schedule_id: str,
    db: Session = Depends(get_db)
):
    """Delete a task schedule"""
    schedule = db.query(TaskSchedule).filter(TaskSchedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    db.delete(schedule)
    db.commit()
    
    return {"message": "Schedule deleted successfully"}


@router.post("/schedules/{schedule_id}/toggle")
def toggle_task_schedule(
    schedule_id: str,
    enabled: bool,
    db: Session = Depends(get_db)
):
    """Enable or disable a task schedule"""
    schedule = db.query(TaskSchedule).filter(TaskSchedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    schedule.enabled = enabled
    schedule.updated_at = datetime.utcnow()
    
    db.commit()
    
    return {"message": f"Schedule {'enabled' if enabled else 'disabled'} successfully"}
```

---

## 🎨 **Frontend UI Components**

### **Schedule Configuration Card**

```tsx
// Add to TaskManagement.tsx

const [scheduleModalOpen, setScheduleModalOpen] = useState(false);
const [editingSchedule, setEditingSchedule] = useState<any>(null);

// Fetch schedules
const { data: schedules = [] } = useQuery({
  queryKey: ['task-schedules', selectedService],
  queryFn: () => selectedService ? taskSchedulingAPI.getSchedules(selectedService) : Promise.resolve([]),
  enabled: !!selectedService,
});

// Schedule configuration modal
<Modal
  title="Configure Task Schedule"
  open={scheduleModalOpen}
  onCancel={() => setScheduleModalOpen(false)}
  onOk={handleScheduleSave}
>
  <Form layout="vertical">
    <Form.Item label="Task">
      <Select>
        <Select.Option value="fetch_logs">Log Fetch & Processing</Select.Option>
        <Select.Option value="generate_rca">RCA Generation</Select.Option>
        <Select.Option value="index_code">Code Indexing</Select.Option>
      </Select>
    </Form.Item>
    
    <Form.Item label="Schedule Type">
      <Radio.Group>
        <Radio value="cron">Cron Expression</Radio>
        <Radio value="interval">Interval</Radio>
      </Radio.Group>
    </Form.Item>
    
    <Form.Item label="Cron Expression" help="Example: */15 * * * * (every 15 minutes)">
      <Input placeholder="*/15 * * * *" />
    </Form.Item>
    
    <Form.Item label="Or Interval (seconds)">
      <InputNumber min={60} max={86400} />
    </Form.Item>
    
    <Form.Item label="Enabled">
      <Switch />
    </Form.Item>
  </Form>
</Modal>

// Schedule list
<Table
  dataSource={schedules}
  columns={[
    { title: 'Task', dataIndex: 'task_name' },
    { title: 'Schedule', render: (record) => 
        record.schedule_type === 'cron' 
          ? record.cron_expression 
          : `Every ${record.interval_seconds}s`
    },
    { title: 'Status', render: (record) => 
        <Switch checked={record.enabled} onChange={(checked) => toggleSchedule(record.id, checked)} />
    },
    { title: 'Actions', render: (record) => 
        <Button onClick={() => editSchedule(record)}>Edit</Button>
    },
  ]}
/>
```

---

## 📋 **Migration Script**

```python
# scripts/migrate_task_schedules.py

"""
Migration to create task_schedules table.
"""
from sqlalchemy import create_engine, text
from src.config import settings

def migrate():
    engine = create_engine(settings.database_url)
    
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS task_schedules (
                id VARCHAR PRIMARY KEY,
                service_id VARCHAR NOT NULL REFERENCES services(id) ON DELETE CASCADE,
                task_name VARCHAR NOT NULL,
                task_path VARCHAR NOT NULL,
                schedule_type VARCHAR DEFAULT 'cron',
                cron_expression VARCHAR,
                interval_seconds INTEGER,
                enabled BOOLEAN DEFAULT TRUE,
                last_run TIMESTAMP,
                next_run TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """))
        conn.commit()
        print("✅ task_schedules table created")

if __name__ == "__main__":
    migrate()
```

---

## 🚀 **Usage Example**

### **1. Create Schedule via API**

```bash
curl -X POST http://localhost:8000/api/v1/task-scheduling/services/web-app/schedules \
  -H "Content-Type: application/json" \
  -d '{
    "task_name": "fetch_logs",
    "schedule_type": "cron",
    "cron_expression": "*/15 * * * *",
    "enabled": true
  }'
```

### **2. Update Schedule**

```bash
curl -X PUT http://localhost:8000/api/v1/task-scheduling/schedules/{schedule_id} \
  -H "Content-Type: application/json" \
  -d '{
    "cron_expression": "*/30 * * * *"
  }'
```

### **3. Celery Beat Picks Up Changes**

- Celery Beat reloads schedules every 60 seconds
- New/updated schedules are applied automatically
- No restart required!

---

## ✅ **Benefits**

1. **Dynamic Configuration** - Change schedules without code changes
2. **Per-Service Schedules** - Each service can have different schedules
3. **UI Control** - Users can configure schedules through UI
4. **No Restart** - Changes applied automatically (within 60 seconds)
5. **Audit Trail** - All schedule changes tracked in database

---

## 🎯 **Summary**

**Implementation Steps:**
1. ✅ Create `task_schedules` table
2. ✅ Implement `DatabaseScheduler` class
3. ✅ Create API endpoints for schedule management
4. ✅ Update Celery config to use database scheduler
5. ✅ Add UI components for schedule configuration

**Result:**
- Users can configure Celery Beat schedules through UI
- Schedules stored in database
- Changes applied automatically without restart
- Full control over task scheduling per service

Would you like me to implement this solution?
