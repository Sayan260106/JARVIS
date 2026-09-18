"""Test Suite for Phase 2: Windows Control Layer & Typed Windows Agent.

Verifies:
1. The 5 Specific Prompt Targets:
   - Target 1: "Open VS Code."
   - Target 2: "Open Downloads."
   - Target 3: "Create a folder called GATE 2027."
   - Target 4: "Shutdown the computer."
   - Target 5: "Close Chrome."
2. Intent -> Typed Tool routing without arbitrary PowerShell generation.
3. Windows Control Tools unit tests:
   - OpenApplicationTool, CloseApplicationTool
   - FocusWindowTool, WindowControlTool, ListWindowsTool, GetActiveWindowTool
   - StartProcessTool, StopProcessTool
   - MouseMoveTool, MouseClickTool, MouseDoubleClickTool, MouseRightClickTool
   - SendHotkeyTool, ClipboardTool
   - ModifyFileTool
   - VolumeControlTool, DisplayControlTool, SleepPCTool, ShutdownTool, RestartTool
"""

from __future__ import annotations
import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from jarvis.core.loop import JarvisAgentLoop
from jarvis.core.schemas import IntentCategory, StepStatus, SubsystemType
from jarvis.core.state import AgentSessionState, LoopPhase
from jarvis.core.task_manager import TaskManager
from jarvis.subsystems.system.windows_executor import WindowsExecutor
from jarvis.tools import get_default_registry
from jarvis.tools.system_tools import (
    ClipboardTool,
    CloseApplicationTool,
    DisplayControlTool,
    FocusWindowTool,
    GetActiveWindowTool,
    ListWindowsTool,
    ModifyFileTool,
    MouseClickTool,
    MouseDoubleClickTool,
    MouseMoveTool,
    MouseRightClickTool,
    OpenApplicationTool,
    SendHotkeyTool,
    SleepPCTool,
    StartProcessTool,
    StopProcessTool,
    VolumeControlTool,
    WindowControlTool,
    ShutdownTool,
    RestartTool,
)


class TestWindowsControlAgent(unittest.TestCase):
    """Verifies Phase 2 Windows Control Layer and Agent Loop integration."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_tasks.db")
        self.task_manager = TaskManager(db_path=self.db_path)
        self.registry = get_default_registry()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # ----------------------------------------------------------------------
    # Target 1: "Open VS Code."
    # ----------------------------------------------------------------------
    @patch.object(WindowsExecutor, "launch_app")
    def test_target_1_open_vs_code(self, mock_launch):
        mock_launch.return_value = {
            "success": True,
            "application": "VS Code",
            "message": "Application 'VS Code' launched successfully",
            "pid": 5432,
        }
        loop = JarvisAgentLoop(registry=self.registry, task_manager=self.task_manager)
        prompt = "Open VS Code."

        # 1. Understand
        objective = loop.understand_cap.understand(prompt, {})
        self.assertEqual(objective.intent, IntentCategory.SYSTEM_COMMAND)
        self.assertEqual(objective.extracted_entities.get("action"), "open_application")
        self.assertEqual(objective.extracted_entities.get("app_name"), "VS Code")

        # 2. Plan
        plan = loop.plan_cap.plan(objective, AgentSessionState(task_id="test"))
        self.assertEqual(len(plan.steps), 1)
        step = plan.steps[0]
        self.assertEqual(step.tool_name, "open_application")
        self.assertEqual(step.arguments.get("app_name"), "VS Code")
        # Critical architectural check: NO powershell_exec!
        self.assertNotEqual(step.tool_name, "powershell_exec")

        # 3. Act & Observe & Verify
        state = loop.run(prompt)
        self.assertEqual(len(state.history), 1)
        self.assertEqual(state.history[0].status, StepStatus.SUCCESS)
        mock_launch.assert_called_once_with("VS Code", None)

    # ----------------------------------------------------------------------
    # Target 2: "Open Downloads."
    # ----------------------------------------------------------------------
    @patch.object(WindowsExecutor, "launch_app")
    def test_target_2_open_downloads(self, mock_launch):
        downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")
        mock_launch.return_value = {
            "success": True,
            "application": "Downloads",
            "path": downloads_path,
            "message": f"Special user folder opened: {downloads_path}",
        }
        loop = JarvisAgentLoop(registry=self.registry, task_manager=self.task_manager)
        prompt = "Open Downloads."

        # Understand & Plan
        objective = loop.understand_cap.understand(prompt, {})
        self.assertEqual(objective.extracted_entities.get("action"), "open_application")
        self.assertEqual(objective.extracted_entities.get("app_name"), "Downloads")

        plan = loop.plan_cap.plan(objective, AgentSessionState(task_id="test"))
        step = plan.steps[0]
        self.assertEqual(step.tool_name, "open_application")
        self.assertEqual(step.arguments.get("app_name"), "Downloads")

        # Run
        state = loop.run(prompt)
        self.assertEqual(state.history[0].status, StepStatus.SUCCESS)
        mock_launch.assert_called_once_with("Downloads", None)

    # ----------------------------------------------------------------------
    # Target 3: "Create a folder called GATE 2027."
    # ----------------------------------------------------------------------
    def test_target_3_create_folder_gate_2027(self):
        target_path = os.path.join(self.temp_dir, "GATE 2027")
        loop = JarvisAgentLoop(registry=self.registry, task_manager=self.task_manager)
        prompt = f"Create a folder called {target_path}."

        objective = loop.understand_cap.understand(prompt, {})
        self.assertEqual(objective.extracted_entities.get("action"), "create_folder")
        self.assertEqual(objective.extracted_entities.get("path"), target_path)

        plan = loop.plan_cap.plan(objective, AgentSessionState(task_id="test"))
        step = plan.steps[0]
        self.assertEqual(step.tool_name, "create_folder")
        self.assertEqual(step.arguments.get("path"), target_path)

        state = loop.run(prompt)
        self.assertEqual(state.history[0].status, StepStatus.SUCCESS)
        self.assertTrue(os.path.isdir(target_path))

    # ----------------------------------------------------------------------
    # Target 4: "Lock the computer."
    # ----------------------------------------------------------------------
    @patch.object(WindowsExecutor, "lock_pc")
    def test_target_4_lock_computer(self, mock_lock):
        mock_lock.return_value = {
            "success": True,
            "message": "Workstation locked successfully.",
        }
        loop = JarvisAgentLoop(registry=self.registry, task_manager=self.task_manager)
        prompt = "Lock the computer."

        objective = loop.understand_cap.understand(prompt, {})
        self.assertEqual(objective.extracted_entities.get("action"), "lock_pc")

        plan = loop.plan_cap.plan(objective, AgentSessionState(task_id="test"))
        step = plan.steps[0]
        self.assertEqual(step.tool_name, "lock_pc")
        self.assertNotEqual(step.tool_name, "powershell_exec")

        state = loop.run(prompt)
        self.assertEqual(state.history[0].status, StepStatus.SUCCESS)
        mock_lock.assert_called_once()

    # ----------------------------------------------------------------------
    # Target 4 (Variant): "Shutdown the computer."
    # ----------------------------------------------------------------------
    @patch.object(WindowsExecutor, "shutdown")
    def test_target_4_shutdown_computer(self, mock_shutdown):
        mock_shutdown.return_value = {
            "success": True,
            "message": "Shutdown initiated with 60s delay.",
            "command": "shutdown /s /t 60",
        }
        loop = JarvisAgentLoop(registry=self.registry, task_manager=self.task_manager)
        prompt = "Shutdown the computer."

        objective = loop.understand_cap.understand(prompt, {})
        self.assertEqual(objective.extracted_entities.get("action"), "shutdown")

        plan = loop.plan_cap.plan(objective, AgentSessionState(task_id="test"))
        step = plan.steps[0]
        self.assertEqual(step.tool_name, "shutdown")
        # Must NOT be arbitrary PowerShell
        self.assertNotEqual(step.tool_name, "powershell_exec")

        state = loop.run(prompt)
        self.assertEqual(state.history[0].status, StepStatus.SUCCESS)
        mock_shutdown.assert_called_once_with(60, False, None)

    # ----------------------------------------------------------------------
    # Target 5: "Close Chrome."
    # ----------------------------------------------------------------------
    @patch.object(WindowsExecutor, "close_app")
    def test_target_5_close_chrome(self, mock_close):
        mock_close.return_value = {
            "success": True,
            "application": "Chrome",
            "terminated_count": 3,
            "message": "Terminated 3 processes for 'Chrome'",
        }
        loop = JarvisAgentLoop(registry=self.registry, task_manager=self.task_manager)
        prompt = "Close Chrome."

        objective = loop.understand_cap.understand(prompt, {})
        self.assertEqual(objective.extracted_entities.get("action"), "close_application")
        self.assertEqual(objective.extracted_entities.get("app_name"), "Chrome")

        plan = loop.plan_cap.plan(objective, AgentSessionState(task_id="test"))
        step = plan.steps[0]
        self.assertEqual(step.tool_name, "close_application")
        self.assertEqual(step.arguments.get("app_name"), "Chrome")

        state = loop.run(prompt)
        self.assertEqual(state.history[0].status, StepStatus.SUCCESS)
        mock_close.assert_called_once_with("Chrome", False)

    # ----------------------------------------------------------------------
    # Unit tests for newly registered Windows control tools
    # ----------------------------------------------------------------------
    def test_all_new_tools_in_registry(self):
        expected_tools = [
            "open_application",
            "close_application",
            "focus_window",
            "window_control",
            "list_windows",
            "get_active_window",
            "start_process",
            "stop_process",
            "mouse_move",
            "mouse_click",
            "mouse_double_click",
            "mouse_right_click",
            "send_hotkey",
            "clipboard",
            "modify_file",
            "volume_control",
            "display_control",
            "sleep_pc",
            "shutdown",
            "restart",
            "keyboard_input",
            "list_processes",
        ]
        for t_name in expected_tools:
            self.assertIsNotNone(self.registry.get(t_name), f"Missing tool in registry: {t_name}")

    def test_modify_file_tool(self):
        tool = ModifyFileTool()
        test_file = os.path.join(self.temp_dir, "modify_me.txt")
        with open(test_file, "w") as f:
            f.write("Line 1\n")

        # Test append
        res_append = tool.execute(path=test_file, content="Line 2\n", mode="append")
        self.assertTrue(res_append.success)
        with open(test_file, "r") as f:
            self.assertEqual(f.read(), "Line 1\nLine 2\n")

        # Test prepend
        res_prepend = tool.execute(path=test_file, content="Line 0\n", mode="prepend")
        self.assertTrue(res_prepend.success)
        with open(test_file, "r") as f:
            self.assertEqual(f.read(), "Line 0\nLine 1\nLine 2\n")

    @patch.object(WindowsExecutor, "get_clipboard")
    @patch.object(WindowsExecutor, "set_clipboard")
    def test_clipboard_tool(self, mock_set, mock_get):
        mock_set.return_value = True
        mock_get.return_value = "Hello Clipboard"

        tool = ClipboardTool()
        res_set = tool.execute(action="set", text="Hello Clipboard")
        self.assertTrue(res_set.success)
        mock_set.assert_called_once_with("Hello Clipboard")

        res_get = tool.execute(action="get")
        self.assertTrue(res_get.success)
        self.assertEqual(res_get.output.get("text"), "Hello Clipboard")
        mock_get.assert_called_once()

    @patch.object(WindowsExecutor, "mouse_move")
    @patch.object(WindowsExecutor, "mouse_click")
    def test_mouse_tools(self, mock_click, mock_move):
        mock_move.return_value = (True, "Moved mouse to (100, 200).")
        mock_click.return_value = (True, "Executed left-click.")

        move_tool = MouseMoveTool()
        click_tool = MouseClickTool()

        res_move = move_tool.execute(x=100, y=200)
        self.assertTrue(res_move.success)
        mock_move.assert_called_once_with(100, 200)

        res_click = click_tool.execute(button="left", x=100, y=200)
        self.assertTrue(res_click.success)
        mock_click.assert_called_once_with(button="left", coords=(100, 200))

    @patch.object(WindowsExecutor, "set_volume")
    def test_volume_control_tool(self, mock_vol):
        mock_vol.return_value = (True, "Volume set to 75%.")
        tool = VolumeControlTool()
        res = tool.execute(action="set", level=75)
        self.assertTrue(res.success)
        mock_vol.assert_called_once_with("set", level=75)

    @patch.object(WindowsExecutor, "set_window_state")
    @patch.object(WindowsExecutor, "focus_window")
    def test_window_control_tools(self, mock_focus, mock_state):
        mock_state.return_value = (True, "Set window 'Chrome' state to 'minimize'.")
        mock_focus.return_value = (True, "Focused window 'Chrome'.")

        win_tool = WindowControlTool()
        focus_tool = FocusWindowTool()

        res_win = win_tool.execute(action="minimize", title="Chrome")
        self.assertTrue(res_win.success)
        mock_state.assert_called_once_with("Chrome", "minimize")

        res_focus = focus_tool.execute(title="Chrome")
        self.assertTrue(res_focus.success)
        mock_focus.assert_called_once_with("Chrome")


if __name__ == "__main__":
    unittest.main()
