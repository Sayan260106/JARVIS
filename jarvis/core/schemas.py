"""Core data schemas for the JARVIS agent architecture.

Defines the typed contracts governing Understand, Plan, Act, Observe, and Recover.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import time
import uuid


class SubsystemType(str, Enum):
    """The three core execution subsystems in JARVIS roadmap."""
    LOCAL = "LOCAL_INTELLIGENCE"    # Ollama, local SLMs, embeddings, vector store
    WEB = "WEB_INTELLIGENCE"        # Browser, Playwright, search, cloud LLM
    SYSTEM = "COMPUTER_CONTROL"     # Windows OS, PowerShell, processes, files


class IntentCategory(str, Enum):
    """Classification of user prompt."""
    QUERY = "QUERY"
    TASK_AUTOMATION = "TASK_AUTOMATION"
    RESEARCH = "RESEARCH"
    SYSTEM_COMMAND = "SYSTEM_COMMAND"
    MEDIA_CONTROL = "MEDIA_CONTROL"
    UNKNOWN = "UNKNOWN"


class StepStatus(str, Enum):
    """Lifecycle status of a single plan step."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class RecoveryStrategy(str, Enum):
    """Available recovery mechanics when an observation fails verification."""
    RETRY_WITH_ADAPTED_ARGS = "RETRY_WITH_ADAPTED_ARGS"
    SWITCH_TOOL = "SWITCH_TOOL"
    REPLAN_GRAPH = "REPLAN_GRAPH"
    ESCALATE_TO_USER = "ESCALATE_TO_USER"


@dataclass
class TaskObjective:
    """1. UNDERSTAND capability output contract."""
    raw_input: str
    intent: IntentCategory
    description: str
    target_criteria: str
    context: Dict[str, Any] = field(default_factory=dict)
    is_ambiguous: bool = False
    clarification_needed: Optional[str] = None


@dataclass
class PlanStep:
    """A discrete unit of work within an ExecutionPlan."""
    step_id: str
    description: str
    subsystem: SubsystemType
    tool_name: str
    arguments: Dict[str, Any]
    expected_outcome: str
    status: StepStatus = StepStatus.PENDING
    retry_count: int = 0
    max_retries: int = 3

    @classmethod
    def create(
        cls,
        description: str,
        subsystem: SubsystemType,
        tool_name: str,
        arguments: Dict[str, Any],
        expected_outcome: str,
        max_retries: int = 3,
    ) -> PlanStep:
        return cls(
            step_id=f"step_{uuid.uuid4().hex[:8]}",
            description=description,
            subsystem=subsystem,
            tool_name=tool_name,
            arguments=arguments,
            expected_outcome=expected_outcome,
            max_retries=max_retries,
        )


@dataclass
class ExecutionPlan:
    """2. PLAN capability output contract."""
    plan_id: str
    objective: TaskObjective
    steps: List[PlanStep] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    @classmethod
    def create(cls, objective: TaskObjective, steps: List[PlanStep]) -> ExecutionPlan:
        return cls(
            plan_id=f"plan_{uuid.uuid4().hex[:8]}",
            objective=objective,
            steps=steps,
        )


@dataclass
class Observation:
    """4. OBSERVE capability output contract."""
    step_id: str
    exit_code: int
    output: str
    error: Optional[str] = None
    telemetry: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0


@dataclass
class VerificationResult:
    """Verification verdict evaluating an Observation against a PlanStep."""
    passed: bool
    evidence: str
    reason: str


@dataclass
class RecoveryAction:
    """5. RECOVER capability output contract."""
    strategy: RecoveryStrategy
    explanation: str
    modified_step: Optional[PlanStep] = None
    new_plan: Optional[ExecutionPlan] = None
    user_prompt: Optional[str] = None
