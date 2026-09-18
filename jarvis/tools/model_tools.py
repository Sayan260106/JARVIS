"""Typed Tools for Inspecting and Managing Model Routing in JARVIS."""

from __future__ import annotations
import time
from typing import Any, Dict

from jarvis.core.llm_provider import ModelRole
from jarvis.core.router import default_model_router
from jarvis.tools.base import (
    BaseTool,
    PermissionLevel,
    RiskLevel,
    ToolParameter,
    ToolResult,
    ToolVerification,
)


class ModelRouteInspectTool(BaseTool):
    """Inspects the model routing decision for a given task or prompt."""
    name = "model_route_inspect"
    description = "Inspect which specialized model (Fast, Reasoning, Coding, Document, Vision, Cloud) is selected for a task."
    risk_level = RiskLevel.LOW
    permission_level = PermissionLevel.LEVEL_0_READ

    parameters = [
        ToolParameter("prompt", "string", "Task prompt or instruction to evaluate", required=True),
        ToolParameter("role_override", "string", "Optional explicit role override (FAST, REASONING, DOCUMENT, CODING, VISION, CLOUD)", required=False),
    ]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        start_time = time.time()
        prompt = arguments.get("prompt", "")
        role_override_str = arguments.get("role_override")

        role_override = None
        if role_override_str:
            try:
                role_override = ModelRole(role_override_str.upper())
            except ValueError:
                pass

        try:
            decision = default_model_router.route(prompt, role=role_override)
            return ToolResult(
                success=True,
                output=decision.to_dict(),
                duration_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Routing inspection failed: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000,
            )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if result.success and result.output and result.output.get("model_name"):
            return ToolVerification(
                verified=True,
                details=f"Task routed to {result.output.get('role')} model '{result.output.get('model_name')}'.",
            )
        return ToolVerification(verified=False, details=result.error or "Routing inspection failed.")
