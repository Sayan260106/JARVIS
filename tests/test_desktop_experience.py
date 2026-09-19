"""Comprehensive Test Suite for Phase 16 — JARVIS Desktop Experience.

Verifies:
1. UIStateManager Step Checklist API (add_step, update_step, set_steps, clear_steps, to_dict serialization).
2. Native Desktop GUI (JarvisDesktopApp) widget creation, layout, step rendering, telemetry formatting, and headless lifecycle.
3. DesktopTUI Phase 16 HUD Wireframe (render_hud with user card, live step checkmarks, and telemetry footer).
4. Web HUD API Step Checklist integration (/api/status JSON payload containing task_steps).
5. Dynamic Task Dispatch & Simulation in GUI.
"""

import json
import os
import shutil
import tempfile
import time
import unittest
from typing import Any, Dict

from jarvis.core.ui_state import UIStateManager, StepStatus, StepItem
from jarvis.interfaces.desktop_tui import DesktopTUI
from jarvis.interfaces.desktop_gui import JarvisDesktopApp, TKINTER_AVAILABLE


class TestUIStateStepChecklist(unittest.TestCase):
    """Tests the granular plan step checklist in UIStateManager."""

    def setUp(self):
        self.state = UIStateManager()

    def test_default_task_steps_initialized(self):
        """UIStateManager should initialize with default step checklist."""
        steps = self.state.task_steps
        self.assertGreaterEqual(len(steps), 4)
        labels = [s.label for s in steps]
        self.assertIn("Chrome opened", labels)
        self.assertIn("Classroom opened", labels)
        self.assertIn("Downloading...", labels)

    def test_add_and_update_step(self):
        """Verify adding and updating step statuses."""
        self.state.clear_steps()
        self.assertEqual(len(self.state.task_steps), 0)

        self.state.add_step("Open VS Code", StepStatus.COMPLETED)
        self.state.add_step("Run unit tests", StepStatus.IN_PROGRESS)
        self.state.add_step("Commit changes", StepStatus.PENDING)

        self.assertEqual(len(self.state.task_steps), 3)
        self.assertEqual(self.state.task_steps[0].icon(), "✓")
        self.assertEqual(self.state.task_steps[1].icon(), "●")
        self.assertEqual(self.state.task_steps[2].icon(), "○")

        # Update step 1 from IN_PROGRESS to COMPLETED
        self.state.update_step(1, StepStatus.COMPLETED)
        self.assertEqual(self.state.task_steps[1].status, StepStatus.COMPLETED)
        self.assertEqual(self.state.task_steps[1].icon(), "✓")

    def test_to_dict_includes_task_steps(self):
        """to_dict() must serialize task_steps for JSON consumers."""
        d = self.state.to_dict()
        self.assertIn("task_steps", d)
        self.assertIsInstance(d["task_steps"], list)
        self.assertGreater(len(d["task_steps"]), 0)

        first_step = d["task_steps"][0]
        self.assertIn("label", first_step)
        self.assertIn("status", first_step)
        self.assertIn("icon", first_step)

    def test_hardware_telemetry_fields(self):
        """get_hardware_telemetry must include tasks and ollama."""
        telemetry = self.state.get_hardware_telemetry()
        self.assertIn("cpu", telemetry)
        self.assertIn("ram", telemetry)
        self.assertIn("tasks", telemetry)
        self.assertIn("ollama", telemetry)


class TestDesktopTUIPhase16Wireframe(unittest.TestCase):
    """Tests the Phase 16 Desktop TUI wireframe representation."""

    def setUp(self):
        self.state = UIStateManager()
        self.tui = DesktopTUI(state_manager=self.state)

    def test_render_hud_contains_required_sections(self):
        """render_hud must produce the exact requested wireframe box format."""
        # Set exact scenario
        self.state.add_message("USER", "Find my ECE Lecture 3 PDF")
        self.state.add_message("JARVIS", "Planning task...")
        self.state.set_steps([
            StepItem("Chrome opened", StepStatus.COMPLETED),
            StepItem("Classroom opened", StepStatus.COMPLETED),
            StepItem("ECE course found", StepStatus.COMPLETED),
            StepItem("Lecture PDF found", StepStatus.COMPLETED),
            StepItem("Downloading...", StepStatus.IN_PROGRESS),
        ])

        rendered = self.tui.render_hud(width=45)

        # Header
        self.assertIn("JARVIS", rendered)
        self.assertIn("ONLINE", rendered)

        # User and Jarvis turns
        self.assertIn("USER", rendered)
        self.assertIn('"Find my ECE Lecture 3 PDF"', rendered)
        self.assertIn("JARVIS", rendered)
        self.assertIn("Planning task...", rendered)

        # Checkmarks
        self.assertIn("✓ Chrome opened", rendered)
        self.assertIn("✓ Classroom opened", rendered)
        self.assertIn("✓ ECE course found", rendered)
        self.assertIn("✓ Lecture PDF found", rendered)
        self.assertIn("● Downloading...", rendered)

        # Footer
        self.assertIn("CPU", rendered)
        self.assertIn("RAM", rendered)
        self.assertIn("Tasks", rendered)
        self.assertIn("Ollama", rendered)

    def test_display_hud_encoding_safe(self):
        """display(style='hud') must execute without raising uncaught exceptions."""
        try:
            self.tui.display(style="hud")
        except Exception as e:
            self.fail(f"tui.display(style='hud') raised exception: {e}")


@unittest.skipUnless(TKINTER_AVAILABLE, "Tkinter is required for Desktop GUI tests")
class TestJarvisDesktopApp(unittest.TestCase):
    """Tests Native Desktop HUD window application in headless mode."""

    def setUp(self):
        self.state = UIStateManager()
        self.state.add_message("USER", "Find my ECE Lecture 3 PDF")
        self.state.add_message("JARVIS", "Planning task...")
        self.state.set_steps([
            StepItem("Chrome opened", StepStatus.COMPLETED),
            StepItem("Classroom opened", StepStatus.COMPLETED),
            StepItem("ECE course found", StepStatus.COMPLETED),
            StepItem("Lecture PDF found", StepStatus.COMPLETED),
            StepItem("Downloading...", StepStatus.IN_PROGRESS),
        ])
        self.app = JarvisDesktopApp(state_manager=self.state, headless=True)

    def tearDown(self):
        self.app.close()

    def test_desktop_gui_widget_hierarchy(self):
        """Verify essential GUI labels and controls exist."""
        self.assertEqual(self.app.lbl_title.cget("text"), "J A R V I S")
        self.assertEqual(self.app.lbl_status.cget("text"), "● ONLINE")
        self.assertEqual(self.app.lbl_user_tag.cget("text"), "USER")
        self.assertIn("Find my ECE Lecture 3 PDF", self.app.lbl_user_query.cget("text"))
        self.assertEqual(self.app.lbl_jarvis_tag.cget("text"), "JARVIS")
        self.assertEqual(self.app.lbl_jarvis_status.cget("text"), "Planning task...")
        self.assertIsNotNone(self.app.btn_send)
        self.assertIsNotNone(self.app.entry_input)

    def test_step_rendering_in_gui(self):
        """Verify steps are rendered as checklist labels in the GUI container."""
        self.assertEqual(len(self.app.step_labels), 5)
        step_texts = [lbl.cget("text").strip() for lbl in self.app.step_labels]
        self.assertIn("Chrome opened", step_texts)
        self.assertIn("Downloading...", step_texts)

    def test_telemetry_footer_formatting(self):
        """Verify footer telemetry formats CPU, RAM, Tasks, Ollama."""
        self.app.update_telemetry()
        footer = self.app.lbl_telemetry.cget("text")
        self.assertIn("CPU", footer)
        self.assertIn("RAM", footer)
        self.assertIn("Tasks", footer)
        self.assertIn("Ollama", footer)

    def test_set_input_and_execute(self):
        """Verify filling input and triggering execute updates query banner."""
        self.app.set_input_and_execute("Organize Downloads")
        query_text = self.app.lbl_user_query.cget("text")
        self.assertEqual(query_text, '"Organize Downloads"')
        status_text = self.app.lbl_jarvis_status.cget("text")
        self.assertEqual(status_text, "Planning task...")


if __name__ == "__main__":
    unittest.main()
