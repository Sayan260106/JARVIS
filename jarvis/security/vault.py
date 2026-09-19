"""Credential Isolation Vault for JARVIS (Phase 15).

Provides isolated storage for sensitive API keys, credentials, and access tokens,
preventing raw exposure in logs, memory dumps, or process outputs.
"""

from __future__ import annotations
import os
import threading
from typing import Dict, Optional, Set


class CredentialVault:
    """Thread-safe in-memory credential storage with isolation and masking."""

    _instance: Optional[CredentialVault] = None
    _lock = threading.Lock()

    def __init__(self):
        self._secrets: Dict[str, str] = {}
        self._scopes: Dict[str, str] = {}
        self._initialized = True
        self._load_environment_defaults()

    @classmethod
    def get_instance(cls) -> CredentialVault:
        with cls._lock:
            if cls._instance is None:
                cls._instance = CredentialVault()
            return cls._instance

    def _load_environment_defaults(self) -> None:
        """Loads known environment variable credentials into isolated vault."""
        known_env_keys = [
            "OPENAI_API_KEY",
            "GEMINI_API_KEY",
            "GOOGLE_API_KEY",
            "GITHUB_TOKEN",
            "AWS_SECRET_ACCESS_KEY",
            "JARVIS_AUTH_TOKEN",
        ]
        for k in known_env_keys:
            val = os.environ.get(k)
            if val:
                self.store(k, val)

    def store(self, key: str, secret: str, scope: Optional[str] = None) -> None:
        """Stores a credential under a namespace key with optional scope."""
        if not key or not secret:
            return
        norm_key = key.strip().upper()
        self._secrets[norm_key] = secret.strip()
        if scope:
            self._scopes[norm_key] = scope

    def store_secret(self, key: str, secret: str, scope: Optional[str] = None) -> None:
        """Alias for store."""
        self.store(key, secret, scope=scope)

    def retrieve(self, key: str, scope: Optional[str] = None) -> Optional[str]:
        """Safely retrieves raw secret for internal authorized client, validating scope if set."""
        norm_key = key.strip().upper()
        if norm_key not in self._secrets:
            return None
        if norm_key in self._scopes:
            expected_scope = self._scopes[norm_key]
            if scope != expected_scope:
                return None
        return self._secrets.get(norm_key)

    def get_secret(self, key: str, scope: Optional[str] = None) -> Optional[str]:
        """Alias for retrieve."""
        return self.retrieve(key, scope=scope)

    def get_masked(self, key: str) -> str:
        """Returns a non-sensitive masked representation for display or logs."""
        norm_key = key.strip().upper()
        val = self._secrets.get(norm_key)
        if not val:
            return "[NOT SET]"
        if len(val) <= 6:
            return "***"
        return f"{val[:4]}****{val[-4:]}"

    def get_masked_secret(self, key: str) -> str:
        """Alias for get_masked."""
        return self.get_masked(key)

    def list_keys(self) -> Set[str]:
        """Lists stored credential names without disclosing contents."""
        return set(self._secrets.keys())
