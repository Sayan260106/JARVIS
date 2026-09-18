"""Core data schemas for the JARVIS agent architecture.

Defines the typed contracts governing Understand, Plan, Act, Observe, and Recover.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import time
import uuid


class SubsystemType(str, Enum):
    """The execution subsystems in JARVIS roadmap."""
    LOCAL = "LOCAL_INTELLIGENCE"       # Ollama, local SLMs, embeddings, vector store
    WEB = "WEB_INTELLIGENCE"           # Browser, Playwright, search, cloud LLM
    SYSTEM = "COMPUTER_CONTROL"        # Windows OS, PowerShell, processes, files
    DOCUMENT = "DOCUMENT_INTELLIGENCE" # PDF/DOCX/PPTX parsing, structure, chunking, retrieval


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
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"


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
    sub_goals: List[str] = field(default_factory=list)
    extracted_entities: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_input": self.raw_input,
            "intent": self.intent.value if isinstance(self.intent, IntentCategory) else str(self.intent),
            "description": self.description,
            "target_criteria": self.target_criteria,
            "context": self.context,
            "is_ambiguous": self.is_ambiguous,
            "clarification_needed": self.clarification_needed,
            "sub_goals": self.sub_goals,
            "extracted_entities": self.extracted_entities,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TaskObjective:
        intent_raw = data.get("intent", IntentCategory.UNKNOWN)
        try:
            intent = IntentCategory(intent_raw)
        except ValueError:
            intent = IntentCategory.UNKNOWN

        return cls(
            raw_input=data.get("raw_input", ""),
            intent=intent,
            description=data.get("description", ""),
            target_criteria=data.get("target_criteria", ""),
            context=data.get("context") or {},
            is_ambiguous=data.get("is_ambiguous", False),
            clarification_needed=data.get("clarification_needed"),
            sub_goals=data.get("sub_goals") or [],
            extracted_entities=data.get("extracted_entities") or {},
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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "exit_code": self.exit_code,
            "output": self.output,
            "error": self.error,
            "telemetry": self.telemetry,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Observation:
        return cls(
            step_id=data.get("step_id", ""),
            exit_code=data.get("exit_code", 0),
            output=data.get("output", ""),
            error=data.get("error"),
            telemetry=data.get("telemetry") or {},
            duration_ms=data.get("duration_ms", 0.0),
        )


@dataclass
class VerificationResult:
    """Verification verdict evaluating an Observation against a PlanStep."""
    passed: bool
    evidence: str
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "evidence": self.evidence,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> VerificationResult:
        return cls(
            passed=data.get("passed", False),
            evidence=data.get("evidence", ""),
            reason=data.get("reason", ""),
        )


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
    depends_on: List[str] = field(default_factory=list)
    action_fn: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    output: Optional[Any] = None
    error: Optional[str] = None
    observation: Optional[Observation] = None
    verification: Optional[VerificationResult] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    status_message: str = ""

    @classmethod
    def create(
        cls,
        description: str,
        subsystem: SubsystemType,
        tool_name: str,
        arguments: Dict[str, Any],
        expected_outcome: str,
        max_retries: int = 3,
        depends_on: Optional[List[str]] = None,
        action_fn: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
    ) -> PlanStep:
        return cls(
            step_id=f"step_{uuid.uuid4().hex[:8]}",
            description=description,
            subsystem=subsystem,
            tool_name=tool_name,
            arguments=arguments,
            expected_outcome=expected_outcome,
            max_retries=max_retries,
            depends_on=depends_on or [],
            action_fn=action_fn,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "description": self.description,
            "subsystem": self.subsystem.value if isinstance(self.subsystem, SubsystemType) else str(self.subsystem),
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "expected_outcome": self.expected_outcome,
            "status": self.status.value if isinstance(self.status, StepStatus) else str(self.status),
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "depends_on": self.depends_on,
            "output": self.output,
            "error": self.error,
            "observation": self.observation.to_dict() if self.observation else None,
            "verification": self.verification.to_dict() if self.verification else None,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "status_message": self.status_message,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PlanStep:
        subsys_raw = data.get("subsystem", SubsystemType.SYSTEM)
        try:
            subsystem = SubsystemType(subsys_raw)
        except ValueError:
            subsystem = SubsystemType.SYSTEM

        status_raw = data.get("status", StepStatus.PENDING)
        try:
            status = StepStatus(status_raw)
        except ValueError:
            status = StepStatus.PENDING

        obs = Observation.from_dict(data["observation"]) if data.get("observation") else None
        ver = VerificationResult.from_dict(data["verification"]) if data.get("verification") else None

        return cls(
            step_id=data.get("step_id", f"step_{uuid.uuid4().hex[:8]}"),
            description=data.get("description", ""),
            subsystem=subsystem,
            tool_name=data.get("tool_name", ""),
            arguments=data.get("arguments") or {},
            expected_outcome=data.get("expected_outcome", ""),
            status=status,
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            depends_on=data.get("depends_on") or [],
            output=data.get("output"),
            error=data.get("error"),
            observation=obs,
            verification=ver,
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            status_message=data.get("status_message", ""),
        )


@dataclass
class ExecutionPlan:
    """2. PLAN capability output contract."""
    plan_id: str
    objective: TaskObjective
    steps: List[PlanStep] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    @classmethod
    def create(cls, objective: TaskObjective, steps: List[PlanStep]) -> ExecutionPlan:
        return cls(
            plan_id=f"plan_{uuid.uuid4().hex[:8]}",
            objective=objective,
            steps=steps,
        )

    def get_step(self, step_id: str) -> Optional[PlanStep]:
        for s in self.steps:
            if s.step_id == step_id:
                return s
        return None

    def get_next_eligible_step(self, completed_ids: set[str]) -> Optional[PlanStep]:
        """Finds the next pending step whose dependencies have succeeded."""
        for step in self.steps:
            if step.status == StepStatus.PENDING:
                if all(dep in completed_ids for dep in step.depends_on):
                    return step
                # If any dependency failed or was cancelled/skipped, skip this step
                failed_deps = [dep for dep in step.depends_on if any(s.step_id == dep and s.status in (StepStatus.FAILED, StepStatus.SKIPPED, StepStatus.CANCELLED) for s in self.steps)]
                if failed_deps:
                    step.status = StepStatus.SKIPPED
                    step.status_message = f"Skipped due to unmet prerequisite {failed_deps[0]}"
        return None

    def is_finished(self) -> bool:
        return all(s.status in (StepStatus.SUCCESS, StepStatus.FAILED, StepStatus.SKIPPED, StepStatus.CANCELLED, StepStatus.BLOCKED) for s in self.steps)

    def has_failures(self) -> bool:
        return any(s.status == StepStatus.FAILED for s in self.steps)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "objective": self.objective.to_dict() if self.objective else None,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExecutionPlan:
        obj = TaskObjective.from_dict(data["objective"]) if data.get("objective") else None
        steps = [PlanStep.from_dict(s) for s in data.get("steps", [])]
        return cls(
            plan_id=data.get("plan_id", f"plan_{uuid.uuid4().hex[:8]}"),
            objective=obj,
            steps=steps,
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
        )


@dataclass
class RecoveryAction:
    """5. RECOVER capability output contract."""
    strategy: RecoveryStrategy
    explanation: str
    modified_step: Optional[PlanStep] = None
    new_plan: Optional[ExecutionPlan] = None
    user_prompt: Optional[str] = None

