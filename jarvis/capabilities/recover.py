"""5. RECOVER Capability — Autonomous Recovery 2.0 (Phase 14).

Diagnoses failures, asks 'Why did it fail?', and selects intelligent recovery paths:
prerequisite injection, alternate selectors, alternate tools, navigation, and state refresh.
"""

from __future__ import annotations
from typing import Optional

from jarvis.capabilities.base import RecoverCapability
from jarvis.core.schemas import (
    Observation,
    PlanStep,
    RecoveryAction,
    RecoveryStrategy,
    VerificationResult,
)
from jarvis.core.state import AgentSessionState
from jarvis.subsystems.recovery import AutonomousRecoveryEngine, get_recovery_engine


class DefaultRecoverCapability(RecoverCapability):
    """Diagnoses failures and formulates adaptive recovery strategies obeying Rule 3 (bounded loops)."""

    def __init__(self, engine: Optional[AutonomousRecoveryEngine] = None):
        self.engine = engine or get_recovery_engine()

    def recover(
        self,
        step: PlanStep,
        observation: Observation,
        verification: VerificationResult,
        state: AgentSessionState,
    ) -> RecoveryAction:
        """Executes the intelligent diagnostic and recovery pipeline."""
        return self.engine.recover(
            step=step,
            observation=observation,
            verification=verification,
            state=state,
        )
