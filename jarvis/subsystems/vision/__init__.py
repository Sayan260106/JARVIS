"""Vision and Desktop Interaction Subsystem for JARVIS.

Provides screen capture, multimodal visual reasoning, UI element localization,
and native Windows desktop mouse/keyboard automation.
"""

from jarvis.subsystems.vision.screen_capture import ScreenCapturer, CapturedScreen
from jarvis.subsystems.vision.desktop_controller import DesktopController
from jarvis.subsystems.vision.vision_model import VisionModel, VisionAnalysis
from jarvis.subsystems.vision.ui_locator import UIElementLocator, ElementCoordinates

__all__ = [
    "ScreenCapturer",
    "CapturedScreen",
    "DesktopController",
    "VisionModel",
    "VisionAnalysis",
    "UIElementLocator",
    "ElementCoordinates",
]
