"""Complex Task Engine & DAG Orchestration Schemas for JARVIS.

Defines models for graph nodes, statuses, error severity, and executive reports.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any, Callable, Dict, List, Optional
import uuid


class NodeStatus(str, Enum):
    """Lifecycle statuses for a task node in the dependency graph."""
    PENDING = "PENDING"
    WAITING_FOR_DEPENDENCY = "WAITING_FOR_DEPENDENCY"
    RUNNING = "RUNNING"
    OBSERVING = "OBSERVING"
    VERIFYING = "VERIFYING"
    RECOVERING = "RECOVERING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class ErrorSeverity(str, Enum):
    """Severity classification for collected errors."""
    LOW = "LOW"            # Non-blocking warnings, minor styling
    MEDIUM = "MEDIUM"      # Non-critical route glitch, slow response
    HIGH = "HIGH"          # Feature failure, endpoint 500
    CRITICAL = "CRITICAL"  # App crash, backend unresponsive, database down


@dataclass
class SubStageRecord:
    """Record of an observe, verify, or recover sub-stage."""
    stage_name: str        # "observe", "verify", "recover"
    status: str            # "SUCCESS", "FAILED", "INFO"
    detail: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class TaskNode:
    """A single node within the Directed Acyclic Graph (DAG)."""
    node_id: str
    name: str
    action: Optional[Callable[..., Any]] = None
    tool_name: Optional[str] = None
    arguments: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    status: NodeStatus = NodeStatus.PENDING
    status_message: str = ""
    result: Any = None
    error: Optional[str] = None
    attempts: int = 0
    max_attempts: int = 3
    has_sub_stages: bool = False
    sub_stages: List[SubStageRecord] = field(default_factory=list)
    output: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0


@dataclass
class CollectedIssue:
    """An issue identified during repository, service, or page inspection."""
    title: str
    description: str
    severity: ErrorSeverity
    source: str           # "backend", "frontend", "dependency", "page_inspection"
    recommended_fix: str = ""


@dataclass
class ExecutionReport:
    """Executive summary report produced after full DAG workflow completion."""
    workflow_name: str
    overall_status: str   # "READY", "ACTION_REQUIRED", "FAILED"
    total_nodes: int
    completed_nodes: int
    failed_nodes: int
    issues: List[CollectedIssue] = field(default_factory=list)
    highest_severity: Optional[ErrorSeverity] = None
    summary_text: str = ""
    artifacts: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
