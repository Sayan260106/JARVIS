"""JARVIS Security & Permission System (Phase 15).

Provides 5-level permission hierarchy, always-restricted operations,
tool allowlists, path restrictions/sandboxing, command sanitization,
credential isolation/vault, secret redaction, and tamper-evident audit logging.
"""

from __future__ import annotations
from typing import Optional

from jarvis.security.schemas import (
    SecurityVerdict,
    SecurityProfile,
    SecurityDecision,
    AuditEntry,
)
from jarvis.security.sanitizer import CommandSanitizer
from jarvis.security.path_guard import PathGuard
from jarvis.security.redactor import SecretRedactor, redact_text
from jarvis.security.vault import CredentialVault
from jarvis.security.allowlist import ToolAllowlist
from jarvis.security.audit_logger import SecurityAuditLogger
from jarvis.security.gatekeeper import SecurityGatekeeper

_default_gatekeeper: Optional[SecurityGatekeeper] = None


def get_gatekeeper() -> SecurityGatekeeper:
    """Returns the global SecurityGatekeeper singleton."""
    global _default_gatekeeper
    if _default_gatekeeper is None:
        _default_gatekeeper = SecurityGatekeeper()
    return _default_gatekeeper


def set_gatekeeper(gatekeeper: SecurityGatekeeper) -> None:
    """Sets the global SecurityGatekeeper singleton."""
    global _default_gatekeeper
    _default_gatekeeper = gatekeeper


def get_audit_logger() -> SecurityAuditLogger:
    """Returns the global SecurityAuditLogger singleton."""
    return SecurityAuditLogger.get_instance()


__all__ = [
    "SecurityVerdict",
    "SecurityProfile",
    "SecurityDecision",
    "AuditEntry",
    "CommandSanitizer",
    "PathGuard",
    "SecretRedactor",
    "redact_text",
    "CredentialVault",
    "ToolAllowlist",
    "SecurityAuditLogger",
    "SecurityGatekeeper",
    "get_gatekeeper",
    "set_gatekeeper",
    "get_audit_logger",
]
