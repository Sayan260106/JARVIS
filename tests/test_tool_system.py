"""Comprehensive Unit Tests for JARVIS Phase 2: Tool System.

Tests:
1. Tool Registry & Schema Generation.
2. Tool Validator & Path Traversal Guardrails.
3. Risk Levels & Permission Gatekeeping.
4. Concrete Tools (Create, Search, Move, Delete, System Info, Screenshot).
5. Tool Verification Layer (Rule 1).
6. AgentToolExecutor Pipeline & JSON Parsing.
"""

import os
import shutil
import unittest

from jarvis.tools.base import RiskLevel
from jarvis.tools.validator import ToolValidator
from jarvis.tools.permissions import PermissionSystem
from jarvis.tools import (
    get_default_registry,
    CreateFileTool,
    SearchFilesTool,
    MoveFileTool,
    DeleteFileTool,
    GetSystemInfoTool,
    TakeScreenshotTool,
    RunCommandTool,
    BrowserSearchTool,
)
from jarvis.capabilities.agent_planner import AgentToolExecutor


class TestJarvisToolSystem(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_dir = os.path.abspath("data/test_tools_sandbox")
        os.makedirs(cls.test_dir, exist_ok=True)
        cls.registry = get_default_registry()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_dir):
            try:
                shutil.rmtree(cls.test_dir)
            except Exception:
                pass

    def test_registry_populated(self):
        """Verify all 13 tools are registered with schemas."""
        tools = self.registry.list_tools()
        self.assertGreaterEqual(len(tools), 13)
        expected_names = [
            "open_file", "open_application", "search_files", "create_file",
            "move_file", "delete_file", "run_command", "take_screenshot",
            "get_system_info", "lock_pc", "shutdown", "restart", "browser_search"
        ]
        for name in expected_names:
            tool = self.registry.get(name)
            self.assertIsNotNone(tool, f"Tool '{name}' should be in registry")
            schema = tool.to_schema()
            self.assertEqual(schema["name"], name)
            self.assertIn("risk_level", schema)

    def test_validator_required_parameters(self):
        """Verify validator flags missing required parameters."""
        tool = CreateFileTool()
        # Missing 'content'
        res = ToolValidator.validate(tool, {"path": "test.txt"})
        self.assertFalse(res.valid)
        self.assertIn("Missing required parameter 'content'", res.error)

    def test_validator_path_traversal_blocking(self):
        """Verify validator blocks access to critical Windows system paths."""
        tool = DeleteFileTool()
        res = ToolValidator.validate(tool, {"path": r"C:\Windows\System32\config\SAM"})
        self.assertFalse(res.valid)
        self.assertIn("Security violation", res.error)

    def test_permission_system_risk_levels(self):
        """Verify permission gatekeeping across LOW, MEDIUM, and HIGH risk."""
        perms = PermissionSystem()

        low_tool = GetSystemInfoTool()
        self.assertEqual(low_tool.risk_level, RiskLevel.LOW)
        d_low = perms.check_permission(low_tool, {})
        self.assertTrue(d_low.allowed)

        med_tool = CreateFileTool()
        self.assertEqual(med_tool.risk_level, RiskLevel.MEDIUM)
        d_med = perms.check_permission(med_tool, {"path": "test.txt", "content": "hi"})
        self.assertTrue(d_med.allowed)

        high_tool = DeleteFileTool()
        self.assertEqual(high_tool.risk_level, RiskLevel.HIGH)
        # By default without callback, HIGH risk is blocked
        d_high = perms.check_permission(high_tool, {"path": "test.txt"})
        self.assertFalse(d_high.allowed)
        self.assertTrue(d_high.user_prompt_required)

        # With approved callback
        perms_approved = PermissionSystem(approval_callback=lambda t, a: True)
        d_approved = perms_approved.check_permission(high_tool, {"path": "test.txt"})
        self.assertTrue(d_approved.allowed)

    def test_file_operations_lifecycle(self):
        """Test full file lifecycle: create -> verify -> search -> move -> delete."""
        create_tool = CreateFileTool()
        search_tool = SearchFilesTool()
        move_tool = MoveFileTool()
        delete_tool = DeleteFileTool()

        file_a = os.path.join(self.test_dir, "document.txt")
        file_b = os.path.join(self.test_dir, "renamed_document.txt")

        # 1. Create File
        c_res = create_tool.execute(path=file_a, content="DBMS Lecture Notes for GATE")
        self.assertTrue(c_res.success)
        c_ver = create_tool.verify({"path": file_a}, c_res)
        self.assertTrue(c_ver.verified)
        self.assertTrue(os.path.exists(file_a))

        # 2. Search Files
        s_res = search_tool.execute(directory=self.test_dir, pattern="*.txt")
        self.assertTrue(s_res.success)
        self.assertGreaterEqual(s_res.output["count"], 1)
        s_ver = search_tool.verify({"pattern": "*.txt"}, s_res)
        self.assertTrue(s_ver.verified)

        # 3. Move File
        m_res = move_tool.execute(source_path=file_a, destination_path=file_b)
        self.assertTrue(m_res.success)
        m_ver = move_tool.verify({"source_path": file_a, "destination_path": file_b}, m_res)
        self.assertTrue(m_ver.verified)
        self.assertFalse(os.path.exists(file_a))
        self.assertTrue(os.path.exists(file_b))

        # 4. Delete File
        d_res = delete_tool.execute(path=file_b)
        self.assertTrue(d_res.success)
        d_ver = delete_tool.verify({"path": file_b}, d_res)
        self.assertTrue(d_ver.verified)
        self.assertFalse(os.path.exists(file_b))

    def test_get_system_info_tool(self):
        """Verify system info tool captures real hardware/OS telemetry."""
        sys_tool = GetSystemInfoTool()
        res = sys_tool.execute()
        self.assertTrue(res.success)
        self.assertIn("cpu_count", res.output)
        self.assertGreater(res.output["cpu_count"], 0)
        self.assertIn("ram_total_gb", res.output)
        self.assertGreater(res.output["ram_total_gb"], 0)

        ver = sys_tool.verify({}, res)
        self.assertTrue(ver.verified)

    def test_take_screenshot_tool(self):
        """Verify take screenshot tool creates a valid image file."""
        shot_tool = TakeScreenshotTool()
        shot_path = os.path.join(self.test_dir, "screen.png")
        res = shot_tool.execute(save_path=shot_path)
        self.assertTrue(res.success)
        self.assertTrue(os.path.exists(shot_path))
        self.assertGreater(os.path.getsize(shot_path), 0)

        ver = shot_tool.verify({"save_path": shot_path}, res)
        self.assertTrue(ver.verified)

    def test_browser_search_tool(self):
        """Verify browser search tool formats URLs correctly."""
        web_tool = BrowserSearchTool()
        res = web_tool.execute(query="gate cs binary search tree", open_in_browser=False)
        self.assertTrue(res.success)
        self.assertIn("google.com/search?q=", res.output["url"])

        ver = web_tool.verify({}, res)
        self.assertTrue(ver.verified)

    def test_agent_tool_executor_json_parsing(self):
        """Verify AgentToolExecutor extracts tool calls from JSON."""
        executor = AgentToolExecutor()

        # Pure JSON
        call1 = executor.extract_tool_call('{"tool": "open_file", "arguments": {"path": "C:/docs/DBMS.pdf"}}')
        self.assertIsNotNone(call1)
        self.assertEqual(call1[0], "open_file")
        self.assertEqual(call1[1]["path"], "C:/docs/DBMS.pdf")

        # Markdown wrapped JSON
        md_text = """Certainly! I will open the requested document:
```json
{
  "tool": "open_file",
  "arguments": {
    "path": "C:/Users/DBMS.pdf"
  }
}
```"""
        call2 = executor.extract_tool_call(md_text)
        self.assertIsNotNone(call2)
        self.assertEqual(call2[0], "open_file")
        self.assertEqual(call2[1]["path"], "C:/Users/DBMS.pdf")

        # Conversational text (no tool call)
        call3 = executor.extract_tool_call("A binary search tree has left and right nodes.")
        self.assertIsNone(call3)

    def test_agent_tool_executor_pipeline(self):
        """Verify AgentToolExecutor runs tool through validation, perms, and verification."""
        perms = PermissionSystem(auto_approve_high=True)
        executor = AgentToolExecutor(permission_system=perms)

        test_file = os.path.join(self.test_dir, "agent_test.txt")
        result, verification, perm = executor.execute_tool(
            "create_file",
            {"path": test_file, "content": "Autonomous agent execution verified."},
        )

        self.assertTrue(perm.allowed)
        self.assertTrue(result.success)
        self.assertTrue(verification.verified)
        self.assertTrue(os.path.exists(test_file))


if __name__ == "__main__":
    unittest.main()
