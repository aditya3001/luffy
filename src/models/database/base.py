"""
Base database model classes and utilities.
Provides common functionality for all database models.
"""
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import Column, String, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session
import uuid


Base = declarative_base()


class BaseModel(Base):
    """
    Base model class with common fields and methods.
    All database models should inherit from this class.
    """
    __abstract__ = True
    
    # Common fields
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary."""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
    
    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """Update model instance from dictionary."""
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    @classmethod
    def create(cls, session: Session, **kwargs) -> 'BaseModel':
        """Create a new instance and save to database."""
        instance = cls(**kwargs)
        session.add(instance)
        session.commit()
        session.refresh(instance)
        return instance
    
    def save(self, session: Session) -> 'BaseModel':
        """Save current instance to database."""
        session.add(self)
        session.commit()
        session.refresh(self)
        return self
    
    def delete(self, session: Session) -> None:
        """Delete current instance from database."""
        session.delete(self)
        session.commit()


class UUIDMixin:
    """Mixin for models that use UUID as primary key."""
    
    @staticmethod
    def generate_id() -> str:
        """Generate a new UUID string."""
        return str(uuid.uuid4())


class TimestampMixin:
    """Mixin for models that need timestamp tracking."""
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class SoftDeleteMixin:
    """Mixin for models that support soft deletion."""
    
    deleted_at = Column(DateTime, nullable=True)
    is_deleted = Column(String, default=False)
    
    def soft_delete(self, session: Session) -> None:
        """Soft delete the record."""
        self.deleted_at = datetime.utcnow()
        self.is_deleted = True
        self.save(session)
    
    def restore(self, session: Session) -> None:
        """Restore a soft-deleted record."""
        self.deleted_at = None
        self.is_deleted = False
        self.save(session)


class AuditMixin:
    """Mixin for models that need audit trail."""
    
    created_by = Column(String, nullable=True)
    updated_by = Column(String, nullable=True)
    
    def set_audit_fields(self, user_id: str, is_create: bool = False) -> None:
        """Set audit fields for create/update operations."""
        if is_create:
            self.created_by = user_id
        self.updated_by = user_id
