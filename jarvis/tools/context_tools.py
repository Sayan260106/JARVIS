"""Agent Tools for Desktop Context Awareness (Phase 10).

Provides typed tools to inspect live desktop context, read active documents/code,
capture selected text, and resolve deictic natural language references.
"""

from __future__ import annotations
import os
import time
from typing import Any, Dict, Optional

from jarvis.tools.base import (
    BaseTool,
    PermissionLevel,
    RiskLevel,
    ToolParameter,
    ToolResult,
    ToolVerification,
)
from jarvis.subsystems.context.collector import ContextCollector
from jarvis.subsystems.context.resolver import ContextResolver


class GetSystemContextTool(BaseTool):
    """Collects and returns the comprehensive 9-dimensional desktop context snapshot."""
    name = "get_system_context"
    description = (
        "Collects comprehensive real-time desktop context including current application, "
        "active window, browser URL, selected text, clipboard, open files, screen state, "
        "running processes, and active JARVIS tasks."
    )
    risk_level = RiskLevel.LOW
    permission_level = PermissionLevel.LEVEL_0_READ

    parameters = [
        ToolParameter("refresh", "boolean", "Whether to bypass the cache and force a fresh telemetry scan", required=False, default=False),
        ToolParameter("include_selection", "boolean", "Whether to capture currently highlighted text", required=False, default=True),
    ]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        start_t = time.time()
        refresh = bool(arguments.get("refresh", False))
        include_sel = bool(arguments.get("include_selection", True))

        collector = ContextCollector.get_instance()
        snapshot = collector.collect(refresh=refresh, capture_selection=include_sel)

        return ToolResult(
            success=True,
            output=snapshot.to_dict(),
            duration_ms=(time.time() - start_t) * 1000,
        )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if not result.success or not isinstance(result.output, dict):
            return ToolVerification(verified=False, details="Failed to obtain system context snapshot.")
        app_name = result.output.get("application", {}).get("friendly_name", "Unknown")
        return ToolVerification(verified=True, details=f"Context snapshot collected successfully (App: {app_name}).")


class GetActiveDocumentTool(BaseTool):
    """Retrieves file details and preview of the document or code file currently active in focus."""
    name = "get_active_document"
    description = "Inspects the active editor or window to retrieve the currently open file path, metadata, and code/text preview."
    risk_level = RiskLevel.LOW
    permission_level = PermissionLevel.LEVEL_0_READ

    parameters = [
        ToolParameter("max_lines", "integer", "Maximum number of lines to preview from file", required=False, default=100),
    ]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        start_t = time.time()
        max_lines = int(arguments.get("max_lines", 100))

        collector = ContextCollector.get_instance()
        snapshot = collector.collect(refresh=True, capture_selection=False)

        pof = snapshot.primary_open_file
        if not pof:
            return ToolResult(
                success=False,
                output=None,
                error=f"No active file detected in foreground window '{snapshot.window.title}'.",
                duration_ms=(time.time() - start_t) * 1000,
            )

        # If file path exists on disk, read full preview up to max_lines
        content = pof.content_preview
        if pof.file_path and os.path.exists(pof.file_path):
            try:
                with open(pof.file_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = [f.readline() for _ in range(max_lines)]
                    content = "".join(lines)
            except Exception:
                pass

        data = {
            "file_name": pof.file_name,
            "file_path": pof.file_path,
            "extension": pof.extension,
            "source_app": pof.source_app,
            "is_code": pof.is_code,
            "is_document": pof.is_document,
            "preview": content,
            "line_count": len(content.splitlines()),
        }

        return ToolResult(
            success=True,
            output=data,
            duration_ms=(time.time() - start_t) * 1000,
        )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if not result.success:
            return ToolVerification(verified=False, details=result.error or "Active document not found.")
        fname = result.output.get("file_name", "unknown")
        return ToolVerification(verified=True, details=f"Active document '{fname}' verified in focus.")


class GetSelectedTextTool(BaseTool):
    """Captures currently highlighted / selected text in the active window."""
    name = "get_selected_text"
    description = "Captures the currently selected/highlighted text from whatever application is active in the foreground."
    risk_level = RiskLevel.LOW
    permission_level = PermissionLevel.LEVEL_0_READ

    parameters = []

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        start_t = time.time()
        collector = ContextCollector.get_instance()
        snapshot = collector.collect(refresh=True, capture_selection=True)
        sel = snapshot.selection

        if not sel.has_selection:
            return ToolResult(
                success=True,
                output={"has_selection": False, "text": "", "char_count": 0},
                duration_ms=(time.time() - start_t) * 1000,
            )

        return ToolResult(
            success=True,
            output=sel.to_dict(),
            duration_ms=(time.time() - start_t) * 1000,
        )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if not result.success:
            return ToolVerification(verified=False, details="Failed to capture selected text.")
        return ToolVerification(verified=True, details="Selection query completed.")


class ResolveContextualPromptTool(BaseTool):
    """Resolves ambiguous or deictic prompts ('Summarize this', 'Fix this', 'Explain this') against active context."""
    name = "resolve_contextual_prompt"
    description = "Resolves deictic pronouns ('this', 'that', 'it') in a user prompt against the live desktop state."
    risk_level = RiskLevel.LOW
    permission_level = PermissionLevel.LEVEL_0_READ

    parameters = [
        ToolParameter("prompt", "string", "User input string containing contextual references like 'Summarize this'", required=True),
    ]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        start_t = time.time()
        prompt = arguments.get("prompt", "")
        collector = ContextCollector.get_instance()
        snapshot = collector.collect(refresh=False, capture_selection=True)

        action = ContextResolver.resolve(prompt, snapshot)

        return ToolResult(
            success=True,
            output=action.to_dict(),
            duration_ms=(time.time() - start_t) * 1000,
        )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if not result.success:
            return ToolVerification(verified=False, details="Failed to resolve contextual prompt.")
        target = result.output.get("target_name", "Unknown")
        return ToolVerification(verified=True, details=f"Context resolved to target '{target}'.")
