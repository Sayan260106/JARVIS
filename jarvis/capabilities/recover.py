"""5. RECOVER Capability — 'If it didn't work, what should I try next?'"""

from jarvis.capabilities.base import RecoverCapability
from jarvis.core.schemas import (
    PlanStep,
    Observation,
    VerificationResult,
    RecoveryAction,
    RecoveryStrategy,
    StepStatus,
)
from jarvis.core.state import AgentSessionState


class DefaultRecoverCapability(RecoverCapability):
    """Diagnoses failures and formulates adaptive recovery strategies obeying Rule 3 (bounded loops)."""

    def recover(
        self,
        step: PlanStep,
        observation: Observation,
        verification: VerificationResult,
        state: AgentSessionState,
    ) -> RecoveryAction:
        step.retry_count += 1
        step.status = StepStatus.FAILED

        # Rule 3: Bounded recovery loops. Never exceed max retries.
        if step.retry_count >= step.max_retries:
            return RecoveryAction(
                strategy=RecoveryStrategy.ESCALATE_TO_USER,
                explanation=f"Step '{step.description}' has failed {step.retry_count} times. Maximum retry ceiling reached.",
                user_prompt=f"Action failed after {step.retry_count} attempts. Reason: {verification.reason}. How would you like to proceed?",
            )

        # Strategy 1: Attempt self-correction / parameter adaptation on first retry
        if step.retry_count == 1:
            adapted_step = PlanStep(
                step_id=step.step_id,
                description=f"{step.description} (Retry with fallback params)",
                subsystem=step.subsystem,
                tool_name=step.tool_name,
                arguments={**step.arguments, "_retry_mode": "strict"},
                expected_outcome=step.expected_outcome,
                status=StepStatus.PENDING,
                retry_count=step.retry_count,
                max_retries=step.max_retries,
            )
            return RecoveryAction(
                strategy=RecoveryStrategy.RETRY_WITH_ADAPTED_ARGS,
                explanation="Attempting retry with adjusted parameters.",
                modified_step=adapted_step,
            )

        # Strategy 2: Switch to alternate fallback tool if available
        if step.retry_count == 2:
            adapted_step = PlanStep(
                step_id=step.step_id,
                description=f"{step.description} (Fallback tool route)",
                subsystem=step.subsystem,
                tool_name=f"{step.tool_name}_fallback" if not step.tool_name.endswith("_fallback") else step.tool_name,
                arguments=step.arguments,
                expected_outcome=step.expected_outcome,
                status=StepStatus.PENDING,
                retry_count=step.retry_count,
                max_retries=step.max_retries,
            )
            return RecoveryAction(
                strategy=RecoveryStrategy.SWITCH_TOOL,
                explanation="Switching to alternative execution strategy or tool route.",
                modified_step=adapted_step,
            )

        # Strategy 3: Structural Replan
        return RecoveryAction(
            strategy=RecoveryStrategy.REPLAN_GRAPH,
            explanation="Initiating task re-plan to circumvent failure point.",
        )
