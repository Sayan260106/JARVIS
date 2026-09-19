"""Failure Diagnostician for Autonomous Recovery 2.0 (Phase 14).

Answers 'Why did it fail?' by analyzing observation errors, exit codes,
verification verdicts, and runtime application context.
"""

from __future__ import annotations
import re
from typing import Any, Dict, Optional

from jarvis.core.schemas import Observation, PlanStep, RecoveryStrategy, VerificationResult
from jarvis.subsystems.recovery.schemas import FailureCategory, FailureDiagnosis


class FailureDiagnostician:
    """Diagnoses the precise root cause of execution failures."""

    PROCESS_PATTERNS = [
        r"not running",
        r"no active browser",
        r"chrome not found",
        r"browser closed",
        r"connection refused",
        r"target closed",
        r"application not running",
        r"failed to connect",
        r"process .* not found",
        r"cannot connect to chrome",
    ]

    ELEMENT_PATTERNS = [
        r"element not found",
        r"nosuchelement",
        r"selector failed",
        r"not visible",
        r"could not be found",
        r"waiting for selector",
        r"target not found",
        r"element .* does not exist",
        r"no node found for selector",
    ]

    NAV_PATTERNS = [
        r"net::err",
        r"404",
        r"navigation failed",
        r"navigation timeout",
        r"url unreachable",
        r"failed to navigate",
        r"page crash",
    ]

    FILE_PATTERNS = [
        r"filenotfound",
        r"no such file or directory",
        r"file does not exist",
        r"path .* not found",
    ]

    WINDOW_PATTERNS = [
        r"window not found",
        r"no matching window",
        r"failed to focus window",
    ]

    def diagnose(
        self,
        step: PlanStep,
        observation: Observation,
        verification: VerificationResult,
        context_state: Optional[Dict[str, Any]] = None,
    ) -> FailureDiagnosis:
        """Determines the failure category and specific root cause."""
        combined_text = f"{verification.reason}\n{observation.error or ''}\n{observation.output or ''}".strip().lower()
        args = step.arguments or {}

        # 1. Check for PROCESS_NOT_RUNNING (e.g. Chrome not running)
        if any(re.search(p, combined_text) for p in self.PROCESS_PATTERNS) or (
            step.tool_name.startswith("browser_") and ("not running" in combined_text or "closed" in combined_text)
        ):
            app_name = args.get("app_name") or ("chrome" if "browser" in step.tool_name else "target_app")
            return FailureDiagnosis(
                category=FailureCategory.PROCESS_NOT_RUNNING,
                root_cause=f"Application '{app_name}' is not running or connection was refused.",
                attempted_action=step.description,
                evidence=verification.reason or observation.error or "Process not running",
                suggested_strategy=RecoveryStrategy.PREREQUISITE_INJECTION,
                context_snapshot={"app_name": app_name, "tool": step.tool_name},
            )

        # 2. Check for ELEMENT_NOT_FOUND (e.g. Click 'ECE' element missing or course renamed)
        if any(re.search(p, combined_text) for p in self.ELEMENT_PATTERNS) or (
            "click" in step.tool_name and "not found" in combined_text
        ):
            target_elem = args.get("selector") or args.get("text") or args.get("element") or "target_element"
            return FailureDiagnosis(
                category=FailureCategory.ELEMENT_NOT_FOUND,
                root_cause=f"Element '{target_elem}' not found in active DOM or screen (may be renamed, dynamic, or unrendered).",
                attempted_action=step.description,
                evidence=verification.reason or observation.error or "Element not found",
                suggested_strategy=RecoveryStrategy.ALTERNATE_SELECTOR,
                context_snapshot={"target_element": target_elem, "tool": step.tool_name},
            )

        # 3. Check for NAVIGATION_FAILED
        if any(re.search(p, combined_text) for p in self.NAV_PATTERNS):
            url = args.get("url") or "target_url"
            return FailureDiagnosis(
                category=FailureCategory.NAVIGATION_FAILED,
                root_cause=f"Navigation to '{url}' failed or timed out.",
                attempted_action=step.description,
                evidence=verification.reason or observation.error or "Navigation error",
                suggested_strategy=RecoveryStrategy.ALTERNATE_NAVIGATION,
                context_snapshot={"url": url, "tool": step.tool_name},
            )

        # 4. Check for FILE_NOT_FOUND
        if any(re.search(p, combined_text) for p in self.FILE_PATTERNS):
            fpath = args.get("path") or args.get("file_path") or "file"
            return FailureDiagnosis(
                category=FailureCategory.FILE_NOT_FOUND,
                root_cause=f"Target file or directory '{fpath}' does not exist on disk.",
                attempted_action=step.description,
                evidence=verification.reason or observation.error or "File not found",
                suggested_strategy=RecoveryStrategy.PREREQUISITE_INJECTION,
                context_snapshot={"file_path": fpath},
            )

        # 5. Check for WINDOW_NOT_FOUND
        if any(re.search(p, combined_text) for p in self.WINDOW_PATTERNS):
            win_title = args.get("title") or args.get("window_title") or "target_window"
            return FailureDiagnosis(
                category=FailureCategory.WINDOW_NOT_FOUND,
                root_cause=f"Window '{win_title}' is not active or visible.",
                attempted_action=step.description,
                evidence=verification.reason or observation.error or "Window not found",
                suggested_strategy=RecoveryStrategy.SWITCH_TOOL,
                context_snapshot={"window_title": win_title},
            )

        # Default fallback
        return FailureDiagnosis(
            category=FailureCategory.UNKNOWN,
            root_cause=f"Execution failed with error: {verification.reason or observation.error or 'unknown'}.",
            attempted_action=step.description,
            evidence=verification.reason or observation.error or "Verification failed",
            suggested_strategy=RecoveryStrategy.RETRY_WITH_ADAPTED_ARGS,
            context_snapshot={"tool": step.tool_name},
        )
