"""Vision and Desktop Computer-Use Subsystem for JARVIS.

Provides screen and region capture, Windows Media OCR, UI element and color detection,
visual grounding, closed-loop desktop actions, and differential visual verification.
"""

from jarvis.subsystems.vision.screen_capture import ScreenCapturer, CapturedScreen
from jarvis.subsystems.vision.desktop_controller import DesktopController
from jarvis.subsystems.vision.vision_model import VisionModel, VisionAnalysis
from jarvis.subsystems.vision.ui_locator import UIElementLocator, ElementCoordinates
from jarvis.subsystems.vision.ocr_engine import (
    OCREngine,
    OCRResult,
    OCRLine,
    OCRWord,
    BoundingBox,
)
from jarvis.subsystems.vision.ui_detector import UIDetector, DetectedUIElement
from jarvis.subsystems.vision.visual_grounding import (
    VisualGroundingEngine,
    GroundedElement,
)
from jarvis.subsystems.vision.visual_verifier import (
    VisualVerifier,
    VisualVerificationResult,
)
from jarvis.subsystems.vision.computer_controller import (
    VisualComputerAgent,
    VisualActionResult,
)

__all__ = [
    "ScreenCapturer",
    "CapturedScreen",
    "DesktopController",
    "VisionModel",
    "VisionAnalysis",
    "UIElementLocator",
    "ElementCoordinates",
    "OCREngine",
    "OCRResult",
    "OCRLine",
    "OCRWord",
    "BoundingBox",
    "UIDetector",
    "DetectedUIElement",
    "VisualGroundingEngine",
    "GroundedElement",
    "VisualVerifier",
    "VisualVerificationResult",
    "VisualComputerAgent",
    "VisualActionResult",
]
