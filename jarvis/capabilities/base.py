"""Abstract capability interfaces for JARVIS's 5 fundamental pillars.

Every capability implementation conforms to these explicit interfaces.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict
from jarvis.core.schemas import (
    TaskObjective,
    ExecutionPlan,
    PlanStep,
    Observation,
    VerificationResult,
    RecoveryAction,
)
from jarvis.core.state import AgentSessionState


class UnderstandCapability(ABC):
    """Capability 1: 'What did the user mean?'"""

    @abstractmethod
    def understand(self, user_input: str, context: Dict[str, Any]) -> TaskObjective:
        """Parse raw input into an unambiguous TaskObjective."""
        pass


class PlanCapability(ABC):
    """Capability 2: 'What steps are required?'"""

    @abstractmethod
    def plan(self, objective: TaskObjective, state: AgentSessionState) -> ExecutionPlan:
        """Decompose objective into an executable sequence of PlanStep items."""
        pass


class ActCapability(ABC):
    """Capability 3: 'What tools can accomplish those steps?'"""

    @abstractmethod
    def execute(self, step: PlanStep, state: AgentSessionState) -> Any:
        """Dispatch step execution to the designated tool/subsystem."""
        pass


class ObserveCapability(ABC):
    """Capability 4: 'Did the action actually work?' (Telemetry Collection)"""

    @abstractmethod
    def observe(self, step: PlanStep, raw_result: Any, duration_ms: float) -> Observation:
        """Capture real environment telemetry and format into a standardized Observation."""
        pass


class VerifyCapability(ABC):
    """Capability 4b: 'Did the action actually work?' (Verification Verdict)"""

    @abstractmethod
    def verify(self, step: PlanStep, observation: Observation) -> VerificationResult:
        """Evaluate observation ground-truth against step expected criteria."""
        pass


class RecoverCapability(ABC):
    """Capability 5: 'If it didn't work, what should I try next?'"""

    @abstractmethod
    def recover(
        self,
        step: PlanStep,
        observation: Observation,
        verification: VerificationResult,
        state: AgentSessionState,
    ) -> RecoveryAction:
        """Formulate a corrective recovery strategy when a step fails verification."""
        pass
