"""Windows Control Layer (WindowsExecutor).

Provides native Windows OS control via ctypes (user32.dll, kernel32.dll),
psutil, and system APIs for windows, processes, input, files, volume, and power.
"""

from __future__ import annotations
import ctypes
from ctypes import wintypes
import fnmatch
import os
import pathlib
import platform
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

import psutil

from jarvis.subsystems.system.app_launcher import WindowsAppLauncher


# --- Win32 Constants & Callbacks ---
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

SW_HIDE = 0
SW_SHOWNORMAL = 1
SW_SHOWMINIMIZED = 2
SW_MAXIMIZE = 3
SW_SHOW = 5
SW_MINIMIZE = 6
SW_RESTORE = 9

WM_CLOSE = 0x0010

# Input Constants
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040

# Virtual Keycodes
VK_LWIN = 0x5B
VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_MENU = 0x12  # Alt
VK_RETURN = 0x0D
VK_TAB = 0x09
VK_ESCAPE = 0x1B
VK_SPACE = 0x20
VK_BACK = 0x08
VK_DELETE = 0x2E
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF

# Clipboard
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002


class WindowsExecutor:
    """Core controller for native Windows operations."""

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    # ---------------------------------------------------------
    # 1. Applications & Processes
    # ---------------------------------------------------------
    @classmethod
    def launch_app(cls, target: str) -> Tuple[bool, str, Optional[int]]:
        """Launches an application, executable, or special user folder (e.g. 'Downloads')."""
        clean = target.strip().lower()

        # Check for special user folders like 'Downloads', 'Documents', 'Desktop', 'Pictures'
        user_home = os.path.expanduser("~")
        special_folders = {
            "downloads": os.path.join(user_home, "Downloads"),
            "documents": os.path.join(user_home, "Documents"),
            "desktop": os.path.join(user_home, "Desktop"),
            "pictures": os.path.join(user_home, "Pictures"),
            "music": os.path.join(user_home, "Music"),
            "videos": os.path.join(user_home, "Videos"),
        }

        if clean in special_folders:
            folder_path = special_folders[clean]
            if not os.path.exists(folder_path):
                os.makedirs(folder_path, exist_ok=True)
            try:
                os.startfile(folder_path)
                return True, f"Opened special folder '{target}' ({folder_path}) in Windows Explorer", None
            except Exception as e:
                return False, f"Failed to open folder '{folder_path}': {e}", None

        # Check if direct directory path
        if os.path.isdir(target):
            try:
                os.startfile(os.path.abspath(target))
                return True, f"Opened directory '{target}' in Windows Explorer", None
            except Exception as e:
                return False, f"Failed to open directory '{target}': {e}", None

        # Launch application via WindowsAppLauncher
        return WindowsAppLauncher.launch(target)

    @classmethod
    def close_app(cls, name_or_title: str, force: bool = False) -> Tuple[bool, str]:
        """Closes application by process name or window title."""
        target = name_or_title.strip().lower()
        matched_procs = []

        # Find matching processes via psutil
        for p in psutil.process_iter(["pid", "name"]):
            try:
                p_name = p.info["name"].lower()
                if target in p_name or target.replace(" ", "") in p_name.replace(" ", ""):
                    matched_procs.append(p)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # If not found by process name, search by window title
        if not matched_procs:
            windows = cls.list_windows(visible_only=True)
            for w in windows:
                if target in w["title"].lower():
                    try:
                        p = psutil.Process(w["pid"])
                        matched_procs.append(p)
                    except Exception:
                        pass

        if not matched_procs:
            return False, f"No running application or process matched '{name_or_title}'."

        closed_count = 0
        for proc in matched_procs:
            try:
                if force:
                    proc.kill()
                else:
                    proc.terminate()
                closed_count += 1
            except Exception:
                pass

        return True, f"Closed {closed_count} process(es) matching '{name_or_title}'."

    @classmethod
    def start_process(cls, command_or_path: str, arguments: Optional[List[str]] = None) -> Tuple[bool, str, Optional[int]]:
        """Starts a background or detached process."""
        cmd = [command_or_path] + (arguments or [])
        try:
            proc = subprocess.Popen(cmd, shell=True)
            return True, f"Started process '{command_or_path}' with PID {proc.pid}", proc.pid
        except Exception as e:
            return False, f"Failed to start process: {e}", None

    @classmethod
    def stop_process(cls, process_name_or_pid: str | int, force: bool = False) -> Tuple[bool, str]:
        """Terminates or kills a process by PID or process name."""
        if isinstance(process_name_or_pid, int) or (isinstance(process_name_or_pid, str) and process_name_or_pid.isdigit()):
            pid = int(process_name_or_pid)
            try:
                p = psutil.Process(pid)
                if force:
                    p.kill()
                else:
                    p.terminate()
                return True, f"Stopped process PID {pid} ({p.name()})."
            except psutil.NoSuchProcess:
                return False, f"Process PID {pid} does not exist."
            except Exception as e:
                return False, f"Failed to stop process PID {pid}: {e}"

        return cls.close_app(str(process_name_or_pid), force=force)

    @classmethod
    def list_processes(cls, filter_name: Optional[str] = None, max_results: int = 50) -> List[Dict[str, Any]]:
        """Lists running processes with CPU, memory, and status telemetry."""
        results = []
        filter_lower = filter_name.strip().lower() if filter_name else None

        for p in psutil.process_iter(["pid", "name", "status", "cpu_percent", "memory_percent"]):
            try:
                name = p.info["name"] or ""
                if filter_lower and filter_lower not in name.lower():
                    continue
                results.append({
                    "pid": p.info["pid"],
                    "name": name,
                    "status": p.info["status"],
                    "cpu_percent": p.info.get("cpu_percent", 0.0),
                    "memory_percent": round(p.info.get("memory_percent", 0.0) or 0.0, 2),
                })
                if len(results) >= max_results:
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        return results

    # ---------------------------------------------------------
    # 2. Window Management
    # ---------------------------------------------------------
    @classmethod
    def list_windows(cls, visible_only: bool = True) -> List[Dict[str, Any]]:
        """Enumerates open top-level windows on the Windows desktop."""
        windows: List[Dict[str, Any]] = []

        def enum_handler(hwnd, lparam):
            if visible_only and not cls.user32.IsWindowVisible(hwnd):
                return True

            length = cls.user32.GetWindowTextLengthW(hwnd)
            if length == 0 and visible_only:
                return True

            buff = ctypes.create_unicode_buffer(length + 1)
            cls.user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value.strip()

            if visible_only and not title:
                return True

            pid = wintypes.DWORD()
            cls.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            proc_name = ""
            try:
                proc = psutil.Process(pid.value)
                proc_name = proc.name()
            except Exception:
                pass

            # Detect minimized / maximized
            is_iconic = bool(cls.user32.IsIconic(hwnd))
            is_zoomed = bool(cls.user32.IsZoomed(hwnd))

            windows.append({
                "hwnd": hwnd,
                "title": title,
                "pid": pid.value,
                "process_name": proc_name,
                "is_minimized": is_iconic,
                "is_maximized": is_zoomed,
            })
            return True

        cb = WNDENUMPROC(enum_handler)
        cls.user32.EnumWindows(cb, 0)
        return windows

    @classmethod
    def get_active_window(cls) -> Dict[str, Any]:
        """Returns details about the currently active (foreground) window."""
        hwnd = cls.user32.GetForegroundWindow()
        if not hwnd:
            return {"hwnd": 0, "title": "", "pid": 0, "process_name": ""}

        length = cls.user32.GetWindowTextLengthW(hwnd)
        buff = ctypes.create_unicode_buffer(length + 1)
        cls.user32.GetWindowTextW(hwnd, buff, length + 1)
        title = buff.value.strip()

        pid = wintypes.DWORD()
        cls.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        proc_name = ""
        try:
            proc = psutil.Process(pid.value)
            proc_name = proc.name()
        except Exception:
            pass

        return {
            "hwnd": hwnd,
            "title": title,
            "pid": pid.value,
            "process_name": proc_name,
        }

    @classmethod
    def focus_window(cls, title_or_name: str) -> Tuple[bool, str]:
        """Brings the matching window into the foreground."""
        target = title_or_name.strip().lower()
        windows = cls.list_windows(visible_only=True)

        matched_hwnd = None
        matched_title = ""
        for w in windows:
            if target in w["title"].lower() or target in w["process_name"].lower():
                matched_hwnd = w["hwnd"]
                matched_title = w["title"]
                break

        if not matched_hwnd:
            return False, f"Could not find window matching '{title_or_name}'."

        # Restore if minimized
        if cls.user32.IsIconic(matched_hwnd):
            cls.user32.ShowWindow(matched_hwnd, SW_RESTORE)

        cls.user32.SetForegroundWindow(matched_hwnd)
        return True, f"Focused window '{matched_title}' (HWND {matched_hwnd})."

    @classmethod
    def set_window_state(cls, title_or_name: str, state: str) -> Tuple[bool, str]:
        """Minimizes, maximizes, or restores a window."""
        target = title_or_name.strip().lower()
        windows = cls.list_windows(visible_only=True)

        matched_hwnd = None
        matched_title = ""
        for w in windows:
            if target in w["title"].lower() or target in w["process_name"].lower():
                matched_hwnd = w["hwnd"]
                matched_title = w["title"]
                break

        if not matched_hwnd:
            return False, f"Could not find window matching '{title_or_name}'."

        state_clean = state.strip().lower()
        cmd = SW_SHOWNORMAL
        if state_clean in ("minimize", "min"):
            cmd = SW_MINIMIZE
        elif state_clean in ("maximize", "max"):
            cmd = SW_MAXIMIZE
        elif state_clean in ("restore", "normal"):
            cmd = SW_RESTORE
        else:
            return False, f"Unknown window state '{state}'. Choose minimize, maximize, or restore."

        cls.user32.ShowWindow(matched_hwnd, cmd)
        return True, f"Set window '{matched_title}' state to '{state_clean}'."

    # ---------------------------------------------------------
    # 3. Input Automation (Keyboard, Mouse, Hotkeys, Clipboard)
    # ---------------------------------------------------------
    @classmethod
    def mouse_move(cls, x: int, y: int) -> Tuple[bool, str]:
        """Moves mouse cursor to coordinate (x, y)."""
        cls.user32.SetCursorPos(int(x), int(y))
        return True, f"Moved mouse to ({x}, {y})."

    @classmethod
    def mouse_click(
        cls,
        button: str = "left",
        coords: Optional[Tuple[int, int]] = None,
    ) -> Tuple[bool, str]:
        """Performs single mouse click."""
        if coords:
            cls.mouse_move(coords[0], coords[1])
            time.sleep(0.02)

        btn = button.lower()
        if btn == "right":
            down_flag, up_flag = MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP
        elif btn == "middle":
            down_flag, up_flag = MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP
        else:
            down_flag, up_flag = MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP

        cls.user32.mouse_event(down_flag, 0, 0, 0, 0)
        time.sleep(0.02)
        cls.user32.mouse_event(up_flag, 0, 0, 0, 0)
        return True, f"Executed {btn}-click."

    @classmethod
    def mouse_double_click(cls, coords: Optional[Tuple[int, int]] = None) -> Tuple[bool, str]:
        """Performs mouse double click."""
        if coords:
            cls.mouse_move(coords[0], coords[1])
            time.sleep(0.02)

        cls.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.02)
        cls.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        time.sleep(0.08)
        cls.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.02)
        cls.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        return True, "Executed left double-click."

    @classmethod
    def type_text(cls, text: str) -> Tuple[bool, str]:
        """Types unicode characters into the currently focused window."""
        try:
            for char in text:
                val = ord(char)
                cls.user32.keybd_event(0, val, KEYEVENTF_UNICODE, 0)
                time.sleep(0.005)
                cls.user32.keybd_event(0, val, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0)
                time.sleep(0.005)
            return True, f"Typed {len(text)} characters."
        except Exception as e:
            return False, f"Typing failed: {e}"

    @classmethod
    def send_hotkey(cls, hotkey: str) -> Tuple[bool, str]:
        """Presses a hotkey combination (e.g. 'ctrl+c', 'ctrl+v', 'alt+tab', 'win+d')."""
        key_map = {
            "ctrl": VK_CONTROL,
            "control": VK_CONTROL,
            "shift": VK_SHIFT,
            "alt": VK_MENU,
            "win": VK_LWIN,
            "windows": VK_LWIN,
            "enter": VK_RETURN,
            "tab": VK_TAB,
            "esc": VK_ESCAPE,
            "escape": VK_ESCAPE,
            "space": VK_SPACE,
            "backspace": VK_BACK,
            "delete": VK_DELETE,
        }

        parts = [p.strip().lower() for p in hotkey.split("+")]
        vk_codes: List[int] = []

        for p in parts:
            if p in key_map:
                vk_codes.append(key_map[p])
            elif len(p) == 1:
                vk_codes.append(ord(p.upper()))
            else:
                return False, f"Unknown key in hotkey: '{p}'"

        try:
            # Key down
            for code in vk_codes:
                cls.user32.keybd_event(code, 0, 0, 0)
                time.sleep(0.02)
            # Key up in reverse order
            for code in reversed(vk_codes):
                cls.user32.keybd_event(code, 0, KEYEVENTF_KEYUP, 0)
                time.sleep(0.02)
            return True, f"Executed hotkey '{hotkey}'."
        except Exception as e:
            return False, f"Failed to execute hotkey: {e}"

    @classmethod
    def get_clipboard(cls) -> str:
        """Retrieves text from Windows clipboard."""
        if not cls.user32.OpenClipboard(0):
            return ""
        try:
            handle = cls.user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                return ""
            data_ptr = cls.kernel32.GlobalLock(handle)
            if not data_ptr:
                return ""
            try:
                return ctypes.c_wchar_p(data_ptr).value or ""
            finally:
                cls.kernel32.GlobalUnlock(handle)
        finally:
            cls.user32.CloseClipboard()

    @classmethod
    def set_clipboard(cls, text: str) -> bool:
        """Copies text to Windows clipboard."""
        if not cls.user32.OpenClipboard(0):
            return False
        try:
            cls.user32.EmptyClipboard()
            encoded = text.encode("utf-16le") + b"\x00\x00"
            h_mem = cls.kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
            if not h_mem:
                return False
            data_ptr = cls.kernel32.GlobalLock(h_mem)
            if not data_ptr:
                return False
            try:
                ctypes.memmove(data_ptr, encoded, len(encoded))
            finally:
                cls.kernel32.GlobalUnlock(h_mem)
            cls.user32.SetClipboardData(CF_UNICODETEXT, h_mem)
            return True
        finally:
            cls.user32.CloseClipboard()

    # ---------------------------------------------------------
    # 4. Files & Folders
    # ---------------------------------------------------------
    @classmethod
    def create_folder(cls, path: str) -> Tuple[bool, str]:
        """Creates directory folder on disk."""
        abs_p = os.path.abspath(path)
        try:
            os.makedirs(abs_p, exist_ok=True)
            return True, f"Folder created: {abs_p}"
        except Exception as e:
            return False, f"Failed to create folder '{path}': {e}"

    @classmethod
    def create_file(cls, path: str, content: str, overwrite: bool = True) -> Tuple[bool, str]:
        """Creates or writes text file on disk."""
        abs_p = os.path.abspath(path)
        if os.path.exists(abs_p) and not overwrite:
            return False, f"File already exists: {abs_p}"
        try:
            os.makedirs(os.path.dirname(abs_p), exist_ok=True)
            with open(abs_p, "w", encoding="utf-8") as f:
                f.write(content)
            return True, f"File created: {abs_p} ({len(content)} characters written)"
        except Exception as e:
            return False, f"Failed to write file '{path}': {e}"

    @classmethod
    def modify_file(cls, path: str, content: str, mode: str = "append") -> Tuple[bool, str]:
        """Appends to or updates a file."""
        abs_p = os.path.abspath(path)
        if not os.path.exists(abs_p):
            return cls.create_file(path, content, overwrite=True)

        try:
            mode_clean = mode.lower()
            if mode_clean == "prepend":
                with open(abs_p, "r", encoding="utf-8", errors="ignore") as rf:
                    existing = rf.read()
                with open(abs_p, "w", encoding="utf-8") as wf:
                    wf.write(content + existing)
            elif mode_clean == "overwrite":
                with open(abs_p, "w", encoding="utf-8") as f:
                    f.write(content)
            else:  # append
                with open(abs_p, "r", encoding="utf-8", errors="ignore") as rf:
                    existing = rf.read()
                sep = "" if (not existing or existing.endswith("\n") or content.startswith("\n")) else "\n"
                with open(abs_p, "a", encoding="utf-8") as f:
                    f.write(sep + content)
            return True, f"Modified file {abs_p} (mode={mode})."
        except Exception as e:
            return False, f"Failed to modify file: {e}"

    @classmethod
    def move_file(cls, source: str, destination: str) -> Tuple[bool, str]:
        """Moves or renames file or folder."""
        src_p = os.path.abspath(source)
        dst_p = os.path.abspath(destination)
        if not os.path.exists(src_p):
            return False, f"Source path does not exist: {src_p}"
        try:
            os.makedirs(os.path.dirname(dst_p), exist_ok=True)
            shutil.move(src_p, dst_p)
            return True, f"Moved '{src_p}' to '{dst_p}'."
        except Exception as e:
            return False, f"Move failed: {e}"

    @classmethod
    def search_files(cls, directory: str, pattern: str = "*", max_results: int = 30) -> List[Dict[str, Any]]:
        """Searches files in a directory by wildcard pattern."""
        abs_d = os.path.abspath(directory)
        if not os.path.isdir(abs_d):
            return []

        results = []
        for root, _, files in os.walk(abs_d):
            for filename in fnmatch.filter(files, pattern):
                full_p = os.path.join(root, filename)
                try:
                    size = os.path.getsize(full_p)
                except OSError:
                    size = 0
                results.append({"name": filename, "path": full_p, "size_bytes": size})
                if len(results) >= max_results:
                    break
            if len(results) >= max_results:
                break
        return results

    # ---------------------------------------------------------
    # 5. Volume, Display, System & Power
    # ---------------------------------------------------------
    @classmethod
    def set_volume(cls, action: str, level: Optional[int] = None) -> Tuple[bool, str]:
        """Controls system master audio volume (mute, unmute, up, down, set)."""
        act = action.lower().strip()
        if act in ("mute", "unmute", "toggle_mute"):
            cls.user32.keybd_event(VK_VOLUME_MUTE, 0, 0, 0)
            time.sleep(0.02)
            cls.user32.keybd_event(VK_VOLUME_MUTE, 0, KEYEVENTF_KEYUP, 0)
            return True, "Toggled master volume mute."

        elif act == "up":
            steps = max(1, (level or 2) // 2)
            for _ in range(steps):
                cls.user32.keybd_event(VK_VOLUME_UP, 0, 0, 0)
                time.sleep(0.01)
                cls.user32.keybd_event(VK_VOLUME_UP, 0, KEYEVENTF_KEYUP, 0)
            return True, f"Turned volume up by {steps * 2}%."

        elif act == "down":
            steps = max(1, (level or 2) // 2)
            for _ in range(steps):
                cls.user32.keybd_event(VK_VOLUME_DOWN, 0, 0, 0)
                time.sleep(0.01)
                cls.user32.keybd_event(VK_VOLUME_DOWN, 0, KEYEVENTF_KEYUP, 0)
            return True, f"Turned volume down by {steps * 2}%."

        return False, f"Unknown volume action '{action}'. Choose mute, unmute, up, or down."

    @classmethod
    def get_display_info(cls) -> Dict[str, Any]:
        """Returns primary display resolution and monitor metrics."""
        w = cls.user32.GetSystemMetrics(0)
        h = cls.user32.GetSystemMetrics(1)
        return {
            "width": w,
            "height": h,
            "aspect_ratio": f"{w}:{h}",
            "is_high_dpi": bool(w > 1920),
        }

    @classmethod
    def lock_pc(cls) -> Tuple[bool, str]:
        """Locks the Windows workstation immediately."""
        try:
            cls.user32.LockWorkStation()
            return True, "Workstation locked successfully."
        except Exception as e:
            return False, f"Failed to lock workstation: {e}"

    @classmethod
    def sleep_pc(cls) -> Tuple[bool, str]:
        """Puts Windows into sleep state."""
        try:
            res = subprocess.run("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
            return True, "Sleep command issued."
        except Exception as e:
            return False, f"Failed to sleep PC: {e}"

    @classmethod
    def shutdown(cls, delay_seconds: int = 60, abort: bool = False) -> Tuple[bool, str]:
        """Initiates or cancels Windows shutdown."""
        cmd = "shutdown /a" if abort else f"shutdown /s /t {delay_seconds}"
        try:
            subprocess.run(cmd, shell=True, capture_output=True, text=True)
            return True, "Shutdown cancelled." if abort else f"Shutdown scheduled in {delay_seconds} seconds."
        except Exception as e:
            return False, f"Shutdown command failed: {e}"

    @classmethod
    def restart(cls, delay_seconds: int = 60, abort: bool = False) -> Tuple[bool, str]:
        """Initiates or cancels Windows restart."""
        cmd = "shutdown /a" if abort else f"shutdown /r /t {delay_seconds}"
        try:
            subprocess.run(cmd, shell=True, capture_output=True, text=True)
            return True, "Restart cancelled." if abort else f"Restart scheduled in {delay_seconds} seconds."
        except Exception as e:
            return False, f"Restart command failed: {e}"
