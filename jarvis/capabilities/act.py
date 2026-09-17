"""3. ACT Capability — 'What tools can accomplish those steps?'"""

from typing import Any, Callable, Dict
from jarvis.capabilities.base import ActCapability
from jarvis.core.schemas import PlanStep, StepStatus
from jarvis.core.state import AgentSessionState


class ToolRegistry:
    """Central registry of executable tools across Local, Web, and Computer Control."""

    def __init__(self):
        self._tools: Dict[str, Callable[..., Any]] = {}

    def register(self, name: str, handler: Callable[..., Any]):
        self._tools[name] = handler

    def get(self, name: str) -> Callable[..., Any]:
        return self._tools.get(name)


class DefaultActCapability(ActCapability):
    """Executes plan steps using registered subsystem tools with safety boundaries."""

    def __init__(self, registry: ToolRegistry = None):
        self.registry = registry or ToolRegistry()
        self._register_default_mock_tools()

    def _register_default_mock_tools(self):
        # Deterministic default tools for Phase 0 validation
        self.registry.register(
            "powershell_exec",
            lambda command: {"status": "ok", "stdout": f"Executed: {command}", "exit_code": 0},
        )
        self.registry.register(
            "web_search",
            lambda query: {"status": "ok", "results": [f"Result 1 for {query}", f"Result 2 for {query}"], "exit_code": 0},
        )
        self.registry.register(
            "local_summarizer",
            lambda style: {"status": "ok", "summary": f"Synthesized research summary in {style} style.", "exit_code": 0},
        )
        self.registry.register(
            "local_reasoning",
            lambda prompt: {"status": "ok", "answer": f"Processed answer for: {prompt}", "exit_code": 0},
        )
        self.registry.register(
            "task_runner",
            lambda task: {"status": "ok", "message": f"Completed {task}", "exit_code": 0},
        )

    def execute(self, step: PlanStep, state: AgentSessionState) -> Any:
        step.status = StepStatus.RUNNING
        handler = self.registry.get(step.tool_name)
        if not handler:
            raise RuntimeError(f"No tool registered for '{step.tool_name}' on subsystem '{step.subsystem.value}'")

        return handler(**step.arguments)
