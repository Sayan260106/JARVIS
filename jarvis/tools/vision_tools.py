"""Vision and Desktop Automation Tools for JARVIS.

Standardized BaseTool implementations wrapping ScreenCapturer, VisionModel,
UIElementLocator, and DesktopController.
"""

from __future__ import annotations
import os
import time
from typing import Any, Dict, Optional

from jarvis.tools.base import BaseTool, RiskLevel, ToolParameter, ToolResult, ToolVerification
from jarvis.subsystems.vision.screen_capture import ScreenCapturer
from jarvis.subsystems.vision.desktop_controller import DesktopController
from jarvis.subsystems.vision.vision_model import VisionModel
from jarvis.subsystems.vision.ui_locator import UIElementLocator


class CaptureScreenTool(BaseTool):
    """Captures a screenshot of the active desktop screen."""
    name = "capture_screen"
    description = "Captures the desktop screen and returns the saved PNG image path and dimensions."
    risk_level = RiskLevel.LOW
    parameters = {
        "save_path": ToolParameter("save_path", "string", "Optional target filepath for screenshot PNG.", required=False),
        "simulated_content": ToolParameter("simulated_content", "string", "Optional simulated content for headless environments.", required=False),
    }

    def __init__(self, capturer: Optional[ScreenCapturer] = None):
        self.capturer = capturer or ScreenCapturer()

    def execute(self, save_path: Optional[str] = None, simulated_content: Optional[str] = None, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        try:
            screen = self.capturer.capture(save_path=save_path, simulated_content=simulated_content)
            data = {
                "image_path": screen.image_path,
                "width": screen.width,
                "height": screen.height,
                "source": screen.source,
            }
            return ToolResult(
                success=True,
                output=data,
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e),
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if not result.success or not result.output:
            return ToolVerification(verified=False, details="Screenshot capture failed.")
        img_path = result.output.get("image_path", "")
        exists = os.path.exists(img_path) and os.path.getsize(img_path) > 0
        return ToolVerification(
            verified=exists,
            details=f"Screenshot verified on disk: {img_path} ({os.path.getsize(img_path)} bytes)" if exists else "Screenshot missing",
        )


class InspectScreenTool(BaseTool):
    """Visually inspects the active screen using multimodal vision models."""
    name = "inspect_screen"
    description = "Visually inspects the desktop screen to diagnose errors, summarize state, or answer 'what's wrong?'."
    risk_level = RiskLevel.LOW
    parameters = {
        "prompt": ToolParameter("prompt", "string", "Diagnostic question or inspection instruction.", required=False, default="What is on the screen and what's wrong?"),
        "simulated_content": ToolParameter("simulated_content", "string", "Optional simulated screen context.", required=False),
    }

    def __init__(
        self,
        capturer: Optional[ScreenCapturer] = None,
        vision_model: Optional[VisionModel] = None,
    ):
        self.capturer = capturer or ScreenCapturer()
        self.vision_model = vision_model or VisionModel()

    def execute(
        self,
        prompt: str = "What is on the screen and what's wrong?",
        simulated_content: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        start_t = time.perf_counter()
        try:
            screen = self.capturer.capture(simulated_content=simulated_content)
            diagnosis = self.vision_model.diagnose_whats_wrong(screen)
            analysis = self.vision_model.analyze_screen(screen, prompt=prompt)
            data = {
                "diagnosis": diagnosis,
                "has_error": analysis.has_error,
                "issues": analysis.detected_issues,
                "suggested_action": analysis.suggested_action,
                "image_path": screen.image_path,
            }
            return ToolResult(
                success=True,
                output=data,
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e),
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        verified = result.success and result.output is not None and bool(result.output.get("diagnosis"))
        return ToolVerification(
            verified=verified,
            details="Screen diagnosis formulated." if verified else "Missing diagnosis.",
        )


class LocateUIElementTool(BaseTool):
    """Locates a target UI element on screen and returns its coordinates."""
    name = "locate_ui_element"
    description = "Locates target UI button/element (e.g. 'Run') on screen and returns its (x, y) coordinates."
    risk_level = RiskLevel.LOW
    parameters = {
        "label": ToolParameter("label", "string", "Element label or text (e.g., 'Run', 'Debug', 'Close').", required=True),
        "simulated_content": ToolParameter("simulated_content", "string", "Optional simulated screen context.", required=False),
    }

    def __init__(
        self,
        capturer: Optional[ScreenCapturer] = None,
        locator: Optional[UIElementLocator] = None,
    ):
        self.capturer = capturer or ScreenCapturer()
        self.locator = locator or UIElementLocator()

    def execute(self, label: str = "Run", simulated_content: Optional[str] = None, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        try:
            screen = self.capturer.capture(simulated_content=simulated_content)
            coords = self.locator.locate(screen, label)
            if not coords:
                return ToolResult(
                    success=False,
                    output={"label": label},
                    error=f"UI element '{label}' could not be located on the current screen.",
                    duration_ms=(time.perf_counter() - start_t) * 1000,
                )
            data = {
                "label": coords.label,
                "x": coords.x,
                "y": coords.y,
                "width": coords.width,
                "height": coords.height,
                "confidence": coords.confidence,
                "source": coords.source,
            }
            return ToolResult(
                success=True,
                output=data,
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e),
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if not result.success or not result.output:
            return ToolVerification(verified=False, details="Location failed.")
        has_coords = "x" in result.output and "y" in result.output
        return ToolVerification(
            verified=has_coords,
            details=f"Coordinates verified: ({result.output.get('x')}, {result.output.get('y')})" if has_coords else "Missing coordinates",
        )


class ClickScreenElementTool(BaseTool):
    """Executes closed-loop visual element interaction: Locate -> Click -> Screenshot -> Verify."""
    name = "click_screen_element"
    description = "Visually finds target element, moves cursor, clicks, and verifies action with follow-up screenshot."
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "label": ToolParameter("label", "string", "Element label to click (e.g., 'Run').", required=True),
        "x": ToolParameter("x", "integer", "Optional direct x coordinate (skips locate if provided).", required=False),
        "y": ToolParameter("y", "integer", "Optional direct y coordinate.", required=False),
        "simulated_content": ToolParameter("simulated_content", "string", "Optional simulated screen context.", required=False),
    }

    def __init__(
        self,
        capturer: Optional[ScreenCapturer] = None,
        locator: Optional[UIElementLocator] = None,
        controller: Optional[DesktopController] = None,
    ):
        self.capturer = capturer or ScreenCapturer()
        self.locator = locator or UIElementLocator()
        self.controller = controller or DesktopController()

    def execute(
        self,
        label: str = "Run",
        x: Optional[int] = None,
        y: Optional[int] = None,
        simulated_content: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        start_t = time.perf_counter()
        target_x = x
        target_y = y
        try:
            # 1. Capture initial screen if coordinates not provided
            initial_screen = self.capturer.capture(simulated_content=simulated_content)
            if target_x is None or target_y is None:
                coords = self.locator.locate(initial_screen, label)
                if not coords:
                    return ToolResult(
                        success=False,
                        output={"label": label},
                        error=f"Could not find element '{label}' to click.",
                        duration_ms=(time.perf_counter() - start_t) * 1000,
                    )
                target_x = coords.x
                target_y = coords.y

            # 2. Mouse action: move and click
            click_success = self.controller.click(target_x, target_y)

            # 3. Capture post-action screen for verification
            post_screen = self.capturer.capture(simulated_content=simulated_content or "Post-click active state")

            data = {
                "label": label,
                "clicked_at": (target_x, target_y),
                "initial_screenshot": initial_screen.image_path,
                "verification_screenshot": post_screen.image_path,
            }
            return ToolResult(
                success=click_success,
                output=data,
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e),
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        verified = result.success and result.output is not None and bool(result.output.get("verification_screenshot"))
        return ToolVerification(
            verified=verified,
            details="Mouse click executed and follow-up screenshot captured." if verified else "Click verification failed.",
        )
