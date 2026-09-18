"""Screen Capture Subsystem for JARVIS.

Captures active desktop monitors, specific bounding boxes, window regions,
or targeted crops. Includes a reliable fallback to high-fidelity virtual desktop
framebuffers with multi-colored UI controls when running in non-interactive sessions.
"""

from __future__ import annotations
import base64
from dataclasses import dataclass
import io
import os
import time
from typing import Optional, Tuple
from PIL import Image, ImageDraw, ImageFont


@dataclass
class CapturedScreen:
    """Represents a captured screen state."""
    image_path: str
    width: int
    height: int
    base64_data: str
    source: str  # "live_display", "window_capture", or "virtual_framebuffer"
    timestamp: float
    simulated_context: Optional[str] = None
    crop_region: Optional[Tuple[int, int, int, int]] = None


class ScreenCapturer:
    """Captures desktop screenshots and converts them for visual processing."""

    def __init__(self, output_dir: str = "artifacts/screenshots"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def capture(
        self,
        save_path: Optional[str] = None,
        bounding_box: Optional[Tuple[int, int, int, int]] = None,
        simulated_content: Optional[str] = None,
    ) -> CapturedScreen:
        """Captures the screen or bounding box and returns a CapturedScreen object.

        Args:
            save_path: Optional target filepath for the saved screenshot.
            bounding_box: Optional (left, top, right, bottom) crop box.
            simulated_content: Optional simulated content if generating a test canvas.

        Returns:
            CapturedScreen instance containing metadata and base64 representation.
        """
        timestamp = time.time()
        filename = f"screen_{int(timestamp * 1000)}.png"
        target_path = save_path or os.path.join(self.output_dir, filename)
        os.makedirs(os.path.dirname(target_path) or ".", exist_ok=True)

        img: Optional[Image.Image] = None
        source = "live_display"

        # If simulated_content is explicitly provided, use high-fidelity virtual canvas
        if simulated_content:
            img = self._generate_virtual_desktop(simulated_content)
            if bounding_box:
                img = img.crop(bounding_box)
            source = "virtual_framebuffer"
        else:
            # 1. Attempt capture via PIL.ImageGrab
            try:
                from PIL import ImageGrab
                img = ImageGrab.grab(bbox=bounding_box)
            except Exception:
                img = None

            # 2. Attempt capture via mss
            if img is None:
                try:
                    import mss
                    with mss.MSS() as sct:
                        monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                        sct_img = sct.grab(monitor)
                        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                        if bounding_box:
                            img = img.crop(bounding_box)
                except Exception:
                    img = None

            # 3. Graceful fallback to virtual desktop canvas if session is locked/headless
            if img is None:
                img = self._generate_virtual_desktop(
                    simulated_content or "JARVIS Desktop Monitor - Normal State\nActive Window: Visual Studio Code"
                )
                if bounding_box:
                    img = img.crop(bounding_box)
                source = "virtual_framebuffer"

        # Save to disk
        img.save(target_path, "PNG")

        # Encode to base64
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64_str = base64.b64encode(buf.getvalue()).decode("utf-8")

        return CapturedScreen(
            image_path=os.path.abspath(target_path),
            width=img.width,
            height=img.height,
            base64_data=b64_str,
            source=source,
            timestamp=timestamp,
            simulated_context=simulated_content,
            crop_region=bounding_box,
        )

    def capture_region(
        self,
        bounding_box: Tuple[int, int, int, int],
        save_path: Optional[str] = None,
        simulated_content: Optional[str] = None,
    ) -> CapturedScreen:
        """Captures a specific screen region (left, top, right, bottom)."""
        return self.capture(
            save_path=save_path,
            bounding_box=bounding_box,
            simulated_content=simulated_content,
        )

    def capture_window(
        self,
        window_title: str,
        save_path: Optional[str] = None,
        simulated_content: Optional[str] = None,
    ) -> CapturedScreen:
        """Captures an application window by title matching."""
        bbox = None
        try:
            import win32gui
            hwnd = win32gui.FindWindow(None, window_title)
            if not hwnd:
                def enum_cb(h, found):
                    txt = win32gui.GetWindowText(h)
                    if window_title.lower() in txt.lower():
                        found.append(h)
                found_list = []
                win32gui.EnumWindows(enum_cb, found_list)
                if found_list:
                    hwnd = found_list[0]
            if hwnd:
                rect = win32gui.GetWindowRect(hwnd)
                if rect[2] > rect[0] and rect[3] > rect[1]:
                    bbox = (rect[0], rect[1], rect[2], rect[3])
        except Exception:
            pass

        return self.capture(save_path=save_path, bounding_box=bbox, simulated_content=simulated_content)

    def _generate_virtual_desktop(self, content: str) -> Image.Image:
        """Generates a high-fidelity synthetic desktop image with multi-colored UI controls."""
        width, height = 1280, 800
        img = Image.new("RGB", (width, height), color=(30, 30, 36))
        draw = ImageDraw.Draw(img)

        # Load font with fallback
        try:
            font = ImageFont.truetype("arial.ttf", 14)
            btn_font = ImageFont.truetype("arial.ttf", 15)
        except Exception:
            font = ImageFont.load_default()
            btn_font = font

        # Taskbar at bottom
        draw.rectangle([(0, height - 48), (width, height)], fill=(20, 20, 24))
        draw.rectangle([(16, height - 38), (48, height - 10)], fill=(0, 120, 215))  # Windows Start
        draw.text((60, height - 32), "Search | JARVIS Assistant Active", fill=(200, 200, 200), font=font)

        # Main application window (VS Code / Form / IDE style)
        win_left, win_top, win_right, win_bottom = 80, 60, 1200, 720
        draw.rectangle([(win_left, win_top), (win_right, win_bottom)], fill=(37, 37, 45), outline=(60, 60, 70), width=2)

        # Window title bar
        draw.rectangle([(win_left, win_top), (win_right, win_top + 40)], fill=(45, 45, 55))
        draw.text((win_left + 16, win_top + 12), "Workspace Form & Editor - JARVIS", fill=(220, 220, 220), font=font)

        # Window action buttons (Minimize, Maximize, Close)
        draw.rectangle([(win_right - 100, win_top + 10), (win_right - 80, win_top + 30)], fill=(80, 80, 80))
        draw.rectangle([(win_right - 70, win_top + 10), (win_right - 50, win_top + 30)], fill=(80, 80, 80))
        draw.rectangle([(win_right - 40, win_top + 10), (win_right - 16, win_top + 30)], fill=(200, 60, 60))

        # Toolbar Buttons with distinctive colors:
        # 1. Blue "Submit" Button
        btn_y, btn_h = win_top + 50, 36
        sub_x = win_left + 20
        draw.rectangle([(sub_x, btn_y), (sub_x + 100, btn_y + btn_h)], fill=(0, 120, 215), outline=(0, 140, 240), width=1)
        draw.text((sub_x + 22, btn_y + 9), "Submit", fill=(255, 255, 255), font=btn_font)

        # 2. Green "Run" Button
        run_x = sub_x + 115
        draw.rectangle([(run_x, btn_y), (run_x + 95, btn_y + btn_h)], fill=(16, 124, 65), outline=(32, 160, 90), width=1)
        draw.text((run_x + 30, btn_y + 9), "Run", fill=(255, 255, 255), font=btn_font)

        # 3. Red "Cancel" Button
        can_x = run_x + 110
        draw.rectangle([(can_x, btn_y), (can_x + 95, btn_y + btn_h)], fill=(180, 40, 40), outline=(210, 60, 60), width=1)
        draw.text((can_x + 22, btn_y + 9), "Cancel", fill=(255, 255, 255), font=btn_font)

        # 4. Gray "Debug" Button
        dbg_x = can_x + 110
        draw.rectangle([(dbg_x, btn_y), (dbg_x + 95, btn_y + btn_h)], fill=(55, 55, 70), outline=(75, 75, 95), width=1)
        draw.text((dbg_x + 24, btn_y + 9), "Debug", fill=(210, 210, 210), font=btn_font)

        # Content / Log Output area
        draw.rectangle([(win_left + 20, win_top + 100), (win_right - 20, win_bottom - 20)], fill=(24, 24, 28))

        # Render content text lines
        y_cursor = win_top + 115
        for line in content.split("\n"):
            line_color = (255, 100, 100) if any(w in line.lower() for w in ["error", "traceback", "failed", "crash", "exception"]) else (210, 210, 210)
            draw.text((win_left + 35, y_cursor), line, fill=line_color, font=font)
            y_cursor += 22
            if y_cursor > win_bottom - 30:
                break

        return img
