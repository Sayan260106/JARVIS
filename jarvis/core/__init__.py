"""Export core schemas, state, and the agent loop."""

from jarvis.core.schemas import (
    SubsystemType,
    IntentCategory,
    StepStatus,
    RecoveryStrategy,
    TaskObjective,
    PlanStep,
    ExecutionPlan,
    Observation,
    VerificationResult,
    RecoveryAction,
)
from jarvis.core.state import (
    LoopPhase,
    StepRecord,
    AgentSessionState,
)


def __getattr__(name: str):
    if name == "JarvisAgentLoop":
        from jarvis.core.loop import JarvisAgentLoop
        return JarvisAgentLoop
    if name == "AutonomousSystem":
        from jarvis.core.autonomous_system import AutonomousSystem
        return AutonomousSystem
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    "SubsystemType",
    "IntentCategory",
    "StepStatus",
    "RecoveryStrategy",
    "TaskObjective",
    "PlanStep",
    "ExecutionPlan",
    "Observation",
    "VerificationResult",
    "RecoveryAction",
    "LoopPhase",
    "StepRecord",
    "AgentSessionState",
    "JarvisAgentLoop",
    "AutonomousSystem",
]
