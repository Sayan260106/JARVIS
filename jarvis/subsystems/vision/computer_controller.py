"""Visual Computer Controller & Closed-Loop Computer-Use Agent for JARVIS.

Coordinates the complete visual automation loop:
Screen Capture -> Visual Grounding -> Desktop Action -> Follow-up Capture -> Visual Verification.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import time
from typing import Any, Dict, Optional, Tuple

from jarvis.subsystems.vision.screen_capture import CapturedScreen, ScreenCapturer
from jarvis.subsystems.vision.desktop_controller import DesktopController
from jarvis.subsystems.vision.visual_grounding import GroundedElement, VisualGroundingEngine
from jarvis.subsystems.vision.visual_verifier import VisualVerificationResult, VisualVerifier
from jarvis.subsystems.vision.ocr_engine import OCREngine


@dataclass
class VisualActionResult:
    """Represents the complete result of a closed-loop visual interaction."""
    success: bool
    action_type: str
    target_query: str
    grounded_element: Optional[GroundedElement]
    coordinates: Optional[Tuple[int, int]]
    screenshot_before_path: str
    screenshot_after_path: str
    verification: VisualVerificationResult
    summary: str
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "action_type": self.action_type,
            "target_query": self.target_query,
            "grounded_element": self.grounded_element.to_dict() if self.grounded_element else None,
            "coordinates": list(self.coordinates) if self.coordinates else None,
            "screenshot_before": self.screenshot_before_path,
            "screenshot_after": self.screenshot_after_path,
            "verification": self.verification.to_dict(),
            "summary": self.summary,
            "duration_ms": round(self.duration_ms, 2),
        }


class VisualComputerAgent:
    """Agent executing closed-loop visual computer control."""

    def __init__(
        self,
        capturer: Optional[ScreenCapturer] = None,
        controller: Optional[DesktopController] = None,
        grounding_engine: Optional[VisualGroundingEngine] = None,
        verifier: Optional[VisualVerifier] = None,
        ocr_engine: Optional[OCREngine] = None,
    ):
        self.ocr = ocr_engine or OCREngine()
        self.capturer = capturer or ScreenCapturer()
        self.controller = controller or DesktopController()
        self.grounder = grounding_engine or VisualGroundingEngine(ocr_engine=self.ocr)
        self.verifier = verifier or VisualVerifier(ocr_engine=self.ocr)

    def execute_action(
        self,
        target_description: str,
        action_type: str = "click",
        text_to_type: Optional[str] = None,
        direct_coordinates: Optional[Tuple[int, int]] = None,
        wait_after_ms: int = 150,
        simulated_content: Optional[str] = None,
        simulated_post_content: Optional[str] = None,
    ) -> VisualActionResult:
        """Executes a complete closed-loop visual computer action.

        Args:
            target_description: Element query (e.g., "Click the blue submit button").
            action_type: "click", "double_click", "right_click", "move", "type".
            text_to_type: Text string to type if action_type is "type".
            direct_coordinates: Optional direct (x, y) coordinates skipping grounding.
            wait_after_ms: Milliseconds to wait before capturing follow-up screenshot.
            simulated_content: Optional synthetic desktop frame for testing before action.
            simulated_post_content: Optional synthetic desktop frame for testing after action.

        Returns:
            VisualActionResult with full audit trail and visual verification.
        """
        start_t = time.perf_counter()

        # Step 1: Capture initial screenshot
        before_screen = self.capturer.capture(simulated_content=simulated_content)

        # Step 2: Visual Grounding to find target coordinates
        grounded: Optional[GroundedElement] = None
        target_x, target_y = None, None

        if direct_coordinates:
            target_x, target_y = direct_coordinates
        else:
            grounded = self.grounder.ground(before_screen, target_description)
            if grounded:
                target_x, target_y = grounded.center_x, grounded.center_y
            else:
                dur = (time.perf_counter() - start_t) * 1000
                return VisualActionResult(
                    success=False,
                    action_type=action_type,
                    target_query=target_description,
                    grounded_element=None,
                    coordinates=None,
                    screenshot_before_path=before_screen.image_path,
                    screenshot_after_path="",
                    verification=VisualVerificationResult(
                        verified=False,
                        diff_percentage=0.0,
                        target_region_changed=False,
                        summary=f"Could not visually ground target '{target_description}'.",
                    ),
                    summary=f"Failed to locate UI element matching '{target_description}' on screen.",
                    duration_ms=dur,
                )

        # Step 3: Perform Desktop Action via DesktopController
        act_ok = True
        act_norm = action_type.lower()

        if act_norm == "click":
            act_ok = self.controller.click(target_x, target_y, button="left")
        elif act_norm == "double_click":
            act_ok = self.controller.click(target_x, target_y, button="left", double_click=True)
        elif act_norm == "right_click":
            act_ok = self.controller.click(target_x, target_y, button="right")
        elif act_norm == "move":
            act_ok = self.controller.move_to(target_x, target_y)
        elif act_norm == "type":
            act_ok = self.controller.click(target_x, target_y)
            if text_to_type:
                time.sleep(0.05)
                act_ok = self.controller.type_text(text_to_type)
        else:
            act_ok = self.controller.click(target_x, target_y)

        # Step 4: Stabilization wait
        if wait_after_ms > 0:
            time.sleep(wait_after_ms / 1000.0)

        # Step 5: Capture follow-up screenshot
        post_context = simulated_post_content or (
            f"{simulated_content or 'Active Workspace'}\n[Action Executed: {act_norm} at ({target_x}, {target_y})]"
        )
        after_screen = self.capturer.capture(simulated_content=post_context)

        # Step 6: Visual Verification
        target_box = grounded.bbox if grounded else None
        ver_result = self.verifier.verify_action(before_screen, after_screen, target_bbox=target_box)

        overall_success = act_ok and ver_result.verified
        dur = (time.perf_counter() - start_t) * 1000

        elem_desc = f"'{grounded.label}' ({grounded.color} {grounded.element_type})" if grounded else f"({target_x}, {target_y})"
        summary = (
            f"Successfully executed {act_norm} on {elem_desc} at ({target_x}, {target_y}). "
            f"{ver_result.summary}"
        )

        return VisualActionResult(
            success=overall_success,
            action_type=act_norm,
            target_query=target_description,
            grounded_element=grounded,
            coordinates=(target_x, target_y),
            screenshot_before_path=before_screen.image_path,
            screenshot_after_path=after_screen.image_path,
            verification=ver_result,
            summary=summary,
            duration_ms=dur,
        )
