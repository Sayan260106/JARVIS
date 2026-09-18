"""3. ACT Capability — 'What tools can accomplish those steps?'"""

import time
from typing import Any, Callable, Dict, Optional
from jarvis.capabilities.base import ActCapability
from jarvis.core.schemas import PlanStep, StepStatus
from jarvis.core.state import AgentSessionState
from jarvis.tools.base import BaseTool, ToolResult
from jarvis.tools.registry import ToolRegistry
from jarvis.tools import get_default_registry


class DefaultActCapability(ActCapability):
    """Executes plan steps using registered subsystem tools or custom handlers with safety boundaries."""

    def __init__(self, registry: Optional[Any] = None):
        self.registry = registry or get_default_registry()
        self._register_default_mock_tools()

    def _register_default_mock_tools(self):
        """Ensures default Phase 0 mock tools are registered as fallbacks."""
        # If registry is an instance of jarvis.tools.registry.ToolRegistry, it might already have system tools
        # For mock names that are not BaseTools, we can attach them to a fallback dictionary if needed
        self._fallback_callables: Dict[str, Callable[..., Any]] = {
            "powershell_exec": lambda command, **kwargs: {"status": "ok", "stdout": f"Executed: {command}", "exit_code": 0},
            "web_search": lambda query, **kwargs: {"status": "ok", "results": [f"Result 1 for {query}", f"Result 2 for {query}"], "exit_code": 0},
            "local_summarizer": lambda style="concise", **kwargs: {"status": "ok", "summary": f"Synthesized research summary in {style} style.", "exit_code": 0},
            "local_reasoning": lambda prompt="", **kwargs: {"status": "ok", "answer": f"Processed answer for: {prompt}", "exit_code": 0},
            "task_runner": lambda task="", **kwargs: {"status": "ok", "message": f"Completed {task}", "exit_code": 0},
            "cancel_task": lambda task_id="", reason="Cancelled", **kwargs: {"status": "ok", "cancelled": True, "reason": reason, "exit_code": 0},
            "rollback_action": lambda task_id="", **kwargs: {"status": "ok", "reverted": True, "exit_code": 0},
        }

    def _resolve_args(self, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Resolves dynamic template parameters from context_state (e.g. $state.var)."""
        resolved = dict(args)
        for k, v in resolved.items():
            if isinstance(v, str) and v.startswith("$state."):
                key = v[7:]
                resolved[k] = context.get(key, v)
        return resolved

    def execute(self, step: PlanStep, state: AgentSessionState) -> Any:
        step.status = StepStatus.RUNNING
        step.started_at = time.time()

        resolved_args = self._resolve_args(step.arguments, state.context_state)

        # Case 1: Custom action function provided on step
        if step.action_fn is not None:
            try:
                out = step.action_fn(state.context_state)
                step.output = out
                return out
            except Exception as ex:
                step.error = str(ex)
                raise ex

        # Case 2: BaseTool from registry
        tool = None
        if hasattr(self.registry, "get"):
            tool = self.registry.get(step.tool_name)

        if isinstance(tool, BaseTool):
            res: ToolResult = tool.execute(**resolved_args)
            step.output = res.output
            step.error = res.error
            return res

        # Case 3: Callable from custom/mock registry
        if callable(tool):
            out = tool(**resolved_args)
            step.output = out
            return out

        # Case 4: Fallback callable
        if step.tool_name in self._fallback_callables:
            out = self._fallback_callables[step.tool_name](**resolved_args)
            step.output = out
            return out

        raise RuntimeError(f"No tool registered for '{step.tool_name}' on subsystem '{step.subsystem.value}'")

