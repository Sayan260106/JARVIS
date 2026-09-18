"""Test Suite for the Central Autonomous Agent Loop and 14-Step Marine Prediction Workflow.

Verifies:
- while task.active loop execution
- State-feeding between sequential actions (Step N output -> Step N+1 input)
- Observe-verify-recover cycle on simulated failures
- Permission checks and ask_user handling
- The complete 14-step ORCA-X marine prediction demonstration workflow
"""

import os
import shutil
import tempfile
import unittest
from typing import Any, Dict, List

from jarvis.core.agent_loop import AgentLoop
from jarvis.core.loop_schemas import ActionStatus, LoopAction
from jarvis.orchestrator.marine_prediction_workflow import MarinePredictionWorkflow
from jarvis.capabilities.agent_planner import AgentToolExecutor


class TestAutonomousAgentLoop(unittest.TestCase):
    """Tests the continuous cognitive agent loop and state feeding."""

    def test_state_feeding_between_steps(self):
        """Verifies that each step's output feeds directly into the next step."""
        loop = AgentLoop()

        plan = [
            LoopAction(
                action_id="step_a",
                name="Step A: Compute initial value",
                action_fn=lambda state: {"base_val": 10},
                depends_on=[],
            ),
            LoopAction(
                action_id="step_b",
                name="Step B: Multiply by 5",
                action_fn=lambda state: {"scaled_val": state.get("base_val", 0) * 5},
                depends_on=["step_a"],
            ),
            LoopAction(
                action_id="step_c",
                name="Step C: Add offset",
                action_fn=lambda state: {"final_val": state.get("scaled_val", 0) + 7},
                depends_on=["step_b"],
            ),
        ]

        task = loop.run(objective="Test State Feeding", initial_plan=plan, print_visual_table=False)
        self.assertEqual(task.status, "COMPLETED")
        self.assertFalse(task.active)
        self.assertEqual(len(task.completed_steps), 3)

        # Check that outputs fed forward correctly
        self.assertEqual(task.state["base_val"], 10)
        self.assertEqual(task.state["scaled_val"], 50)
        self.assertEqual(task.state["final_val"], 57)

    def test_observe_verify_recover_cycle(self):
        """Verifies that failures trigger analyze_failure -> recover -> replan up to max attempts."""
        loop = AgentLoop()

        attempts = 0

        def flaky_action(state: Dict[str, Any]) -> Dict[str, Any]:
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise RuntimeError(f"Simulated transient glitch (attempt {attempts})")
            return {"status": "recovered", "attempts": attempts}

        plan = [
            LoopAction(
                action_id="flaky_step",
                name="Flaky Step with Self-Healing",
                action_fn=flaky_action,
                depends_on=[],
            )
        ]

        task = loop.run(objective="Test Self-Healing Recovery", initial_plan=plan, print_visual_table=False)
        self.assertEqual(task.status, "COMPLETED")
        self.assertEqual(task.recovery_attempts, 2)
        self.assertEqual(task.state["status"], "recovered")
        self.assertEqual(task.state["attempts"], 3)

    def test_permission_blocking_and_ask_user(self):
        """Verifies that an unapproved action halts at ask_user with BLOCKED status."""
        def mock_ask_user(action, details):
            return {"approved": False, "response": "User declined operation."}

        loop = AgentLoop(ask_user_callback=mock_ask_user)

        from jarvis.tools.base import BaseTool, PermissionLevel, RiskLevel, ToolResult, ToolVerification
        from jarvis.tools.registry import ToolRegistry

        class MockDangerousTool(BaseTool):
            name = "mock_dangerous_op"
            description = "Simulates dangerous operation"
            risk_level = RiskLevel.HIGH
            permission_level = PermissionLevel.LEVEL_3_DESTRUCTIVE
            parameters = {}
            def execute(self, **kwargs):
                return ToolResult(success=True, output="Executed")
            def verify(self, args, res):
                return ToolVerification(verified=True, details="Verified")

        reg = ToolRegistry()
        reg.register(MockDangerousTool())
        loop.registry = reg

        plan = [
            LoopAction(
                action_id="risky_step",
                name="Perform High-Risk Operation",
                target_tool="mock_dangerous_op",
                depends_on=[],
            )
        ]

        task = loop.run(objective="Test Policy Blocking", initial_plan=plan, print_visual_table=False)
        self.assertEqual(task.status, "BLOCKED")
        self.assertFalse(task.active)


class TestMarinePredictionWorkflow(unittest.TestCase):
    """Tests the 14-step ORCA-X Marine Prediction Demonstration Workflow."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_14_step_marine_demonstration_workflow(self):
        """Executes all 14 steps of the ORCA-X marine readiness workflow and validates outputs."""
        loop = AgentLoop()
        plan = MarinePredictionWorkflow.build_plan(project_name="ORCA-X", reports_dir=self.temp_dir)
        self.assertEqual(len(plan), 14)

        objective = (
            "Research whether my ORCA-X marine prediction model is ready for tomorrow's demonstration. "
            "Check repository, inspect ML eval, test realtime API, research INCOIS/MOSDAC, "
            "compare findings with ChatGPT and Gemini, and generate report."
        )

        task = loop.run(objective=objective, initial_plan=plan, print_visual_table=True)
        self.assertEqual(task.status, "COMPLETED")
        self.assertFalse(task.active)
        self.assertEqual(len(task.completed_steps), 14)

        # 1. Check state outputs from intermediate steps
        self.assertIn("repo_path", task.state)
        self.assertEqual(task.state["branch"], "main")
        self.assertIn("eval_metrics", task.state)
        self.assertEqual(task.state["eval_metrics"]["accuracy"], "98.2%")
        self.assertIn("service_url", task.state)
        self.assertIn("api_test_response", task.state)
        self.assertEqual(task.state["api_test_response"]["predicted_wave_height_m"], 1.84)
        self.assertIn("incois_data", task.state)
        self.assertEqual(task.state["incois_data"]["observed_wave_height_m"], 1.80)
        self.assertIn("chatgpt_findings", task.state)
        self.assertIn("gemini_findings", task.state)
        self.assertIn("evidence_comparison", task.state)
        self.assertEqual(task.state["evidence_comparison"]["overall_agreement"], "98.4%")
        self.assertIn("generated_report", task.state)
        self.assertIn("READY FOR TOMORROW'S DEMONSTRATION", task.state["generated_report"])

        # 2. Check that report file was saved to disk
        report_file = os.path.join(self.temp_dir, "orca_x_marine_readiness.md")
        self.assertTrue(os.path.exists(report_file))
        with open(report_file, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("ORCA-X Marine Prediction Model", content)
            self.assertIn("What Works", content)
            self.assertIn("What You Should Demonstrate", content)

    def test_agent_tool_executor_triggers_marine_workflow(self):
        """Verifies AgentToolExecutor identifies the complex command and executes the agent loop."""
        executor = AgentToolExecutor()
        complex_prompt = (
            "Jarvis, research whether my ORCA-X marine prediction model is ready for tomorrow's demonstration. "
            "Check the repository, inspect the latest evaluation results, test the realtime API, "
            "research the relevant INCOIS/MOSDAC information online, compare the findings with ChatGPT and Gemini, "
            "and prepare a report telling me what works, what doesn't, and what I should demonstrate."
        )

        turn = executor.run_turn(complex_prompt)
        self.assertTrue(turn.tool_called)
        self.assertEqual(turn.tool_name, "agent_loop_marine_workflow")
        self.assertIn("ORCA-X Marine Prediction Model", turn.final_response)
        self.assertIn("What You Should Demonstrate", turn.final_response)


if __name__ == "__main__":
    unittest.main()
