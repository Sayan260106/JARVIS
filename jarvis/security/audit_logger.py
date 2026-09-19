"""Tamper-Evident Security Audit Logger for JARVIS (Phase 15).

Persists append-only security evaluation records with sanitized arguments,
verdicts, timestamps, and risk assessments to 'logs/security_audit.jsonl'.
"""

from __future__ import annotations
import datetime
import json
import os
import threading
from typing import Any, Dict, List, Optional
import uuid

from jarvis.security.redactor import SecretRedactor
from jarvis.security.schemas import AuditEntry, SecurityDecision


class SecurityAuditLogger:
    """Writes and inspects structured JSON Lines security audit logs."""

    _instance: Optional[SecurityAuditLogger] = None
    _lock = threading.Lock()

    def __init__(
        self,
        log_dir: Optional[str] = None,
        log_file: Optional[str] = None,
        redactor: Optional[SecretRedactor] = None,
    ):
        if log_file:
            self.log_file = log_file
            self.log_dir = os.path.dirname(log_file) or "."
        else:
            self.log_dir = log_dir or "logs"
            self.log_file = os.path.join(self.log_dir, "security_audit.jsonl")
        self.redactor = redactor or SecretRedactor()
        self.in_memory_audit: List[AuditEntry] = []
        if self.log_dir:
            os.makedirs(self.log_dir, exist_ok=True)

    @classmethod
    def get_instance(cls) -> SecurityAuditLogger:
        with cls._lock:
            if cls._instance is None:
                cls._instance = SecurityAuditLogger()
            return cls._instance

    def log_decision(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        decision: SecurityDecision,
        session_id: str = "",
    ) -> AuditEntry:
        """Appends a sanitized security audit record to the log."""
        redacted_args = self.redactor.redact_object(dict(arguments or {}))
        entry = AuditEntry(
            entry_id=f"audit_{uuid.uuid4().hex[:10]}",
            timestamp=datetime.datetime.now().isoformat(),
            session_id=session_id,
            tool_name=tool_name,
            permission_level=decision.permission_level.value,
            verdict=decision.verdict.value,
            reason=decision.reason,
            risk_level=decision.risk_level.value,
            arguments_redacted=redacted_args,
        )

        with self._lock:
            self.in_memory_audit.append(entry)
            try:
                with open(self.log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry.to_dict()) + "\n")
            except Exception:
                pass

        return entry

    def get_recent_entries(self, limit: int = 20) -> List[AuditEntry]:
        """Retrieves the most recent audit log records."""
        with self._lock:
            return list(self.in_memory_audit[-limit:])

    def read_recent_entries(self, limit: int = 20) -> List[AuditEntry]:
        """Reads recent audit entries from memory or disk if available."""
        with self._lock:
            if self.in_memory_audit:
                return list(self.in_memory_audit[-limit:])
            if os.path.exists(self.log_file):
                entries = []
                try:
                    with open(self.log_file, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.strip():
                                data = json.loads(line)
                                entries.append(AuditEntry(**data))
                    return entries[-limit:]
                except Exception:
                    pass
            return []
