"""Fundamental Agent Loop for JARVIS.

Implements the deterministic state-machine workflow:
USER OBJECTIVE
      ↓
UNDERSTAND
      ↓
PLAN
      ↓
EXECUTE
      ↓
OBSERVE
      ↓
VERIFY
      ↓
 ┌────┴────┐
 │         │
PASS      FAIL
 │         │
 ↓         ↓
NEXT     REPLAN
STEP       │
 │         └──────→ EXECUTE
 ↓
FINAL RESULT
"""

from __future__ import annotations
import time
from typing import Any, Dict, Optional

from jarvis.core.schemas import (
    StepStatus,
    RecoveryStrategy,
)
from jarvis.core.state import (
    AgentSessionState,
    LoopPhase,
    StepRecord,
)
from jarvis.capabilities.base import (
    UnderstandCapability,
    PlanCapability,
    ActCapability,
    ObserveCapability,
    VerifyCapability,
    RecoverCapability,
)
from jarvis.capabilities.understand import DefaultUnderstandCapability
from jarvis.capabilities.plan import DefaultPlanCapability
from jarvis.capabilities.act import DefaultActCapability
from jarvis.capabilities.observe import DefaultObserveCapability, DefaultVerifyCapability
from jarvis.capabilities.recover import DefaultRecoverCapability


class JarvisAgentLoop:
    """The central orchestrator driving the 5 fundamental capabilities."""

    def __init__(
        self,
        understand: Optional[UnderstandCapability] = None,
        plan: Optional[PlanCapability] = None,
        act: Optional[ActCapability] = None,
        observe: Optional[ObserveCapability] = None,
        verify: Optional[VerifyCapability] = None,
        recover: Optional[RecoverCapability] = None,
    ):
        self.understand_cap = understand or DefaultUnderstandCapability()
        self.plan_cap = plan or DefaultPlanCapability()
        self.act_cap = act or DefaultActCapability()
        self.observe_cap = observe or DefaultObserveCapability()
        self.verify_cap = verify or DefaultVerifyCapability()
        self.recover_cap = recover or DefaultRecoverCapability()

    def run(self, user_prompt: str, context: Optional[Dict[str, Any]] = None) -> AgentSessionState:
        """Executes the full agent loop from user objective to verified final result."""
        state = AgentSessionState()
        context = context or {}

        # 1. UNDERSTAND: 'What did the user mean?'
        state.phase = LoopPhase.UNDERSTANDING
        objective = self.understand_cap.understand(user_prompt, context)
        state.objective = objective

        if objective.is_ambiguous:
            state.phase = LoopPhase.AWAITING_USER
            state.error_message = objective.clarification_needed
            return state

        # 2. PLAN: 'What steps are required?'
        state.phase = LoopPhase.PLANNING
        plan = self.plan_cap.plan(objective, state)
        state.plan = plan

        if not plan.steps:
            state.phase = LoopPhase.COMPLETED
            state.final_result = "No action steps required for this request."
            return state

        # Step-by-step execution loop
        state.current_step_index = 0

        while state.current_step_index < len(state.plan.steps):
            step = state.plan.steps[state.current_step_index]

            # 3. ACT / EXECUTE: 'What tools can accomplish those steps?'
            state.phase = LoopPhase.EXECUTING
            start_time = time.perf_counter()
            raw_result = None
            try:
                raw_result = self.act_cap.execute(step, state)
            except Exception as ex:
                raw_result = ex
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            # 4. OBSERVE: 'Did the action actually work?'
            state.phase = LoopPhase.OBSERVING
            observation = self.observe_cap.observe(step, raw_result, elapsed_ms)

            # 4b. VERIFY
            state.phase = LoopPhase.VERIFYING
            verification = self.verify_cap.verify(step, observation)

            # Record step telemetry
            step_record = StepRecord(
                step=step,
                observation=observation,
                verification=verification,
            )
            state.history.append(step_record)

            # Decision Gate: PASS vs FAIL
            if verification.passed:
                # PASS -> NEXT STEP
                step.status = StepStatus.SUCCESS
                state.current_step_index += 1
            else:
                # FAIL -> RECOVER / REPLAN
                state.phase = LoopPhase.RECOVERING
                recovery = self.recover_cap.recover(step, observation, verification, state)
                step_record.recovery = recovery

                if recovery.strategy == RecoveryStrategy.ESCALATE_TO_USER:
                    state.phase = LoopPhase.AWAITING_USER
                    state.error_message = recovery.user_prompt or recovery.explanation
                    return state

                elif recovery.strategy in (
                    RecoveryStrategy.RETRY_WITH_ADAPTED_ARGS,
                    RecoveryStrategy.SWITCH_TOOL,
                ):
                    if recovery.modified_step:
                        state.plan.steps[state.current_step_index] = recovery.modified_step
                    # Loops back to EXECUTE on the modified step

                elif recovery.strategy == RecoveryStrategy.REPLAN_GRAPH:
                    new_plan = recovery.new_plan or self.plan_cap.plan(objective, state)
                    state.plan = new_plan
                    state.current_step_index = 0  # Restart on new plan

        # When all steps PASS -> FINAL RESULT
        state.phase = LoopPhase.COMPLETED
        state.final_result = f"Successfully executed {len(state.plan.steps)} steps for objective: '{objective.raw_input}'."
        return state
