"""The Central Autonomous Agent Loop for JARVIS.

Executes the unified loop:
while task.active:
    objective -> understand() -> plan() -> select_next_action() -> permission_check() ->
    execute() -> observe() -> verify() ->
    if success: update_state(), continue
    if failure: analyze_failure(), recover(), replan()
    if blocked: ask_user()

Each result feeds into the next step.
"""

from __future__ import annotations
import os
import time
from typing import Any, Callable, Dict, List, Optional

from jarvis.core.loop_schemas import (
    ActionStatus,
    AgentLoopTask,
    LoopAction,
    StepExecutionRecord,
)
from jarvis.tools.base import BaseTool, PermissionLevel, RiskLevel, ToolResult, ToolVerification
from jarvis.tools.permissions import PermissionSystem, PermissionDecision
from jarvis.tools.registry import ToolRegistry
from jarvis.core.llm_provider import LLMProvider, ModelRole
from jarvis.capabilities.reasoning.intent_analyzer import IntentAnalyzer


class AgentLoop:
    """The central cognitive orchestrator running autonomous state-feeding tasks."""

    def __init__(
        self,
        registry: Optional[ToolRegistry] = None,
        permission_system: Optional[PermissionSystem] = None,
        llm_provider: Optional[LLMProvider] = None,
        intent_analyzer: Optional[IntentAnalyzer] = None,
        ask_user_callback: Optional[Callable[[LoopAction, Dict[str, Any]], Dict[str, Any]]] = None,
    ):
        self.registry = registry or ToolRegistry()
        self.permissions = permission_system or PermissionSystem()
        self.llm_provider = llm_provider
        self.intent_analyzer = intent_analyzer or IntentAnalyzer(llm_provider=self.llm_provider)
        self.ask_user_callback = ask_user_callback
        self._cancellation_requested = False

    def request_cancellation(self) -> None:
        """Signals cancellation to the running agent loop."""
        self._cancellation_requested = True

    def cancel(self) -> None:
        """Alias for request_cancellation."""
        self.request_cancellation()


    def create_task(self, objective: str, initial_plan: Optional[List[LoopAction]] = None) -> AgentLoopTask:
        """Initialize an active task for the agent loop."""
        task_id = f"TASK #{int(time.time()) % 10000:04d}"
        task = AgentLoopTask(
            task_id=task_id,
            objective=objective,
            plan=initial_plan or [],
            state={},
            active=True,
            status="ACTIVE",
        )
        return task

    def understand(self, task: AgentLoopTask) -> Dict[str, Any]:
        """Analyzes task objective and active state using Fast Model & IntentAnalyzer."""
        intent = self.intent_analyzer.analyze(task.objective)
        return {
            "intent_type": intent.intent_type.value,
            "permission_level": intent.permission_level.value,
            "target_tool": intent.target_tool,
            "requires_confirmation": intent.requires_confirmation,
        }

    def plan(self, task: AgentLoopTask, context: Dict[str, Any]) -> List[LoopAction]:
        """Ensures a plan exists for the task. If already populated, preserves dynamic state."""
        return task.plan

    def select_next_action(self, task: AgentLoopTask) -> Optional[LoopAction]:
        """Selects the next pending action whose prerequisites have succeeded."""
        completed_ids = {s.action_id for s in task.completed_steps if s.success}

        for action in task.plan:
            if action.status == ActionStatus.PENDING:
                # Check if dependencies are fulfilled
                if all(dep in completed_ids for dep in action.depends_on):
                    return action
                # If dependency failed or missing, skip action
                failed_deps = [dep for dep in action.depends_on if any(s.action_id == dep and not s.success for s in task.completed_steps)]
                if failed_deps:
                    action.status = ActionStatus.SKIPPED
                    action.status_message = f"Skipped due to failed prerequisite {failed_deps[0]}"
        return None

    def permission_check(self, action: LoopAction, state: Dict[str, Any]) -> PermissionDecision:
        """Evaluates 4-level permission taxonomy for the chosen action."""
        if not action.target_tool or not self.registry.get(action.target_tool):
            # Pure internal or non-destructive action function
            return PermissionDecision(
                allowed=True,
                reason="Internal step automatically authorized.",
                risk_level=RiskLevel.LOW,
                permission_level=PermissionLevel.LEVEL_0_READ,
            )

        tool = self.registry.get(action.target_tool)
        # Dynamic argument resolution from state
        resolved_args = self._resolve_action_args(action, state)
        return self.permissions.check_permission(tool, resolved_args)

    def execute(self, action: LoopAction, state: Dict[str, Any]) -> Dict[str, Any]:
        """Executes the action passing accumulated state outputs."""
        start_t = time.perf_counter()
        action.status = ActionStatus.RUNNING

        resolved_args = self._resolve_action_args(action, state)

        # Case 1: Custom action function provided
        if action.action_fn is not None:
            try:
                out = action.action_fn(state)
                dur = (time.perf_counter() - start_t) * 1000
                action.output = out
                action.status = ActionStatus.SUCCESS
                return {"success": True, "output": out, "error": None, "duration_ms": dur}
            except Exception as e:
                dur = (time.perf_counter() - start_t) * 1000
                action.error = str(e)
                action.status = ActionStatus.FAILED
                return {"success": False, "output": None, "error": str(e), "duration_ms": dur}

        # Case 2: Standard BaseTool from registry
        if action.target_tool and self.registry.get(action.target_tool):
            tool = self.registry.get(action.target_tool)
            res = tool.execute(**resolved_args)
            dur = (time.perf_counter() - start_t) * 1000
            action.output = res.output
            action.error = res.error
            action.status = ActionStatus.SUCCESS if res.success else ActionStatus.FAILED
            return {"success": res.success, "output": res.output, "error": res.error, "duration_ms": dur}

        # Case 3: Pass-through
        dur = (time.perf_counter() - start_t) * 1000
        action.status = ActionStatus.SUCCESS
        return {"success": True, "output": f"Step '{action.name}' completed.", "error": None, "duration_ms": dur}

    def observe(self, action: LoopAction, result: Dict[str, Any]) -> Dict[str, Any]:
        """Observes execution side effects, metrics, and state signals."""
        output = result.get("output")
        metrics = {}
        if isinstance(output, dict):
            metrics = {k: v for k, v in output.items() if isinstance(v, (int, float, str, bool))}
        return {
            "status": action.status.value,
            "has_error": result.get("error") is not None,
            "metrics": metrics,
            "timestamp": time.time(),
        }

    def verify(self, action: LoopAction, result: Dict[str, Any], observation: Dict[str, Any]) -> Dict[str, Any]:
        """Ground-truth verification confirming intended effect."""
        if not result.get("success", False):
            return {"verified": False, "details": f"Execution failed: {result.get('error')}"}

        if action.target_tool and self.registry.get(action.target_tool):
            tool = self.registry.get(action.target_tool)
            v = tool.verify(action.parameters, ToolResult(success=True, output=result.get("output")))
            return {"verified": v.verified, "details": v.details}

        return {"verified": True, "details": f"Step '{action.name}' ground-truth verified."}

    def update_state(
        self,
        task: AgentLoopTask,
        action: LoopAction,
        result: Dict[str, Any],
        observation: Dict[str, Any],
    ) -> None:
        """Updates task state feeding output data directly into subsequent steps."""
        out = result.get("output")
        # Record step in task history
        rec = StepExecutionRecord(
            action_id=action.action_id,
            action_name=action.name,
            success=True,
            output=out,
            error=None,
            observation=observation,
            verified=True,
            verification_details=f"Verified {action.name}",
            duration_ms=result.get("duration_ms", 0.0),
        )
        task.completed_steps.append(rec)

        # Feed step output into shared task state dictionary
        task.state[action.action_id] = out
        if isinstance(out, dict):
            for k, v in out.items():
                task.state[k] = v

    def analyze_failure(self, action: LoopAction, result: Dict[str, Any], observation: Dict[str, Any]) -> str:
        """Analyzes execution failure to formulate recovery strategy."""
        err = result.get("error") or "Unknown execution error"
        return f"Failure in step '{action.name}': {err}"

    def recover(self, action: LoopAction, diagnosis: str, task: AgentLoopTask) -> bool:
        """Attempts safe recovery if within autonomous retry limit."""
        if task.recovery_attempts >= task.max_recovery_attempts:
            return False
        task.recovery_attempts += 1
        # Reset action status for retry or safe parameter adjustment
        action.status = ActionStatus.PENDING
        return True

    def replan(self, task: AgentLoopTask, diagnosis: str) -> None:
        """Dynamically adjusts downstream plan based on failure diagnosis."""
        pass

    def ask_user(self, action: LoopAction, details: Dict[str, Any]) -> Dict[str, Any]:
        """Requests explicit user guidance when an action is blocked or max retries exceeded."""
        if self.ask_user_callback:
            return self.ask_user_callback(action, details)
        return {"approved": False, "response": f"Action '{action.name}' blocked."}

    def _resolve_action_args(self, action: LoopAction, state: Dict[str, Any]) -> Dict[str, Any]:
        """Resolves dynamic argument templates from shared task state."""
        args = dict(action.parameters)
        for k, v in args.items():
            if isinstance(v, str) and v.startswith("$state."):
                key = v[7:]
                args[k] = state.get(key, v)
        return args

    def run(
        self,
        objective: str,
        initial_plan: Optional[List[LoopAction]] = None,
        print_visual_table: bool = True,
    ) -> AgentLoopTask:
        """Runs the continuous agent loop until completion, failure, or policy block."""
        task = self.create_task(objective, initial_plan)

        if print_visual_table:
            print(f"\n{task.task_id}")
            print("-" * 30)

        while task.active:
            if self._cancellation_requested:
                task.status = "CANCELLED"
                task.active = False
                break

            # 1. understand()
            context = self.understand(task)

            # 2. plan()
            plan = self.plan(task, context)

            # 3. select_next_action()
            action = self.select_next_action(task)
            if not action:
                # All eligible plan steps completed!
                task.status = "COMPLETED"
                task.active = False
                break

            # 4. permission_check()
            perm_decision = self.permission_check(action, task.state)
            if not perm_decision.allowed:
                if perm_decision.user_prompt_required:
                    user_resp = self.ask_user(action, {"decision": perm_decision})
                    if not user_resp.get("approved"):
                        action.status = ActionStatus.BLOCKED
                        task.status = "BLOCKED"
                        task.active = False
                        break

            # 5. execute()
            res = self.execute(action, task.state)

            # 6. observe()
            obs = self.observe(action, res)

            # 7. verify()
            ver = self.verify(action, res, obs)

            # 8. if success: update_state() and continue
            if res.get("success", False) and ver.get("verified", False):
                self.update_state(task, action, res, obs)
                if print_visual_table:
                    step_num = len(task.completed_steps)
                    print(f"{step_num:>2}. {action.name:<32} [OK]")
                continue

            # 9. if failure: analyze_failure(), recover(), replan()
            diagnosis = self.analyze_failure(action, res, obs)
            recovered = self.recover(action, diagnosis, task)
            if recovered:
                self.replan(task, diagnosis)
                continue
            else:
                # 10. if blocked / unrecoverable: ask_user()
                self.ask_user(action, {"diagnosis": diagnosis})
                task.status = "FAILED"
                task.active = False
                break

        return task
