"""Permission System and Risk Gatekeeper for JARVIS tools.

Prevents autonomous execution of destructive actions without explicit authorization.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional
from jarvis.tools.base import BaseTool, RiskLevel


@dataclass
class PermissionDecision:
    """The verdict of the permission check."""
    allowed: bool
    reason: str
    risk_level: RiskLevel
    user_prompt_required: bool = False


class PermissionSystem:
    """Evaluates whether a tool request is authorized to execute."""

    def __init__(
        self,
        approval_callback: Optional[Callable[[BaseTool, Dict[str, Any]], bool]] = None,
        auto_approve_high: bool = False,
    ):
        self.approval_callback = approval_callback
        self.auto_approve_high = auto_approve_high

    def check_permission(self, tool: BaseTool, arguments: Dict[str, Any]) -> PermissionDecision:
        """Evaluate permission for the given tool and arguments."""
        if tool.risk_level == RiskLevel.LOW:
            return PermissionDecision(
                allowed=True,
                reason="Low-risk tool automatically permitted.",
                risk_level=RiskLevel.LOW,
            )

        if tool.risk_level == RiskLevel.MEDIUM:
            return PermissionDecision(
                allowed=True,
                reason="Medium-risk operation permitted with audit logging.",
                risk_level=RiskLevel.MEDIUM,
            )

        # High risk operations:
        if self.auto_approve_high:
            return PermissionDecision(
                allowed=True,
                reason="High-risk operation permitted (auto-approve active).",
                risk_level=RiskLevel.HIGH,
            )

        if self.approval_callback is not None:
            user_approved = self.approval_callback(tool, arguments)
            if user_approved:
                return PermissionDecision(
                    allowed=True,
                    reason="High-risk operation approved by user.",
                    risk_level=RiskLevel.HIGH,
                )
            else:
                return PermissionDecision(
                    allowed=False,
                    reason=f"High-risk operation '{tool.name}' was declined by user.",
                    risk_level=RiskLevel.HIGH,
                )

        # Default: if high risk and no callback, require prompt
        return PermissionDecision(
            allowed=False,
            reason=f"Tool '{tool.name}' has HIGH risk level and requires user confirmation.",
            risk_level=RiskLevel.HIGH,
            user_prompt_required=True,
        )
