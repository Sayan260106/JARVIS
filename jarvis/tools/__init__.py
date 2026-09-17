"""JARVIS Tools System: Base classes, registry, validators, permissions, and tool implementations."""

from jarvis.tools.base import (
    BaseTool,
    RiskLevel,
    ToolParameter,
    ToolResult,
    ToolVerification,
)
from jarvis.tools.validator import ToolValidator, ValidationResult
from jarvis.tools.permissions import PermissionSystem, PermissionDecision
from jarvis.tools.registry import ToolRegistry
from jarvis.tools.system_tools import (
    OpenFileTool,
    OpenApplicationTool,
    SearchFilesTool,
    CreateFileTool,
    MoveFileTool,
    DeleteFileTool,
    RunCommandTool,
    TakeScreenshotTool,
    GetSystemInfoTool,
    LockPCTool,
    ShutdownTool,
    RestartTool,
)
from jarvis.tools.productivity_tools import (
    CreateFolderTool,
    CheckProcessTool,
    GetHardwareMetricsTool,
    SetReminderTool,
)
from jarvis.tools.web_tools import BrowserSearchTool


def get_default_registry() -> ToolRegistry:
    """Build and return a ToolRegistry populated with all default tools."""
    registry = ToolRegistry()
    # System & Computer Control
    registry.register(OpenFileTool())
    registry.register(OpenApplicationTool())
    registry.register(SearchFilesTool())
    registry.register(CreateFileTool())
    registry.register(MoveFileTool())
    registry.register(DeleteFileTool())
    registry.register(RunCommandTool())
    registry.register(TakeScreenshotTool())
    registry.register(GetSystemInfoTool())
    registry.register(LockPCTool())
    registry.register(ShutdownTool())
    registry.register(RestartTool())
    # Productivity & Telemetry
    registry.register(CreateFolderTool())
    registry.register(CheckProcessTool())
    registry.register(GetHardwareMetricsTool())
    registry.register(SetReminderTool())
    # Web
    registry.register(BrowserSearchTool())
    return registry


__all__ = [
    "BaseTool",
    "RiskLevel",
    "ToolParameter",
    "ToolResult",
    "ToolVerification",
    "ToolValidator",
    "ValidationResult",
    "PermissionSystem",
    "PermissionDecision",
    "ToolRegistry",
    "OpenFileTool",
    "OpenApplicationTool",
    "SearchFilesTool",
    "CreateFileTool",
    "MoveFileTool",
    "DeleteFileTool",
    "RunCommandTool",
    "TakeScreenshotTool",
    "GetSystemInfoTool",
    "LockPCTool",
    "ShutdownTool",
    "RestartTool",
    "CreateFolderTool",
    "CheckProcessTool",
    "GetHardwareMetricsTool",
    "SetReminderTool",
    "BrowserSearchTool",
    "get_default_registry",
]
