"""Unit and integration tests for JARVIS Phase 9: Vision & Desktop Automation.

Verifies:
1. Screen capture functionality, dimensions, and base64 encoding.
2. Windows desktop mouse/keyboard controller bounds and event generation.
3. Multimodal visual diagnostics ("Jarvis, what's wrong?").
4. UI element grounding ("Run" button pixel coordinates).
5. Closed-loop visual action workflow:
   Screenshot -> Locate "Run" -> Coordinates -> Mouse action -> Screenshot -> Verify.
"""

import os
import unittest

from jarvis.subsystems.vision.screen_capture import ScreenCapturer
from jarvis.subsystems.vision.desktop_controller import DesktopController
from jarvis.subsystems.vision.vision_model import VisionModel
from jarvis.subsystems.vision.ui_locator import UIElementLocator
from jarvis.tools.vision_tools import (
    CaptureScreenTool,
    InspectScreenTool,
    LocateUIElementTool,
    ClickScreenElementTool,
)
from jarvis.capabilities.goal_planner import GoalPlanner
from jarvis.core.task_manager import TaskManager
from jarvis.core.task_schemas import TaskStatus


class TestVisionSystem(unittest.TestCase):
    """Test suite for Phase 9 Vision subsystems and tools."""

    @classmethod
    def setUpClass(cls):
        cls.screenshots_dir = "data/test_screenshots"
        os.makedirs(cls.screenshots_dir, exist_ok=True)
        cls.capturer = ScreenCapturer(output_dir=cls.screenshots_dir)
        cls.controller = DesktopController()
        cls.vision_model = VisionModel()
        cls.locator = UIElementLocator()

    @classmethod
    def tearDownClass(cls):
        # Clean up test screenshots
        if os.path.exists(cls.screenshots_dir):
            for f in os.listdir(cls.screenshots_dir):
                try:
                    os.remove(os.path.join(cls.screenshots_dir, f))
                except Exception:
                    pass
            try:
                os.rmdir(cls.screenshots_dir)
            except Exception:
                pass

    def test_screen_capture_and_encoding(self):
        """Verify screen capture produces valid PNG file, positive dimensions, and base64."""
        screen = self.capturer.capture(simulated_content="Test Workspace Editor")
        self.assertTrue(os.path.exists(screen.image_path))
        self.assertGreater(os.path.getsize(screen.image_path), 0)
        self.assertGreater(screen.width, 0)
        self.assertGreater(screen.height, 0)
        self.assertTrue(len(screen.base64_data) > 100)

    def test_desktop_controller_bounds_and_click(self):
        """Verify DesktopController returns valid screen size and can simulate clicks."""
        w, h = self.controller.get_screen_size()
        self.assertGreater(w, 0)
        self.assertGreater(h, 0)

        # Move mouse to clamped coordinates and perform click
        move_ok = self.controller.move_to(150, 150)
        self.assertTrue(move_ok)

        click_ok = self.controller.click(150, 150)
        self.assertTrue(click_ok)

    def test_visual_diagnostics_whats_wrong(self):
        """Verify 'Jarvis, what's wrong?' detects unhandled exceptions on screen."""
        error_context = (
            "Traceback (most recent call last):\n"
            "  File \"d:/JARVIS/server.py\", line 18, in <module>\n"
            "    import missing_dependency\n"
            "ModuleNotFoundError: No module named 'missing_dependency'\n"
            "[Process exited with code 1]"
        )
        screen = self.capturer.capture(simulated_content=error_context)
        diagnosis = self.vision_model.diagnose_whats_wrong(screen)
        self.assertIn("ModuleNotFoundError", diagnosis)
        self.assertIn("identified the following issue", diagnosis.lower())

        # Test stable screen diagnosis
        clean_screen = self.capturer.capture(simulated_content="Build complete. Server running on port 8080.")
        clean_diagnosis = self.vision_model.diagnose_whats_wrong(clean_screen)
        self.assertIn("normal", clean_diagnosis.lower())

    def test_ui_element_locator(self):
        """Verify UIElementLocator grounds 'Run' and 'Debug' buttons into pixel coordinates."""
        screen = self.capturer.capture(simulated_content="VS Code Editor with Run & Debug toolbar")

        # Locate "Run"
        run_coords = self.locator.locate(screen, "Run")
        self.assertIsNotNone(run_coords)
        self.assertEqual(run_coords.label, "Run")
        self.assertGreater(run_coords.x, 0)
        self.assertGreater(run_coords.y, 0)

        # Locate "Debug"
        dbg_coords = self.locator.locate(screen, "Debug")
        self.assertIsNotNone(dbg_coords)
        self.assertEqual(dbg_coords.label, "Debug")

    def test_vision_tools_execution_and_verification(self):
        """Verify BaseTool implementations for vision subsystem."""
        # 1. CaptureScreenTool
        cap_tool = CaptureScreenTool(capturer=self.capturer)
        cap_res = cap_tool.execute(simulated_content="Tool Test Screen")
        self.assertTrue(cap_res.success)
        cap_ver = cap_tool.verify({}, cap_res)
        self.assertTrue(cap_ver.verified)

        # 2. InspectScreenTool
        insp_tool = InspectScreenTool(capturer=self.capturer, vision_model=self.vision_model)
        insp_res = insp_tool.execute(prompt="What's wrong?", simulated_content="SyntaxError: invalid syntax in test.py:10")
        self.assertTrue(insp_res.success)
        self.assertIn("SyntaxError", insp_res.output["diagnosis"])
        insp_ver = insp_tool.verify({}, insp_res)
        self.assertTrue(insp_ver.verified)

        # 3. LocateUIElementTool
        loc_tool = LocateUIElementTool(capturer=self.capturer, locator=self.locator)
        loc_res = loc_tool.execute(label="Run")
        self.assertTrue(loc_res.success)
        self.assertIn("x", loc_res.output)
        self.assertIn("y", loc_res.output)
        loc_ver = loc_tool.verify({}, loc_res)
        self.assertTrue(loc_ver.verified)

        # 4. ClickScreenElementTool
        click_tool = ClickScreenElementTool(capturer=self.capturer, locator=self.locator, controller=self.controller)
        click_res = click_tool.execute(label="Run")
        self.assertTrue(click_res.success)
        click_ver = click_tool.verify({}, click_res)
        self.assertTrue(click_ver.verified)

    def test_closed_loop_click_run_button_workflow(self):
        """Verify the complete 6-step closed-loop visual desktop plan:
        Screenshot -> Locate 'Run' -> Coordinates -> Mouse action -> Screenshot -> Verify.
        """
        task_db = "data/test_vision_task_manager.db"
        tm = TaskManager(db_path=task_db)
        planner = GoalPlanner(task_manager=tm)

        user_prompt = "Click the Run button."
        self.assertTrue(GoalPlanner.is_visual_click_goal(user_prompt))
        target_label = GoalPlanner.extract_click_target(user_prompt)
        self.assertEqual(target_label, "Run")

        # Create the plan
        plan = planner.create_visual_click_plan(
            objective=user_prompt,
            target_label=target_label,
            simulated_content="IDE Window with active Run button",
        )
        self.assertEqual(len(plan.subtasks), 6)
        self.assertEqual(plan.subtasks[0].name, "Screenshot")
        self.assertEqual(plan.subtasks[1].name, 'Locate "Run"')
        self.assertEqual(plan.subtasks[2].name, "Coordinates")
        self.assertEqual(plan.subtasks[3].name, "Mouse action")
        self.assertEqual(plan.subtasks[4].name, "Screenshot")
        self.assertEqual(plan.subtasks[5].name, "Verify")

        # Execute the plan
        executed_plan = planner.execute_plan(plan)

        # Verify all 6 subtasks succeeded
        for st in executed_plan.subtasks:
            self.assertEqual(st.status, "SUCCESS", f"Subtask {st.task_num} ({st.name}) failed: {st.status_message}")

        # Verify final state in TaskManager
        final_task = tm.get_task(plan.task_id)
        self.assertEqual(final_task.status, TaskStatus.COMPLETED)
        self.assertEqual(final_task.current_step, 6)
        self.assertIn('Done. Located "Run"', executed_plan.final_summary)

        # Clean up test db
        if os.path.exists(task_db):
            try:
                os.remove(task_db)
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()
