"""Command Sanitization & Dangerous Operation Blocker for JARVIS (Phase 15).

Scans shell/CLI commands to detect and block destructive, malicious, or
arbitrary system-compromising operations.
"""

from __future__ import annotations
import re
from typing import List, Tuple


class CommandSanitizer:
    """Detects and blocks dangerous arbitrary system commands."""

    PROHIBITED_COMMAND_PATTERNS: List[Tuple[str, str]] = [
        # Disk formatting
        (r"\bformat\s+[a-zA-Z]:", "Disk format commands are strictly prohibited."),
        (r"\bmkfs(?:\.[a-z0-9]+)?\b", "Filesystem format commands are strictly prohibited."),
        (r"\bdiskpart\b", "Disk partition manipulation is strictly prohibited."),

        # System root / recursive drive wipe
        (r"rmdir\s+(?:/[sS]\s+/[qQ]|/[qQ]\s+/[sS])\s+[cC]:\\?(?:\s|$)", "Recursive deletion of primary system drive is strictly prohibited."),
        (r"del\s+(?:/[sS]\s+/[qQ]|/[qQ]\s+/[sS])\s+[cC]:\\?(?:\s|$)", "Drive-wide file deletion is strictly prohibited."),
        (r"rm\s+-(?:rf|fr|r)\s+/(?:\s|$|\*)", "Root filesystem recursive deletion is strictly prohibited."),

        # Registry destruction
        (r"reg\s+delete\s+(?:hklm|hkcu|hkcr|hkey_local_machine)", "Registry root deletion is strictly prohibited."),

        # Fork bombs
        (r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", "Fork bomb detected and blocked."),
        (r"%\s*0\s*\|\s*%\s*0", "Windows batch fork bomb detected and blocked."),

        # Disabling Windows Defender / Firewalls
        (r"set-mppreference\s+.*-disablerealtimemonitoring\s+\$true", "Disabling antivirus protection is strictly prohibited."),
        (r"netsh\s+advfirewall\s+set\s+.*state\s+off", "Disabling system firewalls is strictly prohibited."),

        # Remote execution piping
        (r"curl\s+[^\n|;]+?\|\s*(?:bash|sh|powershell|iex)", "Direct piping of remote content to shell interpreter is prohibited."),
        (r"wget\s+[^\n|;]+?\|\s*(?:bash|sh|powershell|iex)", "Direct piping of remote content to shell interpreter is prohibited."),
        (r"iex\s*\(\s*(?:new-object|iwr|curl)", "PowerShell Invoke-Expression piping is prohibited."),

        # BCD / Boot tampering
        (r"\bbcdedit\b", "Boot configuration modification is strictly prohibited."),
    ]

    def check_command(self, command: str) -> Tuple[bool, str]:
        """Checks if command contains dangerous or always-restricted instructions."""
        cleaned = command.strip()
        lower = cleaned.lower()

        for pattern, reason in self.PROHIBITED_COMMAND_PATTERNS:
            if re.search(pattern, lower):
                return False, reason

        return True, ""

    def sanitize(self, command: str) -> str:
        """Strips unsafe trailing control characters or normalization escapes."""
        return command.strip().strip("`").strip()
