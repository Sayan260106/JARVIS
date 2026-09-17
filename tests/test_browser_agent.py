"""Unit tests for Phase 8 — Browser Agent (Playwright Microsoft Edge).

Verifies:
1. BrowserController atomic operations (open, new_tab, navigate, extract, screenshot, close).
2. All 12 browser tools registration and schema generation.
3. Multi-step browser planning and execution:
   "Find the official GATE notification and save the PDF."
   SEARCH -> identify official source -> open -> find PDF -> download -> verify file -> store
4. Ground-truth file verification (%PDF magic bytes) and persistent TaskManager state.
"""

from __future__ import annotations
import os
import shutil
import tempfile
import unittest

from jarvis.subsystems.web.browser_controller import BrowserController, get_browser_controller
from jarvis.capabilities.goal_planner import GoalPlanner
from jarvis.core.task_manager import TaskManager, TaskStore
from jarvis.core.task_schemas import TaskStatus
from jarvis.tools import get_default_registry
from jarvis.tools.browser_tools import (
    BrowserOpenTool,
    BrowserNewTabTool,
    BrowserSearchPageTool,
    BrowserNavigateTool,
    BrowserClickTool,
    BrowserTypeTool,
    BrowserScrollTool,
    BrowserExtractTool,
    BrowserScreenshotTool,
    BrowserBackTool,
    BrowserCloseTabTool,
    BrowserDownloadTool,
)


class TestBrowserAgent(unittest.TestCase):
    """Test suite for Playwright browser automation and goal execution."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="jarvis_browser_test_")
        self.db_path = os.path.join(self.test_dir, "browser_tasks.db")
        self.store = TaskStore(db_path=self.db_path)
        self.manager = TaskManager(store=self.store)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)
        # Ensure browser is cleanly closed after tests
        ctrl = get_browser_controller()
        ctrl.close()

    def test_browser_tools_in_registry(self):
        """Verify all 12 browser tools are registered in default ToolRegistry."""
        registry = get_default_registry()
        expected_tools = [
            "browser_open",
            "browser_new_tab",
            "browser_search_page",
            "browser_navigate",
            "browser_click",
            "browser_type",
            "browser_scroll",
            "browser_extract",
            "browser_screenshot",
            "browser_back",
            "browser_close_tab",
            "browser_download",
        ]
        for tool_name in expected_tools:
            tool = registry.get(tool_name)
            self.assertIsNotNone(tool, f"Tool '{tool_name}' missing from registry")
            schema = tool.to_schema()
            self.assertEqual(schema["name"], tool_name)

    def test_browser_controller_html_extraction_and_screenshot(self):
        """Verify navigation, DOM extraction, and screenshot generation."""
        ctrl = BrowserController(headless=True)
        try:
            # Open browser
            open_res = ctrl.open(headless=True)
            self.assertEqual(open_res["status"], "opened")

            # Navigate to data URI containing test HTML
            test_html = "<html><body><h1>Official GATE Portal</h1><a id='notif' href='https://example.com/gate.pdf'>Download Notification PDF</a></body></html>"
            data_url = f"data:text/html,{test_html}"
            nav_res = ctrl.navigate(data_url)
            self.assertEqual(nav_res["status_code"], 200)

            # Extract heading text
            extracted = ctrl.extract(selector="h1", attribute="text")
            self.assertIn("Official GATE Portal", extracted["content"])

            # Extract links
            links = ctrl.extract(selector="a", attribute="links")
            self.assertEqual(links["count"], 1)
            self.assertEqual(links["links"][0]["href"], "https://example.com/gate.pdf")

            # Take screenshot
            ss_path = os.path.join(self.test_dir, "portal_screenshot.png")
            ss_res = ctrl.screenshot(path=ss_path)
            self.assertTrue(os.path.exists(ss_path))
            self.assertGreater(ss_res["size_bytes"], 0)

            # Close tab
            close_res = ctrl.close_tab()
            self.assertIn("closed", close_res["status"])
        finally:
            ctrl.close()

    def test_browser_download_and_pdf_verification(self):
        """Verify downloading file, validating %PDF magic bytes, and verifying file integrity."""
        # Create a mock PDF file in local test dir to serve/download
        sample_pdf_path = os.path.join(self.test_dir, "source_gate.pdf")
        pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Title (Official GATE 2027 Notification) >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
        with open(sample_pdf_path, "wb") as f:
            f.write(pdf_content)

        # Download using file:// URL
        save_dest = os.path.join(self.test_dir, "GATE 2027", "GATE_Notification.pdf")
        download_tool = BrowserDownloadTool()
        file_url = f"file:///{os.path.abspath(sample_pdf_path).replace(os.sep, '/')}"

        res = download_tool.execute(url=file_url, save_path=save_dest)
        self.assertTrue(res.success)
        self.assertTrue(res.output["is_pdf"])
        self.assertTrue(os.path.exists(save_dest))

        # Verify ground truth
        ver = download_tool.verify({"url": file_url, "save_path": save_dest}, res)
        self.assertTrue(ver.verified)

        with open(save_dest, "rb") as f:
            downloaded_bytes = f.read()
        self.assertTrue(downloaded_bytes.startswith(b"%PDF"))

    def test_multi_step_gate_notification_download_workflow(self):
        """Verify: 'Find the official GATE notification and save the PDF.'
        Executes:
        SEARCH -> identify official source -> open -> find PDF -> download -> verify file -> store
        """
        target_folder = os.path.join(self.test_dir, "GATE 2027")
        os.makedirs(target_folder, exist_ok=True)

        # Pre-seed verified notification PDF to simulate web download target
        mock_source_pdf = os.path.join(self.test_dir, "online_notification.pdf")
        with open(mock_source_pdf, "wb") as f:
            f.write(b"%PDF-1.7\n%Official GATE Information Brochure\n%%EOF")

        planner = GoalPlanner(task_manager=self.manager)

        # Detect intent
        user_prompt = "Find the official GATE notification and save the PDF."
        self.assertTrue(GoalPlanner.is_browser_find_and_download_goal(user_prompt))

        # Build 7-step plan
        plan = planner.create_browser_pdf_plan(
            objective="Find the official GATE notification and save the PDF",
            query="official GATE notification",
            target_dir=target_folder,
            filename="GATE_Notification.pdf",
        )

        self.assertEqual(len(plan.subtasks), 7)
        self.assertEqual(plan.subtasks[0].name, "SEARCH")
        self.assertEqual(plan.subtasks[1].name, "Identify official source")
        self.assertEqual(plan.subtasks[2].name, "Open official website")
        self.assertEqual(plan.subtasks[3].name, "Find PDF link")
        self.assertEqual(plan.subtasks[4].name, "Download document")
        self.assertEqual(plan.subtasks[5].name, "Verify file integrity")
        self.assertEqual(plan.subtasks[6].name, "Store and organize")

        # Point download URL to mock source
        file_url = f"file:///{os.path.abspath(mock_source_pdf).replace(os.sep, '/')}"
        plan.subtasks[4].arguments["url"] = file_url

        # Execute Plan
        executed = planner.execute_plan(plan)

        # Assert all 7 subtasks passed
        for st in executed.subtasks:
            self.assertEqual(st.status, "SUCCESS", f"Subtask '{st.name}' failed: {st.status_message}")

        # Assert final synthesized report
        self.assertIn("Done. Found the official GATE notification", executed.final_summary)
        self.assertIn("downloaded the verified PDF", executed.final_summary)
        self.assertIn("GATE 2027", executed.final_summary)

        # Assert downloaded file exists and is valid PDF
        final_pdf = os.path.join(target_folder, "GATE_Notification.pdf")
        self.assertTrue(os.path.exists(final_pdf))
        with open(final_pdf, "rb") as f:
            self.assertTrue(f.read().startswith(b"%PDF"))

        # Assert TaskManager record
        task_record = self.manager.get_task(plan.task_id)
        self.assertIsNotNone(task_record)
        self.assertEqual(task_record.status, TaskStatus.COMPLETED)
        self.assertEqual(task_record.current_step, 7)
        self.assertEqual(len(task_record.completed_steps), 7)


if __name__ == "__main__":
    unittest.main()
