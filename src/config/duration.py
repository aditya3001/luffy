"""
Duration configuration utilities.
Provides flexible duration parsing and conversion for log fetch intervals.
"""
from datetime import timedelta
from typing import Union
from pydantic import BaseModel, Field, field_validator


class Duration(BaseModel):
    """
    Flexible duration class that supports minutes, hours, and days.
    
    Examples:
        Duration(minutes=30)  # 30 minutes
        Duration(hours=2)     # 2 hours
        Duration(days=1)      # 1 day
        Duration(hours=1, minutes=30)  # 1 hour 30 minutes
    """
    
    minutes: int = Field(default=0, ge=0, description="Duration in minutes")
    hours: int = Field(default=0, ge=0, description="Duration in hours")
    days: int = Field(default=0, ge=0, description="Duration in days")
    
    @field_validator('minutes', 'hours', 'days')
    @classmethod
    def validate_non_negative(cls, v: int) -> int:
        """Ensure all duration values are non-negative."""
        if v < 0:
            raise ValueError("Duration values must be non-negative")
        return v
    
    def to_timedelta(self) -> timedelta:
        """Convert to Python timedelta object."""
        return timedelta(days=self.days, hours=self.hours, minutes=self.minutes)
    
    def to_minutes(self) -> int:
        """Convert total duration to minutes."""
        return self.days * 24 * 60 + self.hours * 60 + self.minutes
    
    def to_hours(self) -> float:
        """Convert total duration to hours (as float)."""
        return self.to_minutes() / 60
    
    def to_seconds(self) -> int:
        """Convert total duration to seconds."""
        return self.to_minutes() * 60
    
    @classmethod
    def from_minutes(cls, minutes: int) -> 'Duration':
        """Create Duration from total minutes."""
        return cls(minutes=minutes)
    
    @classmethod
    def from_hours(cls, hours: int) -> 'Duration':
        """Create Duration from total hours."""
        return cls(hours=hours)
    
    @classmethod
    def from_days(cls, days: int) -> 'Duration':
        """Create Duration from total days."""
        return cls(days=days)
    
    @classmethod
    def from_string(cls, duration_str: str) -> 'Duration':
        """
        Parse duration from string format.
        
        Supported formats:
            "30m" or "30min" -> 30 minutes
            "2h" or "2hr" -> 2 hours
            "1d" or "1day" -> 1 day
            "1h30m" -> 1 hour 30 minutes
            "2d12h" -> 2 days 12 hours
        
        Args:
            duration_str: Duration string to parse
            
        Returns:
            Duration object
            
        Raises:
            ValueError: If format is invalid
        """
        duration_str = duration_str.lower().strip()
        
        days = 0
        hours = 0
        minutes = 0
        
        # Parse days
        if 'd' in duration_str:
            parts = duration_str.split('d')
            days = int(parts[0])
            duration_str = parts[1] if len(parts) > 1 else ''
        
        # Parse hours
        if 'h' in duration_str:
            parts = duration_str.split('h')
            hours = int(parts[0])
            duration_str = parts[1] if len(parts) > 1 else ''
        
        # Parse minutes
        if 'm' in duration_str:
            duration_str = duration_str.replace('min', 'm')
            parts = duration_str.split('m')
            if parts[0]:
                minutes = int(parts[0])
        
        if days == 0 and hours == 0 and minutes == 0:
            raise ValueError(f"Invalid duration format: {duration_str}")
        
        return cls(days=days, hours=hours, minutes=minutes)
    
    def __str__(self) -> str:
        """String representation of duration."""
        parts = []
        if self.days > 0:
            parts.append(f"{self.days}d")
        if self.hours > 0:
            parts.append(f"{self.hours}h")
        if self.minutes > 0:
            parts.append(f"{self.minutes}m")
        
        return " ".join(parts) if parts else "0m"
    
    def __repr__(self) -> str:
        """Detailed representation of duration."""
        return f"Duration(days={self.days}, hours={self.hours}, minutes={self.minutes})"
    
    def __bool__(self) -> bool:
        """Check if duration is non-zero."""
        return self.to_minutes() > 0


def parse_duration(value: Union[str, int, Duration]) -> Duration:
    """
    Parse duration from various input formats.
    
    Args:
        value: Duration as string, int (hours), or Duration object
        
    Returns:
        Duration object
        
    Examples:
        parse_duration("30m") -> Duration(minutes=30)
        parse_duration(2) -> Duration(hours=2)
        parse_duration(Duration(hours=1)) -> Duration(hours=1)
    """
    if isinstance(value, Duration):
        return value
    elif isinstance(value, str):
        return Duration.from_string(value)
    elif isinstance(value, int):
        # Default: treat int as hours for backward compatibility
        return Duration.from_hours(value)
    else:
        raise ValueError(f"Cannot parse duration from type {type(value)}")
