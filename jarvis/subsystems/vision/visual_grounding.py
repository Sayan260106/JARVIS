"""Visual Grounding Engine for JARVIS Computer Control.

Maps natural language UI element descriptions (e.g. "Click the blue submit button",
"Cancel button", "Green run button") into exact screen coordinates (x, y).
"""

from __future__ import annotations
from dataclasses import dataclass
import re
from typing import Any, Dict, List, Optional, Tuple

from jarvis.subsystems.vision.screen_capture import CapturedScreen
from jarvis.subsystems.vision.ui_detector import DetectedUIElement, UIDetector
from jarvis.subsystems.vision.ocr_engine import BoundingBox, OCREngine
from jarvis.subsystems.vision.vision_model import VisionModel


@dataclass
class GroundedElement:
    """Represents a grounded target UI element mapped to screen coordinates."""
    label: str
    element_type: str
    color: str
    bbox: BoundingBox
    center_x: int
    center_y: int
    confidence: float
    grounding_method: str
    raw_query: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "element_type": self.element_type,
            "color": self.color,
            "x": self.bbox.x,
            "y": self.bbox.y,
            "width": self.bbox.width,
            "height": self.bbox.height,
            "center_x": self.center_x,
            "center_y": self.center_y,
            "confidence": self.confidence,
            "grounding_method": self.grounding_method,
            "raw_query": self.raw_query,
        }


class VisualGroundingEngine:
    """Grounds user natural language requests to interactive screen controls."""

    KNOWN_COLORS = ["blue", "green", "red", "gray", "grey", "white", "black", "yellow", "orange", "purple"]
    KNOWN_TYPES = ["button", "input", "field", "icon", "box", "window", "tab", "link"]

    def __init__(
        self,
        ui_detector: Optional[UIDetector] = None,
        vision_model: Optional[VisionModel] = None,
        ocr_engine: Optional[OCREngine] = None,
    ):
        self.ocr = ocr_engine or OCREngine()
        self.detector = ui_detector or UIDetector(ocr_engine=self.ocr)
        self.vision_model = vision_model or VisionModel()

    def ground(self, screen: CapturedScreen, query: str) -> Optional[GroundedElement]:
        """Finds the best matching UI element for the given natural language description.

        Args:
            screen: CapturedScreen image.
            query: User's target description (e.g. "Click the blue submit button").

        Returns:
            GroundedElement with screen center coordinates, or None.
        """
        # 1. Parse natural language query intent
        target_color, target_type, target_text = self._parse_query_tokens(query)

        # 2. Detect elements on screen
        detected_elements = self.detector.detect_elements(screen)

        # 3. Score and rank candidates
        best_candidate: Optional[DetectedUIElement] = None
        best_score = -1.0

        for elem in detected_elements:
            score = self._score_element(elem, target_color, target_type, target_text)
            if score > best_score:
                best_score = score
                best_candidate = elem

        # Accept match if confidence score is sufficient
        if best_candidate and best_score >= 0.45:
            cx, cy = best_candidate.center

            # Offset if screen was a cropped region
            if screen.crop_region:
                cx += screen.crop_region[0]
                cy += screen.crop_region[1]

            return GroundedElement(
                label=best_candidate.label,
                element_type=best_candidate.element_type,
                color=best_candidate.color,
                bbox=best_candidate.bbox,
                center_x=cx,
                center_y=cy,
                confidence=min(1.0, best_score),
                grounding_method=f"detector_{best_candidate.source}",
                raw_query=query,
            )

        # 4. Direct OCR text match fallback
        ocr_result = self.ocr.recognize(screen.image_path, simulated_context=screen.simulated_context)
        for term in [target_text] if target_text else []:
            if not term:
                continue
            word_matches = ocr_result.find_words(term)
            if word_matches:
                w = word_matches[0]
                cx, cy = w.bbox.center
                if screen.crop_region:
                    cx += screen.crop_region[0]
                    cy += screen.crop_region[1]
                return GroundedElement(
                    label=w.text,
                    element_type="text",
                    color="unknown",
                    bbox=w.bbox,
                    center_x=cx,
                    center_y=cy,
                    confidence=0.75,
                    grounding_method="direct_ocr_match",
                    raw_query=query,
                )

        return None

    def _parse_query_tokens(self, query: str) -> Tuple[Optional[str], Optional[str], str]:
        """Extracts color modifier, element type, and core text label from a user prompt."""
        clean = query.lower()
        # Remove common action prefix phrases
        for prefix in ["click on the", "click the", "click on", "click", "press the", "press", "tap on", "tap"]:
            if clean.startswith(prefix):
                clean = clean[len(prefix) :].strip()
                break

        tokens = clean.split()
        target_color = None
        target_type = None
        remaining_words: List[str] = []

        for token in tokens:
            t = token.strip(".,;:!?\"'")
            if t in self.KNOWN_COLORS:
                target_color = "gray" if t == "grey" else t
            elif t in self.KNOWN_TYPES:
                target_type = t
            else:
                remaining_words.append(t)

        target_text = " ".join(remaining_words).strip()
        return target_color, target_type, target_text

    def _score_element(
        self,
        elem: DetectedUIElement,
        target_color: Optional[str],
        target_type: Optional[str],
        target_text: str,
    ) -> float:
        """Calculates matching score between query attributes and candidate element."""
        score = 0.0
        elem_label_lower = elem.label.lower()

        # Text Match (Weight: 0.55)
        if target_text:
            if target_text == elem_label_lower:
                score += 0.55
            elif target_text in elem_label_lower:
                score += 0.45
            elif elem_label_lower in target_text:
                score += 0.40
            else:
                # Token overlap
                target_tokens = set(target_text.split())
                elem_tokens = set(elem_label_lower.split())
                overlap = target_tokens.intersection(elem_tokens)
                if overlap:
                    score += 0.30 * (len(overlap) / max(len(target_tokens), 1))
        else:
            # If no specific text specified (e.g. "click the blue button")
            score += 0.20

        # Color Match (Weight: 0.35)
        if target_color:
            if target_color == elem.color.lower():
                score += 0.35
            else:
                # Color mismatch penalty
                score -= 0.25

        # Type Match (Weight: 0.10)
        if target_type:
            if target_type in elem.element_type.lower():
                score += 0.10

        return max(0.0, score)
