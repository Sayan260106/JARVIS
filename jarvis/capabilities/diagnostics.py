"""Error Diagnostic & Root Cause Analysis Engine for JARVIS.

Analyzes process crashes, tracebacks, terminal output, and logs to determine
the exact failure cause and recommend safe automated remediation steps.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any, Dict, List, Optional


class ErrorCategory(str, Enum):
    """Canonical error root causes diagnosed by JARVIS."""
    PORT_IN_USE = "PORT_IN_USE"
    MISSING_DEPENDENCY = "MISSING_DEPENDENCY"
    CONFIG_OR_ENV_MISSING = "CONFIG_OR_ENV_MISSING"
    INVALID_ENTRYPOINT = "INVALID_ENTRYPOINT"
    SYNTAX_ERROR = "SYNTAX_ERROR"
    PROCESS_CRASH = "PROCESS_CRASH"
    HEALTH_CHECK_FAILED = "HEALTH_CHECK_FAILED"
    UNKNOWN = "UNKNOWN"


@dataclass
class DiagnosticResult:
    """Detailed diagnosis of a failure with recommended remediation."""
    category: ErrorCategory
    likely_cause: str
    suggested_fix: str
    safe_remediation_type: Optional[str] = None
    remediation_params: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0


class ErrorDiagnosticEngine:
    """Heuristic and regex-based root cause analyzer for runtime errors."""

    # Regex patterns for common failure signatures
    PORT_PATTERNS = [
        r"(?:errno 98|errno 10048|winerror 10048)",
        r"address already in use",
        r"port (\d+) is already in use",
        r"bind: Only one usage of each socket address",
        r"already listening on port (\d+)",
        r":(\d+) (?:is already in use|address already in use)",
    ]

    DEP_PATTERNS = [
        r"ModuleNotFoundError:\s*No module named ['\"]([^'\"]+)['\"]",
        r"ImportError:\s*cannot import name ['\"]?([^'\"]+)['\"]?",
        r"ImportError:\s*No module named ['\"]([^'\"]+)['\"]",
    ]

    ENV_PATTERNS = [
        r"(?:file not found|filenotfounderror).*?['\"]?(\.env)['\"]?",
        r"keyerror:\s*['\"]([A-Z0-9_]+)['\"]",
        r"environment variable ['\"]?([A-Z0-9_]+)['\"]? (?:is not set|missing|required)",
        r"missing configuration:\s*([A-Z0-9_]+)",
    ]

    ENTRYPOINT_PATTERNS = [
        r"(?:can't open file|filenotfounderror).*?['\"]?([a-zA-Z0-9_.-]+\.py)['\"]?:\s*\[errno 2\]",
        r"no such file or directory.*?['\"]?([a-zA-Z0-9_.-]+\.py)['\"]?",
        r"cannot find path.*?([a-zA-Z0-9_.-]+\.py)",
    ]

    SYNTAX_PATTERNS = [
        r"SyntaxError:\s*(.+)",
        r"IndentationError:\s*(.+)",
    ]

    def diagnose(
        self,
        error_text: str,
        exit_code: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> DiagnosticResult:
        """Analyzes error output and returns structured diagnostic result."""
        text = error_text or ""
        lower = text.lower()
        ctx = context or {}

        # 1. Check for Port In Use
        for pattern in self.PORT_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                port = 8000
                if match.groups() and match.group(1):
                    try:
                        port = int(match.group(1))
                    except ValueError:
                        pass
                elif "port" in ctx:
                    port = int(ctx["port"])
                else:
                    # Look for 4 or 5 digit numbers in text
                    port_num_match = re.search(r"\b(80\d\d|30\d\d|50\d\d)\b", text)
                    if port_num_match:
                        port = int(port_num_match.group(1))

                return DiagnosticResult(
                    category=ErrorCategory.PORT_IN_USE,
                    likely_cause=f"Port {port} is already bound by another active or orphaned process.",
                    suggested_fix=f"Terminate the process occupying port {port} or switch to an alternate port.",
                    safe_remediation_type="free_port",
                    remediation_params={"port": port, "alternate_port": port + 1},
                    confidence=0.95,
                )

        # 2. Check for Missing Dependency (ModuleNotFoundError / ImportError)
        for pattern in self.DEP_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                module_name = match.group(1).split(".")[0].strip()
                # Common package mapping
                pkg_map = {
                    "cv2": "opencv-python",
                    "PIL": "pillow",
                    "yaml": "pyyaml",
                    "sklearn": "scikit-learn",
                }
                pkg_name = pkg_map.get(module_name, module_name)
                return DiagnosticResult(
                    category=ErrorCategory.MISSING_DEPENDENCY,
                    likely_cause=f"Required Python module '{module_name}' is not installed in the active environment.",
                    suggested_fix=f"Install package '{pkg_name}' using pip.",
                    safe_remediation_type="install_package",
                    remediation_params={"module": module_name, "package": pkg_name},
                    confidence=0.98,
                )

        # 3. Check for Missing Configuration or .env
        for pattern in self.ENV_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                var_or_file = match.group(1)
                return DiagnosticResult(
                    category=ErrorCategory.CONFIG_OR_ENV_MISSING,
                    likely_cause=f"Missing configuration or environment setting '{var_or_file}'.",
                    suggested_fix=f"Create default configuration file or set environment variable '{var_or_file}'.",
                    safe_remediation_type="create_default_env",
                    remediation_params={"variable_or_file": var_or_file},
                    confidence=0.90,
                )

        # 4. Check for Invalid Entrypoint script path
        for pattern in self.ENTRYPOINT_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                bad_file = match.group(1)
                return DiagnosticResult(
                    category=ErrorCategory.INVALID_ENTRYPOINT,
                    likely_cause=f"Specified entrypoint file '{bad_file}' does not exist in target directory.",
                    suggested_fix="Search project root for alternative entrypoints (e.g. main.py, app.py, backend.py).",
                    safe_remediation_type="resolve_entrypoint",
                    remediation_params={"target_file": bad_file},
                    confidence=0.92,
                )

        # 5. Check for Syntax / Indentation error
        for pattern in self.SYNTAX_PATTERNS:
            match = re.search(pattern, text)
            if match:
                details = match.group(1)
                return DiagnosticResult(
                    category=ErrorCategory.SYNTAX_ERROR,
                    likely_cause=f"Code syntax error detected: {details}",
                    suggested_fix="Inspect code near error line and correct syntax.",
                    safe_remediation_type="syntax_patch",
                    remediation_params={"details": details},
                    confidence=0.88,
                )

        # 6. Check for Health Check / Timeout failure
        if "connection refused" in lower or "timed out" in lower or "timeout" in lower:
            return DiagnosticResult(
                category=ErrorCategory.HEALTH_CHECK_FAILED,
                likely_cause="Service did not respond to health check or endpoint ping within timeout limit.",
                suggested_fix="Check if service started on expected host/port and increase startup delay.",
                safe_remediation_type="extend_startup_wait",
                remediation_params={"extra_wait_seconds": 3},
                confidence=0.80,
            )

        # 7. Generic Process Crash
        if exit_code is not None and exit_code != 0:
            return DiagnosticResult(
                category=ErrorCategory.PROCESS_CRASH,
                likely_cause=f"Process exited abruptly with non-zero exit code {exit_code}.",
                suggested_fix="Inspect stderr logs, apply safe fallback flags, and restart.",
                safe_remediation_type="restart_with_fallback_flags",
                remediation_params={"exit_code": exit_code},
                confidence=0.60,
            )

        return DiagnosticResult(
            category=ErrorCategory.UNKNOWN,
            likely_cause="Unspecified execution failure.",
            suggested_fix="Review error log and request user clarification if retries are exhausted.",
            confidence=0.30,
        )
