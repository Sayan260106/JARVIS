"""Unit and integration tests for JARVIS Complex Task Engine (DAG Orchestrator).

Verifies:
1. TaskDAG cycle detection, validation, and topological sorting.
2. Dependency layering: Frontend strictly depends on Backend.
3. Observe-verify-recover sub-stage lifecycle.
4. The complete 11-node Presentation Preparation Workflow for ORCA-X:
   - Find project
   - Inspect repository
   - Check dependencies
   - Start backend (observe, verify, recover)
   - Start frontend (depends on backend; observe, verify, recover)
   - Open application
   - Inspect main pages
   - Test important interactions
   - Collect errors
   - Determine severity
   - Generate report
5. Executive report synthesis and error severity classification.
"""

import os
import unittest

from jarvis.orchestrator.schemas import (
    CollectedIssue,
    ErrorSeverity,
    ExecutionReport,
    NodeStatus,
    TaskNode,
)
from jarvis.orchestrator.dag import TaskDAG
from jarvis.orchestrator.engine import ComplexTaskEngine
from jarvis.orchestrator.workflows import PresentationPrepWorkflow
from jarvis.tools.orchestration_tools import RunComplexTaskTool
from jarvis.capabilities.goal_planner import GoalPlanner
from jarvis.core.task_manager import TaskManager


class TestComplexTaskEngine(unittest.TestCase):
    """Test suite for DAG Orchestrator and Complex Task Engine."""

    @classmethod
    def setUpClass(cls):
        cls.test_db = "data/test_orchestrator_tasks.db"
        cls.task_manager = TaskManager(db_path=cls.test_db)
        cls.engine = ComplexTaskEngine(task_manager=cls.task_manager)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_db):
            try:
                os.remove(cls.test_db)
            except Exception:
                pass

    def test_dag_cycle_detection_and_validation(self):
        """Verify TaskDAG validates valid graph and detects cycles."""
        dag = TaskDAG("Test DAG")
        dag.add_node(TaskNode("A", "Node A"))
        dag.add_node(TaskNode("B", "Node B", depends_on=["A"]))
        dag.add_node(TaskNode("C", "Node C", depends_on=["B"]))

        self.assertTrue(dag.validate())
        sorted_nodes = [n.node_id for n in dag.topological_sort()]
        self.assertEqual(sorted_nodes, ["A", "B", "C"])

        # Introduce cycle: A depends on C
        dag.add_dependency(child_id="A", parent_id="C")
        self.assertFalse(dag.validate())
        with self.assertRaises(ValueError):
            dag.topological_sort()

    def test_dependency_layering_frontend_after_backend(self):
        """Verify that Frontend strictly executes after Backend in the DAG."""
        dag = PresentationPrepWorkflow.build_dag(project_name="ORCA-X")
        self.assertTrue(dag.validate())

        # Check frontend explicitly declares backend dependency
        frontend_node = dag.get_node("start_frontend")
        self.assertIn("start_backend", frontend_node.depends_on)

        # Check execution levels
        levels = dag.get_execution_levels()
        level_map = {}
        for idx, lvl in enumerate(levels):
            for node in lvl:
                level_map[node.node_id] = idx

        self.assertLess(level_map["find_project"], level_map["inspect_repo"])
        self.assertLess(level_map["inspect_repo"], level_map["check_dependencies"])
        self.assertLess(level_map["check_dependencies"], level_map["start_backend"])
        self.assertLess(level_map["start_backend"], level_map["start_frontend"])
        self.assertLess(level_map["start_frontend"], level_map["open_application"])

    def test_observe_verify_recover_substage(self):
        """Verify observe, verify, and recover sub-stage execution."""
        dag = TaskDAG("Substage Test")

        def mock_service_action(node, wm):
            return {
                "observe_detail": "Process healthy on PID 9999",
                "verified": True,
                "verify_detail": "HTTP 200 OK",
            }

        node = TaskNode("svc", "Start Service", action=mock_service_action, has_sub_stages=True)
        dag.add_node(node)

        report = self.engine.execute_dag(dag, print_tree=False)
        self.assertEqual(report.completed_nodes, 1)
        self.assertEqual(len(node.sub_stages), 4)
        stage_names = [s.stage_name for s in node.sub_stages]
        self.assertEqual(stage_names, ["execute", "observe", "verify", "recover"])

    def test_orca_x_presentation_prep_workflow_full_execution(self):
        """Verify the complete 11-node Presentation Preparation Workflow for ORCA-X."""
        user_prompt = (
            "Jarvis, prepare my laptop for my presentation tomorrow. Open my ORCA-X project, "
            "check that the frontend and backend work, start them, check the main pages, "
            "and tell me what I need to fix."
        )
        self.assertTrue(GoalPlanner.is_complex_project_goal(user_prompt))

        dag = PresentationPrepWorkflow.build_dag(project_name="ORCA-X")
        self.assertEqual(len(dag.nodes), 11)

        # Execute the full DAG
        report = self.engine.execute_dag(dag, objective=user_prompt, print_tree=True)

        self.assertEqual(report.total_nodes, 11)
        self.assertEqual(report.completed_nodes, 11)
        self.assertEqual(report.failed_nodes, 0)
        self.assertEqual(report.overall_status, "READY")
        self.assertIn("Presentation Readiness Report for ORCA-X", report.summary_text)

        # Check sub-stages on Backend & Frontend
        backend = dag.get_node("start_backend")
        frontend = dag.get_node("start_frontend")
        self.assertTrue(backend.has_sub_stages)
        self.assertTrue(frontend.has_sub_stages)
        self.assertEqual(backend.status, NodeStatus.COMPLETED)
        self.assertEqual(frontend.status, NodeStatus.COMPLETED)

        # Check error collection and severity classification
        self.assertGreater(len(report.issues), 0)
        for issue in report.issues:
            self.assertIsInstance(issue, CollectedIssue)
            self.assertEqual(issue.severity, ErrorSeverity.LOW)

    def test_run_complex_task_tool(self):
        """Verify BaseTool execution and verification for RunComplexTaskTool."""
        tool = RunComplexTaskTool(engine=self.engine)
        res = tool.execute(workflow="presentation_prep", project_name="ORCA-X")
        self.assertTrue(res.success)
        self.assertEqual(res.output["completed_nodes"], 11)

        ver = tool.verify({"workflow": "presentation_prep"}, res)
        self.assertTrue(ver.verified)


if __name__ == "__main__":
    unittest.main()
