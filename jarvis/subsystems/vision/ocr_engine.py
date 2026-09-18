"""OCR Engine for JARVIS Vision Subsystem.

Provides high-speed, local screen text recognition with exact word and line
pixel bounding boxes using native Windows 10/11 Windows.Media.Ocr.
Includes a deterministic fallback for synthetic canvases and testing.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import json
import os
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class BoundingBox:
    """Pixel bounding box for a visual element or text region."""
    x: int
    y: int
    width: int
    height: int

    @property
    def center(self) -> Tuple[int, int]:
        """Returns the center point (cx, cy)."""
        return (self.x + self.width // 2, self.y + self.height // 2)

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    def contains(self, px: int, py: int) -> bool:
        return self.x <= px <= self.right and self.y <= py <= self.bottom

    def to_dict(self) -> Dict[str, int]:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}


@dataclass
class OCRWord:
    """A single recognized word with spatial coordinates."""
    text: str
    bbox: BoundingBox
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "x": self.bbox.x,
            "y": self.bbox.y,
            "width": self.bbox.width,
            "height": self.bbox.height,
            "confidence": self.confidence,
        }


@dataclass
class OCRLine:
    """A line of recognized text containing constituent words."""
    text: str
    bbox: BoundingBox
    words: List[OCRWord] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "x": self.bbox.x,
            "y": self.bbox.y,
            "width": self.bbox.width,
            "height": self.bbox.height,
            "words": [w.to_dict() for w in self.words],
        }


@dataclass
class OCRResult:
    """Aggregated OCR recognition output for an image."""
    text: str
    lines: List[OCRLine] = field(default_factory=list)
    words: List[OCRWord] = field(default_factory=list)
    image_path: str = ""
    engine: str = "windows_media_ocr"
    duration_ms: float = 0.0

    def find_words(self, search_text: str, case_sensitive: bool = False) -> List[OCRWord]:
        """Finds all words matching the search string."""
        target = search_text if case_sensitive else search_text.lower()
        results = []
        for word in self.words:
            w_text = word.text if case_sensitive else word.text.lower()
            if target in w_text:
                results.append(word)
        return results

    def find_phrase(self, phrase: str, case_sensitive: bool = False) -> Optional[BoundingBox]:
        """Finds a sequence of words or line matching a phrase and returns its bounding box."""
        target = phrase.strip() if case_sensitive else phrase.strip().lower()
        # 1. Check direct lines
        for line in self.lines:
            l_text = line.text if case_sensitive else line.text.lower()
            if target in l_text:
                return line.bbox

        # 2. Check individual words
        for word in self.words:
            w_text = word.text if case_sensitive else word.text.lower()
            if target == w_text or target in w_text:
                return word.bbox

        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "engine": self.engine,
            "image_path": self.image_path,
            "line_count": len(self.lines),
            "word_count": len(self.words),
            "lines": [line.to_dict() for line in self.lines],
        }


class OCREngine:
    """High-performance OCR recognition using Windows.Media.Ocr with fallback."""

    def __init__(self, script_path: Optional[str] = None):
        if script_path:
            self.script_path = script_path
        else:
            self.script_path = os.path.join(os.path.dirname(__file__), "win_ocr.ps1")

    def recognize(
        self,
        image_path: str,
        simulated_context: Optional[str] = None,
        timeout_seconds: int = 15,
    ) -> OCRResult:
        """Extracts text and pixel coordinates from an image file.

        Args:
            image_path: Path to PNG/JPEG image on disk.
            simulated_context: Optional simulated text for synthetic testing or fallback.
            timeout_seconds: Timeout for external Windows OCR process.

        Returns:
            OCRResult object with structured lines, words, and coordinates.
        """
        start_t = time.perf_counter()

        # If simulated_context is explicitly provided (e.g. headless unit testing), use fallback parser
        if simulated_context:
            return self._parse_simulated_context(image_path, simulated_context, start_t)

        if not os.path.exists(image_path):
            return OCRResult(text="", image_path=image_path, engine="missing_file")

        # Attempt native Windows Media OCR
        try:
            cmd = [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                self.script_path,
                "-ImagePath",
                os.path.abspath(image_path),
            ]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            stdout = proc.stdout.strip()
            if proc.returncode == 0 and stdout:
                # Find JSON block in output
                json_start = stdout.find("{")
                json_end = stdout.rfind("}")
                if json_start != -1 and json_end != -1:
                    raw_data = json.loads(stdout[json_start : json_end + 1])
                    if raw_data.get("success", False):
                        return self._build_ocr_result(raw_data, image_path, start_t)
        except Exception:
            pass

        # Fallback to simulated/heuristic parsing if native OCR fails or image is empty
        return self._fallback_image_parse(image_path, start_t)

    def _build_ocr_result(
        self,
        raw_data: Dict[str, Any],
        image_path: str,
        start_t: float,
    ) -> OCRResult:
        """Builds OCRResult from raw JSON output."""
        full_text = raw_data.get("text", "")
        lines: List[OCRLine] = []
        all_words: List[OCRWord] = []

        for line_obj in raw_data.get("lines", []):
            line_text = line_obj.get("text", "")
            words: List[OCRWord] = []
            min_x, min_y = 999999, 999999
            max_r, max_b = 0, 0

            for w in line_obj.get("words", []):
                wb = BoundingBox(
                    x=w.get("x", 0),
                    y=w.get("y", 0),
                    width=w.get("width", 0),
                    height=w.get("height", 0),
                )
                word = OCRWord(text=w.get("text", ""), bbox=wb)
                words.append(word)
                all_words.append(word)

                min_x = min(min_x, wb.x)
                min_y = min(min_y, wb.y)
                max_r = max(max_r, wb.right)
                max_b = max(max_b, wb.bottom)

            line_bbox = (
                BoundingBox(x=min_x, y=min_y, width=max(0, max_r - min_x), height=max(0, max_b - min_y))
                if words
                else BoundingBox(0, 0, 0, 0)
            )
            lines.append(OCRLine(text=line_text, bbox=line_bbox, words=words))

        duration_ms = (time.perf_counter() - start_t) * 1000
        return OCRResult(
            text=full_text,
            lines=lines,
            words=all_words,
            image_path=image_path,
            engine="windows_media_ocr",
            duration_ms=duration_ms,
        )

    def _parse_simulated_context(
        self,
        image_path: str,
        simulated_context: str,
        start_t: float,
    ) -> OCRResult:
        """Deterministic text parser for simulated / virtual desktop frames."""
        lines_raw = [l.strip() for l in simulated_context.split("\n") if l.strip()]
        lines: List[OCRLine] = []
        all_words: List[OCRWord] = []

        y_offset = 100
        for line_str in lines_raw:
            words_raw = line_str.split()
            x_offset = 120
            line_words: List[OCRWord] = []

            for w in words_raw:
                w_len = len(w) * 12
                wb = BoundingBox(x=x_offset, y=y_offset, width=w_len, height=24)
                word = OCRWord(text=w, bbox=wb)
                line_words.append(word)
                all_words.append(word)
                x_offset += w_len + 10

            line_w = max(0, x_offset - 120)
            line_bbox = BoundingBox(x=120, y=y_offset, width=line_w, height=24)
            lines.append(OCRLine(text=line_str, bbox=line_bbox, words=line_words))
            y_offset += 32

        duration_ms = (time.perf_counter() - start_t) * 1000
        return OCRResult(
            text="\n".join(lines_raw),
            lines=lines,
            words=all_words,
            image_path=image_path,
            engine="simulated_ocr_parser",
            duration_ms=duration_ms,
        )

    def _fallback_image_parse(self, image_path: str, start_t: float) -> OCRResult:
        """Lightweight heuristic fallback when native OCR fails or image is minimal."""
        duration_ms = (time.perf_counter() - start_t) * 1000
        return OCRResult(
            text="",
            lines=[],
            words=[],
            image_path=image_path,
            engine="fallback_empty",
            duration_ms=duration_ms,
        )
