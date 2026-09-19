"""Tool Allowlist & Profile Enforcer for JARVIS (Phase 15).

Manages tool execution permissions across configured security profiles.
"""

from __future__ import annotations
from __future__ import annotations
from typing import List, Optional, Set, Tuple

from jarvis.security.schemas import SecurityProfile
from jarvis.tools.base import PermissionLevel


class ToolAllowlist:
    """Controls permitted tool invocation based on active security posture profile."""

    def __init__(
        self,
        profile: SecurityProfile = SecurityProfile.DEVELOPER,
        allowed_tools: Optional[List[str]] = None,
        blocked_tools: Optional[List[str]] = None,
    ):
        self.profile = profile
        self.explicit_allowed_tools: Set[str] = {t.lower() for t in (allowed_tools or [])}
        self.explicit_blocked_tools: Set[str] = {t.lower() for t in (blocked_tools or [])}

    def set_profile(self, profile: SecurityProfile) -> None:
        """Updates the active security profile."""
        self.profile = profile

    def allow_tool(self, tool_name: str) -> None:
        """Adds a tool to the explicit allowlist."""
        self.explicit_allowed_tools.add(tool_name.lower())

    def block_tool(self, tool_name: str) -> None:
        """Adds a tool to the explicit blocklist."""
        self.explicit_blocked_tools.add(tool_name.lower())

    def is_tool_allowed(
        self,
        tool_name: str,
        permission_level: PermissionLevel,
    ) -> Tuple[bool, str]:
        """Evaluates whether the specified tool is permitted under the active profile."""
        t_name = tool_name.lower()

        # 1. Explicit blocklist check
        if t_name in self.explicit_blocked_tools:
            return False, f"Tool '{tool_name}' is explicitly blacklisted by administrator policy."

        # 2. Explicit allowlist override
        if t_name in self.explicit_allowed_tools:
            return True, ""

        # 3. Always restricted operations are NEVER allowed via allowlist
        if permission_level == PermissionLevel.ALWAYS_RESTRICTED:
            return False, f"Tool '{tool_name}' is permanently restricted due to dangerous system impact."

        # 4. Profile-based enforcement
        if self.profile == SecurityProfile.STRICT_READ_ONLY:
            if permission_level != PermissionLevel.LEVEL_0_READ:
                return False, f"Tool '{tool_name}' (Level {permission_level.value}) blocked: STRICT_READ_ONLY profile active."
            return True, ""

        if self.profile == SecurityProfile.AUTONOMOUS_SAFE:
            if permission_level not in (PermissionLevel.LEVEL_0_READ, PermissionLevel.LEVEL_1_NON_DESTRUCTIVE):
                return False, f"Tool '{tool_name}' (Level {permission_level.value}) blocked: AUTONOMOUS_SAFE allows Levels 0 and 1 only."
            return True, ""

        if self.profile == SecurityProfile.DEVELOPER:
            if permission_level == PermissionLevel.LEVEL_4_DESTRUCTIVE:
                return False, f"Tool '{tool_name}' (Level 4 Destructive) blocked: DEVELOPER profile permits Levels 0-3 only."
            return True, ""

        if self.profile == SecurityProfile.UNRESTRICTED_ADMIN:
            return True, ""

        return True, ""
