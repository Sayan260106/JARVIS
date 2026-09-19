"""Context Collector for Phase 10 — Context Awareness.

Continuously captures the 9 essential desktop state dimensions:
1. Current application
2. Current window
3. Current URL
4. Selected text
5. Clipboard
6. Open files
7. Screen state
8. Running processes
9. Active task
"""

from __future__ import annotations
import ctypes
from ctypes import wintypes
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import psutil

from jarvis.subsystems.context.schemas import (
    ActiveTaskContext,
    AppCategory,
    ApplicationContext,
    BrowserContext,
    ClipboardContext,
    OpenFileContext,
    ProcessContextSummary,
    ScreenStateContext,
    SelectionContext,
    SystemContextSnapshot,
    WindowContext,
)
from jarvis.subsystems.context.browser_detector import BrowserDetector
from jarvis.subsystems.context.selection_detector import SelectionDetector
from jarvis.subsystems.system.windows_executor import WindowsExecutor


# Map known process names to friendly app names and categories
KNOWN_APPS: Dict[str, Tuple[str, AppCategory]] = {
    "code.exe": ("Visual Studio Code", AppCategory.EDITOR),
    "devenv.exe": ("Visual Studio", AppCategory.EDITOR),
    "notepad.exe": ("Notepad", AppCategory.EDITOR),
    "notepad++.exe": ("Notepad++", AppCategory.EDITOR),
    "sublime_text.exe": ("Sublime Text", AppCategory.EDITOR),
    "pycharm64.exe": ("PyCharm", AppCategory.EDITOR),
    "cursor.exe": ("Cursor IDE", AppCategory.EDITOR),
    "msedge.exe": ("Microsoft Edge", AppCategory.BROWSER),
    "chrome.exe": ("Google Chrome", AppCategory.BROWSER),
    "brave.exe": ("Brave Browser", AppCategory.BROWSER),
    "firefox.exe": ("Mozilla Firefox", AppCategory.BROWSER),
    "opera.exe": ("Opera", AppCategory.BROWSER),
    "windowsterminal.exe": ("Windows Terminal", AppCategory.TERMINAL),
    "powershell.exe": ("PowerShell", AppCategory.TERMINAL),
    "pwsh.exe": ("PowerShell 7", AppCategory.TERMINAL),
    "cmd.exe": ("Command Prompt", AppCategory.TERMINAL),
    "explorer.exe": ("File Explorer", AppCategory.SYSTEM),
    "winword.exe": ("Microsoft Word", AppCategory.DOCUMENT),
    "excel.exe": ("Microsoft Excel", AppCategory.DOCUMENT),
    "powerpnt.exe": ("Microsoft PowerPoint", AppCategory.DOCUMENT),
    "acrobat.exe": ("Adobe Acrobat", AppCategory.DOCUMENT),
    "acrord32.exe": ("Adobe Acrobat Reader", AppCategory.DOCUMENT),
    "spotify.exe": ("Spotify", AppCategory.MEDIA),
    "slack.exe": ("Slack", AppCategory.COMMUNICATION),
    "discord.exe": ("Discord", AppCategory.COMMUNICATION),
    "teams.exe": ("Microsoft Teams", AppCategory.COMMUNICATION),
}

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json",
    ".cpp", ".c", ".h", ".cs", ".java", ".go", ".rs", ".sql", ".sh", ".bat", ".ps1", ".yaml", ".yml"
}

DOCUMENT_EXTENSIONS = {
    ".txt", ".md", ".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", ".csv", ".rtf"
}


class ContextCollector:
    """Collects, aggregates, and caches real-time Windows desktop context."""

    _instance: Optional["ContextCollector"] = None
    _lock = threading.Lock()

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = workspace_root or os.path.abspath(".")
        self._cached_snapshot: Optional[SystemContextSnapshot] = None
        self._cache_timestamp: float = 0.0
        self._cache_ttl: float = 0.5  # 500ms caching to prevent excessive OS polling
        self._simulated_snapshot: Optional[SystemContextSnapshot] = None

    @classmethod
    def get_instance(cls, workspace_root: Optional[str] = None) -> "ContextCollector":
        with cls._lock:
            if cls._instance is None:
                cls._instance = ContextCollector(workspace_root=workspace_root)
            return cls._instance

    def set_simulated_snapshot(self, snapshot: Optional[SystemContextSnapshot]) -> None:
        """Sets an explicit simulation snapshot for unit testing or headless runs."""
        self._simulated_snapshot = snapshot

    def collect(self, refresh: bool = False, capture_selection: bool = True) -> SystemContextSnapshot:
        """Collects the complete 9-dimensional desktop context snapshot."""
        if self._simulated_snapshot is not None:
            return self._simulated_snapshot

        now = time.time()
        if not refresh and self._cached_snapshot and (now - self._cache_timestamp < self._cache_ttl):
            return self._cached_snapshot

        # 1 & 2. Active Window and Application
        app_ctx, win_ctx = self._collect_application_and_window()

        # 3. Active Browser URL
        browser_ctx = BrowserDetector.detect_context(
            process_name=app_ctx.process_name,
            window_title=win_ctx.title,
            hwnd=win_ctx.hwnd,
        )

        # 4. Selected Text
        if capture_selection:
            selection_ctx = SelectionDetector.capture_selected_text(
                active_app_name=app_ctx.friendly_name,
                hwnd=win_ctx.hwnd,
            )
        else:
            selection_ctx = SelectionContext(has_selection=False)

        # 5. Clipboard Content
        clipboard_ctx = self._collect_clipboard()

        # 6. Open Files (In active editor / window)
        open_files = self._collect_open_files(win_ctx.title, app_ctx)

        # 7. Screen State
        screen_ctx = self._collect_screen_state(win_ctx)

        # 8. Running Processes Summary
        process_summary = self._collect_processes()

        # 9. Active Task
        active_task = self._collect_active_task()

        snapshot = SystemContextSnapshot(
            timestamp=now,
            application=app_ctx,
            window=win_ctx,
            browser=browser_ctx,
            selection=selection_ctx,
            clipboard=clipboard_ctx,
            open_files=open_files,
            screen_state=screen_ctx,
            processes=process_summary,
            active_task=active_task,
        )

        self._cached_snapshot = snapshot
        self._cache_timestamp = now
        return snapshot

    # ------------------------------------------------------------------
    # Collectors for individual dimensions
    # ------------------------------------------------------------------

    def _collect_application_and_window(self) -> Tuple[ApplicationContext, WindowContext]:
        raw_win = WindowsExecutor.get_active_window()
        hwnd = raw_win.get("hwnd", 0)
        title = raw_win.get("title", "")
        pid = raw_win.get("pid", 0)
        proc_name = raw_win.get("process_name", "")

        friendly_name, category = self._resolve_app_details(proc_name, title)

        # Retrieve exe path if process is valid
        exe_path = ""
        if pid > 0:
            try:
                proc = psutil.Process(pid)
                exe_path = proc.exe()
            except Exception:
                pass

        app_ctx = ApplicationContext(
            process_name=proc_name,
            friendly_name=friendly_name,
            pid=pid,
            exe_path=exe_path,
            category=category,
            is_editor=(category == AppCategory.EDITOR),
            is_browser=(category == AppCategory.BROWSER),
            is_terminal=(category == AppCategory.TERMINAL),
            is_document_viewer=(category == AppCategory.DOCUMENT),
        )

        # Window geometry & states
        rect = (0, 0, 0, 0)
        width, height = 0, 0
        is_min = False
        is_max = False
        if hwnd:
            try:
                user32 = ctypes.windll.user32
                r = wintypes.RECT()
                if user32.GetWindowRect(hwnd, ctypes.byref(r)):
                    rect = (r.left, r.top, r.right, r.bottom)
                    width = max(0, r.right - r.left)
                    height = max(0, r.bottom - r.top)
                is_min = bool(user32.IsIconic(hwnd))
                is_max = bool(user32.IsZoomed(hwnd))
            except Exception:
                pass

        win_ctx = WindowContext(
            hwnd=hwnd,
            title=title,
            rect=rect,
            width=width,
            height=height,
            is_minimized=is_min,
            is_maximized=is_max,
            is_focused=(hwnd != 0),
        )

        return app_ctx, win_ctx

    def _resolve_app_details(self, proc_name: str, window_title: str) -> Tuple[str, AppCategory]:
        clean_proc = proc_name.strip().lower() if proc_name else ""
        if clean_proc in KNOWN_APPS:
            return KNOWN_APPS[clean_proc]

        # Check window title cues
        lower_title = window_title.lower() if window_title else ""
        if "visual studio code" in lower_title or " - code" in lower_title:
            return "Visual Studio Code", AppCategory.EDITOR
        if "google chrome" in lower_title:
            return "Google Chrome", AppCategory.BROWSER
        if "microsoft edge" in lower_title:
            return "Microsoft Edge", AppCategory.BROWSER
        if "powershell" in lower_title:
            return "PowerShell", AppCategory.TERMINAL

        # Fallback friendly name
        base = clean_proc.replace(".exe", "").title() if clean_proc else "Unknown Application"
        return base, AppCategory.OTHER

    def _collect_clipboard(self) -> ClipboardContext:
        try:
            text = WindowsExecutor.get_clipboard()
            if text:
                preview = text.strip()[:100]
                return ClipboardContext(
                    has_text=True,
                    text=text,
                    preview=preview,
                    char_count=len(text),
                )
        except Exception:
            pass
        return ClipboardContext(has_text=False)

    def _collect_open_files(
        self,
        window_title: str,
        app: ApplicationContext,
    ) -> List[OpenFileContext]:
        """Detects open files by analyzing active window title and matching workspace files."""
        open_files: List[OpenFileContext] = []
        if not window_title:
            return open_files

        # Common IDE/Editor title patterns:
        # "● main.py - JARVIS - Visual Studio Code"
        # "settings.json - Code"
        # "document.docx - Word"
        # "notes.txt - Notepad"
        clean_title = window_title.replace("●", "").strip()

        # Extract possible filenames from title
        # Match tokens containing '.' followed by known extensions
        candidates = re.findall(r"\b([a-zA-Z0-9_\-]+\.[a-zA-Z0-9_]{1,6})\b", clean_title)

        for fname in candidates:
            ext = os.path.splitext(fname)[1].lower()
            is_code = ext in CODE_EXTENSIONS
            is_doc = ext in DOCUMENT_EXTENSIONS

            # Attempt to locate file path on disk (in workspace_root or cwd)
            resolved_path = self._find_file_in_workspace(fname)
            content_preview = ""
            line_count = 0
            size_bytes = 0

            if resolved_path and os.path.exists(resolved_path):
                try:
                    size_bytes = os.path.getsize(resolved_path)
                    # Read preview of first 50 lines / 2000 chars
                    with open(resolved_path, "r", encoding="utf-8", errors="ignore") as f:
                        lines = [f.readline() for _ in range(50)]
                        content_preview = "".join(lines)
                        # Estimate total lines
                        line_count = len(lines)
                except Exception:
                    pass

            open_files.append(
                OpenFileContext(
                    file_name=fname,
                    file_path=resolved_path or fname,
                    extension=ext,
                    source_app=app.friendly_name,
                    is_code=is_code,
                    is_document=is_doc,
                    file_size_bytes=size_bytes,
                    content_preview=content_preview,
                    line_count=line_count,
                )
            )

        return open_files

    def _find_file_in_workspace(self, filename: str) -> Optional[str]:
        """Searches workspace root for a matching filename."""
        # 1. Direct path check in workspace root
        direct = os.path.join(self.workspace_root, filename)
        if os.path.exists(direct):
            return direct

        # 2. Walk directory (shallow search up to depth 3)
        for root, dirs, files in os.walk(self.workspace_root):
            # Skip hidden and cache folders
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("venv", "node_modules", "__pycache__")]
            if filename in files:
                return os.path.join(root, filename)

        return None

    def _collect_screen_state(self, win: WindowContext) -> ScreenStateContext:
        width = 1920
        height = 1080
        monitors = 1
        try:
            user32 = ctypes.windll.user32
            width = user32.GetSystemMetrics(0)  # SM_CXSCREEN
            height = user32.GetSystemMetrics(1)  # SM_CYSCREEN
            monitors = user32.GetSystemMetrics(80) or 1  # SM_CMONITORS
        except Exception:
            pass

        # Fullscreen check: Does active window cover the screen?
        is_fullscreen = False
        if win.width >= width and win.height >= height and not win.is_minimized:
            is_fullscreen = True

        return ScreenStateContext(
            width=width,
            height=height,
            monitor_count=monitors,
            virtual_width=width,
            virtual_height=height,
            is_fullscreen=is_fullscreen,
            screenshot_path=None,
            has_screenshot=False,
        )

    def _collect_processes(self) -> ProcessContextSummary:
        user_apps: List[str] = []
        cpu_procs: List[Dict[str, Any]] = []
        mem_procs: List[Dict[str, Any]] = []
        total = 0

        try:
            procs = list(psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]))
            total = len(procs)

            for p in procs:
                try:
                    name = p.info.get("name") or ""
                    clean_name = name.lower()
                    if clean_name in KNOWN_APPS and clean_name not in user_apps:
                        user_apps.append(KNOWN_APPS[clean_name][0])
                except Exception:
                    pass

            # Top CPU
            sorted_cpu = sorted(procs, key=lambda x: x.info.get("cpu_percent") or 0.0, reverse=True)[:3]
            for p in sorted_cpu:
                cpu_procs.append({
                    "name": p.info.get("name", ""),
                    "pid": p.info.get("pid", 0),
                    "cpu_percent": p.info.get("cpu_percent", 0.0),
                })

            # Top Memory
            sorted_mem = sorted(procs, key=lambda x: x.info.get("memory_percent") or 0.0, reverse=True)[:3]
            for p in sorted_mem:
                mem_procs.append({
                    "name": p.info.get("name", ""),
                    "pid": p.info.get("pid", 0),
                    "memory_percent": round(p.info.get("memory_percent", 0.0) or 0.0, 1),
                })
        except Exception:
            pass

        return ProcessContextSummary(
            total_processes=total,
            active_user_apps=user_apps[:8],
            top_cpu_processes=cpu_procs,
            top_mem_processes=mem_procs,
        )

    def _collect_active_task(self) -> ActiveTaskContext:
        """Retrieves currently running JARVIS task from TaskManager if available."""
        try:
            from jarvis.core.task_manager import TaskManager
            tm = TaskManager()
            running_tasks = tm.get_active_tasks()
            if running_tasks:
                task = running_tasks[0]
                return ActiveTaskContext(
                    has_active_task=True,
                    task_id=task.id,
                    objective=task.objective,
                    status=task.status.value,
                    current_step=0,
                    total_steps=len(task.plan),
                    progress_percent=0.0,
                )
        except Exception:
            pass
        return ActiveTaskContext(has_active_task=False)
