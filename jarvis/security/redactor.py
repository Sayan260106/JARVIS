"""Secret Redaction Engine for JARVIS (Phase 15).

Scans strings, data structures, and tool outputs to mask API keys, passwords,
bearer tokens, and private keys before logging or display.
"""

from __future__ import annotations
import re
from typing import Any, Dict, List, Tuple


class SecretRedactor:
    """Intercepts and masks confidential tokens across inputs, outputs, and logs."""

    REDACTION_PATTERNS: List[Tuple[str, str]] = [
        # OpenAI API Keys (sk-...)
        (r"\bsk-[A-Za-z0-9_-]{20,}\b", "[REDACTED_OPENAI_KEY]"),
        # Google API Keys (AIza...)
        (r"\bAIza[0-9A-Za-z-_]{30,45}\b", "[REDACTED_GOOGLE_KEY]"),
        # GitHub Tokens (ghp_..., github_pat_...)
        (r"\bghp_[A-Za-z0-9]{36}\b", "[REDACTED_GITHUB_TOKEN]"),
        (r"\bgithub_pat_[A-Za-z0-9_]{50,}\b", "[REDACTED_GITHUB_TOKEN]"),
        # AWS Access Key IDs (AKIA...)
        (r"\bAKIA[0-9A-Z]{16}\b", "[REDACTED_AWS_KEY]"),
        # Generic Bearer Tokens
        (r"(?i)\bBearer\s+[A-Za-z0-9_\-\.]{25,}\b", "Bearer [REDACTED_BEARER_TOKEN]"),
        # Passwords in URLs (http://user:password@host)
        (r"(https?://[^:\s]+:)([^@\s]+)(@)", r"\1[REDACTED_PASSWORD]\3"),
        # PEM Private Keys
        (
            r"-----BEGIN (?:[A-Z0-9_-]+ )?PRIVATE KEY-----[\s\S]*?-----END (?:[A-Z0-9_-]+ )?PRIVATE KEY-----",
            "[REDACTED_PRIVATE_KEY]",
        ),
        # Generic API Key keyword assignments (api_key = "...", token = "...")
        (
            r"""(?i)(?:api_key|access_token|secret_key|auth_token)\s*[:=]\s*["']([^"']{12,})["']""",
            r'api_key="[REDACTED_SECRET]"',
        ),
    ]

    def redact_text(self, text: str) -> str:
        """Applies all regex redactions to a raw text string."""
        if not text or not isinstance(text, str):
            return text

        redacted = text
        for pattern, replacement in self.REDACTION_PATTERNS:
            redacted = re.sub(pattern, replacement, redacted)
        return redacted

    def redact_object(self, data: Any) -> Any:
        """Recursively walks dictionaries, lists, and strings to redact sensitive tokens."""
        if isinstance(data, str):
            return self.redact_text(data)
        elif isinstance(data, dict):
            redacted_dict = {}
            for k, v in data.items():
                k_str = str(k).lower()
                # Check for password/secret key names
                if any(sec in k_str for sec in ["password", "secret", "api_key", "token", "credential"]):
                    if isinstance(v, str) and len(v) > 0:
                        redacted_dict[k] = "[REDACTED_SECRET]"
                    else:
                        redacted_dict[k] = self.redact_object(v)
                else:
                    redacted_dict[k] = self.redact_object(v)
            return redacted_dict
        elif isinstance(data, (list, tuple, set)):
            res = [self.redact_object(item) for item in data]
            return type(data)(res)
        return data


_default_redactor = SecretRedactor()


def redact_text(text: str) -> str:
    """Convenience module helper to redact text."""
    return _default_redactor.redact_text(text)


def redact_object(data: Any) -> Any:
    """Convenience module helper to redact objects."""
    return _default_redactor.redact_object(data)

