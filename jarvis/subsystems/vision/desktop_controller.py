"""Desktop Mouse and Keyboard Controller for Windows.

Provides native input automation using Windows ctypes (user32.dll)
with zero heavy external binary dependencies.
"""

from __future__ import annotations
import ctypes
from ctypes import wintypes
import time
from typing import Optional, Tuple

# Windows API Constants
SM_CXSCREEN = 0
SM_CYSCREEN = 1

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_ABSOLUTE = 0x8000

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

VK_RETURN = 0x0D
VK_TAB = 0x09
VK_ESCAPE = 0x1B
VK_SPACE = 0x20


class DesktopController:
    """Controls mouse movement, clicks, and keystrokes on Windows."""

    def __init__(self):
        self.user32 = ctypes.windll.user32
        self._current_pos = (0, 0)

    def get_screen_size(self) -> Tuple[int, int]:
        """Returns the primary monitor (width, height) in pixels."""
        try:
            w = self.user32.GetSystemMetrics(SM_CXSCREEN)
            h = self.user32.GetSystemMetrics(SM_CYSCREEN)
            return (w, h) if (w > 0 and h > 0) else (1280, 800)
        except Exception:
            return (1280, 800)

    def get_mouse_position(self) -> Tuple[int, int]:
        """Returns current mouse cursor coordinates (x, y)."""
        pt = wintypes.POINT()
        try:
            if self.user32.GetCursorPos(ctypes.byref(pt)):
                if pt.x > 0 or pt.y > 0:
                    return (pt.x, pt.y)
        except Exception:
            pass
        return self._current_pos

    def move_to(self, x: int, y: int) -> bool:
        """Moves the mouse cursor to the specified coordinates with bounds clamping."""
        max_w, max_h = self.get_screen_size()
        clamped_x = max(0, min(int(x), max_w - 1))
        clamped_y = max(0, min(int(y), max_h - 1))
        self._current_pos = (clamped_x, clamped_y)
        try:
            self.user32.SetCursorPos(clamped_x, clamped_y)
            return True
        except Exception:
            return True

    def click(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
        button: str = "left",
        double_click: bool = False,
    ) -> bool:
        """Clicks at specified or current mouse coordinates."""
        if x is not None and y is not None:
            self.move_to(x, y)
            time.sleep(0.02)

        cur_x, cur_y = self.get_mouse_position()
        btn = button.lower()

        if btn == "right":
            down_flag = MOUSEEVENTF_RIGHTDOWN
            up_flag = MOUSEEVENTF_RIGHTUP
        elif btn == "middle":
            down_flag = MOUSEEVENTF_MIDDLEDOWN
            up_flag = MOUSEEVENTF_MIDDLEUP
        else:
            down_flag = MOUSEEVENTF_LEFTDOWN
            up_flag = MOUSEEVENTF_LEFTUP

        try:
            self.user32.mouse_event(down_flag, 0, 0, 0, 0)
            time.sleep(0.03)
            self.user32.mouse_event(up_flag, 0, 0, 0, 0)

            if double_click:
                time.sleep(0.08)
                self.user32.mouse_event(down_flag, 0, 0, 0, 0)
                time.sleep(0.03)
                self.user32.mouse_event(up_flag, 0, 0, 0, 0)

            return True
        except Exception:
            return False

    def type_text(self, text: str) -> bool:
        """Types Unicode text string into the currently focused window."""
        try:
            for char in text:
                val = ord(char)
                self.user32.keybd_event(0, val, KEYEVENTF_UNICODE, 0)
                time.sleep(0.01)
                self.user32.keybd_event(0, val, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0)
                time.sleep(0.01)
            return True
        except Exception:
            return False

    def press_key(self, key_name: str) -> bool:
        """Presses a special key (e.g. enter, tab, escape, space)."""
        mapping = {
            "enter": VK_RETURN,
            "return": VK_RETURN,
            "tab": VK_TAB,
            "esc": VK_ESCAPE,
            "escape": VK_ESCAPE,
            "space": VK_SPACE,
        }
        vk_code = mapping.get(key_name.lower())
        if not vk_code:
            return False
        try:
            self.user32.keybd_event(vk_code, 0, 0, 0)
            time.sleep(0.03)
            self.user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)
            return True
        except Exception:
            return False
