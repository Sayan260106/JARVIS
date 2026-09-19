"""Unit Tests for Phase 10 — Context Awareness.

Verifies:
1. ContextCollector: All 9 desktop telemetry dimensions.
2. BrowserDetector: Active browser URL and domain inference.
3. SelectionDetector: Safe non-destructive clipboard snapshot technique.
4. ContextResolver: Deictic reference resolution:
   - "Summarize this." -> Open document / webpage
   - "Fix this." -> Visible code in VS Code / editor
   - "Explain this." -> Selected text
5. Context Tools:
   - GetSystemContextTool
   - GetActiveDocumentTool
   - GetSelectedTextTool
   - ResolveContextualPromptTool
6. Understand & Plan Integration:
   - UnderstandCapability correctly maps contextual queries into structured TaskObjectives.
   - PlanCapability creates corresponding PlanSteps.
7. IntentAnalyzer: Contextual deictic query classification and permission assignment.
"""

from __future__ import annotations
import os
import unittest
from unittest.mock import MagicMock, patch

from jarvis.subsystems.context import (
    AppCategory,
    ApplicationContext,
    BrowserContext,
    BrowserDetector,
    ClipboardContext,
    ContextCollector,
    ContextResolver,
    DeicticTargetType,
    OpenFileContext,
    ProcessContextSummary,
    ResolvedContextAction,
    ScreenStateContext,
    SelectionContext,
    SelectionDetector,
    SystemContextSnapshot,
    WindowContext,
)
from jarvis.tools import get_default_registry
from jarvis.tools.context_tools import (
    GetActiveDocumentTool,
    GetSelectedTextTool,
    GetSystemContextTool,
    ResolveContextualPromptTool,
)
from jarvis.capabilities.understand import DefaultUnderstandCapability
from jarvis.capabilities.plan import DefaultPlanCapability
from jarvis.capabilities.reasoning.intent_analyzer import IntentAnalyzer, IntentType
from jarvis.core.schemas import IntentCategory
from jarvis.tools.base import PermissionLevel


class TestContextAwareness(unittest.TestCase):
    """Comprehensive test suite for Phase 10 Context Awareness."""

    def setUp(self):
        self.collector = ContextCollector.get_instance()
        # Reset any simulation overrides
        self.collector.set_simulated_snapshot(None)
        SelectionDetector.set_simulated_selection(None)

    def tearDown(self):
        self.collector.set_simulated_snapshot(None)
        SelectionDetector.set_simulated_selection(None)

    # ------------------------------------------------------------------
    # 1. Context Collector & 9-Dimension Telemetry Tests
    # ------------------------------------------------------------------

    def test_context_collector_dimensions(self):
        """Verify that a collected snapshot contains all 9 required dimensions."""
        snapshot = self.collector.collect(refresh=True, capture_selection=False)

        self.assertIsInstance(snapshot, SystemContextSnapshot)
        # 1. Current Application
        self.assertIsInstance(snapshot.application, ApplicationContext)
        self.assertTrue(hasattr(snapshot.application, "friendly_name"))
        self.assertTrue(hasattr(snapshot.application, "process_name"))

        # 2. Current Window
        self.assertIsInstance(snapshot.window, WindowContext)
        self.assertTrue(hasattr(snapshot.window, "title"))
        self.assertTrue(hasattr(snapshot.window, "hwnd"))

        # 3. Current URL (Browser)
        self.assertIsInstance(snapshot.browser, BrowserContext)
        self.assertTrue(hasattr(snapshot.browser, "current_url"))

        # 4. Selected Text
        self.assertIsInstance(snapshot.selection, SelectionContext)
        self.assertTrue(hasattr(snapshot.selection, "has_selection"))

        # 5. Clipboard
        self.assertIsInstance(snapshot.clipboard, ClipboardContext)
        self.assertTrue(hasattr(snapshot.clipboard, "has_text"))

        # 6. Open Files
        self.assertIsInstance(snapshot.open_files, list)

        # 7. Screen State
        self.assertIsInstance(snapshot.screen_state, ScreenStateContext)
        self.assertGreater(snapshot.screen_state.width, 0)
        self.assertGreater(snapshot.screen_state.height, 0)

        # 8. Running Processes
        self.assertIsInstance(snapshot.processes, ProcessContextSummary)
        self.assertGreaterEqual(snapshot.processes.total_processes, 0)

        # 9. Active Task
        self.assertTrue(hasattr(snapshot.active_task, "has_active_task"))

    def test_snapshot_serialization(self):
        """Verify .to_dict() and .to_prompt_context() formatting."""
        simulated = SystemContextSnapshot(
            application=ApplicationContext(
                process_name="Code.exe",
                friendly_name="Visual Studio Code",
                pid=1234,
                category=AppCategory.EDITOR,
                is_editor=True,
            ),
            window=WindowContext(
                hwnd=5678,
                title="main.py - JARVIS - Visual Studio Code",
            ),
            browser=BrowserContext(
                is_browser_active=False,
            ),
            selection=SelectionContext(
                has_selection=True,
                text="def calculate_total():",
                char_count=22,
                source_app="Visual Studio Code",
            ),
            clipboard=ClipboardContext(
                has_text=True,
                text="npm start",
                preview="npm start",
                char_count=9,
            ),
            open_files=[
                OpenFileContext(
                    file_name="main.py",
                    file_path=os.path.abspath("main.py"),
                    extension=".py",
                    source_app="Visual Studio Code",
                    is_code=True,
                    content_preview="import sys\nimport time\n",
                    line_count=2,
                )
            ],
        )

        d = simulated.to_dict()
        self.assertEqual(d["application"]["friendly_name"], "Visual Studio Code")
        self.assertEqual(d["window"]["title"], "main.py - JARVIS - Visual Studio Code")
        self.assertEqual(len(d["open_files"]), 1)
        self.assertEqual(d["open_files"][0]["file_name"], "main.py")

        prompt_str = simulated.to_prompt_context()
        self.assertIn("Visual Studio Code", prompt_str)
        self.assertIn("main.py", prompt_str)
        self.assertIn("def calculate_total():", prompt_str)
        self.assertIn("npm start", prompt_str)

    # ------------------------------------------------------------------
    # 2. Browser Detection Tests
    # ------------------------------------------------------------------

    def test_browser_url_extraction(self):
        """Verify URL and domain detection for active browsers."""
        ctx = BrowserDetector.detect_context(
            process_name="msedge.exe",
            window_title="GitHub - JARVIS Agent Control - Personal - Microsoft Edge",
            hwnd=0,
        )
        self.assertTrue(ctx.is_browser_active)
        self.assertEqual(ctx.browser_name, "Microsoft Edge")
        self.assertEqual(ctx.domain, "github.com")

        # Test direct URL in window title
        ctx2 = BrowserDetector.detect_context(
            process_name="chrome.exe",
            window_title="https://en.wikipedia.org/wiki/Artificial_intelligence - Google Chrome",
            hwnd=0,
        )
        self.assertTrue(ctx2.is_browser_active)
        self.assertEqual(ctx2.current_url, "https://en.wikipedia.org/wiki/Artificial_intelligence")
        self.assertEqual(ctx2.domain, "en.wikipedia.org")

    # ------------------------------------------------------------------
    # 3. Selection Detection & Safe Clipboard Technique
    # ------------------------------------------------------------------

    def test_selection_detection_simulation(self):
        """Verify non-destructive selected text capture simulation."""
        SelectionDetector.set_simulated_selection("def test_function(): pass")
        sel = SelectionDetector.capture_selected_text(active_app_name="Visual Studio Code")

        self.assertTrue(sel.has_selection)
        self.assertEqual(sel.text, "def test_function(): pass")
        self.assertEqual(sel.char_count, len("def test_function(): pass"))
        self.assertEqual(sel.word_count, 3)

    # ------------------------------------------------------------------
    # 4. Context Resolver: "Summarize this", "Fix this", "Explain this"
    # ------------------------------------------------------------------

    def test_resolve_summarize_open_document(self):
        """Verify 'Summarize this.' resolves to the open document."""
        simulated = SystemContextSnapshot(
            application=ApplicationContext(
                process_name="winword.exe",
                friendly_name="Microsoft Word",
                category=AppCategory.DOCUMENT,
                is_document_viewer=True,
            ),
            window=WindowContext(title="Annual_Report_2026.docx - Word"),
            open_files=[
                OpenFileContext(
                    file_name="Annual_Report_2026.docx",
                    file_path="C:\\Docs\\Annual_Report_2026.docx",
                    extension=".docx",
                    source_app="Microsoft Word",
                    is_document=True,
                    content_preview="Executive Summary: The company grew by 42%...",
                )
            ],
        )

        action = ContextResolver.resolve("Summarize this.", simulated)
        self.assertEqual(action.target_type, DeicticTargetType.OPEN_DOCUMENT)
        self.assertEqual(action.target_name, "Annual_Report_2026.docx")
        self.assertIn("Annual_Report_2026.docx", action.resolved_prompt)
        self.assertIn("Microsoft Word", action.resolved_prompt)

    def test_resolve_fix_code_in_vs_code(self):
        """Verify 'Fix this.' resolves to the visible code in VS Code."""
        simulated = SystemContextSnapshot(
            application=ApplicationContext(
                process_name="Code.exe",
                friendly_name="Visual Studio Code",
                category=AppCategory.EDITOR,
                is_editor=True,
            ),
            window=WindowContext(title="agent_loop.py - JARVIS - Visual Studio Code"),
            open_files=[
                OpenFileContext(
                    file_name="agent_loop.py",
                    file_path="d:\\JARVIS\\jarvis\\core\\agent_loop.py",
                    extension=".py",
                    source_app="Visual Studio Code",
                    is_code=True,
                    content_preview="def run_step(): raise ValueError('Missing tool')",
                )
            ],
        )

        action = ContextResolver.resolve("Fix this.", simulated)
        self.assertEqual(action.target_type, DeicticTargetType.CODE_IN_EDITOR)
        self.assertEqual(action.target_name, "agent_loop.py")
        self.assertIn("agent_loop.py", action.resolved_prompt)
        self.assertIn("Visual Studio Code", action.resolved_prompt)

    def test_resolve_explain_selected_text(self):
        """Verify 'Explain this.' resolves to the currently selected text."""
        simulated = SystemContextSnapshot(
            application=ApplicationContext(
                process_name="chrome.exe",
                friendly_name="Google Chrome",
                category=AppCategory.BROWSER,
                is_browser=True,
            ),
            window=WindowContext(title="Quantum Computing - Wikipedia"),
            selection=SelectionContext(
                has_selection=True,
                text="Quantum decoherence is the loss of quantum coherence.",
                char_count=52,
                word_count=8,
                source_app="Google Chrome",
            ),
        )

        action = ContextResolver.resolve("Explain this.", simulated)
        self.assertEqual(action.target_type, DeicticTargetType.SELECTED_TEXT)
        self.assertEqual(action.target_name, "Selected Text")
        self.assertIn("Quantum decoherence", action.resolved_prompt)

    def test_resolve_summarize_browser_tab(self):
        """Verify 'Summarize this.' resolves to active browser tab when no document is open."""
        simulated = SystemContextSnapshot(
            application=ApplicationContext(
                process_name="chrome.exe",
                friendly_name="Google Chrome",
                category=AppCategory.BROWSER,
                is_browser=True,
            ),
            window=WindowContext(title="AI Alignment Forum - Research Paper - Google Chrome"),
            browser=BrowserContext(
                is_browser_active=True,
                browser_name="Google Chrome",
                current_url="https://alignmentforum.org/posts/xyz",
                page_title="Research Paper",
                domain="alignmentforum.org",
            ),
        )

        action = ContextResolver.resolve("Summarize this.", simulated)
        self.assertEqual(action.target_type, DeicticTargetType.BROWSER_PAGE)
        self.assertIn("alignmentforum.org", action.resolved_prompt)

    # ------------------------------------------------------------------
    # 5. Context Tools Verification
    # ------------------------------------------------------------------

    def test_context_tools_in_registry(self):
        """Verify all 4 new context tools are registered in default ToolRegistry."""
        reg = get_default_registry()
        for tool_name in [
            "get_system_context",
            "get_active_document",
            "get_selected_text",
            "resolve_contextual_prompt",
        ]:
            tool = reg.get(tool_name)
            self.assertIsNotNone(tool, f"Tool '{tool_name}' missing from registry.")

    def test_resolve_contextual_prompt_tool_execution(self):
        """Verify ResolveContextualPromptTool executes and verifies."""
        simulated = SystemContextSnapshot(
            application=ApplicationContext(
                process_name="Code.exe",
                friendly_name="Visual Studio Code",
                is_editor=True,
            ),
            window=WindowContext(title="test.py - VS Code"),
            open_files=[
                OpenFileContext(
                    file_name="test.py",
                    file_path="d:\\JARVIS\\test.py",
                    extension=".py",
                    is_code=True,
                )
            ],
        )
        self.collector.set_simulated_snapshot(simulated)

        tool = ResolveContextualPromptTool()
        res = tool.execute({"prompt": "Fix this."})
        self.assertTrue(res.success)
        self.assertEqual(res.output["target_type"], "code_in_editor")
        self.assertEqual(res.output["target_name"], "test.py")

        ver = tool.verify({"prompt": "Fix this."}, res)
        self.assertTrue(ver.verified)

    # ------------------------------------------------------------------
    # 6. Understand & Plan Integration Tests
    # ------------------------------------------------------------------

    def test_understand_summarize_this_document(self):
        """Verify DefaultUnderstandCapability resolves 'Summarize this.' to a document task."""
        simulated = SystemContextSnapshot(
            application=ApplicationContext(
                process_name="notepad.exe",
                friendly_name="Notepad",
                category=AppCategory.EDITOR,
            ),
            window=WindowContext(title="meeting_notes.txt - Notepad"),
            open_files=[
                OpenFileContext(
                    file_name="meeting_notes.txt",
                    file_path="d:\\JARVIS\\meeting_notes.txt",
                    extension=".txt",
                    is_document=True,
                    content_preview="Meeting Agenda: Q3 OKRs and System Launch...",
                )
            ],
        )

        understand_cap = DefaultUnderstandCapability()
        obj = understand_cap.understand("Summarize this.", context={"system_context": simulated})

        self.assertEqual(obj.intent, IntentCategory.TASK_AUTOMATION)
        self.assertIn("meeting_notes.txt", obj.description)
        self.assertEqual(obj.extracted_entities.get("action"), "summarize_document")
        self.assertEqual(obj.extracted_entities.get("file_name"), "meeting_notes.txt")

        # Now verify plan generation
        plan_cap = DefaultPlanCapability()
        plan = plan_cap.plan(obj, MagicMock())
        self.assertGreaterEqual(len(plan.steps), 2)
        self.assertEqual(plan.steps[0].tool_name, "document_read")
        self.assertEqual(plan.steps[1].tool_name, "document_summarize")

    def test_understand_fix_this_code(self):
        """Verify DefaultUnderstandCapability resolves 'Fix this.' to a code fix task."""
        simulated = SystemContextSnapshot(
            application=ApplicationContext(
                process_name="Code.exe",
                friendly_name="Visual Studio Code",
                is_editor=True,
            ),
            window=WindowContext(title="server.py - Visual Studio Code"),
            open_files=[
                OpenFileContext(
                    file_name="server.py",
                    file_path="d:\\JARVIS\\server.py",
                    extension=".py",
                    is_code=True,
                    content_preview="app = FastAPI()\n@app.get('/')\ndef index(): return 1/0",
                )
            ],
        )

        understand_cap = DefaultUnderstandCapability()
        obj = understand_cap.understand("Fix this.", context={"system_context": simulated})

        self.assertEqual(obj.intent, IntentCategory.TASK_AUTOMATION)
        self.assertIn("server.py", obj.description)
        self.assertEqual(obj.extracted_entities.get("action"), "fix_code")
        self.assertEqual(obj.extracted_entities.get("file_name"), "server.py")

        # Now verify plan generation
        plan_cap = DefaultPlanCapability()
        plan = plan_cap.plan(obj, MagicMock())
        self.assertGreaterEqual(len(plan.steps), 2)
        self.assertEqual(plan.steps[0].tool_name, "get_active_document")
        self.assertEqual(plan.steps[1].tool_name, "modify_file")

    def test_understand_explain_this_selection(self):
        """Verify DefaultUnderstandCapability resolves 'Explain this.' to selected text explanation."""
        simulated = SystemContextSnapshot(
            application=ApplicationContext(
                process_name="chrome.exe",
                friendly_name="Google Chrome",
            ),
            window=WindowContext(title="Distributed Systems Article"),
            selection=SelectionContext(
                has_selection=True,
                text="The Raft consensus algorithm ensures state machine replication.",
                char_count=65,
                source_app="Google Chrome",
            ),
        )

        understand_cap = DefaultUnderstandCapability()
        obj = understand_cap.understand("Explain this.", context={"system_context": simulated})

        self.assertEqual(obj.intent, IntentCategory.QUERY)
        self.assertEqual(obj.extracted_entities.get("action"), "explain_selection")
        self.assertEqual(obj.extracted_entities.get("target_type"), "selected_text")

        # Verify plan generation
        plan_cap = DefaultPlanCapability()
        plan = plan_cap.plan(obj, MagicMock())
        self.assertGreaterEqual(len(plan.steps), 1)
        self.assertEqual(plan.steps[0].tool_name, "get_selected_text")

    # ------------------------------------------------------------------
    # 7. Intent Analyzer Tests
    # ------------------------------------------------------------------

    def test_intent_analyzer_contextual_resolution(self):
        """Verify IntentAnalyzer properly routes contextual deictic queries."""
        simulated = SystemContextSnapshot(
            application=ApplicationContext(
                process_name="Code.exe",
                friendly_name="Visual Studio Code",
                is_editor=True,
            ),
            window=WindowContext(title="main.py - Visual Studio Code"),
            open_files=[
                OpenFileContext(
                    file_name="main.py",
                    file_path="d:\\JARVIS\\main.py",
                    extension=".py",
                    is_code=True,
                )
            ],
        )
        self.collector.set_simulated_snapshot(simulated)

        analyzer = IntentAnalyzer()
        intent = analyzer.analyze("Fix this.")
        self.assertEqual(intent.intent_type, IntentType.WRITE_ACTION)
        self.assertEqual(intent.permission_level, PermissionLevel.LEVEL_1_REVERSIBLE_WRITE)
        self.assertEqual(intent.target_tool, "modify_file")


if __name__ == "__main__":
    unittest.main()
