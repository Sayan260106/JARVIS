"""Comprehensive Tests for Phase 3: Windows Control.

Verifies:
1. Application launcher alias resolution (Edge, VS Code, Spotify).
2. Hardware telemetry: RAM usage (GB & %) and CPU load.
3. Process inspector: checking if Ollama is running.
4. File management & chaining: search notes, create folder, move file into folder.
5. Productivity tools: reminder scheduling.
"""

import os
import shutil
import unittest
import time

from jarvis.subsystems.system.app_launcher import WindowsAppLauncher
from jarvis.tools import (
    get_default_registry,
    CreateFolderTool,
    CheckProcessTool,
    GetHardwareMetricsTool,
    SetReminderTool,
    SearchFilesTool,
    CreateFileTool,
    MoveFileTool,
)


class TestWindowsControl(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.sandbox_dir = os.path.abspath("data/test_phase3_sandbox")
        os.makedirs(cls.sandbox_dir, exist_ok=True)
        cls.registry = get_default_registry()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.sandbox_dir):
            try:
                shutil.rmtree(cls.sandbox_dir)
            except Exception:
                pass

    def test_app_launcher_aliases(self):
        """Verify smart alias mapping for Edge, VS Code, and Spotify."""
        edge_spec = WindowsAppLauncher.resolve_app("Edge")
        self.assertEqual(edge_spec["type"], "protocol")
        self.assertIn("microsoft-edge:", edge_spec["target"])

        code_spec = WindowsAppLauncher.resolve_app("VS Code")
        self.assertEqual(code_spec["type"], "cmd")
        self.assertEqual(code_spec["target"], "code")

        spotify_spec = WindowsAppLauncher.resolve_app("Spotify")
        self.assertEqual(spotify_spec["type"], "protocol")
        self.assertEqual(spotify_spec["target"], "spotify:")

    def test_hardware_metrics_ram_and_cpu(self):
        """Verify RAM in GB & % and CPU usage retrieval."""
        metrics_tool = GetHardwareMetricsTool()

        # Query RAM
        res_ram = metrics_tool.execute(metric="ram")
        self.assertTrue(res_ram.success)
        self.assertIn("ram_used_gb", res_ram.output)
        self.assertGreater(res_ram.output["ram_used_gb"], 0)
        self.assertIn("ram_total_gb", res_ram.output)
        self.assertGreater(res_ram.output["ram_total_gb"], 0)
        self.assertGreaterEqual(res_ram.output["ram_percent"], 0)

        # Query CPU
        res_cpu = metrics_tool.execute(metric="cpu")
        self.assertTrue(res_cpu.success)
        self.assertIn("cpu_percent", res_cpu.output)
        self.assertIn("cpu_cores", res_cpu.output)
        self.assertGreater(res_cpu.output["cpu_cores"], 0)

    def test_check_process_ollama(self):
        """Verify Ollama process check reflects real service state."""
        proc_tool = CheckProcessTool()
        res = proc_tool.execute(process_name="ollama")
        self.assertTrue(res.success)
        self.assertTrue(res.output["is_running"], "Ollama should be detected as running on this machine")
        self.assertGreaterEqual(res.output["count"], 1)

    def test_file_and_folder_chaining(self):
        """Verify: Find notes -> Create folder 'GATE 2027' -> Move PDF into that folder."""
        create_file_tool = CreateFileTool()
        search_tool = SearchFilesTool()
        create_folder_tool = CreateFolderTool()
        move_tool = MoveFileTool()

        # 1. User has a file: DBMS_Notes.pdf
        dbms_file = os.path.join(self.sandbox_dir, "DBMS_Notes.pdf")
        create_file_tool.execute(path=dbms_file, content="Binary search trees and normalization in DBMS.")
        self.assertTrue(os.path.exists(dbms_file))

        # 2. 'Find my DBMS notes.'
        search_res = search_tool.execute(directory=self.sandbox_dir, pattern="*DBMS*")
        self.assertTrue(search_res.success)
        self.assertGreaterEqual(search_res.output["count"], 1)
        found_path = search_res.output["matches"][0]["path"]
        self.assertEqual(os.path.abspath(found_path), os.path.abspath(dbms_file))

        # 3. 'Create a folder called GATE 2027.'
        gate_folder = os.path.join(self.sandbox_dir, "GATE 2027")
        folder_res = create_folder_tool.execute(path=gate_folder)
        self.assertTrue(folder_res.success)
        self.assertTrue(os.path.isdir(gate_folder))

        # 4. 'Move this PDF into that folder.'
        target_dest = os.path.join(gate_folder, os.path.basename(found_path))
        move_res = move_tool.execute(source_path=found_path, destination_path=target_dest)
        self.assertTrue(move_res.success)

        # 5. Verify ground truth
        self.assertFalse(os.path.exists(dbms_file))
        self.assertTrue(os.path.exists(target_dest))
        self.assertTrue(move_tool.verify({"source_path": found_path, "destination_path": target_dest}, move_res).verified)

    def test_reminder_scheduling(self):
        """Verify reminder timer registers and schedules correctly."""
        triggered = []

        def mock_callback(msg):
            triggered.append(msg)

        reminder_tool = SetReminderTool(alert_callback=mock_callback)
        res = reminder_tool.execute(message="Review GATE mock test", delay_seconds=1)
        self.assertTrue(res.success)
        self.assertEqual(res.output["message"], "Review GATE mock test")

        ver = reminder_tool.verify({"message": "Review GATE mock test", "delay_seconds": 1}, res)
        self.assertTrue(ver.verified)

        # Wait for 1.1s for timer to trigger
        time.sleep(1.2)
        self.assertIn("Review GATE mock test", triggered)

    def test_default_registry_has_all_phase3_tools(self):
        """Verify all phase 3 tools are registered."""
        expected = [
            "open_application", "create_folder", "check_process",
            "get_hardware_metrics", "set_reminder", "lock_pc",
            "shutdown", "restart", "take_screenshot", "create_file"
        ]
        for name in expected:
            tool = self.registry.get(name)
            self.assertIsNotNone(tool, f"Tool '{name}' must be registered")


if __name__ == "__main__":
    unittest.main()
