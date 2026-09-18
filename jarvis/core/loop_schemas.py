"""Data schemas for the Central Autonomous Agent Loop.

Supports continuous state-feeding, observe-verify-recover sub-stages,
and dynamic replanning.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import time


class ActionStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    BLOCKED = "BLOCKED"


@dataclass
class LoopAction:
    """A discrete executable action within an agent plan."""
    action_id: str
    name: str
    target_tool: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    action_fn: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    status: ActionStatus = ActionStatus.PENDING
    status_message: str = ""
    output: Optional[Any] = None
    error: Optional[str] = None


@dataclass
class StepExecutionRecord:
    """Record of execution, observation, and ground-truth verification for a step."""
    action_id: str
    action_name: str
    success: bool
    output: Any
    error: Optional[str] = None
    observation: Dict[str, Any] = field(default_factory=dict)
    verified: bool = False
    verification_details: str = ""
    duration_ms: float = 0.0


@dataclass
class AgentLoopTask:
    """An autonomous task executing inside the agent loop."""
    task_id: str
    objective: str
    state: Dict[str, Any] = field(default_factory=dict)
    plan: List[LoopAction] = field(default_factory=list)
    completed_steps: List[StepExecutionRecord] = field(default_factory=list)
    current_step_index: int = 0
    active: bool = True
    status: str = "ACTIVE"   # ACTIVE, COMPLETED, BLOCKED, FAILED
    recovery_attempts: int = 0
    max_recovery_attempts: int = 3
    final_report: str = ""
    created_at: float = field(default_factory=time.time)
