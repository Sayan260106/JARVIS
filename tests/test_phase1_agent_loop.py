"""Test Suite for Phase 1: Reliable Agent Loop with Multi-Step Verification,
Step Dependencies, Bounded Recovery, SQLite Persistence, Cancellation, and Resume.
"""

from __future__ import annotations
import os
import shutil
import tempfile
import unittest
from typing import Any, Dict, List

from jarvis.core.loop import JarvisAgentLoop
from jarvis.core.schemas import (
    ExecutionPlan,
    IntentCategory,
    PlanStep,
    RecoveryStrategy,
    StepStatus,
    SubsystemType,
    TaskObjective,
)
from jarvis.core.state import LoopPhase
from jarvis.core.task_manager import TaskManager, TaskStore
from jarvis.core.task_schemas import TaskStatus
from jarvis.tools.base import BaseTool, ToolResult, ToolVerification
from jarvis.tools.registry import ToolRegistry


class TestPhase1ReliableAgentLoop(unittest.TestCase):
    """Verifies all Phase 1 Agent Loop requirements."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_tasks.db")
        self.task_manager = TaskManager(db_path=self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_notepad_target_multistep_verified_task(self):
        """Target Scenario: 'Open Notepad, type Hello, save it as test.txt.'
        Must be parsed into a multi-step, dependency-linked, verified execution plan,
        executing open_application -> type_text -> create_file, verifying file on disk,
        and persisting state to SQLite.
        """
        target_file = os.path.join(self.temp_dir, "test.txt")
        prompt = f"Open Notepad, type Hello, save it as {target_file}."

        loop = JarvisAgentLoop(task_manager=self.task_manager)

        # 1. Test Understand Capability output
        objective = loop.understand_cap.understand(prompt, {})
        self.assertEqual(objective.intent, IntentCategory.TASK_AUTOMATION)
        self.assertIn("Notepad", objective.sub_goals[0])
        self.assertEqual(objective.extracted_entities["app_name"].lower(), "notepad")
        self.assertEqual(objective.extracted_entities["text"], "Hello")
        self.assertEqual(objective.extracted_entities["file_path"], target_file)

        # 2. Test Plan Capability output & Execution
        state = loop.run(prompt)

        self.assertEqual(state.phase, LoopPhase.COMPLETED)
        self.assertEqual(len(state.plan.steps), 3)

        # Step 1: Open Notepad
        step1 = state.plan.steps[0]
        self.assertEqual(step1.tool_name, "open_application")
        self.assertEqual(step1.status, StepStatus.SUCCESS)
        self.assertEqual(step1.depends_on, [])

        # Step 2: Type Hello
        step2 = state.plan.steps[1]
        self.assertEqual(step2.tool_name, "type_text")
        self.assertEqual(step2.status, StepStatus.SUCCESS)
        self.assertIn(step1.step_id, step2.depends_on)

        # Step 3: Save file
        step3 = state.plan.steps[2]
        self.assertEqual(step3.tool_name, "create_file")
        self.assertEqual(step3.status, StepStatus.SUCCESS)
        self.assertIn(step2.step_id, step3.depends_on)

        # 3. Verify Ground-Truth on disk
        self.assertTrue(os.path.exists(target_file), "test.txt was not created on disk")
        with open(target_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertEqual(content, "Hello", f"Expected 'Hello' in test.txt, got '{content}'")

        # 4. Verify Persistent SQLite State
        persistent_task = self.task_manager.get_task(state.task_id)
        self.assertIsNotNone(persistent_task)
        self.assertEqual(persistent_task.status, TaskStatus.COMPLETED)
        self.assertEqual(len(persistent_task.completed_steps), 3)

    def test_step_dependencies_and_skipping_on_failure(self):
        """Verifies that downstream steps are skipped when an upstream prerequisite fails."""
        loop = JarvisAgentLoop(task_manager=self.task_manager)

        step_a = PlanStep.create(
            description="Step A (Fails)",
            subsystem=SubsystemType.SYSTEM,
            tool_name="failing_tool",
            arguments={},
            expected_outcome="Success",
            action_fn=lambda s: (_ for _ in ()).throw(RuntimeError("Step A failed intentionally")),
        )
        step_b = PlanStep.create(
            description="Step B (Depends on A)",
            subsystem=SubsystemType.SYSTEM,
            tool_name="dependent_tool",
            arguments={},
            expected_outcome="Success",
            depends_on=[step_a.step_id],
            action_fn=lambda s: {"result": "should not run"},
        )

        state = loop.run(
            user_prompt="Run dependent steps",
            initial_plan=[step_a, step_b],
        )

        self.assertEqual(step_a.status, StepStatus.FAILED)
        self.assertEqual(step_b.status, StepStatus.SKIPPED)
        self.assertIn("Skipped due to unmet prerequisite", step_b.status_message)

    def test_maximum_retry_and_recovery_policy(self):
        """Verifies bounded recovery loops (max 3 retries, then escalate to user)."""
        loop = JarvisAgentLoop(task_manager=self.task_manager)

        attempts = 0

        def flaky_action(state):
            nonlocal attempts
            attempts += 1
            raise RuntimeError(f"Failure attempt {attempts}")

        step = PlanStep.create(
            description="Unrecoverable Flaky Step",
            subsystem=SubsystemType.SYSTEM,
            tool_name="flaky_tool",
            arguments={},
            expected_outcome="Pass",
            max_retries=3,
            action_fn=flaky_action,
        )

        state = loop.run(
            user_prompt="Test bounded retries",
            initial_plan=[step],
        )

        self.assertEqual(state.phase, LoopPhase.AWAITING_USER)
        self.assertEqual(state.plan.steps[0].retry_count, 3)
        self.assertIn("failed after 3 attempts", state.error_message)

    def test_persistent_execution_state_in_sqlite(self):
        """Verifies that step advancements and execution state are persisted in SQLite."""
        loop = JarvisAgentLoop(task_manager=self.task_manager)

        step1 = PlanStep.create(
            description="Compute Step 1",
            subsystem=SubsystemType.SYSTEM,
            tool_name="calc_1",
            arguments={},
            expected_outcome="Value 42",
            action_fn=lambda s: {"computed_value": 42},
        )
        step2 = PlanStep.create(
            description="Compute Step 2",
            subsystem=SubsystemType.SYSTEM,
            tool_name="calc_2",
            arguments={},
            expected_outcome="Value 84",
            depends_on=[step1.step_id],
            action_fn=lambda s: {"double_value": s.get("computed_value", 0) * 2},
        )

        state = loop.run(
            user_prompt="Test SQLite state persistence",
            initial_plan=[step1, step2],
        )

        self.assertEqual(state.phase, LoopPhase.COMPLETED)
        self.assertEqual(state.context_state["computed_value"], 42)
        self.assertEqual(state.context_state["double_value"], 84)

        # Verify directly in SQLite
        db_task = self.task_manager.get_task(state.task_id)
        self.assertIsNotNone(db_task)
        self.assertEqual(db_task.status, TaskStatus.COMPLETED)
        self.assertEqual(len(db_task.completed_steps), 2)
        self.assertEqual(db_task.context["context_state"]["double_value"], 84)

    def test_cancellation_support(self):
        """Verifies that an agent loop task can be cancelled cleanly."""
        loop = JarvisAgentLoop(task_manager=self.task_manager)

        step1 = PlanStep.create(
            description="Step 1 (Triggers cancellation)",
            subsystem=SubsystemType.SYSTEM,
            tool_name="cancel_trigger",
            arguments={},
            expected_outcome="Cancels loop",
            action_fn=lambda s: loop.request_cancellation(),
        )
        step2 = PlanStep.create(
            description="Step 2 (Should not run)",
            subsystem=SubsystemType.SYSTEM,
            tool_name="never_run",
            arguments={},
            expected_outcome="Should not run",
            depends_on=[step1.step_id],
            action_fn=lambda s: {"ran": True},
        )

        state = loop.run(
            user_prompt="Test cancellation",
            initial_plan=[step1, step2],
        )

        self.assertEqual(state.phase, LoopPhase.CANCELLED)
        self.assertEqual(step2.status, StepStatus.CANCELLED)

        # Verify in SQLite
        db_task = self.task_manager.get_task(state.task_id)
        self.assertEqual(db_task.status, TaskStatus.CANCELLED)

    def test_resume_interrupted_task(self):
        """Verifies that an interrupted task can be resumed from SQLite and completed."""
        loop = JarvisAgentLoop(task_manager=self.task_manager)

        target_file = os.path.join(self.temp_dir, "resumed.txt")

        # Step 1 creates initial file
        step1 = PlanStep.create(
            description="Step 1: Create initial file",
            subsystem=SubsystemType.SYSTEM,
            tool_name="create_file",
            arguments={"path": target_file, "content": "InitialData"},
            expected_outcome="Created",
        )
        # Step 2 requests cancellation before step 3
        step2 = PlanStep.create(
            description="Step 2: Interrupt before step 3",
            subsystem=SubsystemType.SYSTEM,
            tool_name="cancel_trigger",
            arguments={},
            expected_outcome="Interrupts",
            depends_on=[step1.step_id],
            action_fn=lambda s: loop.request_cancellation(),
        )
        # Step 3 saves final data
        step3 = PlanStep.create(
            description="Step 3: Save final file",
            subsystem=SubsystemType.SYSTEM,
            tool_name="create_file",
            arguments={"path": target_file, "content": "ResumedAndSaved"},
            expected_outcome="Saves file",
            depends_on=[step2.step_id],
        )

        # 1. Run until cancellation after step 2
        state = loop.run(
            user_prompt="Test Resume Workflow",
            initial_plan=[step1, step2, step3],
        )
        self.assertEqual(state.phase, LoopPhase.CANCELLED)
        task_id = state.task_id

        # Verify step 1 was completed and file created
        self.assertTrue(os.path.exists(target_file))
        with open(target_file, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "InitialData")

        # In SQLite, reset step 2 to succeed (e.g. replacing with open_application or simple step) and step 3 to pending
        db_task = self.task_manager.get_task(task_id)
        for s in db_task.context["plan_json"]["steps"]:
            if s["step_id"] == step2.step_id:
                s["tool_name"] = "task_runner"
                s["status"] = "PENDING"
            elif s["step_id"] == step3.step_id:
                s["status"] = "PENDING"
        db_task.status = TaskStatus.RUNNING
        self.task_manager.update_task(db_task)

        # 2. Resume task from SQLite!
        resumed_state = loop.resume(task_id)
        self.assertEqual(resumed_state.phase, LoopPhase.COMPLETED)

        # Verify final file content was updated by resumed step 3
        with open(target_file, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "ResumedAndSaved")

        # Verify SQLite has status COMPLETED
        final_db_task = self.task_manager.get_task(task_id)
        self.assertEqual(final_db_task.status, TaskStatus.COMPLETED)
        self.assertEqual(len(final_db_task.completed_steps), 3)


if __name__ == "__main__":
    unittest.main()

