"""Standardized Tool Interface for JARVIS.

Every tool implements typed parameters, risk levels, isolated execution, and ground-truth verification.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import time


class RiskLevel(str, Enum):
    """Classification of tool execution impact and safety risk."""
    LOW = "LOW"         # Read-only queries, passive inspection, safe info retrieval (Auto-allowed)
    MEDIUM = "MEDIUM"   # Local creation, non-destructive app/file opening (Permitted with logging)
    HIGH = "HIGH"       # File deletion, arbitrary shell execution, system reboot/shutdown (Requires approval)


class PermissionLevel(str, Enum):
    """The 4-level permission taxonomy for autonomous agent safety."""
    LEVEL_0_READ = "LEVEL_0_READ"                       # Automatic (read file, search, system info, screen capture)
    LEVEL_1_REVERSIBLE_WRITE = "LEVEL_1_REVERSIBLE_WRITE" # Reversible write (create folder/file, move file, open app)
    LEVEL_2_EXTERNAL_ACTION = "LEVEL_2_EXTERNAL_ACTION"   # External actions (email, publish, upload, post, purchase) -> requires confirmation + preview
    LEVEL_3_DESTRUCTIVE = "LEVEL_3_DESTRUCTIVE"           # Destructive (delete, shutdown, format, admin) -> requires explicit confirmation + impact warning


@dataclass
class ToolParameter:
    """Specification of a single parameter accepted by a tool."""
    name: str
    type: str                  # "string", "integer", "boolean", "number", "array"
    description: str
    required: bool = True
    default: Any = None


@dataclass
class ToolResult:
    """The raw execution result returned by a tool."""
    success: bool
    output: Any
    error: Optional[str] = None
    duration_ms: float = 0.0


@dataclass
class ToolVerification:
    """Ground-truth verification verdict confirming if the action actually achieved its intended effect."""
    verified: bool
    details: str


class BaseTool(ABC):
    """Abstract base class for all JARVIS tools."""

    name: str = ""
    description: str = ""
    risk_level: RiskLevel = RiskLevel.LOW
    permission_level: Optional[PermissionLevel] = None
    parameters: Dict[str, ToolParameter] = {}

    @property
    def effective_permission_level(self) -> PermissionLevel:
        """Derive permission level explicitly or backward-compatibly from risk_level."""
        if self.permission_level is not None:
            return self.permission_level
        if self.risk_level == RiskLevel.HIGH:
            return PermissionLevel.LEVEL_3_DESTRUCTIVE
        elif self.risk_level == RiskLevel.MEDIUM:
            return PermissionLevel.LEVEL_1_REVERSIBLE_WRITE
        return PermissionLevel.LEVEL_0_READ

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """Execute the tool action with the validated arguments.

        Args:
            **kwargs: Validated keyword arguments matching tool parameters.

        Returns:
            ToolResult containing execution status and output.
        """
        pass

    @abstractmethod
    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        """Verify against the real environment that the action succeeded (Rule 1).

        Args:
            arguments: The arguments passed to execute().
            result: The ToolResult returned by execute().

        Returns:
            ToolVerification with verified boolean and diagnostic details.
        """
        pass

    def to_schema(self) -> Dict[str, Any]:
        """Convert tool signature into standard JSON schema format for Ollama / LLM."""
        properties = {}
        required = []

        for param_name, param in self.parameters.items():
            properties[param_name] = {
                "type": param.type,
                "description": param.description,
            }
            if param.default is not None:
                properties[param_name]["default"] = param.default
            if param.required:
                required.append(param_name)

        return {
            "name": self.name,
            "description": self.description,
            "risk_level": self.risk_level.value,
            "permission_level": self.effective_permission_level.value,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }
