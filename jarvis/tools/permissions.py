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


class PermissionSystem:
    """Evaluates whether a tool request is authorized to execute based on 4-level safety taxonomy."""

    def __init__(
        self,
        approval_callback: Optional[Callable[..., bool]] = None,
        auto_approve_high: bool = False,
        auto_approve_external: bool = False,
        auto_approve_destructive: bool = False,
    ):
        self.approval_callback = approval_callback
        # auto_approve_high sets both external and destructive for backward compatibility
        self.auto_approve_high = auto_approve_high
        self.auto_approve_external = auto_approve_external or auto_approve_high
        self.auto_approve_destructive = auto_approve_destructive or auto_approve_high

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

    def check_permission(self, tool: BaseTool, arguments: Dict[str, Any]) -> PermissionDecision:
        """Evaluate permission for the given tool and arguments."""
        perm_level = tool.effective_permission_level

        # LEVEL 0 — READ (Automatic)
        if perm_level == PermissionLevel.LEVEL_0_READ:
            return PermissionDecision(
                allowed=True,
                reason="Level 0 Read operation automatically permitted.",
                risk_level=tool.risk_level,
                permission_level=PermissionLevel.LEVEL_0_READ,
            )

        # LEVEL 1 — REVERSIBLE WRITE (Usually automatic with audit logging)
        if perm_level == PermissionLevel.LEVEL_1_REVERSIBLE_WRITE:
            return PermissionDecision(
                allowed=True,
                reason="Level 1 Reversible Write operation permitted with audit logging.",
                risk_level=tool.risk_level,
                permission_level=PermissionLevel.LEVEL_1_REVERSIBLE_WRITE,
            )

        # LEVEL 2 — EXTERNAL ACTION (Require confirmation with parameter preview)
        if perm_level == PermissionLevel.LEVEL_2_EXTERNAL_ACTION:
            # Build preview dict
            preview = getattr(tool, "build_confirmation_preview", None)
            preview_data = preview(arguments) if callable(preview) else dict(arguments)

            decision = PermissionDecision(
                allowed=False,
                reason=f"External action '{tool.name}' requires user confirmation before proceeding.",
                risk_level=tool.risk_level,
                permission_level=PermissionLevel.LEVEL_2_EXTERNAL_ACTION,
                user_prompt_required=True,
                confirmation_preview=preview_data,
            )

            if self.auto_approve_external:
                decision.allowed = True
                decision.user_prompt_required = False
                decision.reason = "External action permitted (auto-approve active)."
                return decision

            if self.approval_callback is not None:
                approved = self._invoke_callback(tool, arguments, decision)
                if approved:
                    decision.allowed = True
                    decision.user_prompt_required = False
                    decision.reason = "External action approved by user."
                else:
                    decision.allowed = False
                    decision.user_prompt_required = False
                    decision.reason = f"External action '{tool.name}' was declined by user."
                return decision

            return decision

        # LEVEL 3 — DESTRUCTIVE (Require explicit confirmation + warning)
        if perm_level == PermissionLevel.LEVEL_3_DESTRUCTIVE:
            # Check for specialized custom warning prompt
            custom_builder = getattr(tool, "build_destructive_prompt", None)
            custom_prompt = custom_builder(arguments) if callable(custom_builder) else (
                f"Destructive action '{tool.name}' is irreversible. Do you want to proceed?"
            )

            decision = PermissionDecision(
                allowed=False,
                reason=f"Destructive action '{tool.name}' requires explicit confirmation.",
                risk_level=RiskLevel.HIGH,
                permission_level=PermissionLevel.LEVEL_3_DESTRUCTIVE,
                user_prompt_required=True,
                custom_prompt=custom_prompt,
            )

            if self.auto_approve_destructive:
                decision.allowed = True
                decision.user_prompt_required = False
                decision.reason = "Destructive operation permitted (auto-approve active)."
                return decision

            if self.approval_callback is not None:
                approved = self._invoke_callback(tool, arguments, decision)
                if approved:
                    decision.allowed = True
                    decision.user_prompt_required = False
                    decision.reason = "Destructive operation approved by user."
                else:
                    decision.allowed = False
                    decision.user_prompt_required = False
                    decision.reason = f"Destructive operation '{tool.name}' was declined by user."
                return decision

            return decision

        # Fallback
        return PermissionDecision(
            allowed=False,
            reason="Unrecognized permission level.",
            risk_level=RiskLevel.HIGH,
            permission_level=PermissionLevel.LEVEL_3_DESTRUCTIVE,
            user_prompt_required=True,
        )
