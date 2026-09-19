"""Comprehensive Test Suite for Phase 11 — Workflow / Skill System.

Verifies:
1. BaseSkill lifecycle: Preconditions, Execution, Verification, Recovery.
2. SkillRegistry: Registration, namespaced lookup, domain filtering.
3. The 9 Domain Skills:
   - browser/
   - classroom/
   - vscode/
   - files/
   - pdf/
   - research/
   - coding/
   - system/
   - productivity/
4. Direct Python calling via Domain Proxies (e.g. classroom.find_material(), pdf.summarize()).
5. SkillComposer: Pipeline composition, parameter piping, execution report, and plan compilation.
6. Integration with DefaultUnderstandCapability and DefaultPlanCapability.
"""

from __future__ import annotations
import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock

from jarvis.skills import (
    BaseSkill,
    PreconditionResult,
    RecoveryAction,
    RecoveryStrategy,
    SkillContext,
    SkillParameter,
    SkillResult,
    VerificationResult,
    SkillRegistry,
    SkillComposer,
    get_default_skill_registry,
    browser,
    classroom,
    vscode,
    files,
    pdf,
    research,
    coding,
    system,
    productivity,
)
from jarvis.capabilities.understand import DefaultUnderstandCapability
from jarvis.capabilities.plan import DefaultPlanCapability
from jarvis.core.schemas import TaskObjective, IntentCategory


class TestSkillSystem(unittest.TestCase):
    """Test suite covering the complete Phase 11 Skill System."""

    @classmethod
    def setUpClass(cls):
        cls.sandbox_dir = os.path.abspath("data/test_skills_sandbox")
        os.makedirs(cls.sandbox_dir, exist_ok=True)
        cls.registry = get_default_skill_registry()
        cls.composer = SkillComposer(cls.registry)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.sandbox_dir):
            try:
                shutil.rmtree(cls.sandbox_dir)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # 1. BaseSkill Contract Tests
    # ------------------------------------------------------------------

    def test_base_skill_preconditions_validation(self):
        """Verify preconditions fail when required parameters are omitted."""
        class DummySkill(BaseSkill):
            name = "test.dummy"
            domain = "test"
            capability = "A dummy skill for testing"
            parameters = {
                "target": SkillParameter("target", "string", "Target name", required=True),
            }
            def execute(self, params, context):
                return SkillResult(success=True, output=f"Executed on {params['target']}")

        skill = DummySkill()
        ctx = SkillContext()

        # Missing required param
        res = skill.run({}, ctx)
        self.assertFalse(res.success)
        self.assertIn("Preconditions not met", res.error or "")
        self.assertEqual(res.recovery.strategy, RecoveryStrategy.RETRY)

        # Passing required param
        res_ok = skill.run({"target": "Laptop"}, ctx)
        self.assertTrue(res_ok.success)
        self.assertEqual(res_ok.output, "Executed on Laptop")

    # ------------------------------------------------------------------
    # 2. Skill Registry & Discovery Tests
    # ------------------------------------------------------------------

    def test_skill_registry_all_domains_present(self):
        """Verify all 9 core domains exist in the registry."""
        expected_domains = {
            "browser",
            "classroom",
            "vscode",
            "files",
            "pdf",
            "research",
            "coding",
            "system",
            "productivity",
        }
        all_skills = self.registry.list_skills()
        registered_domains = {s.domain for s in all_skills}
        for d in expected_domains:
            self.assertIn(d, registered_domains, f"Domain '{d}' missing from registry.")

    def test_skill_namespaced_lookup(self):
        """Verify specific skills can be retrieved by their exact names."""
        for sname in [
            "classroom.find_material",
            "classroom.download_material",
            "pdf.summarize",
            "vscode.open_file",
            "browser.navigate",
            "files.organize",
            "coding.analyze_code",
            "system.get_metrics",
            "productivity.set_reminder",
        ]:
            skill = self.registry.get(sname)
            self.assertIsNotNone(skill, f"Skill '{sname}' not found.")
            self.assertEqual(skill.name, sname)

    # ------------------------------------------------------------------
    # 3. Domain Skills Verification
    # ------------------------------------------------------------------

    def test_classroom_skills(self):
        """Verify classroom.find_material and download_material skills."""
        find_skill = self.registry.get("classroom.find_material")
        ctx = SkillContext()
        res_find = find_skill.run({"course": "DBMS", "material_type": "assignment"}, ctx)
        self.assertTrue(res_find.success)
        self.assertIn("DBMS", res_find.output)
        self.assertEqual(ctx.get("target_course"), "DBMS")

        # Download material
        dest_folder = os.path.join(self.sandbox_dir, "classroom_test")
        dl_skill = self.registry.get("classroom.download_material")
        res_dl = dl_skill.run({"course": "DBMS", "destination_folder": dest_folder}, ctx)
        self.assertTrue(res_dl.success)
        self.assertTrue(os.path.exists(res_dl.artifacts["file_path"]))

    def test_pdf_skills(self):
        """Verify pdf.read, pdf.summarize, and pdf.verify_integrity."""
        test_pdf = os.path.join(self.sandbox_dir, "test_doc.pdf")
        with open(test_pdf, "wb") as f:
            f.write(b"%PDF-1.4\n1 0 obj\n<< /Title (Test Document) >>\nendobj\n%%EOF\n")

        # Integrity
        integ_skill = self.registry.get("pdf.verify_integrity")
        res_integ = integ_skill.run({"file_path": test_pdf})
        self.assertTrue(res_integ.success)
        self.assertTrue(res_integ.artifacts["is_valid"])

        # Read
        read_skill = self.registry.get("pdf.read")
        res_read = read_skill.run({"file_path": test_pdf})
        self.assertTrue(res_read.success)

        # Summarize
        sum_skill = self.registry.get("pdf.summarize")
        res_sum = sum_skill.run({"file_path": test_pdf})
        self.assertTrue(res_sum.success)
        self.assertIn("Executive Summary", res_sum.output)

    def test_vscode_skills(self):
        """Verify vscode.open_file creates/verifies file and launches editor handle."""
        test_file = os.path.join(self.sandbox_dir, "sample.py")
        open_skill = self.registry.get("vscode.open_file")
        res = open_skill.run({"file_path": test_file, "line_number": 1})
        self.assertTrue(res.success)
        self.assertTrue(os.path.exists(test_file))

    def test_files_skills(self):
        """Verify files.organize, files.search, and files.safe_delete."""
        org_dir = os.path.join(self.sandbox_dir, "org_test")
        os.makedirs(org_dir, exist_ok=True)
        with open(os.path.join(org_dir, "doc1.txt"), "w") as f: f.write("hello")
        with open(os.path.join(org_dir, "script.py"), "w") as f: f.write("print(1)")

        org_skill = self.registry.get("files.organize")
        res_org = org_skill.run({"directory": org_dir})
        self.assertTrue(res_org.success)
        self.assertTrue(os.path.exists(os.path.join(org_dir, "Documents", "doc1.txt")))
        self.assertTrue(os.path.exists(os.path.join(org_dir, "Code", "script.py")))

        # Search
        search_skill = self.registry.get("files.search")
        res_search = search_skill.run({"query": "script.py", "directory": org_dir})
        self.assertTrue(res_search.success)
        self.assertGreaterEqual(len(res_search.artifacts["matches"]), 1)

    def test_system_skills(self):
        """Verify system.get_metrics returns live hardware data."""
        metrics_skill = self.registry.get("system.get_metrics")
        res = metrics_skill.run()
        self.assertTrue(res.success)
        self.assertIn("cpu_percent", res.output)
        self.assertIn("ram_percent", res.output)

    def test_coding_skills(self):
        """Verify coding.analyze_code detects syntax status."""
        test_code = os.path.join(self.sandbox_dir, "clean_code.py")
        with open(test_code, "w") as f:
            f.write("def add(a, b):\n    return a + b\n")

        analyze_skill = self.registry.get("coding.analyze_code")
        res = analyze_skill.run({"file_path": test_code})
        self.assertTrue(res.success)
        self.assertEqual(res.artifacts["clean"], True)

    def test_productivity_skills(self):
        """Verify productivity.set_reminder and track_task."""
        rem_skill = self.registry.get("productivity.set_reminder")
        res_rem = rem_skill.run({"message": "Stand up and stretch", "delay_seconds": 30})
        self.assertTrue(res_rem.success)

        task_skill = self.registry.get("productivity.track_task")
        res_task = task_skill.run({"title": "Review Skill System Architecture"})
        self.assertTrue(res_task.success)

    # ------------------------------------------------------------------
    # 4. Direct Python Calling via Domain Proxies
    # ------------------------------------------------------------------

    def test_direct_domain_proxy_calls(self):
        """Verify calling skills like classroom.find_material(), pdf.summarize(), vscode.open_file()."""
        # 1. classroom.find_material()
        res_find = classroom.find_material(course="AI", material_type="lecture")
        self.assertTrue(res_find.success)
        self.assertIn("AI", res_find.output)

        # 2. pdf.summarize()
        pdf_file = os.path.join(self.sandbox_dir, "proxy_test.pdf")
        with open(pdf_file, "wb") as f:
            f.write(b"%PDF-1.4 Mock PDF Content %%EOF")
        res_pdf = pdf.summarize(file_path=pdf_file)
        self.assertTrue(res_pdf.success)

        # 3. vscode.open_file()
        py_file = os.path.join(self.sandbox_dir, "proxy_code.py")
        res_code = vscode.open_file(file_path=py_file)
        self.assertTrue(res_code.success)

    # ------------------------------------------------------------------
    # 5. SkillComposer: Pipeline Composition & Parameter Piping
    # ------------------------------------------------------------------

    def test_skill_composition_pipeline_and_parameter_piping(self):
        """Compose: classroom.find_material -> classroom.download_material -> pdf.summarize -> vscode.open_file."""
        dest_dir = os.path.join(self.sandbox_dir, "composed_test")
        chain = [
            ("classroom.find_material", {"course": "DBMS"}),
            ("classroom.download_material", {"course": "DBMS", "destination_folder": dest_dir}),
            ("pdf.summarize", {}),       # file_path automatically piped from download_material!
            ("vscode.open_file", {}),     # file_path automatically piped from download_material!
        ]

        report = self.composer.execute_chain(chain)
        self.assertTrue(report.success, f"Composition failed: {report.final_output}")
        self.assertEqual(report.total_steps, 4)
        self.assertEqual(report.completed_steps, 4)

        # Verify step 3 (pdf.summarize) received the downloaded file path
        step3_res = report.step_results[2]
        self.assertEqual(step3_res["skill"], "pdf.summarize")
        self.assertIn("DBMS_Assignment_1.pdf", step3_res["params"].get("file_path", ""))

        # Verify step 4 (vscode.open_file) received the file path
        step4_res = report.step_results[3]
        self.assertEqual(step4_res["skill"], "vscode.open_file")
        self.assertIn("DBMS_Assignment_1.pdf", step4_res["params"].get("file_path", ""))

    def test_skill_composer_compilation_to_plan(self):
        """Verify compiling composed skills into PlanSteps for the agent loop."""
        chain = [
            ("classroom.find_material", {"course": "OS"}),
            ("classroom.download_material", {"course": "OS"}),
            ("pdf.summarize", {}),
            ("vscode.open_file", {}),
        ]
        objective = TaskObjective(
            raw_input="Get OS assignment and open in VS Code",
            intent=IntentCategory.TASK_AUTOMATION,
            description="Compound classroom workflow",
            target_criteria="Assignment retrieved and open in editor",
        )

        plan = self.composer.compile_to_plan(objective, chain)
        self.assertEqual(len(plan.steps), 4)
        self.assertIn("CLASSROOM", plan.steps[0].description)
        self.assertIn("PDF", plan.steps[2].description)
        self.assertIn("VSCODE", plan.steps[3].description)
        # Check dependency chaining
        self.assertEqual(plan.steps[1].depends_on, [plan.steps[0].step_id])
        self.assertEqual(plan.steps[2].depends_on, [plan.steps[1].step_id])

    # ------------------------------------------------------------------
    # 6. Understand & Plan Integration
    # ------------------------------------------------------------------

    def test_understand_direct_skill_syntax(self):
        """Verify DefaultUnderstandCapability parses 'classroom.find_material(course=DBMS)'."""
        understand_cap = DefaultUnderstandCapability()
        obj = understand_cap.understand("classroom.find_material(course=DBMS)", context={})

        self.assertEqual(obj.intent, IntentCategory.TASK_AUTOMATION)
        self.assertEqual(obj.extracted_entities.get("action"), "classroom.find_material")
        self.assertEqual(obj.extracted_entities.get("params", {}).get("course"), "DBMS")

        # Plan compilation
        plan_cap = DefaultPlanCapability()
        plan = plan_cap.plan(obj, MagicMock())
        self.assertEqual(len(plan.steps), 1)
        self.assertIn("CLASSROOM", plan.steps[0].description)


if __name__ == "__main__":
    unittest.main()
