"""Task schemas and status definitions for JARVIS.

Defines the persistent Task structure and lifecycle statuses.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import time
import uuid


class TaskStatus(str, Enum):
    """The 9 canonical lifecycle statuses for persistent tasks."""
    PENDING = "PENDING"
    PLANNING = "PLANNING"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    VERIFYING = "VERIFYING"
    FAILED = "FAILED"
    RECOVERING = "RECOVERING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class TaskPriority(str, Enum):
    """Task execution priority levels."""
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class Task:
    """Persistent Task model representing long-running workflows.

    Task
    |-- ID
    |-- Objective
    |-- Status
    |-- Priority
    |-- Context
    |-- Plan
    |-- Current step
    |-- Completed steps
    |-- Failed steps
    |-- Retry count
    |-- Artifacts
    `-- Final result
    """
    id: str = field(default_factory=lambda: f"task_{uuid.uuid4().hex[:12]}")
    objective: str = ""
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    context: Dict[str, Any] = field(default_factory=dict)
    plan: List[Dict[str, Any]] = field(default_factory=list)
    current_step: Optional[int] = None
    completed_steps: List[Dict[str, Any]] = field(default_factory=list)
    failed_steps: List[Dict[str, Any]] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    final_result: Optional[Any] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes task into a dictionary suitable for JSON/SQLite storage."""
        return {
            "id": self.id,
            "objective": self.objective,
            "status": self.status.value if isinstance(self.status, TaskStatus) else str(self.status),
            "priority": self.priority.value if isinstance(self.priority, TaskPriority) else str(self.priority),
            "context": self.context,
            "plan": self.plan,
            "current_step": self.current_step,
            "completed_steps": self.completed_steps,
            "failed_steps": self.failed_steps,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "artifacts": self.artifacts,
            "final_result": self.final_result,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Task:
        """Deserializes task from a dictionary."""
        status_raw = data.get("status", TaskStatus.PENDING)
        try:
            status = TaskStatus(status_raw)
        except ValueError:
            status = TaskStatus.PENDING

        priority_raw = data.get("priority", TaskPriority.NORMAL)
        try:
            priority = TaskPriority(priority_raw)
        except ValueError:
            priority = TaskPriority.NORMAL

        return cls(
            id=data.get("id", f"task_{uuid.uuid4().hex[:12]}"),
            objective=data.get("objective", ""),
            status=status,
            priority=priority,
            context=data.get("context") or {},
            plan=data.get("plan") or [],
            current_step=data.get("current_step"),
            completed_steps=data.get("completed_steps") or [],
            failed_steps=data.get("failed_steps") or [],
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            artifacts=data.get("artifacts") or [],
            final_result=data.get("final_result"),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
        )
