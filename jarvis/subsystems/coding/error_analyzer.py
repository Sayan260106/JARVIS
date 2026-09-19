"""Error Analysis Engine for JARVIS Coding Agent (Phase 13).

Parses Python test output and stack traces to isolate error types, file locations,
failing code lines, and root cause diagnoses.
"""

from __future__ import annotations
import os
import re
from typing import Optional

from jarvis.subsystems.coding.schemas import ErrorAnalysis, ErrorCategory, TestRunResult


class ErrorAnalyzer:
    """Diagnoses failures and pinpoints root causes in source code."""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = os.path.abspath(workspace_root)

    def analyze_test_failure(self, test_result: TestRunResult) -> Optional[ErrorAnalysis]:
        """Analyzes test failures to extract file, line, error category, and root cause."""
        if test_result.passed or not test_result.tracebacks:
            return None

        # Take primary traceback
        tb = test_result.tracebacks[0]
        return self.analyze_traceback(tb)

    def analyze_traceback(self, tb_text: str) -> ErrorAnalysis:
        """Parses traceback text into structured ErrorAnalysis."""
        # 1. Identify Error Type and Message
        error_type = ErrorCategory.UNKNOWN
        error_msg = ""

        last_line = ""
        for line in reversed(tb_text.strip().splitlines()):
            if line.strip():
                last_line = line.strip()
                break

        if "AssertionError" in last_line:
            error_type = ErrorCategory.ASSERTION_FAILURE
            error_msg = last_line
        elif "AttributeError" in last_line:
            error_type = ErrorCategory.ATTRIBUTE_ERROR
            error_msg = last_line
        elif "TypeError" in last_line:
            error_type = ErrorCategory.TYPE_ERROR
            error_msg = last_line
        elif "NameError" in last_line:
            error_type = ErrorCategory.NAME_ERROR
            error_msg = last_line
        elif "SyntaxError" in last_line:
            error_type = ErrorCategory.SYNTAX_ERROR
            error_msg = last_line
        elif "ImportError" in last_line or "ModuleNotFoundError" in last_line:
            error_type = ErrorCategory.IMPORT_ERROR
            error_msg = last_line
        elif "KeyError" in last_line or "IndexError" in last_line:
            error_type = ErrorCategory.INDEX_KEY_ERROR
            error_msg = last_line
        else:
            error_type = ErrorCategory.RUNTIME_EXCEPTION
            error_msg = last_line

        # 2. Extract Stack Frames: File "...", line 123, in func
        frame_matches = re.findall(
            r'File "(.*?)", line (\d+)(?:, in (.*))?',
            tb_text,
        )

        failing_file = ""
        failing_line = None
        failing_func = None
        target_snippet = ""

        # Find the frame in the workspace that caused the error (prefer non-test code if available, else test frame)
        workspace_frames = []
        for path_str, line_str, func_str in frame_matches:
            abs_p = os.path.abspath(path_str)
            if self.workspace_root.lower() in abs_p.lower():
                workspace_frames.append((abs_p, int(line_str), func_str.strip() if func_str else None))

        if workspace_frames:
            # Check if there is a source file frame (not in tests/)
            source_frames = [f for f in workspace_frames if "tests" not in f[0].replace("\\", "/")]
            if source_frames:
                target_frame = source_frames[-1]
            else:
                target_frame = workspace_frames[-1]

            failing_file, failing_line, failing_func = target_frame

            # Read target snippet around line if file exists
            if os.path.exists(failing_file) and failing_line:
                try:
                    with open(failing_file, "r", encoding="utf-8", errors="ignore") as f:
                        file_lines = f.readlines()
                    if 1 <= failing_line <= len(file_lines):
                        target_snippet = file_lines[failing_line - 1].strip()
                except Exception:
                    pass

        # 3. Formulate root cause and suggested fix
        root_cause = f"Failure triggered at {os.path.basename(failing_file)}:L{failing_line or '?'}: {error_msg}"
        suggested_fix = self._derive_suggested_fix(error_type, error_msg, target_snippet)

        return ErrorAnalysis(
            error_type=error_type,
            error_message=error_msg,
            failing_file=failing_file,
            failing_line=failing_line,
            failing_function=failing_func,
            root_cause=root_cause,
            suggested_fix=suggested_fix,
            target_code_snippet=target_snippet,
        )

    def _derive_suggested_fix(self, error_type: ErrorCategory, error_msg: str, snippet: str) -> str:
        """Heuristically suggests a remediation path based on error category."""
        if error_type == ErrorCategory.ATTRIBUTE_ERROR:
            m = re.search(r"has no attribute '([a-zA-Z0-9_]+)'", error_msg)
            if m:
                return f"Verify attribute or method '{m.group(1)}' exists or replace with corresponding correct attribute."
        elif error_type == ErrorCategory.TYPE_ERROR:
            return f"Inspect argument count and types passed in statement: '{snippet}'."
        elif error_type == ErrorCategory.ASSERTION_FAILURE:
            return f"Reconcile return value or condition tested in: '{snippet}'."
        elif error_type == ErrorCategory.NAME_ERROR:
            return f"Define or import the unresolved variable or name."
        return f"Inspect and adjust code statement: '{snippet}'."
