"""
Unit tests for Phase 8 — Unified Computer-Use Planner and end-to-end integration.
"""

import os
import shutil
import tempfile
import unittest

from jarvis.core.schemas import SubsystemType
from jarvis.core.state import AgentSessionState
from jarvis.capabilities.understand import DefaultUnderstandCapability
from jarvis.capabilities.plan import DefaultPlanCapability
from jarvis.capabilities.goal_planner import GoalPlanner
from jarvis.orchestrator.unified_planner import (
    UnifiedComputerUsePlanner,
    UnifiedComputerUsePlan,
    UnifiedPlanStep,
    UnifiedExecutionReport,
)
from jarvis.tools.orchestration_tools import UnifiedComputerUseTool
from jarvis.tools import get_default_registry


class TestUnifiedComputerUsePlanner(unittest.TestCase):
    """Test suite covering the 13-step unified computer-use workflow."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="jarvis_unified_test_")
        self.destination_folder = os.path.join(self.temp_dir, "college_folder", "DBMS")
        self.prompt = (
            "Find the latest DBMS assignment in Classroom, download it, solve it, "
            "save the solution in my college folder, and open it in VS Code."
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_understand_compound_computer_use_request(self):
        """Test DefaultUnderstandCapability parses compound 13-stage request and extracts subgoals."""
        understand = DefaultUnderstandCapability()
        intent = understand.understand(self.prompt, {})

        self.assertEqual(intent.extracted_entities.get("action"), "unified_computer_use_workflow")
        self.assertEqual(intent.extracted_entities.get("course"), "DBMS")
        self.assertEqual(intent.extracted_entities.get("editor"), "VS Code")
        self.assertIn("college folder", intent.extracted_entities.get("destination_folder", "").lower())

        sub_goals = intent.sub_goals
        self.assertEqual(len(sub_goals), 13)
        self.assertIn("Open Chrome", sub_goals[0])
        self.assertIn("Classroom", sub_goals[1])
        self.assertIn("Download", sub_goals[4])
        self.assertIn("Solve", sub_goals[7])
        self.assertIn("Save", sub_goals[9])
        self.assertIn("Open", sub_goals[10])
        self.assertIn("Verify", sub_goals[11])
        self.assertIn("Report", sub_goals[12])

    def test_plan_capability_13_steps(self):
        """Test DefaultPlanCapability generates 13 PlanSteps across all 6 subsystems."""
        understand = DefaultUnderstandCapability()
        intent = understand.understand(self.prompt, {})

        planner = DefaultPlanCapability()
        plan = planner.plan(intent, AgentSessionState(task_id="test_unified"))

        self.assertEqual(len(plan.steps), 13)

        expected_subsystems = [
            SubsystemType.WEB,       # 1. Open Chrome
            SubsystemType.WEB,       # 2. Navigate Classroom
            SubsystemType.WEB,       # 3. Find DBMS
            SubsystemType.WEB,       # 4. Find assignment
            SubsystemType.WEB,       # 5. Download
            SubsystemType.SYSTEM,    # 6. Verify file
            SubsystemType.DOCUMENT,  # 7. Parse assignment
            SubsystemType.LOCAL,     # 8. Solve
            SubsystemType.DOCUMENT,  # 9. Create solution
            SubsystemType.SYSTEM,    # 10. Save
            SubsystemType.SYSTEM,    # 11. Open VS Code
            SubsystemType.VISION,    # 12. Verify file opened
            SubsystemType.LOCAL,     # 13. Report completion
        ]

        for i, step in enumerate(plan.steps):
            self.assertEqual(step.subsystem, expected_subsystems[i], f"Step {i+1} subsystem mismatch")

    def test_unified_planner_canonical_plan(self):
        """Test UnifiedComputerUsePlanner creates the canonical 13-stage plan and registers tasks."""
        planner = UnifiedComputerUsePlanner()
        plan = planner.create_assignment_workflow_plan(
            objective=self.prompt,
            course="DBMS",
            destination_folder=self.destination_folder,
            editor="VS Code",
            simulated=True,
        )

        self.assertIsInstance(plan, UnifiedComputerUsePlan)
        self.assertEqual(len(plan.steps), 13)
        self.assertIsNotNone(plan.task_id)
        self.assertTrue(plan.solution_path.endswith("DBMS_Assignment_Solution.sql"))

        # Verify steps
        step_names = [s.name for s in plan.steps]
        self.assertEqual(
            step_names,
            [
                "Open Chrome",
                "Navigate Classroom",
                "Find DBMS",
                "Find assignment",
                "Download",
                "Verify file",
                "Parse assignment",
                "Solve",
                "Create solution",
                "Save",
                "Open VS Code",
                "Verify file opened",
                "Report completion",
            ],
        )

    def test_unified_planner_execution_simulated(self):
        """Test end-to-end execution creates solution file and reports 13 successful steps."""
        planner = UnifiedComputerUsePlanner()
        plan = planner.create_assignment_workflow_plan(
            objective=self.prompt,
            course="DBMS",
            destination_folder=self.destination_folder,
            editor="VS Code",
            simulated=True,
        )

        report = planner.execute_plan(plan, simulated=True)
        self.assertTrue(report.success)
        self.assertEqual(report.completed_steps, 13)
        self.assertEqual(report.total_steps, 13)

        # Verify solution file created
        self.assertTrue(os.path.exists(plan.solution_path))
        with open(plan.solution_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("DBMS", content)
        self.assertIn("CREATE TABLE", content)

    def test_goal_planner_integration(self):
        """Test GoalPlanner recognizes unified goal and executes all 13 steps."""
        gp = GoalPlanner()
        self.assertTrue(gp.is_unified_computer_use_goal(self.prompt))

        plan = gp.create_unified_computer_use_plan(
            self.prompt,
            course="DBMS",
            destination_folder=self.destination_folder,
            editor="VS Code",
            simulated=True,
        )
        self.assertEqual(len(plan.subtasks), 13)

        success = gp.execute_plan(plan)
        self.assertTrue(success)

        # Check all 13 subtasks completed
        completed = [st for st in plan.subtasks if st.status == "SUCCESS"]
        self.assertEqual(len(completed), 13)

    def test_unified_computer_use_tool(self):
        """Test UnifiedComputerUseTool registered and executable via ToolRegistry."""
        registry = get_default_registry()
        tool = registry.get("unified_computer_use")
        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "unified_computer_use")

        result = tool.execute(
            prompt=self.prompt,
            course="DBMS",
            destination_folder=self.destination_folder,
            editor="VS Code",
            simulated=True,
        )

        self.assertTrue(result.success)
        self.assertIsNotNone(result.output)
        self.assertEqual(result.output.get("completed_steps"), 13)

        verification = tool.verify({}, result)
        self.assertTrue(verification.verified)


if __name__ == "__main__":
    unittest.main()
