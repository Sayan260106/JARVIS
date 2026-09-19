"""Schemas and data models for Phase 10 Context Awareness.

Provides structured, typed representations for all 9 desktop telemetry dimensions:
1. Current Application
2. Current Window
3. Current URL (Active Browser)
4. Selected Text
5. Clipboard Content
6. Open Files & Code in Editor
7. Screen State
8. Running Processes
9. Active JARVIS Task
"""

from __future__ import annotations
import json
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class AppCategory(str, Enum):
    EDITOR = "editor"
    BROWSER = "browser"
    TERMINAL = "terminal"
    DOCUMENT = "document"
    COMMUNICATION = "communication"
    MEDIA = "media"
    SYSTEM = "system"
    OTHER = "other"


class DeicticTargetType(str, Enum):
    SELECTED_TEXT = "selected_text"
    OPEN_DOCUMENT = "open_document"
    CODE_IN_EDITOR = "code_in_editor"
    BROWSER_PAGE = "browser_page"
    CLIPBOARD = "clipboard"
    ACTIVE_WINDOW = "active_window"
    SCREEN_STATE = "screen_state"
    UNKNOWN = "unknown"


@dataclass
class ApplicationContext:
    """Telemetry for the currently active foreground application."""
    process_name: str = ""
    friendly_name: str = "Unknown Application"
    pid: int = 0
    exe_path: str = ""
    category: AppCategory = AppCategory.OTHER
    is_editor: bool = False
    is_browser: bool = False
    is_terminal: bool = False
    is_document_viewer: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value
        return d


@dataclass
class WindowContext:
    """Telemetry for the currently active foreground window."""
    hwnd: int = 0
    title: str = ""
    rect: Tuple[int, int, int, int] = (0, 0, 0, 0)  # left, top, right, bottom
    width: int = 0
    height: int = 0
    is_minimized: bool = False
    is_maximized: bool = False
    is_focused: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BrowserContext:
    """Telemetry for active web browser tabs."""
    is_browser_active: bool = False
    browser_name: str = ""
    current_url: str = ""
    page_title: str = ""
    domain: str = ""
    detection_method: str = "none"  # "uia", "window_title", "browser_agent", "mock"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SelectionContext:
    """Telemetry for currently highlighted / selected text."""
    has_selection: bool = False
    text: str = ""
    char_count: int = 0
    word_count: int = 0
    source_app: str = ""
    detection_method: str = "none"  # "clipboard_snapshot", "uia", "mock"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ClipboardContext:
    """Telemetry for system clipboard state."""
    has_text: bool = False
    text: str = ""
    preview: str = ""
    char_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OpenFileContext:
    """Telemetry for files currently active or open in an editor/viewer."""
    file_name: str = ""
    file_path: str = ""
    extension: str = ""
    source_app: str = ""
    is_code: bool = False
    is_document: bool = False
    file_size_bytes: int = 0
    content_preview: str = ""
    line_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScreenStateContext:
    """Telemetry for screen dimensions, multi-monitor configuration, and layout."""
    width: int = 1920
    height: int = 1080
    monitor_count: int = 1
    virtual_width: int = 1920
    virtual_height: int = 1080
    is_fullscreen: bool = False
    screenshot_path: Optional[str] = None
    has_screenshot: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProcessContextSummary:
    """Telemetry summary of interactive user processes and system resource consumers."""
    total_processes: int = 0
    active_user_apps: List[str] = field(default_factory=list)
    top_cpu_processes: List[Dict[str, Any]] = field(default_factory=list)
    top_mem_processes: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ActiveTaskContext:
    """Telemetry on JARVIS's own internal tasks and agent loops."""
    has_active_task: bool = False
    task_id: str = ""
    objective: str = ""
    status: str = "IDLE"
    current_step: int = 0
    total_steps: int = 0
    progress_percent: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SystemContextSnapshot:
    """Master aggregated snapshot across all 9 context dimensions."""
    timestamp: float = field(default_factory=time.time)
    application: ApplicationContext = field(default_factory=ApplicationContext)
    window: WindowContext = field(default_factory=WindowContext)
    browser: BrowserContext = field(default_factory=BrowserContext)
    selection: SelectionContext = field(default_factory=SelectionContext)
    clipboard: ClipboardContext = field(default_factory=ClipboardContext)
    open_files: List[OpenFileContext] = field(default_factory=list)
    screen_state: ScreenStateContext = field(default_factory=ScreenStateContext)
    processes: ProcessContextSummary = field(default_factory=ProcessContextSummary)
    active_task: ActiveTaskContext = field(default_factory=ActiveTaskContext)

    @property
    def primary_open_file(self) -> Optional[OpenFileContext]:
        return self.open_files[0] if self.open_files else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "application": self.application.to_dict(),
            "window": self.window.to_dict(),
            "browser": self.browser.to_dict(),
            "selection": self.selection.to_dict(),
            "clipboard": self.clipboard.to_dict(),
            "open_files": [f.to_dict() for f in self.open_files],
            "screen_state": self.screen_state.to_dict(),
            "processes": self.processes.to_dict(),
            "active_task": self.active_task.to_dict(),
        }

    def to_prompt_context(self) -> str:
        """Produces a clean, dense textual representation suitable for injection into LLM prompts."""
        lines = [
            "=== Active System Context ===",
            f"Active Application: {self.application.friendly_name} (Process: {self.application.process_name}, PID: {self.application.pid})",
            f"Active Window: \"{self.window.title}\"",
        ]
        if self.browser.is_browser_active and self.browser.current_url:
            lines.append(f"Browser URL: {self.browser.current_url} (Domain: {self.browser.domain})")

        if self.selection.has_selection:
            preview = self.selection.text.strip().replace("\n", " ")
            if len(preview) > 120:
                preview = preview[:117] + "..."
            lines.append(f"Selected Text ({self.selection.char_count} chars): \"{preview}\"")

        if self.primary_open_file:
            pof = self.primary_open_file
            lines.append(f"Open File in Focus: {pof.file_name} ({pof.file_path or 'Workspace File'}) [Lines: {pof.line_count}]")

        if self.clipboard.has_text:
            clip_prev = self.clipboard.preview.replace("\n", " ")
            lines.append(f"Clipboard Text: \"{clip_prev}\"")

        if self.active_task.has_active_task:
            lines.append(f"JARVIS Task: {self.active_task.objective} (Status: {self.active_task.status}, Progress: {self.active_task.progress_percent:.0f}%)")

        lines.append("=============================")
        return "\n".join(lines)


@dataclass
class ResolvedContextAction:
    """Result of deictic natural language reference resolution ('this', 'that', 'it')."""
    original_prompt: str
    resolved_prompt: str
    target_type: DeicticTargetType
    target_name: str = ""
    target_path: Optional[str] = None
    content_payload: str = ""
    confidence: float = 1.0
    explanation: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["target_type"] = self.target_type.value
        return d
