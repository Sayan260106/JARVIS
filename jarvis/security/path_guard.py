"""Path Restrictions & Sandboxing Guard for JARVIS (Phase 15).

Restricts filesystem access to authorized project workspaces and explicitly
blocks path traversal and sensitive OS/credential directories.
"""

from __future__ import annotations
import os
import tempfile
from typing import List, Optional, Tuple


class PathGuard:
    """Guards against directory traversal and unauthorized access to sensitive system paths."""

    FORBIDDEN_DIR_PATTERNS = [
        "c:\\windows",
        "c:\\windows\\system32",
        "c:\\program files",
        "c:\\program files (x86)",
        "\\.ssh",
        "\\.aws",
        "\\.gemini",
        "\\credentials\\",
        "\\sam",
        "\\system32",
    ]

    FORBIDDEN_FILE_PATTERNS = [
        "id_rsa",
        "id_ed25519",
        "id_ecdsa",
        ".env",
        "credentials.json",
        "service_account.json",
        "ntuser.dat",
        "sam",
        "system",
    ]

    def __init__(self, allowed_roots: Optional[List[str]] = None, allow_temp: bool = True):
        roots = list(allowed_roots) if allowed_roots is not None else [os.path.abspath(".")]
        if allow_temp:
            roots.append(tempfile.gettempdir())
        self.allowed_roots = [
            os.path.realpath(os.path.abspath(r)).lower()
            for r in roots
        ]

    def add_allowed_root(self, path: str) -> None:
        """Adds an additional allowed workspace directory."""
        self.allowed_roots.append(os.path.realpath(os.path.abspath(path)).lower())

    def validate_path(self, target_path: str) -> Tuple[bool, str]:
        """Validates that target path is within allowed workspaces and not forbidden."""
        if not target_path:
            return True, ""

        # Normalize and resolve all symlinks and traversal components
        try:
            resolved_abs = os.path.realpath(os.path.abspath(target_path))
        except Exception as e:
            return False, f"Invalid path specification: {e}"

        resolved_lower = resolved_abs.lower()

        # 1. Block Traversal attempts in raw string
        if ".." in target_path.replace("\\", "/").split("/"):
            # Check if resolved escaped allowed roots
            in_allowed = any(resolved_lower.startswith(root) for root in self.allowed_roots)
            if not in_allowed:
                return False, f"Path traversal attack detected: target '{target_path}' escapes workspace."

        # 2. Check Forbidden System & Credential Directories
        for forbidden in self.FORBIDDEN_DIR_PATTERNS:
            if forbidden in resolved_lower:
                return False, f"Access to sensitive directory '{forbidden}' is strictly prohibited."

        # 3. Check Forbidden Sensitive Files
        base_name = os.path.basename(resolved_lower)
        if base_name in self.FORBIDDEN_FILE_PATTERNS:
            return False, f"Access to sensitive credential or system file '{base_name}' is prohibited."

        # 4. Enforce Workspace Sandboxing
        in_allowed_root = any(resolved_lower.startswith(root) for root in self.allowed_roots)
        if not in_allowed_root:
            return False, f"Path '{resolved_abs}' is outside permitted workspace roots."

        return True, ""
