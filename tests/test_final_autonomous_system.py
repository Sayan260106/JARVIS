"""Tests for Phase 18 — Final Autonomous System.

Validates:
1. End-to-end autonomous multi-subsystem DAG execution (Windows, Browser, Docs).
2. Multimodal Observer telemetry (Screen, DOM, FS, Process).
3. Deterministic Verifier validation logic.
4. Closed-loop recovery and replanning (self-healing port conflicts, missing files).
5. Bounded retry escalation policy.
6. UI State & TaskManager live synchronization.
"""

import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from jarvis.core.autonomous_system import (
    AutonomousSystem,
    AutonomousTaskNode,
    AgentSubsystem,
    MultimodalObserver,
    DeterministicVerifier,
    ObservationEvidence,
    VerificationVerdict,
    AutonomousExecutionReport,
)
from jarvis.core.task_manager import TaskManager
from jarvis.core.ui_state import UIStateManager
from jarvis.tools.base import BaseTool, ToolResult, ToolVerification, PermissionLevel
from jarvis.tools.registry import ToolRegistry


class DummySuccessTool(BaseTool):
    name = "dummy_success"
    description = "A dummy tool that always succeeds"
    permission_level = PermissionLevel.LEVEL_0_READ

    def execute(self, **kwargs) -> ToolResult:
        return ToolResult(
            success=True,
            output="Operation completed successfully.",
            data={"status": "ok"},
            verification=ToolVerification(verified=True, details="Verified success output."),
        )

    def verify(self, arguments: dict, result: ToolResult) -> ToolVerification:
        return ToolVerification(verified=True, details="Dummy verified success.")


class DummyFailingTool(BaseTool):
    name = "dummy_fail"
    description = "A dummy tool that always fails"
    permission_level = PermissionLevel.LEVEL_0_READ

    def execute(self, **kwargs) -> ToolResult:
        return ToolResult(
            success=False,
            output=None,
            error="Resource locked: Port 8000 already in use by PID 4412",
            verification=ToolVerification(verified=False, details="Port conflict detected."),
        )

    def verify(self, arguments: dict, result: ToolResult) -> ToolVerification:
        return ToolVerification(verified=False, details="Port conflict detected.")


class TestFinalAutonomousSystem(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_autonomous_tasks.db")
        self.task_manager = TaskManager(db_path=self.db_path)
        self.ui_state = UIStateManager()
        self.registry = ToolRegistry()
        self.registry.register(DummySuccessTool())
        self.registry.register(DummyFailingTool())

        self.system = AutonomousSystem(
            registry=self.registry,
            task_manager=self.task_manager,
            ui_state=self.ui_state,
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_multimodal_observer_capture(self):
        """Observer correctly correlates execution output, timing, and system context."""
        observer = MultimodalObserver(registry=self.registry)
        node = AutonomousTaskNode(
            node_id="test_node_1",
            name="Test Verification Step",
            target_agent=AgentSubsystem.WINDOWS_CONTROL,
            tool_name="dummy_success",
            arguments={},
        )
        tool_result = ToolResult(
            success=True,
            output="Processed 15 files.",
        )

        obs = observer.observe(node, tool_result, duration_ms=42.5)
        self.assertIsInstance(obs, ObservationEvidence)
        self.assertEqual(obs.node_id, "test_node_1")
        self.assertTrue(obs.success)
        self.assertEqual(obs.duration_ms, 42.5)
        self.assertIn("screen_active_window", obs.system_state)
        self.assertIn("processes_running", obs.system_state)
        self.assertIn("Processed", str(obs.tool_output))

    def test_deterministic_verifier_pass(self):
        """Verifier grants PASS when ToolResult succeeds and verification checks pass."""
        verifier = DeterministicVerifier(registry=self.registry)
        node = AutonomousTaskNode(
            node_id="test_node_1",
            name="Verify Valid Output",
            target_agent=AgentSubsystem.BROWSER_AGENT,
            tool_name="dummy_success",
            arguments={},
        )
        obs = ObservationEvidence(
            step_id="test_node_1",
            exit_code=0,
            raw_output="All good",
            error=None,
            duration_ms=10.0,
        )

        verdict = verifier.verify(node, obs)
        self.assertIsInstance(verdict, VerificationVerdict)
        self.assertTrue(verdict.passed)
        self.assertIn("VERIFIED", verdict.reason.upper())

    def test_deterministic_verifier_fail(self):
        """Verifier flags FAIL when ToolResult or verification fails."""
        verifier = DeterministicVerifier(registry=self.registry)
        node = AutonomousTaskNode(
            node_id="test_node_2",
            name="Verify Failure Handling",
            target_agent=AgentSubsystem.WINDOWS_CONTROL,
            tool_name="dummy_fail",
            arguments={},
        )
        obs = ObservationEvidence(
            step_id="test_node_2",
            exit_code=1,
            raw_output=None,
            error="Port 8000 in use",
            duration_ms=5.0,
        )

        verdict = verifier.verify(node, obs)
        self.assertFalse(verdict.passed)
        self.assertIn("FAILED", verdict.reason.upper())

    def test_end_to_end_presentation_workflow_dag(self):
        """Executes the complete Orca-X presentation DAG across multiple subsystems."""
        progress_calls = []

        def on_progress(n: AutonomousTaskNode):
            progress_calls.append(n.node_id)

        objective = "Prepare presentation for Orca-X and start backend"
        report: AutonomousExecutionReport = self.system.process_objective(
            objective, on_node_progress=on_progress
        )

        self.assertEqual(report.status, "SUCCESS")
        self.assertEqual(report.nodes_completed, report.total_nodes)
        self.assertGreaterEqual(report.total_nodes, 4)
        self.assertEqual(len(progress_calls), report.total_nodes)

        # Check that multiple agent subsystems were invoked
        subsystems_invoked = {res["agent"] for res in report.step_results}
        self.assertIn(AgentSubsystem.WINDOWS_CONTROL.value, subsystems_invoked)
        self.assertIn(AgentSubsystem.BROWSER_AGENT.value, subsystems_invoked)
        self.assertIn(AgentSubsystem.DOCUMENT_RAG.value, subsystems_invoked)

        # Verify UI state was updated
        steps = self.ui_state.task_steps
        self.assertTrue(all(s.status.value == "COMPLETED" for s in steps))

    def test_end_to_end_classroom_assignment_dag(self):
        """Executes the Classroom DBMS assignment workflow across Browser, Document RAG, and Windows."""
        objective = "Solve DBMS assignment from Classroom"
        report = self.system.process_objective(objective)

        self.assertEqual(report.status, "SUCCESS")
        self.assertEqual(report.nodes_completed, 5)

        # Verify step details
        step_names = [res["node_name"] for res in report.step_results]
        self.assertTrue(any("Classroom" in name for name in step_names))
        self.assertTrue(any("solution" in name.lower() for name in step_names))

    def test_closed_loop_recovery_and_replan_port_conflict(self):
        """Simulates port collision failure and verifies self-healing recovery."""
        node = AutonomousTaskNode(
            node_id="conflict_node",
            name="Start backend on port 8000",
            target_agent=AgentSubsystem.WINDOWS_CONTROL,
            tool_name="dummy_fail",
            arguments={"port": 8000},
        )
        obs = ObservationEvidence(
            step_id="conflict_node",
            exit_code=1,
            raw_output=None,
            error="Port 8000 already in use",
            duration_ms=12.0,
        )
        verdict = VerificationVerdict(passed=False, evidence=obs.error, details="Execution failed")

        with patch("jarvis.tools.service_tools.FreePortTool.execute") as mock_free:
            mock_free.return_value = ToolResult(success=True, output="Freed port 8000")
            recovered, fix_msg = self.system._attempt_recovery_and_replan(
                node, obs, verdict, [node]
            )

            self.assertTrue(recovered)
            self.assertIn("Freed conflicting port 8000", fix_msg)

    def test_closed_loop_recovery_missing_directory(self):
        """Self-heals missing prerequisite directory or file path."""
        target_path = os.path.join(self.temp_dir, "missing_subdir", "prereq.txt")
        node = AutonomousTaskNode(
            node_id="missing_file_node",
            name="Access prerequisite artifact",
            target_agent=AgentSubsystem.WINDOWS_CONTROL,
            tool_name="read_file",
            arguments={"path": target_path},
        )
        obs = ObservationEvidence(
            step_id="missing_file_node",
            exit_code=1,
            raw_output=None,
            error=f"Path does not exist: {target_path}",
            duration_ms=8.0,
        )
        verdict = VerificationVerdict(passed=False, evidence=obs.error, details="Execution failed")

        recovered, fix_msg = self.system._attempt_recovery_and_replan(
            node, obs, verdict, [node]
        )

        self.assertTrue(recovered)
        self.assertIn("Created missing prerequisite path", fix_msg)
        self.assertTrue(os.path.exists(target_path))

    def test_bounded_retry_escalation(self):
        """Unrecoverable errors trigger bounded retry policy (max 3 retries) and escalate."""
        # Create a custom DAG with a tool that fails every time
        node = AutonomousTaskNode(
            node_id="failing_node",
            name="Permanent failure node",
            target_agent=AgentSubsystem.WINDOWS_CONTROL,
            tool_name="dummy_fail",
            arguments={},
            max_retries=3,
        )

        with patch.object(self.system, "_plan_dag", return_value=[node]):
            with patch.object(self.system, "_attempt_recovery_and_replan", return_value=(False, "Cannot recover")):
                report = self.system.process_objective("Run unrecoverable task")

                self.assertIn(report.status, ("FAILED", "PARTIAL_FAILURE"))
                self.assertEqual(report.nodes_completed, 0)
                # Ensure it did not run indefinitely
                self.assertLessEqual(node.retry_count, 3)

    def test_proactive_monitoring_intent_planning(self):
        """Proactive requests ('watch my Downloads folder') generate proactive DAGs."""
        report = self.system.process_objective("Watch my Downloads folder for PDFs")
        self.assertEqual(report.status, "SUCCESS")
        self.assertEqual(report.total_nodes, 1)
        self.assertEqual(
            report.step_results[0]["agent"],
            AgentSubsystem.PROACTIVE_SYSTEM.value,
        )
        self.assertEqual(report.step_results[0]["tool_name"], "watch_folder")


if __name__ == "__main__":
    unittest.main()
