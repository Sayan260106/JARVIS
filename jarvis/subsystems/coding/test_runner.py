"""Automated Test Runner & Execution Observer for JARVIS Coding Agent (Phase 13).

Executes test suites in workspace virtual environments and extracts structured failure telemetry.
"""

from __future__ import annotations
import os
import re
import subprocess
import sys
import time
from typing import List, Optional

from jarvis.subsystems.coding.schemas import TestRunResult


class TestRunner:
    """Runs test suites in isolated terminal processes and extracts failure telemetry."""

    def __init__(self, workspace_root: str = "."):
        self.workspace_root = os.path.abspath(workspace_root)

    def find_python_executable(self) -> str:
        """Locates the project virtualenv python or falls back to current runtime."""
        candidates = [
            os.path.join(self.workspace_root, "venv", "Scripts", "python.exe"),
            os.path.join(self.workspace_root, ".venv", "Scripts", "python.exe"),
            os.path.join(self.workspace_root, "venv", "bin", "python"),
            os.path.join(self.workspace_root, ".venv", "bin", "python"),
        ]
        for c in candidates:
            if os.path.exists(c):
                return os.path.abspath(c)
        return sys.executable

    def run_tests(
        self,
        test_path: str,
        runner: str = "unittest",
        timeout_sec: int = 60,
    ) -> TestRunResult:
        """Executes test suite and captures output, returncode, and failure signatures."""
        py_exe = self.find_python_executable()
        clean_target = test_path.replace("/", "\\") if os.name == "nt" else test_path

        cmd = [py_exe, "-m", runner, clean_target]
        start_t = time.perf_counter()

        try:
            res = subprocess.run(
                cmd,
                cwd=self.workspace_root,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_sec,
            )
            duration_ms = (time.perf_counter() - start_t) * 1000
            combined_output = (res.stdout + "\n" + res.stderr).strip()
            passed = (res.returncode == 0)

            failed_tests, tracebacks = self._parse_failures(combined_output)

            return TestRunResult(
                command=" ".join(cmd),
                passed=passed,
                returncode=res.returncode,
                output=combined_output,
                failed_tests=failed_tests,
                tracebacks=tracebacks,
                duration_ms=duration_ms,
            )
        except subprocess.TimeoutExpired:
            duration_ms = (time.perf_counter() - start_t) * 1000
            return TestRunResult(
                command=" ".join(cmd),
                passed=False,
                returncode=-1,
                output=f"Test run timed out after {timeout_sec} seconds.",
                failed_tests=[test_path],
                tracebacks=["TimeoutExpired"],
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start_t) * 1000
            return TestRunResult(
                command=" ".join(cmd),
                passed=False,
                returncode=-1,
                output=str(e),
                failed_tests=[test_path],
                tracebacks=[str(e)],
                duration_ms=duration_ms,
            )

    def _parse_failures(self, output: str) -> tuple[List[str], List[str]]:
        """Extracts failing test case names and exception tracebacks from unittest output."""
        failed_tests = []
        tracebacks = []

        # Standard unittest failure header: FAIL: test_name (tests.module.Class.test_name)
        # or ERROR: test_name (tests.module.Class.test_name)
        fail_matches = re.findall(
            r"^(?:FAIL|ERROR):\s+([a-zA-Z0-9_]+)\s+\((.*?)\)",
            output,
            re.MULTILINE,
        )
        for name, mod_class in fail_matches:
            failed_tests.append(f"{mod_class}.{name}")

        # Extract traceback blocks
        tb_blocks = re.split(r"=+\s*\n(?:FAIL|ERROR):", output)
        if len(tb_blocks) > 1:
            for blk in tb_blocks[1:]:
                # Truncate before next summary line
                end_idx = blk.find("----------------------------------------------------------------------")
                if end_idx != -1:
                    tracebacks.append(blk[:end_idx].strip())
                else:
                    tracebacks.append(blk.strip())
        elif "Traceback (most recent call last):" in output:
            tracebacks.append(output[output.find("Traceback"):])

        return failed_tests, tracebacks
