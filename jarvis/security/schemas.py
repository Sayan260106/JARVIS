"""Data schemas for JARVIS Security & Permission System (Phase 15).

Defines typed contracts for:
- 5-level permission hierarchy & always-restricted actions
- Security decisions & verdicts
- Tool allowlists & policies
- Audit log telemetry
"""

from __future__ import annotations
from dataclasses import dataclass, field
import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from jarvis.tools.base import PermissionLevel, RiskLevel


class SecurityVerdict(str, Enum):
    """The outcome of a security gatekeeper inspection."""
    ALLOWED = "ALLOWED"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    BLOCKED_ALLOWLIST = "BLOCKED_ALLOWLIST"
    BLOCKED_PATH_RESTRICTION = "BLOCKED_PATH_RESTRICTION"
    BLOCKED_COMMAND_SANITIZATION = "BLOCKED_COMMAND_SANITIZATION"
    BLOCKED_ALWAYS_RESTRICTED = "BLOCKED_ALWAYS_RESTRICTED"
    USER_APPROVED = "USER_APPROVED"
    USER_DECLINED = "USER_DECLINED"


class SecurityProfile(str, Enum):
    """Pre-configured security posture profiles."""
    AUTONOMOUS_SAFE = "AUTONOMOUS_SAFE"       # Levels 0 and 1 only
    DEVELOPER = "DEVELOPER"                   # Levels 0-3 with confirmation gates
    UNRESTRICTED_ADMIN = "UNRESTRICTED_ADMIN" # Levels 0-4 with confirmation gates
    STRICT_READ_ONLY = "STRICT_READ_ONLY"     # Level 0 only


@dataclass
class SecurityDecision:
    """The definitive gatekeeping decision for an attempted action."""
    allowed: bool
    verdict: SecurityVerdict
    permission_level: PermissionLevel
    risk_level: RiskLevel
    reason: str
    user_prompt_required: bool = False
    confirmation_preview: Optional[Dict[str, Any]] = None
    custom_prompt: Optional[str] = None
    sanitized_arguments: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "verdict": self.verdict.value,
            "permission_level": self.permission_level.value,
            "risk_level": self.risk_level.value,
            "reason": self.reason,
            "user_prompt_required": self.user_prompt_required,
            "confirmation_preview": self.confirmation_preview,
            "custom_prompt": self.custom_prompt,
        }


@dataclass
class AuditEntry:
    """Tamper-evident record of a security evaluation."""
    entry_id: str
    timestamp: str
    tool_name: str
    permission_level: str
    verdict: str
    reason: str
    risk_level: str
    arguments_redacted: Dict[str, Any] = field(default_factory=dict)
    session_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "tool_name": self.tool_name,
            "permission_level": self.permission_level,
            "verdict": self.verdict,
            "reason": self.reason,
            "risk_level": self.risk_level,
            "arguments_redacted": self.arguments_redacted,
        }
