"""Unit tests for Phase 6: Memory 2.0.

Verifies:
1. Short-term Session Memory (recording activities and answering 'What were we doing?').
2. Long-term Semantic Memory (explicit user preferences: Chrome, VS Code, directories, search).
3. Task / Workflow Memory (reusable workflows like 'Open ECE Classroom', matching, and telemetry).
4. UnifiedMemoryManager integration and context synthesis.
5. Typed Memory 2.0 tools (session_recall, manage_preference, manage_workflow).
6. Capability integration (Understand & Plan).
"""

from __future__ import annotations
import os
import shutil
import tempfile
import unittest

from jarvis.capabilities.plan import DefaultPlanCapability
from jarvis.capabilities.understand import DefaultUnderstandCapability
from jarvis.core.schemas import IntentCategory
from jarvis.core.state import AgentSessionState
from jarvis.subsystems.memory.semantic_memory import SemanticMemory
from jarvis.subsystems.memory.session_memory import SessionMemory
from jarvis.subsystems.memory.unified_memory import UnifiedMemoryManager
from jarvis.subsystems.memory.workflow_memory import WorkflowMemory
from jarvis.tools import get_default_registry


class TestMemory2(unittest.TestCase):
    """Test suite for Memory 2.0 three-tier memory architecture."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="jarvis_memory2_test_")
        self.db_path = os.path.join(self.test_dir, "test_memory.db")
        self.memory = UnifiedMemoryManager(db_path=self.db_path)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # --- 1. Short-Term Session Memory ---

    def test_session_memory_what_were_we_doing(self):
        """Verify session memory records activities and answers 'What were we doing?'."""
        session = SessionMemory(db_path=self.db_path)

        # Before any activities
        empty_answer = session.what_were_we_doing()
        self.assertIn("haven't started any tasks yet", empty_answer)

        # Record activities
        session.record_activity(
            goal="Organize Downloads",
            step_name="Inspect Directory",
            action="Scanned 12 files",
            status="SUCCESS",
        )
        session.record_activity(
            goal="Organize Downloads",
            step_name="Detect Duplicates",
            action="Found 2 duplicates",
            status="SUCCESS",
        )
        session.record_activity(
            goal="Organize Downloads",
            step_name="Move Lecture 3.pdf",
            action="Moved to Documents/ECE",
            status="SUCCESS",
        )

        answer = session.what_were_we_doing()
        self.assertIn("Organize Downloads", answer)
        self.assertIn("Move Lecture 3.pdf", answer)
        self.assertIn("SUCCESS", answer)

        activities = session.get_recent_activities(limit=5)
        self.assertEqual(len(activities), 3)

    # --- 2. Long-Term Semantic Memory ---

    def test_semantic_memory_preferences(self):
        """Verify long-term semantic memory for explicit preferences (Chrome, VS Code, dirs)."""
        semantic = SemanticMemory(db_path=self.db_path)

        # Verify pre-seeded defaults
        self.assertEqual(semantic.get_preference("preferred_browser"), "Chrome")
        self.assertEqual(semantic.get_preference("preferred_editor"), "VS Code")
        self.assertEqual(semantic.get_preference("default_project_dir"), "d:/JARVIS")

        # Explicitly set and retrieve a preference
        pref = semantic.remember_preference(
            key="theme_mode",
            value="Dark",
            category="ui",
            context="User requested dark theme aesthetic",
            is_explicit=True,
        )
        self.assertTrue(pref.is_explicit)
        self.assertEqual(semantic.get_preference("theme_mode"), "Dark")

        # Update an existing preference
        semantic.remember_preference(
            key="preferred_editor",
            value="VS Code Insiders",
            category="editor",
        )
        self.assertEqual(semantic.get_preference("preferred_editor"), "VS Code Insiders")

        # Search preferences
        matches = semantic.search_preferences("editor")
        self.assertTrue(len(matches) > 0)
        self.assertEqual(matches[0].key, "preferred_editor")

        # Context injection
        injection = semantic.get_prompt_injection()
        self.assertIn("Preferred Browser: Chrome", injection)
        self.assertIn("Preferred Editor: VS Code Insiders", injection)

    # --- 3. Task / Workflow Memory ---

    def test_workflow_memory_reusable_workflows(self):
        """Verify workflow memory captures reusable workflows like 'Open ECE Classroom'."""
        wf_mem = WorkflowMemory(db_path=self.db_path)

        # Verify pre-seeded 'Open ECE Classroom'
        wf = wf_mem.find_matching_workflow("Open ECE Classroom")
        self.assertIsNotNone(wf)
        self.assertEqual(wf.name, "Open ECE Classroom")
        self.assertEqual(len(wf.steps), 4)
        step_tools = [s["tool"] for s in wf.steps]
        self.assertEqual(step_tools, ["browser_open", "browser_detect_session", "browser_navigate", "browser_click"])

        # Test trigger matching with variations
        self.assertIsNotNone(wf_mem.find_matching_workflow("open ece classroom"))
        self.assertIsNotNone(wf_mem.find_matching_workflow("launch ece classroom"))
        self.assertIsNotNone(wf_mem.find_matching_workflow("ECE Classroom"))

        # Save and retrieve a custom workflow
        custom_wf = wf_mem.save_workflow(
            name="Run Linter and Tests",
            trigger_patterns=[r"\brun\s+(?:all\s+)?tests\b", r"\btest\s+suite\b"],
            steps=[
                {"tool": "run_command", "arguments": {"command": "pytest"}},
            ],
            description="Runs pytest test suite",
        )
        self.assertEqual(custom_wf.name, "Run Linter and Tests")
        matched_custom = wf_mem.find_matching_workflow("run all tests please")
        self.assertIsNotNone(matched_custom)
        self.assertEqual(matched_custom.name, "Run Linter and Tests")

    # --- 4. Unified Memory Manager Facade ---

    def test_unified_memory_facade(self):
        """Verify UnifiedMemoryManager integrates all 3 tiers."""
        # 1. Session activity
        self.memory.record_activity(
            goal="Test Memory Facade",
            step_name="Step 1",
            action="Executed mock check",
        )
        what_doing = self.memory.what_were_we_doing()
        self.assertIn("Test Memory Facade", what_doing)

        # 2. Semantic preference
        self.assertEqual(self.memory.get_preference("preferred_browser"), "Chrome")
        self.memory.set_preference("preferred_shell", "PowerShell")
        self.assertEqual(self.memory.get_preference("preferred_shell"), "PowerShell")

        # 3. Workflow matching
        wf = self.memory.find_workflow("Open ECE Classroom")
        self.assertIsNotNone(wf)

        # 4. Injected context
        ctx = self.memory.get_injected_context("what were we doing?")
        self.assertIn("Current Session Status:", ctx)
        self.assertIn("Explicit User Preferences:", ctx)

    # --- 5. Typed Tools Execution ---

    def test_typed_memory_tools(self):
        """Verify SessionRecallTool, ManagePreferenceTool, and WorkflowMemoryTool in registry."""
        registry = get_default_registry()

        # 1. session_recall tool
        recall_tool = registry.get("session_recall")
        self.assertIsNotNone(recall_tool)
        res_recall = recall_tool.execute({})
        self.assertTrue(res_recall.success)
        ver_recall = recall_tool.verify({}, res_recall)
        self.assertTrue(ver_recall.verified)

        # 2. manage_preference tool
        pref_tool = registry.get("manage_preference")
        self.assertIsNotNone(pref_tool)
        res_set = pref_tool.execute({"action": "set", "key": "test_pref", "value": "test_val"})
        self.assertTrue(res_set.success)
        res_get = pref_tool.execute({"action": "get", "key": "test_pref"})
        self.assertTrue(res_get.success)
        self.assertEqual(res_get.output["value"], "test_val")

        # 3. manage_workflow tool
        wf_tool = registry.get("manage_workflow")
        self.assertIsNotNone(wf_tool)
        res_find = wf_tool.execute({"action": "find", "prompt": "Open ECE Classroom"})
        self.assertTrue(res_find.success)
        self.assertTrue(res_find.output["found"])

    # --- 6. Understand and Plan Capability Integration ---

    def test_capability_integration_session_recall(self):
        """Verify 'What were we doing?' intent is recognized and planned."""
        understand = DefaultUnderstandCapability()
        objective = understand.understand("What were we doing?", {})

        self.assertEqual(objective.intent, IntentCategory.QUERY)
        self.assertEqual(objective.extracted_entities.get("action"), "session_recall")

        planner = DefaultPlanCapability()
        plan = planner.plan(objective, AgentSessionState(task_id="test_recall"))

        self.assertEqual(len(plan.steps), 1)
        self.assertEqual(plan.steps[0].tool_name, "session_recall")


if __name__ == "__main__":
    unittest.main()
