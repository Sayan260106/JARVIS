"""Unit Tests for Phase 4: The Planner (Multi-Step Goal Decomposition & Execution).

Tests:
1. InspectDirectoryTool: File categorization and extension breakdown.
2. DetectDuplicatesTool: SHA-256 duplicate content identification.
3. BatchOrganizeFilesTool: Organization with duplicates left untouched.
4. GoalPlanner Full Plan Execution:
   - Objective: 'Organize Downloads'
   - Subtasks 1-8 execution and telemetry propagation.
   - Verification of final synthesized summary report.
"""

import os
import shutil
import unittest

from jarvis.tools.file_organization_tools import (
    InspectDirectoryTool,
    DetectDuplicatesTool,
    BatchOrganizeFilesTool,
)
from jarvis.capabilities.goal_planner import GoalPlanner


class TestGoalPlanner(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.sandbox_dir = os.path.abspath("data/test_planner_sandbox")
        os.makedirs(cls.sandbox_dir, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.sandbox_dir):
            try:
                shutil.rmtree(cls.sandbox_dir)
            except Exception:
                pass

    def setUp(self):
        # Reset sandbox directory for each test
        if os.path.exists(self.sandbox_dir):
            shutil.rmtree(self.sandbox_dir)
        os.makedirs(self.sandbox_dir, exist_ok=True)

    def test_inspect_directory_tool(self):
        """Verify inspection categorizes files correctly."""
        # Create test files
        with open(os.path.join(self.sandbox_dir, "report.pdf"), "w") as f:
            f.write("PDF Document Content")
        with open(os.path.join(self.sandbox_dir, "photo.png"), "w") as f:
            f.write("PNG Image Content")
        with open(os.path.join(self.sandbox_dir, "script.py"), "w") as f:
            f.write("print('Hello Python')")

        tool = InspectDirectoryTool()
        res = tool.execute(directory=self.sandbox_dir)

        self.assertTrue(res.success)
        self.assertEqual(res.output["total_files"], 3)
        self.assertIn("Documents", res.output["categories"])
        self.assertIn("Images", res.output["categories"])
        self.assertIn("Code", res.output["categories"])

        ver = tool.verify({"directory": self.sandbox_dir}, res)
        self.assertTrue(ver.verified)

    def test_detect_duplicates_tool(self):
        """Verify SHA-256 detection identifies exact file duplicates."""
        dup_content = "Identical binary duplicate payload"
        # 1 original + 2 duplicates
        with open(os.path.join(self.sandbox_dir, "file_original.pdf"), "w") as f:
            f.write(dup_content)
        with open(os.path.join(self.sandbox_dir, "file_copy1.pdf"), "w") as f:
            f.write(dup_content)
        with open(os.path.join(self.sandbox_dir, "file_copy2.pdf"), "w") as f:
            f.write(dup_content)
        # 1 unique file
        with open(os.path.join(self.sandbox_dir, "file_unique.pdf"), "w") as f:
            f.write("Completely different unique text")

        tool = DetectDuplicatesTool()
        res = tool.execute(directory=self.sandbox_dir)

        self.assertTrue(res.success)
        self.assertEqual(res.output["total_duplicate_clusters"], 1)
        self.assertEqual(res.output["total_duplicates_found"], 2)

        ver = tool.verify({"directory": self.sandbox_dir}, res)
        self.assertTrue(ver.verified)

    def test_batch_organize_preserves_duplicates_untouched(self):
        """Verify organize moves unique files into categories and leaves duplicates untouched."""
        dup_content = "Duplicate test data"
        # Duplicates
        with open(os.path.join(self.sandbox_dir, "dup_a.pdf"), "w") as f:
            f.write(dup_content)
        with open(os.path.join(self.sandbox_dir, "dup_b.pdf"), "w") as f:
            f.write(dup_content)

        # Unique files
        with open(os.path.join(self.sandbox_dir, "unique_doc.txt"), "w") as f:
            f.write("Unique Doc")
        with open(os.path.join(self.sandbox_dir, "unique_img.jpg"), "w") as f:
            f.write("Unique Image")

        tool = BatchOrganizeFilesTool()
        res = tool.execute(directory=self.sandbox_dir, exclude_duplicates=True)

        self.assertTrue(res.success)
        self.assertEqual(res.output["moved_files_count"], 2)
        self.assertGreaterEqual(res.output["skipped_duplicates_count"], 2)

        # Verify duplicate files are still in root untouched
        self.assertTrue(os.path.exists(os.path.join(self.sandbox_dir, "dup_a.pdf")))
        self.assertTrue(os.path.exists(os.path.join(self.sandbox_dir, "dup_b.pdf")))

        # Verify unique files are in categorized subfolders
        self.assertTrue(os.path.exists(os.path.join(self.sandbox_dir, "Documents", "unique_doc.txt")))
        self.assertTrue(os.path.exists(os.path.join(self.sandbox_dir, "Images", "unique_img.jpg")))

    def test_goal_planner_full_plan_execution(self):
        """Verify: 'Jarvis, organize my Downloads folder' generates and executes the 8-step plan."""
        # Create realistic sandbox folder with 6 files across 3 categories + 1 duplicate pair
        dup_bytes = "Shared payload for duplicate test"
        with open(os.path.join(self.sandbox_dir, "lecture1.pdf"), "w") as f:
            f.write("Lecture 1 notes")
        with open(os.path.join(self.sandbox_dir, "diagram.png"), "w") as f:
            f.write("Architecture Diagram")
        with open(os.path.join(self.sandbox_dir, "solution.py"), "w") as f:
            f.write("def solve(): pass")
        with open(os.path.join(self.sandbox_dir, "archive.zip"), "w") as f:
            f.write("ZIP ARCHIVE DATA")
        with open(os.path.join(self.sandbox_dir, "dup1.pdf"), "w") as f:
            f.write(dup_bytes)
        with open(os.path.join(self.sandbox_dir, "dup2.pdf"), "w") as f:
            f.write(dup_bytes)
        with open(os.path.join(self.sandbox_dir, "dup3.pdf"), "w") as f:
            f.write(dup_bytes)
        with open(os.path.join(self.sandbox_dir, "dup4.pdf"), "w") as f:
            f.write(dup_bytes)

        planner = GoalPlanner()
        plan = planner.create_organization_plan("Organize Downloads", self.sandbox_dir)

        self.assertEqual(len(plan.subtasks), 8)
        self.assertEqual(plan.subtasks[0].name, f"Inspect {os.path.basename(self.sandbox_dir)}")
        self.assertEqual(plan.subtasks[3].name, "Detect duplicates")
        self.assertEqual(plan.subtasks[5].name, "Move files")

        # Execute Plan
        executed = planner.execute_plan(plan)

        # Assert subtask results
        self.assertEqual(executed.subtasks[0].status, "SUCCESS")
        self.assertEqual(executed.subtasks[3].status, "SUCCESS")
        self.assertIn("duplicates detected", executed.subtasks[3].status_message)
        self.assertEqual(executed.subtasks[5].status, "SUCCESS")

        # Assert final synthesized summary format
        self.assertIn("Done. I organized", executed.final_summary)
        self.assertIn("duplicates", executed.final_summary)
        self.assertIn("I left the duplicates untouched", executed.final_summary)


if __name__ == "__main__":
    unittest.main()
