"""Vision and Desktop Automation Tools for JARVIS.

Standardized BaseTool implementations wrapping ScreenCapturer, VisionModel,
OCREngine, UIDetector, VisualGroundingEngine, VisualVerifier, and VisualComputerAgent.
"""

from __future__ import annotations
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from jarvis.tools.base import BaseTool, RiskLevel, ToolParameter, ToolResult, ToolVerification
from jarvis.subsystems.vision.screen_capture import ScreenCapturer, CapturedScreen
from jarvis.subsystems.vision.desktop_controller import DesktopController
from jarvis.subsystems.vision.vision_model import VisionModel
from jarvis.subsystems.vision.ui_locator import UIElementLocator
from jarvis.subsystems.vision.ocr_engine import OCREngine, OCRResult, BoundingBox
from jarvis.subsystems.vision.ui_detector import UIDetector, DetectedUIElement
from jarvis.subsystems.vision.visual_grounding import VisualGroundingEngine, GroundedElement
from jarvis.subsystems.vision.visual_verifier import VisualVerifier, VisualVerificationResult
from jarvis.subsystems.vision.computer_controller import VisualComputerAgent, VisualActionResult


class CaptureScreenTool(BaseTool):
    """Captures a screenshot of the active desktop screen."""
    name = "capture_screen"
    description = "Captures the desktop screen and returns the saved PNG image path, dimensions, and base64 representation."
    risk_level = RiskLevel.LOW
    parameters = {
        "save_path": ToolParameter("save_path", "string", "Optional target filepath for screenshot PNG.", required=False),
        "bounding_box": ToolParameter("bounding_box", "list", "Optional [left, top, right, bottom] crop box.", required=False),
        "simulated_content": ToolParameter("simulated_content", "string", "Optional simulated content for headless environments.", required=False),
    }

    def __init__(self, capturer: Optional[ScreenCapturer] = None):
        self.capturer = capturer or ScreenCapturer()

    def execute(self, *args, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        params = args[0] if args and isinstance(args[0], dict) else kwargs
        save_path = params.get("save_path")
        bbox = params.get("bounding_box")
        if isinstance(bbox, list) and len(bbox) == 4:
            bbox = tuple(bbox)
        simulated_content = params.get("simulated_content")

        try:
            screen = self.capturer.capture(save_path=save_path, bounding_box=bbox, simulated_content=simulated_content)
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


class CaptureRegionTool(BaseTool):
    """Captures a targeted sub-region of the screen or an active application window."""
    name = "capture_region"
    description = "Captures a specific screen crop region [left, top, right, bottom] or window by title."
    risk_level = RiskLevel.LOW
    parameters = {
        "bounding_box": ToolParameter("bounding_box", "list", "Crop coordinates [left, top, right, bottom].", required=False),
        "window_title": ToolParameter("window_title", "string", "Optional window title to capture.", required=False),
        "save_path": ToolParameter("save_path", "string", "Target save path.", required=False),
        "simulated_content": ToolParameter("simulated_content", "string", "Simulated frame content for test environments.", required=False),
    }

    def __init__(self, capturer: Optional[ScreenCapturer] = None):
        self.capturer = capturer or ScreenCapturer()

    def execute(self, *args, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        params = args[0] if args and isinstance(args[0], dict) else kwargs
        bbox = params.get("bounding_box")
        if isinstance(bbox, list) and len(bbox) == 4:
            bbox = tuple(bbox)
        w_title = params.get("window_title")
        save_path = params.get("save_path")
        simulated_content = params.get("simulated_content")

        try:
            if w_title:
                screen = self.capturer.capture_window(w_title, save_path=save_path, simulated_content=simulated_content)
            elif bbox:
                screen = self.capturer.capture_region(bbox, save_path=save_path, simulated_content=simulated_content)
            else:
                screen = self.capturer.capture(save_path=save_path, simulated_content=simulated_content)

            data = {
                "image_path": screen.image_path,
                "width": screen.width,
                "height": screen.height,
                "source": screen.source,
                "crop_region": list(screen.crop_region) if screen.crop_region else None,
            }
            return ToolResult(success=True, output=data, duration_ms=(time.perf_counter() - start_t) * 1000)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.perf_counter() - start_t) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        verified = result.success and result.output is not None and os.path.exists(result.output.get("image_path", ""))
        return ToolVerification(verified=verified, details="Region screenshot captured." if verified else "Region capture failed.")


class ScreenOCRTool(BaseTool):
    """Performs native optical character recognition on screen or region."""
    name = "screen_ocr"
    description = "Extracts text and exact pixel bounding boxes for words/lines on screen or an image."
    risk_level = RiskLevel.LOW
    parameters = {
        "image_path": ToolParameter("image_path", "string", "Optional path to existing screenshot. If omitted, captures current screen.", required=False),
        "search_text": ToolParameter("search_text", "string", "Optional phrase to locate within OCR results.", required=False),
        "simulated_content": ToolParameter("simulated_content", "string", "Optional simulated screen text for testing.", required=False),
    }

    def __init__(self, capturer: Optional[ScreenCapturer] = None, ocr_engine: Optional[OCREngine] = None):
        self.capturer = capturer or ScreenCapturer()
        self.ocr = ocr_engine or OCREngine()

    def execute(self, *args, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        params = args[0] if args and isinstance(args[0], dict) else kwargs
        img_path = params.get("image_path")
        search_text = params.get("search_text")
        simulated_content = params.get("simulated_content")

        try:
            if not img_path:
                screen = self.capturer.capture(simulated_content=simulated_content)
                img_path = screen.image_path
                sim_ctx = screen.simulated_context
            else:
                sim_ctx = simulated_content

            res = self.ocr.recognize(img_path, simulated_context=sim_ctx)
            found_coords = None
            if search_text:
                found_bbox = res.find_phrase(search_text)
                if found_bbox:
                    found_coords = {"x": found_bbox.x, "y": found_bbox.y, "center": list(found_bbox.center)}

            data = {
                "text": res.text,
                "lines_count": len(res.lines),
                "words_count": len(res.words),
                "engine": res.engine,
                "image_path": img_path,
                "search_result": found_coords,
                "words": [w.to_dict() for w in res.words[:20]],
            }
            return ToolResult(success=True, output=data, duration_ms=(time.perf_counter() - start_t) * 1000)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.perf_counter() - start_t) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        verified = result.success and result.output is not None
        return ToolVerification(verified=verified, details="OCR extraction complete." if verified else "OCR failed.")


class DetectUIElementsTool(BaseTool):
    """Detects interactive UI buttons, window controls, and their colors."""
    name = "detect_ui_elements"
    description = "Scans screen or image to locate buttons and controls, identifying their text labels, bounding boxes, and colors."
    risk_level = RiskLevel.LOW
    parameters = {
        "color_filter": ToolParameter("color_filter", "string", "Optional color to filter by (e.g., 'blue', 'green', 'red').", required=False),
        "simulated_content": ToolParameter("simulated_content", "string", "Optional simulated content for test frames.", required=False),
    }

    def __init__(self, capturer: Optional[ScreenCapturer] = None, detector: Optional[UIDetector] = None):
        self.capturer = capturer or ScreenCapturer()
        self.detector = detector or UIDetector()

    def execute(self, *args, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        params = args[0] if args and isinstance(args[0], dict) else kwargs
        color_filter = params.get("color_filter")
        sim_content = params.get("simulated_content")

        try:
            screen = self.capturer.capture(simulated_content=sim_content)
            elements = self.detector.detect_elements(screen)

            if color_filter:
                elements = [e for e in elements if e.color.lower() == color_filter.lower()]

            data = {
                "elements_count": len(elements),
                "elements": [e.to_dict() for e in elements],
                "image_path": screen.image_path,
            }
            return ToolResult(success=True, output=data, duration_ms=(time.perf_counter() - start_t) * 1000)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.perf_counter() - start_t) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        verified = result.success and result.output is not None
        return ToolVerification(verified=verified, details=f"Detected {result.output.get('elements_count', 0)} UI element(s).")


class VisualGroundingTool(BaseTool):
    """Grounds natural language descriptions (e.g. 'Click the blue submit button') to pixel coordinates."""
    name = "visual_grounding"
    description = "Resolves a natural language UI target (e.g. 'blue submit button', 'cancel button') to exact screen coordinates (x, y)."
    risk_level = RiskLevel.LOW
    parameters = {
        "query": ToolParameter("query", "string", "Target element description (e.g., 'blue submit button', 'Run button').", required=True),
        "simulated_content": ToolParameter("simulated_content", "string", "Optional simulated screen content for testing.", required=False),
    }

    def __init__(self, capturer: Optional[ScreenCapturer] = None, grounder: Optional[VisualGroundingEngine] = None):
        self.capturer = capturer or ScreenCapturer()
        self.grounder = grounder or VisualGroundingEngine()

    def execute(self, *args, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        params = args[0] if args and isinstance(args[0], dict) else kwargs
        query = params.get("query", "Run")
        sim_content = params.get("simulated_content")

        try:
            screen = self.capturer.capture(simulated_content=sim_content)
            res = self.grounder.ground(screen, query)
            if not res:
                return ToolResult(
                    success=False,
                    output={"query": query},
                    error=f"Could not visually ground target element for: '{query}'",
                    duration_ms=(time.perf_counter() - start_t) * 1000,
                )

            data = res.to_dict()
            data["image_path"] = screen.image_path
            return ToolResult(success=True, output=data, duration_ms=(time.perf_counter() - start_t) * 1000)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.perf_counter() - start_t) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        verified = result.success and result.output is not None and "center_x" in result.output
        return ToolVerification(
            verified=verified,
            details=f"Grounded to ({result.output.get('center_x')}, {result.output.get('center_y')})" if verified else "Grounding failed.",
        )


class VisualComputerActionTool(BaseTool):
    """Executes closed-loop visual desktop computer control: Capture -> Ground -> Action -> Capture -> Verify."""
    name = "visual_computer_action"
    description = "Closed-loop computer action: visually locates target element, executes click or text input, and verifies visual state change."
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "target": ToolParameter("target", "string", "Element description to interact with (e.g., 'Click the blue submit button', 'Cancel').", required=True),
        "action_type": ToolParameter("action_type", "string", "Action type: 'click', 'double_click', 'right_click', 'move', 'type'.", required=False, default="click"),
        "text_to_type": ToolParameter("text_to_type", "string", "Text string to type if action_type is 'type'.", required=False),
        "simulated_content": ToolParameter("simulated_content", "string", "Optional pre-action simulated frame.", required=False),
        "simulated_post_content": ToolParameter("simulated_post_content", "string", "Optional post-action simulated frame.", required=False),
    }

    def __init__(self, agent: Optional[VisualComputerAgent] = None):
        self.agent = agent or VisualComputerAgent()

    def execute(self, *args, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        params = args[0] if args and isinstance(args[0], dict) else kwargs
        target = params.get("target", "Run")
        action_type = params.get("action_type", "click")
        text_to_type = params.get("text_to_type")
        sim_content = params.get("simulated_content")
        sim_post_content = params.get("simulated_post_content")

        try:
            res = self.agent.execute_action(
                target_description=target,
                action_type=action_type,
                text_to_type=text_to_type,
                simulated_content=sim_content,
                simulated_post_content=sim_post_content,
            )
            return ToolResult(
                success=res.success,
                output=res.to_dict(),
                error=None if res.success else res.summary,
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.perf_counter() - start_t) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        verified = result.success and result.output is not None and result.output.get("verification", {}).get("verified", False)
        return ToolVerification(
            verified=verified,
            details="Visual computer action executed and verified." if verified else "Action or visual verification failed.",
        )


class VisualVerifyTool(BaseTool):
    """Compares two screenshots to verify whether a visual state change took effect."""
    name = "visual_verify"
    description = "Compares screenshot before and screenshot after an action to measure pixel delta and verify state transition."
    risk_level = RiskLevel.LOW
    parameters = {
        "before_image_path": ToolParameter("before_image_path", "string", "Filepath of pre-action screenshot.", required=True),
        "after_image_path": ToolParameter("after_image_path", "string", "Filepath of post-action screenshot.", required=True),
    }

    def __init__(self, verifier: Optional[VisualVerifier] = None):
        self.verifier = verifier or VisualVerifier()

    def execute(self, *args, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        params = args[0] if args and isinstance(args[0], dict) else kwargs
        before_path = params.get("before_image_path", "")
        after_path = params.get("after_image_path", "")

        try:
            b_screen = CapturedScreen(
                image_path=before_path, width=1280, height=800, base64_data="", source="file", timestamp=time.time()
            )
            a_screen = CapturedScreen(
                image_path=after_path, width=1280, height=800, base64_data="", source="file", timestamp=time.time() + 1
            )
            res = self.verifier.verify_action(b_screen, a_screen)
            return ToolResult(success=res.verified, output=res.to_dict(), duration_ms=(time.perf_counter() - start_t) * 1000)
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.perf_counter() - start_t) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        verified = result.success and result.output is not None and result.output.get("verified", False)
        return ToolVerification(
            verified=verified,
            details=result.output.get("summary", "") if result.output else "Verification failed.",
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

    def execute(self, *args, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        params = args[0] if args and isinstance(args[0], dict) else kwargs
        prompt = params.get("prompt", "What is on the screen and what's wrong?")
        simulated_content = params.get("simulated_content")

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

    def execute(self, *args, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        params = args[0] if args and isinstance(args[0], dict) else kwargs
        label = params.get("label", "Run")
        simulated_content = params.get("simulated_content")

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

    def execute(self, *args, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        params = args[0] if args and isinstance(args[0], dict) else kwargs
        label = params.get("label", "Run")
        x = params.get("x")
        y = params.get("y")
        simulated_content = params.get("simulated_content")

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
