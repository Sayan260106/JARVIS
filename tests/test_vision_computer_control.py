"""Unit and integration tests for JARVIS Phase 7: Vision-Based Computer Control.

Verifies:
1. Screen and region capture (full monitor & crop regions).
2. Local OCR engine (lines, words, and pixel bounding boxes).
3. UI element detection and color analysis (e.g. blue, green, red buttons).
4. Visual grounding of natural language requests ("Click the blue submit button").
5. Closed-loop action execution: Screenshot -> Ground -> Action -> Screenshot -> Visual Verification.
6. Differential visual verifier (pixel delta & state transition).
7. Typed BaseTools registration and execution.
8. Capability layer integration (Understand & Plan).
"""

import os
import shutil
import unittest

from jarvis.subsystems.vision.screen_capture import ScreenCapturer, CapturedScreen
from jarvis.subsystems.vision.ocr_engine import OCREngine, BoundingBox
from jarvis.subsystems.vision.ui_detector import UIDetector, DetectedUIElement
from jarvis.subsystems.vision.visual_grounding import VisualGroundingEngine, GroundedElement
from jarvis.subsystems.vision.visual_verifier import VisualVerifier, VisualVerificationResult
from jarvis.subsystems.vision.computer_controller import VisualComputerAgent, VisualActionResult
from jarvis.subsystems.vision.desktop_controller import DesktopController
from jarvis.tools.vision_tools import (
    CaptureScreenTool,
    CaptureRegionTool,
    ScreenOCRTool,
    DetectUIElementsTool,
    VisualGroundingTool,
    VisualComputerActionTool,
    VisualVerifyTool,
)
from jarvis.tools import get_default_registry
from jarvis.capabilities.understand import DefaultUnderstandCapability
from jarvis.capabilities.plan import DefaultPlanCapability
from jarvis.core.schemas import SubsystemType, IntentCategory
from jarvis.core.state import AgentSessionState


class TestVisionComputerControl(unittest.TestCase):
    """Test suite for Phase 7 Vision-Based Computer Control."""

    @classmethod
    def setUpClass(cls):
        cls.test_dir = "data/test_phase7_vision"
        os.makedirs(cls.test_dir, exist_ok=True)
        cls.capturer = ScreenCapturer(output_dir=cls.test_dir)
        cls.ocr = OCREngine()
        cls.detector = UIDetector(ocr_engine=cls.ocr)
        cls.grounder = VisualGroundingEngine(ui_detector=cls.detector, ocr_engine=cls.ocr)
        cls.verifier = VisualVerifier(ocr_engine=cls.ocr, diff_output_dir=os.path.join(cls.test_dir, "diffs"))
        cls.controller = DesktopController()
        cls.agent = VisualComputerAgent(
            capturer=cls.capturer,
            controller=cls.controller,
            grounding_engine=cls.grounder,
            verifier=cls.verifier,
            ocr_engine=cls.ocr,
        )

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_dir):
            shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_screen_and_region_capture(self):
        """Verify full screen and targeted region capture."""
        # 1. Full capture
        screen = self.capturer.capture(simulated_content="Phase 7 Screen Frame")
        self.assertTrue(os.path.exists(screen.image_path))
        self.assertGreater(os.path.getsize(screen.image_path), 0)
        self.assertEqual(screen.width, 1280)
        self.assertEqual(screen.height, 800)
        self.assertTrue(len(screen.base64_data) > 100)

        # 2. Region capture
        region = self.capturer.capture_region((100, 100, 400, 300), simulated_content="Region Frame")
        self.assertTrue(os.path.exists(region.image_path))
        self.assertEqual(region.width, 300)
        self.assertEqual(region.height, 200)
        self.assertEqual(region.crop_region, (100, 100, 400, 300))

    def test_ocr_engine_words_and_boxes(self):
        """Verify OCR extracts words, lines, and bounding boxes."""
        sim_text = "System Form Ready\nSubmit Details Now"
        screen = self.capturer.capture(simulated_content=sim_text)
        result = self.ocr.recognize(screen.image_path, simulated_context=sim_text)

        self.assertGreater(len(result.lines), 0)
        self.assertGreater(len(result.words), 0)

        # Search for specific word
        matches = result.find_words("Submit")
        self.assertGreater(len(matches), 0)
        submit_word = matches[0]
        self.assertEqual(submit_word.text, "Submit")
        self.assertGreater(submit_word.bbox.x, 0)
        self.assertGreater(submit_word.bbox.y, 0)

        # Search for phrase
        phrase_box = result.find_phrase("System Form Ready")
        self.assertIsNotNone(phrase_box)

    def test_ui_element_and_color_detection(self):
        """Verify UI detector locates controls and classifies colors (blue, green, red, gray)."""
        screen = self.capturer.capture(simulated_content="Form with Action Controls")
        elements = self.detector.detect_elements(screen)
        self.assertGreater(len(elements), 0)

        by_label = {e.label.lower(): e for e in elements}

        # Verify blue Submit button
        self.assertIn("submit", by_label)
        sub_elem = by_label["submit"]
        self.assertEqual(sub_elem.color, "blue")
        self.assertEqual(sub_elem.element_type, "button")
        self.assertGreater(sub_elem.center[0], 0)
        self.assertGreater(sub_elem.center[1], 0)

        # Verify green Run button
        self.assertIn("run", by_label)
        run_elem = by_label["run"]
        self.assertEqual(run_elem.color, "green")
        self.assertEqual(run_elem.element_type, "button")

        # Verify red Cancel button
        self.assertIn("cancel", by_label)
        can_elem = by_label["cancel"]
        self.assertEqual(can_elem.color, "red")

        # Verify gray Debug button
        self.assertIn("debug", by_label)
        dbg_elem = by_label["debug"]
        self.assertEqual(dbg_elem.color, "gray")

    def test_visual_grounding_blue_submit_button(self):
        """Verify visual grounding resolves 'Click the blue submit button' to center coordinates."""
        screen = self.capturer.capture(simulated_content="Active form waiting for submission")

        grounded = self.grounder.ground(screen, "Click the blue submit button")
        self.assertIsNotNone(grounded)
        self.assertEqual(grounded.label, "Submit")
        self.assertEqual(grounded.color, "blue")
        self.assertEqual(grounded.center_x, 150)
        self.assertEqual(grounded.center_y, 128)
        self.assertGreaterEqual(grounded.confidence, 0.90)

        # Test green run button
        run_grounded = self.grounder.ground(screen, "Click the green run button")
        self.assertIsNotNone(run_grounded)
        self.assertEqual(run_grounded.label, "Run")
        self.assertEqual(run_grounded.color, "green")
        self.assertEqual(run_grounded.center_x, 262)

    def test_visual_verifier_differential_check(self):
        """Verify differential visual verifier detects state transitions."""
        before = self.capturer.capture(simulated_content="Initial state")
        after = self.capturer.capture(simulated_content="State changed: Process Completed Successfully")

        ver = self.verifier.verify_action(before, after)
        self.assertTrue(ver.verified)
        self.assertGreater(ver.diff_percentage, 0.0)
        self.assertIn("SUCCESS", ver.summary)

    def test_closed_loop_visual_computer_action(self):
        """Verify complete closed-loop action execution: Screenshot -> Ground -> Action -> Screenshot -> Verify."""
        res = self.agent.execute_action(
            target_description="Click the blue submit button",
            action_type="click",
            simulated_content="Form awaiting submission",
            simulated_post_content="Form submission complete! Status 200 OK",
        )

        self.assertTrue(res.success)
        self.assertEqual(res.action_type, "click")
        self.assertIsNotNone(res.grounded_element)
        self.assertEqual(res.grounded_element.label, "Submit")
        self.assertEqual(res.grounded_element.color, "blue")
        self.assertEqual(res.coordinates, (150, 128))
        self.assertTrue(os.path.exists(res.screenshot_before_path))
        self.assertTrue(os.path.exists(res.screenshot_after_path))
        self.assertTrue(res.verification.verified)
        self.assertIn("Successfully executed click", res.summary)

    def test_typed_vision_tools_and_registry(self):
        """Verify all Phase 7 vision tools execute and are in default registry."""
        registry = get_default_registry()

        # 1. CaptureRegionTool
        cr_tool = registry.get("capture_region")
        self.assertIsNotNone(cr_tool)
        cr_res = cr_tool.execute({"bounding_box": [50, 50, 250, 250], "simulated_content": "Tool Test"})
        self.assertTrue(cr_res.success)
        self.assertTrue(cr_tool.verify({}, cr_res).verified)

        # 2. ScreenOCRTool
        ocr_tool = registry.get("screen_ocr")
        self.assertIsNotNone(ocr_tool)
        ocr_res = ocr_tool.execute({"search_text": "Submit", "simulated_content": "Form Ready\nSubmit Now"})
        self.assertTrue(ocr_res.success)
        self.assertTrue(ocr_tool.verify({}, ocr_res).verified)

        # 3. DetectUIElementsTool
        ui_tool = registry.get("detect_ui_elements")
        self.assertIsNotNone(ui_tool)
        ui_res = ui_tool.execute({"color_filter": "blue", "simulated_content": "Toolbar Canvas"})
        self.assertTrue(ui_res.success)
        self.assertGreater(ui_res.output["elements_count"], 0)
        self.assertEqual(ui_res.output["elements"][0]["color"], "blue")

        # 4. VisualGroundingTool
        vg_tool = registry.get("visual_grounding")
        self.assertIsNotNone(vg_tool)
        vg_res = vg_tool.execute({"query": "Click the blue submit button", "simulated_content": "Form Canvas"})
        self.assertTrue(vg_res.success)
        self.assertEqual(vg_res.output["label"], "Submit")
        self.assertEqual(vg_res.output["center_x"], 150)

        # 5. VisualComputerActionTool
        act_tool = registry.get("visual_computer_action")
        self.assertIsNotNone(act_tool)
        act_res = act_tool.execute(
            {
                "target": "Click the blue submit button",
                "simulated_content": "Before submission",
                "simulated_post_content": "After submission: SUCCESS",
            }
        )
        self.assertTrue(act_res.success)
        self.assertTrue(act_tool.verify({}, act_res).verified)

        # 6. VisualVerifyTool
        vv_tool = registry.get("visual_verify")
        self.assertIsNotNone(vv_tool)
        vv_res = vv_tool.execute(
            {
                "before_image_path": act_res.output["screenshot_before"],
                "after_image_path": act_res.output["screenshot_after"],
            }
        )
        self.assertTrue(vv_res.success)

    def test_capabilities_understand_and_plan_visual_action(self):
        """Verify Understand and Plan capabilities generate closed-loop visual steps."""
        u = DefaultUnderstandCapability()
        p = DefaultPlanCapability()
        state = AgentSessionState()

        # Test prompt
        prompt = "Click the blue submit button"
        obj = u.understand(prompt, {})
        self.assertEqual(obj.intent, IntentCategory.TASK_AUTOMATION)
        self.assertEqual(obj.extracted_entities.get("action"), "visual_computer_action")
        self.assertIn("submit", obj.extracted_entities.get("target").lower())

        # Test plan generation
        plan = p.plan(obj, state)
        self.assertEqual(len(plan.steps), 1)
        step = plan.steps[0]
        self.assertEqual(step.subsystem, SubsystemType.VISION)
        self.assertEqual(step.tool_name, "visual_computer_action")
        self.assertEqual(step.arguments.get("action_type"), "click")


if __name__ == "__main__":
    unittest.main()
