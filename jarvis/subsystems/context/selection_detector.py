"""Selected Text Detection Subsystem for Phase 10.

Captures currently highlighted / selected text across Windows applications
(VS Code, browsers, Word, PDF viewers, Notepad, terminals) non-destructively
by temporarily backing up and restoring the user's system clipboard.
"""

from __future__ import annotations
import time
from typing import Optional
from jarvis.subsystems.context.schemas import SelectionContext
from jarvis.subsystems.system.windows_executor import WindowsExecutor


class SelectionDetector:
    """Non-destructively extracts currently highlighted / selected text in active window."""

    _simulated_selection: Optional[str] = None

    @classmethod
    def set_simulated_selection(cls, text: Optional[str]) -> None:
        """Sets a simulated selection for testing or programmatic overrides."""
        cls._simulated_selection = text

    @classmethod
    def capture_selected_text(
        cls,
        active_app_name: str = "",
        hwnd: int = 0,
        timeout_ms: int = 60,
    ) -> SelectionContext:
        """Captures selected text by saving clipboard, firing Ctrl+C, reading, and restoring."""
        # 0. Check simulation override
        if cls._simulated_selection is not None:
            sel_text = cls._simulated_selection.strip()
            return SelectionContext(
                has_selection=bool(sel_text),
                text=sel_text,
                char_count=len(sel_text),
                word_count=len(sel_text.split()) if sel_text else 0,
                source_app=active_app_name or "Simulated Environment",
                detection_method="mock",
            )

        # 1. Non-interactive or zero HWND check
        if hwnd == 0:
            return SelectionContext(has_selection=False, detection_method="none")

        # 2. Safe Clipboard Snapshot Technique
        try:
            # Step A: Backup existing clipboard
            original_clipboard = WindowsExecutor.get_clipboard()

            # Step B: Temporarily set a unique sentinel into clipboard
            sentinel = f"__JARVIS_SENTINEL_{time.time_ns()}__"
            WindowsExecutor.set_clipboard(sentinel)

            # Step C: Send Ctrl+C keystroke to active application
            WindowsExecutor.send_hotkey("ctrl+c")
            time.sleep(timeout_ms / 1000.0)

            # Step D: Read new clipboard content
            copied_text = WindowsExecutor.get_clipboard()

            # Step E: Restore user's original clipboard content immediately
            WindowsExecutor.set_clipboard(original_clipboard)

            # Step F: Verify if copy succeeded and changed from sentinel
            if copied_text and copied_text != sentinel and copied_text.strip():
                clean_text = copied_text.strip()
                return SelectionContext(
                    has_selection=True,
                    text=clean_text,
                    char_count=len(clean_text),
                    word_count=len(clean_text.split()),
                    source_app=active_app_name,
                    detection_method="clipboard_snapshot",
                )
        except Exception:
            pass

        return SelectionContext(
            has_selection=False,
            source_app=active_app_name,
            detection_method="clipboard_snapshot_empty",
        )
