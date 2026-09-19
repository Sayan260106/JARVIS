"""Permission System and 4-Level Risk Gatekeeper for JARVIS.

Enforces:
- LEVEL 0 — READ: Read file, search, system info, screen capture -> Automatic
- LEVEL 1 — REVERSIBLE WRITE: Create folder, create file, move file, open application -> Automatic with logging
- LEVEL 2 — EXTERNAL ACTION: Send email, publish, upload, post, purchase -> Require confirmation + preview
- LEVEL 3 — DESTRUCTIVE: Delete, shutdown, format, administrator commands -> Require explicit confirmation
"""

from __future__ import annotations
import inspect
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional
from jarvis.tools.base import BaseTool, RiskLevel, PermissionLevel


@dataclass
class PermissionDecision:
    """The verdict of the permission check."""
    allowed: bool
    reason: str
    risk_level: RiskLevel
    permission_level: PermissionLevel = PermissionLevel.LEVEL_0_READ
    user_prompt_required: bool = False
    confirmation_preview: Optional[Dict[str, Any]] = None
    custom_prompt: Optional[str] = None
    verdict: Optional[Any] = None


class PermissionSystem:
    """Evaluates whether a tool request is authorized to execute based on 5-level safety taxonomy and enterprise gatekeeping."""

    def __init__(
        self,
        approval_callback: Optional[Callable[..., bool]] = None,
        auto_approve_high: bool = False,
        auto_approve_external: bool = False,
        auto_approve_destructive: bool = False,
        auto_approve_files: bool = False,
        gatekeeper: Optional[Any] = None,
    ):
        self.approval_callback = approval_callback
        # auto_approve_high sets both external and destructive for backward compatibility
        self.auto_approve_high = auto_approve_high
        self.auto_approve_external = auto_approve_external or auto_approve_high
        self.auto_approve_destructive = auto_approve_destructive or auto_approve_high
        self.auto_approve_files = auto_approve_files or auto_approve_high

        if gatekeeper is not None:
            self.gatekeeper = gatekeeper
        else:
            from jarvis.security.allowlist import ToolAllowlist
            from jarvis.security.schemas import SecurityProfile
            from jarvis.security.gatekeeper import SecurityGatekeeper
            self.gatekeeper = SecurityGatekeeper(
                allowlist=ToolAllowlist(SecurityProfile.UNRESTRICTED_ADMIN),
                approval_callback=self.approval_callback,
                auto_approve_files=self.auto_approve_files,
                auto_approve_external=self.auto_approve_external,
                auto_approve_destructive=self.auto_approve_destructive,
            )

    def _invoke_callback(
        self,
        tool: BaseTool,
        arguments: Dict[str, Any],
        decision: PermissionDecision,
    ) -> bool:
        """Invokes approval callback supporting both 2-arg and 3-arg signatures."""
        if not self.approval_callback:
            return False
        sig = inspect.signature(self.approval_callback)
        param_count = len(sig.parameters)
        if param_count >= 3:
            return bool(self.approval_callback(tool, arguments, decision))
        return bool(self.approval_callback(tool, arguments))

    def check_permission(self, tool: BaseTool, arguments: Dict[str, Any], session_id: str = "") -> PermissionDecision:
        """Evaluate permission for the given tool and arguments via SecurityGatekeeper."""
        # Synchronize gatekeeper settings
        self.gatekeeper.approval_callback = self.approval_callback
        self.gatekeeper.auto_approve_files = self.auto_approve_files
        self.gatekeeper.auto_approve_external = self.auto_approve_external
        self.gatekeeper.auto_approve_destructive = self.auto_approve_destructive

        sec_decision = self.gatekeeper.evaluate_tool_request(tool, arguments, session_id=session_id)

        return PermissionDecision(
            allowed=sec_decision.allowed,
            reason=sec_decision.reason,
            risk_level=sec_decision.risk_level,
            permission_level=sec_decision.permission_level,
            user_prompt_required=sec_decision.user_prompt_required,
            confirmation_preview=sec_decision.confirmation_preview,
            custom_prompt=sec_decision.custom_prompt,
            verdict=sec_decision.verdict,
        )

    def evaluate(self, tool: Any, arguments: Dict[str, Any], session_id: str = "") -> PermissionDecision:
        """Convenience evaluation accepting either a BaseTool instance or tool name."""
        if isinstance(tool, str):
            from jarvis.tools import get_default_registry
            tool_obj = get_default_registry().get(tool)
            if tool_obj is None:
                return PermissionDecision(allowed=True, reason="Unregistered tool or simulation step")
            tool = tool_obj
        return self.check_permission(tool, arguments, session_id=session_id)
