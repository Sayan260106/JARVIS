"""Comprehensive Test Suite for Phase 13: Coding Agent.

Validates:
- Repository awareness (branch, commit, status, diff)
- File dependency awareness (AST imports, test correlations)
- Terminal test execution & failure extraction
- Error diagnostics & root cause analysis
- Safe code modification with AST validation & rollback
- Gated git push security
- Skills, tools, understand & plan capability integration
- End-to-end 10-stage test diagnosis and repair pipeline
"""

from __future__ import annotations
import os
import shutil
import sys
import tempfile
import unittest

from jarvis.capabilities.plan import DefaultPlanCapability
from jarvis.capabilities.understand import DefaultUnderstandCapability
from jarvis.core.schemas import IntentCategory, SubsystemType
from jarvis.core.state import AgentSessionState
from jarvis.skills import get_default_skill_registry
from jarvis.skills.base import SkillContext
from jarvis.subsystems.coding.agent import CodingAgent
from jarvis.subsystems.coding.code_modifier import CodeModifier
from jarvis.subsystems.coding.dependency_analyzer import DependencyAnalyzer
from jarvis.subsystems.coding.error_analyzer import ErrorAnalyzer
from jarvis.subsystems.coding.repo_inspector import RepoInspector
from jarvis.subsystems.coding.schemas import ErrorCategory, TestRunResult
from jarvis.subsystems.coding.test_runner import TestRunner
from jarvis.tools import get_default_registry


class TestCodingAgent(unittest.TestCase):
    """Unit and integration tests for Coding Agent and subsystems."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="jarvis_coding_test_")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    # ----------------------------------------------------------------------
    # 1. Repository Inspector & Git Awareness
    # ----------------------------------------------------------------------
    def test_repo_inspector_awareness(self):
        inspector = RepoInspector(default_repo_path=".")
        inspection = inspector.inspect(".")

        self.assertIsNotNone(inspection.branch)
        self.assertIsNotNone(inspection.commit_sha)
        self.assertTrue(os.path.isdir(inspection.repo_path))
        self.assertIsInstance(inspection.modified_files, list)

        # Verify git diff inspection
        diff = inspector.get_diff(".")
        self.assertIsInstance(diff, str)

    def test_repo_commit_preparation_and_gated_push(self):
        inspector = RepoInspector(default_repo_path=".")

        # Test commit preparation
        prep = inspector.prepare_commit(files=["README.md"], message="test: prepare commit", commit_now=False)
        self.assertEqual(prep.commit_message, "test: prepare commit")
        self.assertTrue(prep.push_gated)
        self.assertFalse(prep.push_permitted)

        # Test security gate: autonomous push MUST be blocked
        success, msg = inspector.push_to_remote(force_confirmed=False)
        self.assertFalse(success)
        self.assertIn("SECURITY GATE", msg)

    # ----------------------------------------------------------------------
    # 2. File Dependency Awareness
    # ----------------------------------------------------------------------
    def test_dependency_analyzer_ast(self):
        analyzer = DependencyAnalyzer(workspace_root=".")
        imports = analyzer.extract_imports("jarvis/capabilities/understand.py")

        self.assertIn("re", imports)
        self.assertTrue(any("schemas" in imp for imp in imports))

        # Test workspace scan
        graph = analyzer.analyze_workspace(target_dirs=["jarvis/subsystems/coding"], max_files=20)
        self.assertIsNotNone(graph)
        self.assertIsInstance(graph.imports_by_file, dict)

    # ----------------------------------------------------------------------
    # 3. Test Runner & Terminal Execution
    # ----------------------------------------------------------------------
    def test_test_runner_execution_and_parsing(self):
        runner = TestRunner(workspace_root=".")
        py_exe = runner.find_python_executable()
        self.assertTrue(os.path.exists(py_exe))

        # Run an existing small test suite
        res = runner.run_tests("tests.test_windows_control", timeout_sec=20)
        self.assertIsInstance(res, TestRunResult)
        self.assertTrue(res.passed)
        self.assertEqual(res.returncode, 0)
        self.assertEqual(len(res.failed_tests), 0)

    # ----------------------------------------------------------------------
    # 4. Error Diagnostics & Analysis
    # ----------------------------------------------------------------------
    def test_error_analyzer_traceback(self):
        analyzer = ErrorAnalyzer(workspace_root=".")
        sample_traceback = """
Traceback (most recent call last):
  File "D:\\JARVIS\\jarvis\\subsystems\\sample.py", line 42, in calculate_metric
    return value / 0
ZeroDivisionError: division by zero
        """
        analysis = analyzer.analyze_traceback(sample_traceback)
        self.assertEqual(analysis.error_type, ErrorCategory.RUNTIME_EXCEPTION)
        self.assertIn("ZeroDivisionError", analysis.error_message)
        self.assertEqual(analysis.failing_line, 42)
        self.assertEqual(analysis.failing_function, "calculate_metric")
        self.assertIn("sample.py", analysis.failing_file)

    def test_error_analyzer_assertion_failure(self):
        analyzer = ErrorAnalyzer(workspace_root=".")
        sample_traceback = """
Traceback (most recent call last):
  File "D:\\JARVIS\\tests\\test_sample.py", line 18, in test_value
    self.assertEqual(res, 42)
AssertionError: 40 != 42
        """
        analysis = analyzer.analyze_traceback(sample_traceback)
        self.assertEqual(analysis.error_type, ErrorCategory.ASSERTION_FAILURE)
        self.assertEqual(analysis.failing_line, 18)
        self.assertIn("40 != 42", analysis.error_message)

    # ----------------------------------------------------------------------
    # 5. Safe Code Modification & AST Validation
    # ----------------------------------------------------------------------
    def test_code_modifier_safe_patch_and_syntax_guard(self):
        test_file = os.path.join(self.test_dir, "module.py")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("def compute():\n    return 10\n")

        modifier = CodeModifier()

        # 1. Refuse syntax-invalid patch
        bad_patch = "def compute():\n    return 10 + \n"
        success, patch, err = modifier.apply_replacement(
            file_path=test_file,
            target_snippet="def compute():\n    return 10\n",
            replacement_snippet=bad_patch,
        )
        self.assertFalse(success)
        self.assertIn("SyntaxError", err)

        # 2. Apply valid patch
        good_patch = "def compute():\n    return 20\n"
        success, patch, err = modifier.apply_replacement(
            file_path=test_file,
            target_snippet="def compute():\n    return 10\n",
            replacement_snippet=good_patch,
        )
        self.assertTrue(success)
        with open(test_file, "r", encoding="utf-8") as f:
            self.assertIn("return 20", f.read())

        # 3. Rollback
        modifier.rollback(test_file)
        with open(test_file, "r", encoding="utf-8") as f:
            self.assertIn("return 10", f.read())

    # ----------------------------------------------------------------------
    # 6. Coding Tools & Remote Push Gate
    # ----------------------------------------------------------------------
    def test_tools_git_inspect_and_push_gate(self):
        registry = get_default_registry()
        inspect_tool = registry.get("git_inspect")
        push_tool = registry.get("git_push")
        coding_tool = registry.get("run_coding_agent")

        self.assertIsNotNone(inspect_tool)
        self.assertIsNotNone(push_tool)
        self.assertIsNotNone(coding_tool)

        # git_inspect
        res_insp = inspect_tool.execute(repo_path=".")
        self.assertTrue(res_insp.success)
        self.assertIn("branch", res_insp.output)

        # git_push gate: without confirmed=True, must fail with security warning
        res_push_blocked = push_tool.execute(confirmed=False)
        self.assertFalse(res_push_blocked.success)
        self.assertIn("SECURITY GATE", res_push_blocked.error)

    # ----------------------------------------------------------------------
    # 7. Coding Domain Skills
    # ----------------------------------------------------------------------
    def test_coding_domain_skills(self):
        skill_reg = get_default_skill_registry()
        skill_analyze = skill_reg.get("coding.analyze_code")
        skill_fix_bug = skill_reg.get("coding.fix_bug")
        skill_run_tests = skill_reg.get("coding.run_tests")
        skill_inspect = skill_reg.get("coding.inspect_repo")
        skill_commit = skill_reg.get("coding.prepare_commit")

        self.assertIsNotNone(skill_analyze)
        self.assertIsNotNone(skill_fix_bug)
        self.assertIsNotNone(skill_run_tests)
        self.assertIsNotNone(skill_inspect)
        self.assertIsNotNone(skill_commit)

        ctx = SkillContext()

        # Execute coding.inspect_repo
        res_insp = skill_inspect.execute({"repo_path": "."}, ctx)
        self.assertTrue(res_insp.success)
        self.assertIsNotNone(ctx.get("repo_inspection"))

        # Execute coding.prepare_commit
        res_com = skill_commit.execute({"files": ["README.md"], "message": "chore: test commit"}, ctx)
        self.assertTrue(res_com.success)
        self.assertIsNotNone(ctx.get("commit_prep"))

    # ----------------------------------------------------------------------
    # 8. Understand & Plan Capability Integration
    # ----------------------------------------------------------------------
    def test_understand_and_plan_coding_task(self):
        understand = DefaultUnderstandCapability()
        prompt = "Open my JARVIS project and fix the failing test."
        objective = understand.understand(prompt, context={})

        self.assertEqual(objective.intent, IntentCategory.TASK_AUTOMATION)
        self.assertEqual(objective.extracted_entities.get("action"), "fix_failing_test")
        self.assertEqual(objective.extracted_entities.get("project"), "JARVIS")
        self.assertGreaterEqual(len(objective.sub_goals), 8)

        planner = DefaultPlanCapability()
        state = AgentSessionState(task_id="task_code_1")
        plan = planner.plan(objective, state)

        self.assertIsNotNone(plan)
        self.assertEqual(len(plan.steps), 3)
        self.assertEqual(plan.steps[0].tool_name, "open_application")
        self.assertEqual(plan.steps[1].tool_name, "git_inspect")
        self.assertEqual(plan.steps[2].tool_name, "run_coding_agent")

    # ----------------------------------------------------------------------
    # 9. End-to-End 10-Stage Test Diagnosis and Repair Pipeline
    # ----------------------------------------------------------------------
    def test_end_to_end_test_diagnosis_and_repair(self):
        # Create a real mini project in self.test_dir
        src_dir = os.path.join(self.test_dir, "calc")
        tests_dir = os.path.join(self.test_dir, "tests")
        os.makedirs(src_dir, exist_ok=True)
        os.makedirs(tests_dir, exist_ok=True)

        calc_file = os.path.join(src_dir, "engine.py")
        test_file = os.path.join(tests_dir, "test_engine.py")

        # Code with intentional bug
        with open(calc_file, "w", encoding="utf-8") as f:
            f.write(
                "def calculate_total(a: int, b: int) -> int:\n"
                "    return a - b  # Bug: should be a + b\n"
            )

        # Test expecting correct calculation
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(
                "import unittest\n"
                "import sys, os\n"
                "sys.path.insert(0, os.path.abspath('.'))\n"
                "from calc.engine import calculate_total\n"
                "\n"
                "class TestEngine(unittest.TestCase):\n"
                "    def test_total(self):\n"
                "        self.assertEqual(calculate_total(10, 5), 15)\n"
                "\n"
                "if __name__ == '__main__':\n"
                "    unittest.main()\n"
            )

        # Run CodingAgent against this test
        agent = CodingAgent(workspace_root=self.test_dir)
        result = agent.fix_failing_test(
            test_path="tests.test_engine",
            target_file=calc_file,
            target_snippet="return a - b  # Bug: should be a + b",
            replacement_snippet="return a + b",
            open_editor=False,
            auto_commit=False,
        )

        self.assertTrue(result.success)
        self.assertFalse(result.initial_test.passed)
        self.assertTrue(result.final_test.passed)
        self.assertEqual(len(result.patches_applied), 1)
        self.assertIn("All tests now PASS", result.explanation)

        # Verify fixed file content on disk
        with open(calc_file, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("return a + b", content)
            self.assertNotIn("return a - b", content)


if __name__ == "__main__":
    unittest.main()
