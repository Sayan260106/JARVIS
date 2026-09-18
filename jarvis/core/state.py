"""Execution state and memory tracking for the JARVIS agent loop."""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from jarvis.core.schemas import (
    TaskObjective,
    ExecutionPlan,
    PlanStep,
    StepStatus,
    Observation,
    VerificationResult,
    RecoveryAction,
)


class LoopPhase(str, Enum):
    """The phases of the core agent loop."""
    IDLE = "IDLE"
    UNDERSTANDING = "UNDERSTANDING"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    OBSERVING = "OBSERVING"
    VERIFYING = "VERIFYING"
    RECOVERING = "RECOVERING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    AWAITING_USER = "AWAITING_USER"
    CANCELLED = "CANCELLED"
    PAUSED = "PAUSED"


@dataclass
class StepRecord:
    """Historical execution record of a single step attempt."""
    step: PlanStep
    observation: Observation
    verification: VerificationResult
    recovery: Optional[RecoveryAction] = None


@dataclass
class AgentSessionState:
    """Complete runtime state of an active JARVIS session."""
    task_id: str = ""
    phase: LoopPhase = LoopPhase.IDLE
    objective: Optional[TaskObjective] = None
    plan: Optional[ExecutionPlan] = None
    current_step_index: int = 0
    history: List[StepRecord] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    context_state: Dict[str, Any] = field(default_factory=dict)
    final_result: Optional[str] = None
    error_message: Optional[str] = None
    is_cancelled: bool = False
    is_paused: bool = False

    @property
    def current_step(self) -> Optional[PlanStep]:
        if self.plan and 0 <= self.current_step_index < len(self.plan.steps):
            return self.plan.steps[self.current_step_index]
        return None

    @property
    def completed_step_ids(self) -> set[str]:
        ids = {r.step.step_id for r in self.history if r.verification.passed}
        if self.plan:
            ids.update(s.step_id for s in self.plan.steps if s.status == StepStatus.SUCCESS)
        return ids


    def is_finished(self) -> bool:
        return self.phase in (LoopPhase.COMPLETED, LoopPhase.FAILED, LoopPhase.AWAITING_USER, LoopPhase.CANCELLED)

