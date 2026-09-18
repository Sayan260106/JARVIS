"""Fundamental Agent Loop for JARVIS.

Implements the deterministic state-machine workflow:
USER OBJECTIVE
      ↓
UNDERSTAND (Structured TaskObjective)
      ↓
PLAN (Structured ExecutionPlan with Step Dependencies & Tool Selection)
      ↓
ACT / EXECUTE (Subsystem Tool Dispatch & Dynamic State Feeding)
      ↓
OBSERVE (Environmental Telemetry Collection)
      ↓
VERIFY (Ground-Truth Evidence Checking)
      ↓
 ┌────┴────┐
 │         │
PASS      FAIL
 │         │
 ↓         ↓
NEXT     RECOVER (Bounded Retry Policy: Retries <= 3)
STEP       │
 │         ├──────→ ADAPT ARGS / SWITCH TOOL / REPLAN GRAPH
 │         └──────→ ESCALATE TO USER (Max retries reached)
 ↓
FINAL RESULT & SQLite PERSISTENCE
"""

from __future__ import annotations
import json
import threading
import time
from typing import Any, Dict, List, Optional

from jarvis.core.schemas import (
    ExecutionPlan,
    PlanStep,
    RecoveryStrategy,
    StepStatus,
    SubsystemType,
    TaskObjective,
)
from jarvis.core.state import (
    AgentSessionState,
    LoopPhase,
    StepRecord,
)
from jarvis.core.task_manager import TaskManager
from jarvis.core.task_schemas import Task, TaskPriority, TaskStatus
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
    """The central orchestrator driving the 5 fundamental capabilities with genuine reliability."""

    def __init__(
        self,
        understand: Optional[UnderstandCapability] = None,
        plan: Optional[PlanCapability] = None,
        act: Optional[ActCapability] = None,
        observe: Optional[ObserveCapability] = None,
        verify: Optional[VerifyCapability] = None,
        recover: Optional[RecoverCapability] = None,
        task_manager: Optional[TaskManager] = None,
        registry: Optional[Any] = None,
    ):
        self.registry = registry
        self.understand_cap = understand or DefaultUnderstandCapability()
        self.plan_cap = plan or DefaultPlanCapability(registry=registry)
        self.act_cap = act or DefaultActCapability(registry=registry)
        self.observe_cap = observe or DefaultObserveCapability()
        self.verify_cap = verify or DefaultVerifyCapability()
        self.recover_cap = recover or DefaultRecoverCapability()
        self.task_manager = task_manager or TaskManager()
        self._cancellation_requested = False
        self._lock = threading.Lock()

    def request_cancellation(self, task_id: Optional[str] = None) -> None:
        """Signals cancellation to the running agent loop."""
        with self._lock:
            self._cancellation_requested = True
            if task_id:
                try:
                    self.task_manager.cancel_task(task_id, reason="User cancellation requested")
                except Exception:
                    pass

    def cancel(self, task_id: Optional[str] = None) -> None:
        """Alias for request_cancellation."""
        self.request_cancellation(task_id)

    def run(
        self,
        user_prompt: str,
        context: Optional[Dict[str, Any]] = None,
        initial_plan: Optional[List[PlanStep]] = None,
        task_id: Optional[str] = None,
    ) -> AgentSessionState:
        """Executes the full agent loop from user objective to verified final result."""
        with self._lock:
            self._cancellation_requested = False

        state = AgentSessionState()
        context = dict(context or {})

        # 1. Register persistent Task in SQLite via TaskManager
        persistent_task = self.task_manager.create_task(
            objective=user_prompt,
            context=context,
        )
        state.task_id = persistent_task.id
        self.task_manager.transition_status(state.task_id, TaskStatus.RUNNING)

        # 2. UNDERSTAND: 'What did the user mean?'
        state.phase = LoopPhase.UNDERSTANDING
        objective = self.understand_cap.understand(user_prompt, context)
        state.objective = objective

        # Save parsed objective into persistent task context
        persistent_task.context["objective"] = objective.to_dict()
        self.task_manager.update_task(persistent_task)

        if objective.is_ambiguous:
            state.phase = LoopPhase.AWAITING_USER
            state.error_message = objective.clarification_needed
            self.task_manager.transition_status(state.task_id, TaskStatus.WAITING, reason=state.error_message)
            return state

        # 3. PLAN: 'What steps are required?'
        state.phase = LoopPhase.PLANNING
        if initial_plan:
            plan = ExecutionPlan.create(objective, initial_plan)
        else:
            plan = self.plan_cap.plan(objective, state)
        state.plan = plan

        if not plan.steps:
            state.phase = LoopPhase.COMPLETED
            state.final_result = "No action steps required for this request."
            self.task_manager.complete_task(state.task_id, final_result=state.final_result)
            return state

        # Checkpoint planned steps into TaskManager
        self.task_manager.set_plan(state.task_id, [s.to_dict() for s in plan.steps])
        self._save_plan_state(state)

        # 4. Execute the plan
        return self._run_plan(state)

    def resume(self, task_id: str) -> AgentSessionState:
        """Resumes an interrupted or paused task from SQLite storage."""
        persistent_task = self.task_manager.get_task(task_id)
        if not persistent_task:
            raise ValueError(f"Task '{task_id}' not found in task store.")
        if persistent_task.status == TaskStatus.COMPLETED:
            raise ValueError(f"Task '{task_id}' is already COMPLETED.")

        self.task_manager.resume_task(task_id)

        state = AgentSessionState(task_id=task_id, phase=LoopPhase.EXECUTING)

        # Restore objective
        obj_data = persistent_task.context.get("objective")
        if obj_data:
            state.objective = TaskObjective.from_dict(obj_data)
        else:
            state.objective = self.understand_cap.understand(persistent_task.objective, persistent_task.context)

        # Restore plan
        plan_data = persistent_task.context.get("plan_json")
        if plan_data:
            state.plan = ExecutionPlan.from_dict(plan_data)
        else:
            steps = [PlanStep.from_dict(s) for s in persistent_task.plan]
            state.plan = ExecutionPlan.create(state.objective, steps)

        # Restore context state from previously completed steps
        saved_state = persistent_task.context.get("context_state", {})
        state.context_state.update(saved_state)
        for comp in persistent_task.completed_steps:
            res = comp.get("result")
            name = comp.get("name")
            if res is not None:
                state.context_state[name] = res
                if isinstance(res, dict):
                    for k, v in res.items():
                        state.context_state[k] = v

        with self._lock:
            self._cancellation_requested = False

        return self._run_plan(state)

    def resume_task(self, task_id: str) -> AgentSessionState:
        """Alias for resume()."""
        return self.resume(task_id)

    def _run_plan(self, state: AgentSessionState) -> AgentSessionState:
        """Internal execution loop advancing steps according to dependencies."""
        plan = state.plan
        if not plan:
            state.phase = LoopPhase.FAILED
            state.error_message = "No execution plan found."
            return state

        while not state.is_finished():
            # Check for cancellation signal
            if self._cancellation_requested or state.is_cancelled:
                state.phase = LoopPhase.CANCELLED
                state.is_cancelled = True
                for s in plan.steps:
                    if s.status in (StepStatus.PENDING, StepStatus.RUNNING):
                        s.status = StepStatus.CANCELLED
                self.task_manager.cancel_task(state.task_id, reason="Execution cancelled by user")
                self._save_plan_state(state)
                state.final_result = f"Task '{state.task_id}' was cancelled."
                return state

            # Select next eligible step respecting dependencies
            step = plan.get_next_eligible_step(state.completed_step_ids)
            if not step:
                # No more executable steps
                break

            # 4. ACT / EXECUTE
            state.phase = LoopPhase.EXECUTING
            step.status = StepStatus.RUNNING
            self._save_plan_state(state)

            start_time = time.perf_counter()
            raw_result = None
            try:
                raw_result = self.act_cap.execute(step, state)
            except Exception as ex:
                raw_result = ex
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            # 5. OBSERVE
            state.phase = LoopPhase.OBSERVING
            observation = self.observe_cap.observe(step, raw_result, elapsed_ms)
            step.observation = observation

            # 6. VERIFY
            state.phase = LoopPhase.VERIFYING
            verification = self.verify_cap.verify(step, observation)
            step.verification = verification

            step_record = StepRecord(
                step=step,
                observation=observation,
                verification=verification,
            )
            state.history.append(step_record)

            # Decision Gate: PASS vs FAIL
            if verification.passed:
                step.status = StepStatus.SUCCESS
                step.completed_at = time.time()
                step.status_message = "SUCCESS"

                # State Feeding: Feed output into accumulated context_state
                out = step.output
                if out is not None:
                    state.context_state[step.step_id] = out
                    if isinstance(out, dict):
                        for k, v in out.items():
                            state.context_state[k] = v

                # Checkpoint successful step in SQLite
                step_num = len(state.completed_step_ids)
                self.task_manager.advance_step(state.task_id, step_num, step.description, result=out)
                self._save_plan_state(state)

            else:
                # Step failed verification
                step.status = StepStatus.FAILED
                step.status_message = verification.reason

                # Record failure in SQLite
                self.task_manager.record_failure(
                    state.task_id,
                    len(state.history),
                    step.description,
                    error=verification.reason,
                    can_retry=(step.retry_count < step.max_retries),
                )

                # 7. RECOVER
                state.phase = LoopPhase.RECOVERING
                recovery = self.recover_cap.recover(step, observation, verification, state)
                step_record.recovery = recovery

                if recovery.strategy == RecoveryStrategy.ESCALATE_TO_USER:
                    self._skip_downstream_steps(plan, step.step_id)
                    state.phase = LoopPhase.AWAITING_USER
                    state.error_message = recovery.user_prompt or recovery.explanation
                    self.task_manager.transition_status(state.task_id, TaskStatus.WAITING, reason=state.error_message)
                    self._save_plan_state(state)
                    return state

                elif recovery.strategy in (
                    RecoveryStrategy.RETRY_WITH_ADAPTED_ARGS,
                    RecoveryStrategy.SWITCH_TOOL,
                ):
                    if recovery.modified_step:
                        for idx, s in enumerate(plan.steps):
                            if s.step_id == step.step_id:
                                plan.steps[idx] = recovery.modified_step
                                break
                    self._save_plan_state(state)
                    continue

                elif recovery.strategy == RecoveryStrategy.REPLAN_GRAPH:
                    new_plan = recovery.new_plan or self.plan_cap.plan(state.objective, state)
                    state.plan = new_plan
                    self._save_plan_state(state)
                    continue

        # Post-loop completion evaluation
        if state.phase == LoopPhase.CANCELLED:
            state.final_result = f"Task '{state.task_id}' was cancelled."
        elif plan.has_failures():
            state.phase = LoopPhase.FAILED
            state.final_result = f"Task execution halted with unrecoverable failures."
            self.task_manager.transition_status(state.task_id, TaskStatus.FAILED, reason=state.final_result)
        else:
            state.phase = LoopPhase.COMPLETED
            completed_count = len([s for s in plan.steps if s.status == StepStatus.SUCCESS])
            state.final_result = f"Successfully executed {completed_count} verified steps for objective: '{state.objective.raw_input}'."
            self.task_manager.complete_task(state.task_id, final_result=state.final_result)

        self._save_plan_state(state)
        return state

    def _save_plan_state(self, state: AgentSessionState) -> None:
        """Persists current plan steps, status, and context_state into SQLite task store."""
        if not state.task_id or not state.plan:
            return
        task = self.task_manager.get_task(state.task_id)
        if task:
            task.context["plan_json"] = state.plan.to_dict()
            task.context["context_state"] = state.context_state
            task.plan = [s.to_dict() for s in state.plan.steps]
            self.task_manager.update_task(task)

    def _skip_downstream_steps(self, plan: ExecutionPlan, failed_id: str) -> None:
        """Recursively marks all downstream dependent steps as SKIPPED."""
        skipped_ids = {failed_id}
        changed = True
        while changed:
            changed = False
            for s in plan.steps:
                if s.status == StepStatus.PENDING and any(dep in skipped_ids for dep in s.depends_on):
                    s.status = StepStatus.SKIPPED
                    s.status_message = f"Skipped due to unmet prerequisite {failed_id}"
                    skipped_ids.add(s.step_id)
                    changed = True


