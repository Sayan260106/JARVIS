"""Phase 10 Context Awareness Subsystem for JARVIS.

Exports the core context collector, resolver, and typed telemetry schemas.
"""

from jarvis.subsystems.context.schemas import (
    AppCategory,
    ApplicationContext,
    WindowContext,
    BrowserContext,
    SelectionContext,
    ClipboardContext,
    OpenFileContext,
    ScreenStateContext,
    ProcessContextSummary,
    ActiveTaskContext,
    SystemContextSnapshot,
    DeicticTargetType,
    ResolvedContextAction,
)
from jarvis.subsystems.context.browser_detector import BrowserDetector
from jarvis.subsystems.context.selection_detector import SelectionDetector
from jarvis.subsystems.context.collector import ContextCollector
from jarvis.subsystems.context.resolver import ContextResolver

__all__ = [
    "AppCategory",
    "ApplicationContext",
    "WindowContext",
    "BrowserContext",
    "SelectionContext",
    "ClipboardContext",
    "OpenFileContext",
    "ScreenStateContext",
    "ProcessContextSummary",
    "ActiveTaskContext",
    "SystemContextSnapshot",
    "DeicticTargetType",
    "ResolvedContextAction",
    "BrowserDetector",
    "SelectionDetector",
    "ContextCollector",
    "ContextResolver",
]
