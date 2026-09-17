"""Unit tests for Phase 6 — Self-correction / Recovery Engine.

Verifies:
1. Error diagnostics root cause detection across error categories.
2. Recovery progression (Attempt 1 fails -> safe fix -> Attempt 2 succeeds).
3. Multi-stage recovery (Attempt 1 FAILED -> Attempt 2 FAILED -> New plan -> Attempt 3 SUCCESS).
4. Strict bounded limit (max_attempts = 3) escalating with:
   "I've attempted three recovery strategies. The remaining issue requires your input."
5. ORCA-X backend startup simulation with port conflict resolution and endpoint verification.
6. Persistent TaskManager checkpointing during recovery cycles.
"""

from __future__ import annotations
import os
import shutil
import tempfile
import unittest

from jarvis.capabilities.diagnostics import (
    DiagnosticResult,
    ErrorCategory,
    ErrorDiagnosticEngine,
)
from jarvis.capabilities.recovery_engine import (
    RecoveryAttempt,
    RecoveryEngine,
    RecoveryExecutionResult,
)
from jarvis.core.task_schemas import Task, TaskStatus
from jarvis.core.task_manager import TaskManager, TaskStore
from jarvis.tools.service_tools import FreePortTool, VerifyEndpointTool, StartBackendServiceTool


class TestRecoveryEngine(unittest.TestCase):
    """Test suite for diagnostic classification, safe fixes, and bounded recovery."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="jarvis_recovery_test_")
        self.diagnostics = ErrorDiagnosticEngine()
        self.db_path = os.path.join(self.test_dir, "recovery_tasks.db")
        self.store = TaskStore(db_path=self.db_path)
        self.manager = TaskManager(store=self.store)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_diagnostic_port_in_use(self):
        """Verify port in use errors are accurately parsed and categorized."""
        error_sample = (
            "ERROR: [WinError 10048] Only one usage of each socket address "
            "(protocol/network address/port) is normally permitted: ('127.0.0.1', 8080)"
        )
        diag = self.diagnostics.diagnose(error_sample)
        self.assertEqual(diag.category, ErrorCategory.PORT_IN_USE)
        self.assertEqual(diag.remediation_params.get("port"), 8080)
        self.assertEqual(diag.safe_remediation_type, "free_port")

    def test_diagnostic_missing_dependency(self):
        """Verify ModuleNotFoundError maps to package installer fix."""
        error_sample = "ModuleNotFoundError: No module named 'fastapi'"
        diag = self.diagnostics.diagnose(error_sample)
        self.assertEqual(diag.category, ErrorCategory.MISSING_DEPENDENCY)
        self.assertEqual(diag.remediation_params.get("package"), "fastapi")
        self.assertEqual(diag.safe_remediation_type, "install_package")

    def test_diagnostic_missing_env(self):
        """Verify missing environment variables or .env file are detected."""
        error_sample = "FileNotFoundError: [Errno 2] No such file or directory: '.env'"
        diag = self.diagnostics.diagnose(error_sample)
        self.assertEqual(diag.category, ErrorCategory.CONFIG_OR_ENV_MISSING)
        self.assertEqual(diag.safe_remediation_type, "create_default_env")

    def test_diagnostic_invalid_entrypoint(self):
        """Verify missing script files trigger entrypoint resolution."""
        error_sample = "python: can't open file 'orca_backend.py': [Errno 2] No such file or directory"
        diag = self.diagnostics.diagnose(error_sample)
        self.assertEqual(diag.category, ErrorCategory.INVALID_ENTRYPOINT)
        self.assertEqual(diag.safe_remediation_type, "resolve_entrypoint")

    def test_recovery_attempt_1_success(self):
        """Verify an action succeeding on attempt 1 finishes without recovery overhead."""
        engine = RecoveryEngine(max_attempts=3, diagnostics_engine=self.diagnostics)

        def simple_action(ctx):
            return True, "Backend started on port 8000", None

        res = engine.execute_with_recovery("Start service", simple_action)
        self.assertTrue(res.success)
        self.assertEqual(res.total_attempts, 1)
        self.assertFalse(res.escalated_to_user)
        self.assertEqual(len(res.attempts_history), 1)
        self.assertEqual(res.attempts_history[0].status, "SUCCESS")

    def test_recovery_attempt_1_fails_attempt_2_succeeds(self):
        """Verify: Attempt 1 fails -> safe fix applied -> Attempt 2 succeeds."""
        engine = RecoveryEngine(max_attempts=3, diagnostics_engine=self.diagnostics)
        call_count = 0

        def flaky_action(ctx):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return False, None, "OSError: [WinError 10048] address already in use: 8000"
            return True, "Started successfully after port freed", None

        res = engine.execute_with_recovery("Run backend", flaky_action)
        self.assertTrue(res.success)
        self.assertEqual(res.total_attempts, 2)
        self.assertFalse(res.escalated_to_user)
        self.assertEqual(res.attempts_history[0].status, "FAILED")
        self.assertIsNotNone(res.attempts_history[0].fix_applied)
        self.assertEqual(res.attempts_history[1].status, "SUCCESS")

    def test_recovery_attempt_3_success_progression(self):
        """Verify:
        Attempt 1 -> FAILED
        Attempt 2 -> FAILED
        Analyze failure -> New plan
        Attempt 3 -> SUCCESS
        """
        engine = RecoveryEngine(max_attempts=3, diagnostics_engine=self.diagnostics)
        attempt_counter = 0

        def multi_fail_action(ctx):
            nonlocal attempt_counter
            attempt_counter += 1
            if attempt_counter == 1:
                return False, None, "ModuleNotFoundError: No module named 'pydantic'"
            elif attempt_counter == 2:
                return False, None, "FileNotFoundError: .env configuration missing"
            else:
                return True, "Service initialized and healthy on third plan iteration", None

        res = engine.execute_with_recovery("Start ORCA-X Service", multi_fail_action)
        self.assertTrue(res.success)
        self.assertEqual(res.total_attempts, 3)
        self.assertFalse(res.escalated_to_user)
        self.assertEqual(res.attempts_history[0].status, "FAILED")
        self.assertEqual(res.attempts_history[1].status, "FAILED")
        self.assertEqual(res.attempts_history[2].status, "SUCCESS")

    def test_recovery_hard_limit_escalation_after_3_attempts(self):
        """Verify:
        Attempt 1 -> FAILED
        Attempt 2 -> FAILED
        Attempt 3 -> FAILED
        max_attempts = 3 reached -> Escalates immediately with exact message:
        "I've attempted three recovery strategies. The remaining issue requires your input."
        """
        task = self.manager.create_task("Run crashing backend")
        engine = RecoveryEngine(
            max_attempts=3,
            diagnostics_engine=self.diagnostics,
            task_manager=self.manager,
        )

        def perpetually_failing_action(ctx):
            return False, None, "FatalError: Hardware device disconnected"

        res = engine.execute_with_recovery(
            objective="Run my ORCA-X backend",
            action_fn=perpetually_failing_action,
            task_id=task.id,
        )

        self.assertFalse(res.success)
        self.assertEqual(res.total_attempts, 3)
        self.assertTrue(res.escalated_to_user)
        self.assertEqual(
            res.final_message,
            "I've attempted three recovery strategies. The remaining issue requires your input."
        )

        # Verify TaskManager record
        persisted = self.manager.get_task(task.id)
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted.status, TaskStatus.FAILED)
        self.assertEqual(persisted.retry_count, 3)
        self.assertEqual(len(persisted.failed_steps), 3)

    def test_service_tools_and_endpoint_verification(self):
        """Verify FreePortTool, StartBackendServiceTool, and VerifyEndpointTool."""
        # 1. FreePortTool
        free_tool = FreePortTool()
        free_res = free_tool.execute(port=8999)
        self.assertTrue(free_res.success)
        self.assertTrue(free_res.output["freed"])

        # 2. VerifyEndpointTool with invalid port (graceful error)
        verify_tool = VerifyEndpointTool()
        unreachable_res = verify_tool.execute(url="http://127.0.0.1:59999/health", timeout_seconds=1)
        self.assertFalse(unreachable_res.success)
        self.assertIn("unreachable", unreachable_res.error.lower())

        # 3. StartBackendServiceTool with short diagnostic command
        service_tool = StartBackendServiceTool()
        cmd_res = service_tool.execute(
            command="python -c \"import time; time.sleep(0.5)\"",
            startup_wait_seconds=1,
        )
        self.assertTrue(cmd_res.success)


if __name__ == "__main__":
    unittest.main()
