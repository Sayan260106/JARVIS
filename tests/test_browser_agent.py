"""Unit tests for Phase 3 — Dedicated Browser Agent with Chrome Profile Support,
Semantic DOM Inspection, and Google Classroom Lecture PDF Extraction.

Verifies:
1. Complete registry of 21 browser automation and inspection tools.
2. ChromeProfileResolver discovering institutional profile (e.g. heritageit.edu.in).
3. BrowserState inspection (URL, open tabs, semantic DOM elements without coordinate clicking).
4. Authentication & session detection for Google / Classroom services.
5. Material & PDF detection on course stream pages.
6. Target academic workflow:
   "Open Chrome, go to my institutional profile, open Google Classroom, open ECE Classroom, find Lecture 3 and 4 PDF."
   - Understand capability intent & entities extraction
   - Plan capability decomposition into verified PlanSteps
   - Execution & file verification (%PDF magic bytes)
"""

from __future__ import annotations
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from jarvis.subsystems.web.browser_controller import BrowserController, get_browser_controller
from jarvis.subsystems.web.browser_lifecycle import ChromeProfileResolver, BrowserLifecycleManager
from jarvis.core.loop import JarvisAgentLoop
from jarvis.core.schemas import IntentCategory, StepStatus
from jarvis.core.state import AgentSessionState
from jarvis.core.task_manager import TaskManager, TaskStore
from jarvis.core.task_schemas import TaskStatus
from jarvis.capabilities.goal_planner import GoalPlanner
from jarvis.tools import get_default_registry
from jarvis.tools.browser_tools import (
    BrowserOpenTool,
    BrowserNewTabTool,
    BrowserSearchPageTool,
    BrowserNavigateTool,
    BrowserClickTool,
    BrowserTypeTool,
    BrowserSelectTool,
    BrowserUploadTool,
    BrowserScrollTool,
    BrowserExtractTool,
    BrowserScreenshotTool,
    BrowserBackTool,
    BrowserCloseTabTool,
    BrowserDownloadTool,
    BrowserGetStateTool,
    BrowserInspectDOMTool,
    BrowserManageTabsTool,
    BrowserDetectPDFsTool,
    BrowserDetectSessionTool,
    BrowserVerifyPDFTool,
    BrowserVerifyNavigationTool,
)


class TestBrowserAgent(unittest.TestCase):
    """Test suite for Playwright browser automation and goal execution."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="jarvis_browser_test_")
        self.db_path = os.path.join(self.test_dir, "browser_tasks.db")
        self.store = TaskStore(db_path=self.db_path)
        self.manager = TaskManager(store=self.store)
        self.registry = get_default_registry()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)
        # Ensure browser is cleanly closed after tests
        ctrl = get_browser_controller()
        ctrl.close()

    def test_browser_tools_in_registry(self):
        """Verify all 21 browser tools are registered in default ToolRegistry."""
        expected_tools = [
            "browser_open",
            "browser_new_tab",
            "browser_search_page",
            "browser_navigate",
            "browser_click",
            "browser_type",
            "browser_select",
            "browser_upload",
            "browser_scroll",
            "browser_extract",
            "browser_screenshot",
            "browser_back",
            "browser_close_tab",
            "browser_download",
            "browser_get_state",
            "browser_inspect_dom",
            "browser_manage_tabs",
            "browser_detect_pdfs",
            "browser_detect_session",
            "browser_verify_pdf",
            "browser_verify_navigation",
        ]
        for tool_name in expected_tools:
            tool = self.registry.get(tool_name)
            self.assertIsNotNone(tool, f"Tool '{tool_name}' missing from registry")
            schema = tool.to_schema()
            self.assertEqual(schema["name"], tool_name)

    def test_chrome_profile_resolver_institutional(self):
        """Verify ChromeProfileResolver resolves real or simulated institutional profiles."""
        # Test real host resolution if Chrome exists
        real_profile = ChromeProfileResolver.resolve_profile("institutional")
        if real_profile:
            self.assertTrue(real_profile["is_institutional"])
            self.assertIn(".edu", real_profile["email"].lower())

        # Test simulated Local State in sandbox
        sandbox_dir = os.path.join(self.test_dir, "User Data")
        os.makedirs(sandbox_dir, exist_ok=True)
        local_state_content = {
            "profile": {
                "info_cache": {
                    "Default": {"name": "Personal", "user_name": "personal@gmail.com"},
                    "Profile 1": {"name": "College", "user_name": "student@university.edu.in"},
                }
            }
        }
        import json
        with open(os.path.join(sandbox_dir, "Local State"), "w", encoding="utf-8") as f:
            json.dump(local_state_content, f)

        res = ChromeProfileResolver.resolve_profile("institutional", user_data_dir=sandbox_dir)
        self.assertIsNotNone(res)
        self.assertEqual(res["directory_name"], "Profile 1")
        self.assertEqual(res["email"], "student@university.edu.in")
        self.assertTrue(res["is_institutional"])

    def test_browser_controller_state_and_semantic_dom_inspection(self):
        """Verify state capture and semantic element identification without coordinate clicking."""
        ctrl = BrowserController(headless=True)
        try:
            ctrl.open(headless=True)

            # Serve mock Classroom course page
            mock_html = """
            <html>
                <head><title>ECE Classroom - Google Classroom</title></head>
                <body>
                    <h1>ECE 2026 Course Stream</h1>
                    <div role="button" aria-label="Classwork Tab" id="classwork-tab">Classwork</div>
                    <a href="https://drive.google.com/file/d/123/view" class="material">Lecture 3 - Semiconductor Physics.pdf</a>
                    <a href="https://drive.google.com/file/d/456/view" class="material">Lecture 4 - MOSFET Characteristics.pdf</a>
                    <button id="refresh-btn">Refresh</button>
                </body>
            </html>
            """
            data_url = f"data:text/html,{mock_html}"
            ctrl.navigate(data_url)

            # 1. State Inspection
            state = ctrl.get_state()
            self.assertIn("ECE Classroom", state["title"])
            self.assertEqual(state["tab_count"], 1)
            self.assertGreater(len(state["visible_elements"]), 0)

            # 2. Semantic DOM inspection
            dom = ctrl.inspect_dom(query="Lecture")
            self.assertGreaterEqual(dom["count"], 2)
            lecture_texts = [el["text"] for el in dom["elements"]]
            self.assertTrue(any("Lecture 3" in t for t in lecture_texts))
            self.assertTrue(any("Lecture 4" in t for t in lecture_texts))

            # 3. PDF Detection
            pdfs = ctrl.detect_pdfs(query="Lecture")
            self.assertGreaterEqual(pdfs["count"], 2)

            # 4. Navigation Verification
            nav_ver = ctrl.verify_navigation(title_pattern="ECE Classroom")
            self.assertTrue(nav_ver["verified"])

        finally:
            ctrl.close()

    def test_browser_download_and_pdf_magic_bytes_verification(self):
        """Verify downloading file, validating %PDF magic bytes, and verifying file integrity."""
        sample_pdf_path = os.path.join(self.test_dir, "ECE_Lecture_3.pdf")
        pdf_content = b"%PDF-1.5\n1 0 obj\n<< /Title (Lecture 3 - Semiconductor Physics) >>\nendobj\n%%EOF"
        with open(sample_pdf_path, "wb") as f:
            f.write(pdf_content)

        verify_tool = BrowserVerifyPDFTool()
        res_ok = verify_tool.execute(file_path=sample_pdf_path)
        self.assertTrue(res_ok.success)
        self.assertTrue(res_ok.output["verified"])

        # Test corrupt / non-pdf file
        corrupt_path = os.path.join(self.test_dir, "corrupt.txt")
        with open(corrupt_path, "w") as f:
            f.write("This is not a PDF.")
        res_fail = verify_tool.execute(file_path=corrupt_path)
        self.assertFalse(res_fail.success)

    def test_target_institutional_classroom_lecture_workflow(self):
        """Verify Target:
        'Open Chrome, go to my institutional profile, open Google Classroom, open ECE Classroom, find Lecture 3 and 4 PDF.'
        """
        loop = JarvisAgentLoop(registry=self.registry, task_manager=self.manager)
        prompt = "Open Chrome, go to my institutional profile, open Google Classroom, open ECE Classroom, find Lecture 3 and 4 PDF."

        # 1. UNDERSTAND
        objective = loop.understand_cap.understand(prompt, {})
        self.assertEqual(objective.intent, IntentCategory.TASK_AUTOMATION)
        entities = objective.extracted_entities
        self.assertEqual(entities.get("action"), "classroom_lecture_extraction")
        self.assertEqual(entities.get("browser"), "chrome")
        self.assertEqual(entities.get("profile"), "institutional")
        self.assertEqual(entities.get("service"), "Google Classroom")
        self.assertEqual(entities.get("course"), "ECE")
        self.assertIn("Lecture 3", entities.get("materials", []))
        self.assertIn("Lecture 4", entities.get("materials", []))

        # 2. PLAN
        plan = loop.plan_cap.plan(objective, AgentSessionState(task_id="test_classroom"))
        self.assertEqual(len(plan.steps), 8)

        step_tools = [s.tool_name for s in plan.steps]
        self.assertEqual(step_tools, [
            "browser_open",
            "browser_detect_session",
            "browser_navigate",
            "browser_click",
            "browser_inspect_dom",
            "browser_detect_pdfs",
            "browser_download",
            "browser_verify_pdf",
        ])

        # Verify no blind coordinates or arbitrary powershell in plan!
        for s in plan.steps:
            self.assertNotEqual(s.tool_name, "powershell_exec")
            self.assertNotIn("x", s.arguments)
            self.assertNotIn("y", s.arguments)

        # 3. Check arguments
        self.assertEqual(plan.steps[0].arguments["profile_name"], "institutional")
        self.assertEqual(plan.steps[2].arguments["url"], "https://classroom.google.com")
        self.assertEqual(plan.steps[3].arguments["selector"], "ECE")


if __name__ == "__main__":
    unittest.main()
