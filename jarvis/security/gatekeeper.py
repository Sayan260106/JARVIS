"""Master Security Gatekeeper for JARVIS (Phase 15).

Coordinates:
1. Tool Allowlists
2. Path Restrictions & Sandboxing
3. Command Sanitization & Dangerous Operation Blocking
4. 5-Level Permission Hierarchy & Always-Restricted Gates
5. User Confirmation Workflows
6. Tamper-Evident Audit Logging & Secret Redaction
"""

from __future__ import annotations
import inspect
import os
from typing import Any, Callable, Dict, List, Optional

from jarvis.security.allowlist import ToolAllowlist
from jarvis.security.audit_logger import SecurityAuditLogger
from jarvis.security.path_guard import PathGuard
from jarvis.security.redactor import SecretRedactor
from jarvis.security.sanitizer import CommandSanitizer
from jarvis.security.schemas import (
    AuditEntry,
    SecurityDecision,
    SecurityProfile,
    SecurityVerdict,
)
from jarvis.tools.base import BaseTool, PermissionLevel, RiskLevel


class SecurityGatekeeper:
    """Enterprise security gatekeeper evaluating every attempted tool invocation."""

    ALWAYS_RESTRICTED_KEYWORDS = [
        "format c:",
        "format d:",
        "rm -rf /",
        "rmdir /s /q c:",
        "del /s /q c:",
        "reg delete hklm",
        "disable realtimemonitoring",
        ":(){ :|:& };:",
        "clean disk",
        "format drive",
        "erase hard drive",
    ]

    def __init__(
        self,
        allowlist: Optional[ToolAllowlist] = None,
        path_guard: Optional[PathGuard] = None,
        sanitizer: Optional[CommandSanitizer] = None,
        redactor: Optional[SecretRedactor] = None,
        audit_logger: Optional[SecurityAuditLogger] = None,
        approval_callback: Optional[Callable[..., bool]] = None,
        auto_approve_files: bool = False,
        auto_approve_external: bool = False,
        auto_approve_destructive: bool = False,
    ):
        self.allowlist = allowlist or ToolAllowlist(SecurityProfile.DEVELOPER)
        self.path_guard = path_guard or PathGuard()
        self.sanitizer = sanitizer or CommandSanitizer()
        self.redactor = redactor or SecretRedactor()
        self.audit_logger = audit_logger or SecurityAuditLogger.get_instance()
        self.approval_callback = approval_callback
        self.auto_approve_files = auto_approve_files
        self.auto_approve_external = auto_approve_external
        self.auto_approve_destructive = auto_approve_destructive

    def evaluate_tool_request(
        self,
        tool: BaseTool,
        arguments: Dict[str, Any],
        session_id: str = "",
    ) -> SecurityDecision:
        """Executes full defense-in-depth inspection for a tool invocation."""
        t_name = tool.name
        perm_level = self._normalize_permission_level(tool.effective_permission_level)
        risk_level = tool.risk_level

        # 1. Always Restricted Operations Check
        raw_args_str = str(arguments).lower()
        if any(kw in raw_args_str for kw in self.ALWAYS_RESTRICTED_KEYWORDS) or perm_level == PermissionLevel.ALWAYS_RESTRICTED:
            decision = SecurityDecision(
                allowed=False,
                verdict=SecurityVerdict.BLOCKED_ALWAYS_RESTRICTED,
                permission_level=PermissionLevel.ALWAYS_RESTRICTED,
                risk_level=RiskLevel.HIGH,
                reason="Operation is permanently restricted: dangerous arbitrary system operation.",
                user_prompt_required=False,
            )
            self.audit_logger.log_decision(t_name, arguments, decision, session_id)
            return decision

        # 2. Tool Allowlist Check
        allowed_by_policy, policy_reason = self.allowlist.is_tool_allowed(t_name, perm_level)
        if not allowed_by_policy:
            decision = SecurityDecision(
                allowed=False,
                verdict=SecurityVerdict.BLOCKED_ALLOWLIST,
                permission_level=perm_level,
                risk_level=risk_level,
                reason=policy_reason,
                user_prompt_required=False,
            )
            self.audit_logger.log_decision(t_name, arguments, decision, session_id)
            return decision

        # 3. Path Restrictions & Sandboxing Check
        path_arg = self._extract_path_argument(arguments)
        if path_arg:
            valid_path, path_err = self.path_guard.validate_path(path_arg)
            if not valid_path:
                decision = SecurityDecision(
                    allowed=False,
                    verdict=SecurityVerdict.BLOCKED_PATH_RESTRICTION,
                    permission_level=perm_level,
                    risk_level=RiskLevel.HIGH,
                    reason=f"Path security restriction violation: {path_err}",
                    user_prompt_required=False,
                )
                self.audit_logger.log_decision(t_name, arguments, decision, session_id)
                return decision

        # 4. Command Sanitization Check
        cmd_arg = self._extract_command_argument(arguments)
        if cmd_arg:
            safe_cmd, cmd_err = self.sanitizer.check_command(cmd_arg)
            if not safe_cmd:
                decision = SecurityDecision(
                    allowed=False,
                    verdict=SecurityVerdict.BLOCKED_COMMAND_SANITIZATION,
                    permission_level=PermissionLevel.ALWAYS_RESTRICTED,
                    risk_level=RiskLevel.HIGH,
                    reason=f"Command sanitization failure: {cmd_err}",
                    user_prompt_required=False,
                )
                self.audit_logger.log_decision(t_name, arguments, decision, session_id)
                return decision

        # 5. Evaluate 5-Level Permission Hierarchy
        decision = self._evaluate_permission_level(tool, perm_level, risk_level, arguments)

        # 6. Dispatch Approval Callback if confirmation required
        if decision.user_prompt_required and self.approval_callback is not None:
            approved = self._invoke_callback(tool, arguments, decision)
            if approved:
                decision.allowed = True
                decision.verdict = SecurityVerdict.USER_APPROVED
                decision.user_prompt_required = False
                decision.reason = f"Action '{t_name}' approved by user."
            else:
                decision.allowed = False
                decision.verdict = SecurityVerdict.USER_DECLINED
                decision.user_prompt_required = False
                decision.reason = f"Action '{t_name}' declined by user."

        # 7. Audit Log with Secret Redaction
        self.audit_logger.log_decision(t_name, arguments, decision, session_id)
        return decision

    def _normalize_permission_level(self, level: Any) -> PermissionLevel:
        """Normalizes enum levels supporting Phase 15 and legacy mappings."""
        val = level.value if hasattr(level, "value") else str(level)
        if val in ("LEVEL_0_READ",):
            return PermissionLevel.LEVEL_0_READ
        if val in ("LEVEL_1_NON_DESTRUCTIVE", "LEVEL_1_REVERSIBLE_WRITE"):
            return PermissionLevel.LEVEL_1_NON_DESTRUCTIVE
        if val in ("LEVEL_2_MODIFY_FILES",):
            return PermissionLevel.LEVEL_2_MODIFY_FILES
        if val in ("LEVEL_3_EXTERNAL_COMM", "LEVEL_2_EXTERNAL_ACTION"):
            return PermissionLevel.LEVEL_3_EXTERNAL_COMM
        if val in ("LEVEL_4_DESTRUCTIVE", "LEVEL_3_DESTRUCTIVE"):
            return PermissionLevel.LEVEL_4_DESTRUCTIVE
        if val in ("ALWAYS_RESTRICTED",):
            return PermissionLevel.ALWAYS_RESTRICTED
        return PermissionLevel.LEVEL_4_DESTRUCTIVE

    def _evaluate_permission_level(
        self,
        tool: BaseTool,
        level: PermissionLevel,
        risk: RiskLevel,
        arguments: Dict[str, Any],
    ) -> SecurityDecision:
        """Maps permission level to automatic allowance or confirmation requirement."""
        t_name = tool.name

        # LEVEL 0 — Read: Automatically allowed
        if level == PermissionLevel.LEVEL_0_READ:
            return SecurityDecision(
                allowed=True,
                verdict=SecurityVerdict.ALLOWED,
                permission_level=PermissionLevel.LEVEL_0_READ,
                risk_level=risk,
                reason=f"Level 0 (Read) operation '{t_name}' automatically permitted.",
                user_prompt_required=False,
            )

        # LEVEL 1 — Non-destructive actions: Automatically allowed with audit logging
        if level == PermissionLevel.LEVEL_1_NON_DESTRUCTIVE:
            return SecurityDecision(
                allowed=True,
                verdict=SecurityVerdict.ALLOWED,
                permission_level=PermissionLevel.LEVEL_1_NON_DESTRUCTIVE,
                risk_level=risk,
                reason=f"Level 1 (Non-destructive) action '{t_name}' automatically permitted with audit logging.",
                user_prompt_required=False,
            )

        # LEVEL 2 — Modify user files: Confirmation required
        if level == PermissionLevel.LEVEL_2_MODIFY_FILES:
            if self.auto_approve_files:
                return SecurityDecision(
                    allowed=True,
                    verdict=SecurityVerdict.ALLOWED,
                    permission_level=PermissionLevel.LEVEL_2_MODIFY_FILES,
                    risk_level=risk,
                    reason=f"Level 2 (Modify files) permitted (auto-approve active).",
                )
            return SecurityDecision(
                allowed=False,
                verdict=SecurityVerdict.CONFIRMATION_REQUIRED,
                permission_level=PermissionLevel.LEVEL_2_MODIFY_FILES,
                risk_level=RiskLevel.MEDIUM,
                reason=f"Level 2 action '{t_name}' modifies user files and requires confirmation.",
                user_prompt_required=True,
                custom_prompt=f"Do you authorize '{t_name}' to modify target files?",
            )

        # LEVEL 3 — External communication: Confirmation required + preview
        if level == PermissionLevel.LEVEL_3_EXTERNAL_COMM:
            if self.auto_approve_external:
                return SecurityDecision(
                    allowed=True,
                    verdict=SecurityVerdict.ALLOWED,
                    permission_level=PermissionLevel.LEVEL_3_EXTERNAL_COMM,
                    risk_level=risk,
                    reason=f"Level 3 (External communication) permitted (auto-approve active).",
                )
            preview_builder = getattr(tool, "build_confirmation_preview", None)
            preview = preview_builder(arguments) if callable(preview_builder) else dict(arguments)
            return SecurityDecision(
                allowed=False,
                verdict=SecurityVerdict.CONFIRMATION_REQUIRED,
                permission_level=PermissionLevel.LEVEL_3_EXTERNAL_COMM,
                risk_level=RiskLevel.HIGH,
                reason=f"Level 3 external communication '{t_name}' requires confirmation with parameter preview.",
                user_prompt_required=True,
                confirmation_preview=preview,
            )

        # LEVEL 4 — Destructive / System actions: Confirmation required + impact warning
        if level == PermissionLevel.LEVEL_4_DESTRUCTIVE:
            if self.auto_approve_destructive:
                return SecurityDecision(
                    allowed=True,
                    verdict=SecurityVerdict.ALLOWED,
                    permission_level=PermissionLevel.LEVEL_4_DESTRUCTIVE,
                    risk_level=risk,
                    reason=f"Level 4 (Destructive) action permitted (auto-approve active).",
                )
            custom_builder = getattr(tool, "build_destructive_prompt", None)
            prompt = custom_builder(arguments) if callable(custom_builder) else (
                f"Destructive/system action '{t_name}' has significant or irreversible impact. Do you want to proceed?"
            )
            return SecurityDecision(
                allowed=False,
                verdict=SecurityVerdict.CONFIRMATION_REQUIRED,
                permission_level=PermissionLevel.LEVEL_4_DESTRUCTIVE,
                risk_level=RiskLevel.HIGH,
                reason=f"Level 4 destructive action '{t_name}' requires explicit confirmation.",
                user_prompt_required=True,
                custom_prompt=prompt,
            )

        return SecurityDecision(
            allowed=False,
            verdict=SecurityVerdict.BLOCKED_ALWAYS_RESTRICTED,
            permission_level=PermissionLevel.ALWAYS_RESTRICTED,
            risk_level=RiskLevel.HIGH,
            reason="Unrecognized permission tier.",
            user_prompt_required=False,
        )

    def _extract_path_argument(self, arguments: Dict[str, Any]) -> Optional[str]:
        """Extracts file or directory path argument from arguments dictionary."""
        for key in ["path", "file_path", "target_path", "destination", "workspace_folder", "directory", "target_directory", "dir_path", "folder_path"]:
            if key in arguments and isinstance(arguments[key], str):
                return arguments[key]
        return None

    def _extract_command_argument(self, arguments: Dict[str, Any]) -> Optional[str]:
        """Extracts shell command argument from arguments dictionary."""
        for key in ["command", "cmd", "script", "command_line"]:
            if key in arguments and isinstance(arguments[key], str):
                return arguments[key]
        return None

    def _invoke_callback(
        self,
        tool: BaseTool,
        arguments: Dict[str, Any],
        decision: SecurityDecision,
    ) -> bool:
        """Dispatches to registered user approval callback."""
        if not self.approval_callback:
            return False
        sig = inspect.signature(self.approval_callback)
        param_count = len(sig.parameters)
        if param_count >= 3:
            return bool(self.approval_callback(tool, arguments, decision))
        return bool(self.approval_callback(tool, arguments))
