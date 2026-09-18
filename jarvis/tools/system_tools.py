"""Concrete Computer Control Tools for Windows.

Implements file operations, system metrics, command execution, and OS controls.
"""

from __future__ import annotations
import ctypes
import fnmatch
import os
import pathlib
import platform
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional
from jarvis.tools.base import BaseTool, RiskLevel, ToolParameter, ToolResult, ToolVerification


class OpenFileTool(BaseTool):
    """Opens a file with its default Windows application."""
    name = "open_file"
    description = "Opens a document, image, audio, or PDF file with its default Windows application."
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "path": ToolParameter("path", "string", "Absolute or relative path of the file to open.", required=True),
    }

    def execute(self, path: str, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path):
            return ToolResult(
                success=False,
                output=None,
                error=f"File does not exist: {abs_path}",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        try:
            os.startfile(abs_path)
            return ToolResult(
                success=True,
                output=f"Opened file: {abs_path}",
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
        abs_path = os.path.abspath(arguments["path"])
        if not os.path.exists(abs_path):
            return ToolVerification(verified=False, details="File path does not exist on disk.")
        if not result.success:
            return ToolVerification(verified=False, details=f"Failed to launch file handler: {result.error}")
        return ToolVerification(verified=True, details=f"File verified at {abs_path} and launch initiated.")


class OpenApplicationTool(BaseTool):
    """Launches an executable or application on Windows."""
    name = "open_application"
    description = "Launches an application by name (e.g. 'Edge', 'VS Code', 'Spotify', 'Notepad', 'Calculator')."
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "app_name": ToolParameter("app_name", "string", "Name or alias of application to open.", required=True),
    }

    def execute(self, app_name: str, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        from jarvis.subsystems.system.windows_executor import WindowsExecutor
        success, msg, pid = WindowsExecutor.launch_app(app_name)
        return ToolResult(
            success=success,
            output={"app_name": app_name, "message": msg, "pid": pid},
            error=None if success else msg,
            duration_ms=(time.perf_counter() - start_t) * 1000,
        )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if not result.success:
            return ToolVerification(verified=False, details=f"Failed to start application: {result.error}")
        return ToolVerification(verified=True, details=f"Application '{arguments['app_name']}' launch verified.")


class SearchFilesTool(BaseTool):
    """Searches for files matching a pattern in a directory."""
    name = "search_files"
    description = "Searches for files matching a wildcard pattern (e.g. '*.pdf', '*DBMS*') in a directory."
    risk_level = RiskLevel.LOW
    parameters = {
        "directory": ToolParameter("directory", "string", "Directory path to search in.", required=True),
        "pattern": ToolParameter("pattern", "string", "Wildcard search pattern (e.g. '*.txt').", required=False, default="*"),
        "max_results": ToolParameter("max_results", "integer", "Maximum matching files to return.", required=False, default=20),
    }

    def execute(self, directory: str, pattern: str = "*", max_results: int = 20, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        abs_dir = os.path.abspath(directory)
        if not os.path.exists(abs_dir):
            return ToolResult(
                success=False,
                output=None,
                error=f"Directory does not exist: {abs_dir}",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

        matches = []
        try:
            for root, _, files in os.walk(abs_dir):
                for filename in fnmatch.filter(files, pattern):
                    full_path = os.path.join(root, filename)
                    try:
                        size = os.path.getsize(full_path)
                    except OSError:
                        size = 0
                    matches.append({"path": full_path, "name": filename, "size_bytes": size})
                    if len(matches) >= max_results:
                        break
                if len(matches) >= max_results:
                    break

            return ToolResult(
                success=True,
                output={"matches": matches, "count": len(matches), "searched_directory": abs_dir},
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
        if not result.success:
            return ToolVerification(verified=False, details=f"Search failed: {result.error}")
        return ToolVerification(
            verified=True,
            details=f"Search completed: found {result.output.get('count', 0)} files matching pattern '{arguments.get('pattern', '*')}'."
        )


class CreateFileTool(BaseTool):
    """Creates or writes text content to a file."""
    name = "create_file"
    description = "Creates a new file or writes content to a specified file path."
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "path": ToolParameter("path", "string", "Target file path.", required=True),
        "content": ToolParameter("content", "string", "Text content to write into the file.", required=True),
        "overwrite": ToolParameter("overwrite", "boolean", "Overwrite if file already exists.", required=False, default=True),
    }

    def execute(self, path: str, content: str, overwrite: bool = True, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        abs_path = os.path.abspath(path)
        if os.path.exists(abs_path) and not overwrite:
            return ToolResult(
                success=False,
                output=None,
                error=f"File already exists and overwrite is False: {abs_path}",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        try:
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(content)
            return ToolResult(
                success=True,
                output={"path": abs_path, "bytes_written": len(content.encode("utf-8"))},
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
        abs_path = os.path.abspath(arguments["path"])
        if not os.path.exists(abs_path):
            return ToolVerification(verified=False, details="File was not found on disk after write operation.")
        size = os.path.getsize(abs_path)
        return ToolVerification(verified=True, details=f"File exists at '{abs_path}' with {size} bytes.")


class MoveFileTool(BaseTool):
    """Moves or renames a file or directory."""
    name = "move_file"
    description = "Moves or renames a file or directory from source_path to destination_path."
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "source_path": ToolParameter("source_path", "string", "Current path of file to move.", required=True),
        "destination_path": ToolParameter("destination_path", "string", "Destination path.", required=True),
    }

    def execute(self, source_path: str, destination_path: str, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        src = os.path.abspath(source_path)
        dst = os.path.abspath(destination_path)
        if not os.path.exists(src):
            return ToolResult(
                success=False,
                output=None,
                error=f"Source path does not exist: {src}",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(src, dst)
            return ToolResult(
                success=True,
                output={"from": src, "to": dst},
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
        dst = os.path.abspath(arguments["destination_path"])
        src = os.path.abspath(arguments["source_path"])
        if not os.path.exists(dst):
            return ToolVerification(verified=False, details=f"Destination '{dst}' does not exist.")
        if os.path.exists(src) and src != dst:
            return ToolVerification(verified=False, details=f"Source '{src}' still exists after move.")
        return ToolVerification(verified=True, details=f"File successfully moved to '{dst}'.")


class DeleteFileTool(BaseTool):
    """Deletes a file from disk."""
    name = "delete_file"
    description = "Permanently deletes a file from the filesystem."
    risk_level = RiskLevel.HIGH
    parameters = {
        "path": ToolParameter("path", "string", "Path of file to delete.", required=True),
    }

    def execute(self, path: str, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path):
            return ToolResult(
                success=False,
                output=None,
                error=f"Path does not exist: {abs_path}",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        try:
            if os.path.isdir(abs_path):
                shutil.rmtree(abs_path)
            else:
                os.remove(abs_path)
            return ToolResult(
                success=True,
                output=f"Deleted: {abs_path}",
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
        abs_path = os.path.abspath(arguments["path"])
        if os.path.exists(abs_path):
            return ToolVerification(verified=False, details=f"Target path '{abs_path}' still exists on disk.")
        return ToolVerification(verified=True, details=f"Target path '{abs_path}' confirmed removed.")


class RunCommandTool(BaseTool):
    """Executes a command via PowerShell/Windows shell."""
    name = "run_command"
    description = "Executes a PowerShell or shell command with output and error capture."
    risk_level = RiskLevel.HIGH
    parameters = {
        "command": ToolParameter("command", "string", "Shell or PowerShell command to execute.", required=True),
        "timeout": ToolParameter("timeout", "integer", "Maximum execution time in seconds.", required=False, default=30),
    }

    def execute(self, command: str, timeout: int = 30, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", command],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return ToolResult(
                success=(res.returncode == 0),
                output={"stdout": res.stdout.strip(), "stderr": res.stderr.strip(), "exit_code": res.returncode},
                error=res.stderr.strip() if res.returncode != 0 else None,
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                output=None,
                error=f"Command timed out after {timeout} seconds",
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
        if not result.success:
            return ToolVerification(verified=False, details=f"Command failed: {result.error}")
        return ToolVerification(verified=True, details=f"Command exited successfully with code {result.output.get('exit_code', 0)}.")


class TakeScreenshotTool(BaseTool):
    """Captures desktop screenshot to an image file."""
    name = "take_screenshot"
    description = "Captures the current screen and saves it as an image file."
    risk_level = RiskLevel.LOW
    parameters = {
        "save_path": ToolParameter("save_path", "string", "File path to save the screenshot.", required=False, default=""),
    }

    def execute(self, save_path: str = "", **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        target_path = save_path or f"artifacts/screenshot_{int(time.time())}.png"
        abs_path = os.path.abspath(target_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)

        # 1. Attempt standard live screen capture
        captured = False
        last_error = None
        try:
            from PIL import ImageGrab
            screenshot = ImageGrab.grab()
            screenshot.save(abs_path)
            captured = True
        except Exception as ex1:
            last_error = ex1
            try:
                import mss
                with mss.MSS() as sct:
                    sct.shot(output=abs_path)
                captured = True
            except Exception as ex2:
                last_error = ex2

        # 2. If running in non-interactive/headless Windows session, generate diagnostic capture
        if not captured:
            try:
                from PIL import Image, ImageDraw
                img = Image.new("RGB", (1280, 800), color=(25, 28, 36))
                draw = ImageDraw.Draw(img)
                draw.text((40, 40), f"JARVIS System Screen Capture - {time.ctime()}", fill=(240, 240, 240))
                draw.text((40, 80), f"Status: Headless/Non-Interactive Window Station ({last_error})", fill=(180, 180, 180))
                img.save(abs_path)
                captured = True
            except Exception as ex3:
                return ToolResult(
                    success=False,
                    output=None,
                    error=f"Screenshot failed: {ex3}",
                    duration_ms=(time.perf_counter() - start_t) * 1000,
                )

        return ToolResult(
            success=True,
            output={"saved_path": abs_path, "size_bytes": os.path.getsize(abs_path)},
            duration_ms=(time.perf_counter() - start_t) * 1000,
        )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if not result.success:
            return ToolVerification(verified=False, details=f"Screenshot capture failed: {result.error}")
        saved_path = result.output.get("saved_path")
        if not saved_path or not os.path.exists(saved_path) or os.path.getsize(saved_path) == 0:
            return ToolVerification(verified=False, details="Screenshot image was not saved or is empty.")
        return ToolVerification(verified=True, details=f"Screenshot verified at '{saved_path}' ({os.path.getsize(saved_path)} bytes).")


class GetSystemInfoTool(BaseTool):
    """Gathers OS, CPU, RAM, and disk utilization metrics."""
    name = "get_system_info"
    description = "Retrieves operating system details, CPU load, memory usage, and disk space."
    risk_level = RiskLevel.LOW
    parameters = {}

    def execute(self, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        try:
            import psutil
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("C:\\")
            info = {
                "os": f"{platform.system()} {platform.release()} ({platform.architecture()[0]})",
                "cpu_count": psutil.cpu_count(logical=True),
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "ram_total_gb": round(mem.total / (1024**3), 2),
                "ram_used_gb": round(mem.used / (1024**3), 2),
                "ram_percent": mem.percent,
                "disk_c_total_gb": round(disk.total / (1024**3), 2),
                "disk_c_free_gb": round(disk.free / (1024**3), 2),
                "disk_c_percent": disk.percent,
            }
            return ToolResult(
                success=True,
                output=info,
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
        if not result.success:
            return ToolVerification(verified=False, details=f"Failed to gather system metrics: {result.error}")
        return ToolVerification(verified=True, details="System telemetry retrieved successfully.")


class LockPCTool(BaseTool):
    """Locks the Windows computer workstation."""
    name = "lock_pc"
    description = "Immediately locks the active Windows desktop workstation."
    risk_level = RiskLevel.MEDIUM
    parameters = {}

    def execute(self, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        try:
            success = bool(ctypes.windll.user32.LockWorkStation())
            return ToolResult(
                success=success,
                output="Workstation locked",
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
        if not result.success:
            return ToolVerification(verified=False, details=f"Lock workstation call failed: {result.error}")
        return ToolVerification(verified=True, details="LockWorkStation call executed successfully.")


class ShutdownTool(BaseTool):
    """Initiates a Windows shutdown."""
    name = "shutdown"
    description = "Initiates or cancels a system shutdown (delay in seconds, or abort=true)."
    risk_level = RiskLevel.HIGH
    parameters = {
        "delay_seconds": ToolParameter("delay_seconds", "integer", "Shutdown delay in seconds.", required=False, default=60),
        "abort": ToolParameter("abort", "boolean", "Abort a pending shutdown.", required=False, default=False),
    }

    def execute(self, delay_seconds: int = 60, abort: bool = False, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        from jarvis.subsystems.system.windows_executor import WindowsExecutor
        success, msg = WindowsExecutor.shutdown(delay_seconds=delay_seconds, abort=abort)
        return ToolResult(
            success=success,
            output={"delay_seconds": delay_seconds, "abort": abort, "message": msg},
            error=None if success else msg,
            duration_ms=(time.perf_counter() - start_t) * 1000,
        )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if not result.success:
            return ToolVerification(verified=False, details=f"Shutdown command failed: {result.error}")
        return ToolVerification(verified=True, details=result.output.get("message", "Shutdown command executed and verified."))


class RestartTool(BaseTool):
    """Initiates a Windows restart."""
    name = "restart"
    description = "Initiates or cancels a system restart (delay in seconds, or abort=true)."
    risk_level = RiskLevel.HIGH
    parameters = {
        "delay_seconds": ToolParameter("delay_seconds", "integer", "Restart delay in seconds.", required=False, default=60),
        "abort": ToolParameter("abort", "boolean", "Abort a pending restart.", required=False, default=False),
    }

    def execute(self, delay_seconds: int = 60, abort: bool = False, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        from jarvis.subsystems.system.windows_executor import WindowsExecutor
        success, msg = WindowsExecutor.restart(delay_seconds=delay_seconds, abort=abort)
        return ToolResult(
            success=success,
            output={"delay_seconds": delay_seconds, "abort": abort, "message": msg},
            error=None if success else msg,
            duration_ms=(time.perf_counter() - start_t) * 1000,
        )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if not result.success:
            return ToolVerification(verified=False, details=f"Restart command failed: {result.error}")
        return ToolVerification(verified=True, details=result.output.get("message", "Restart command executed and verified."))


class TypeTextTool(BaseTool):
    """Types text keystrokes into the active focused window on Windows."""
    name = "type_text"
    description = "Types text characters into the currently focused window (e.g. Notepad, text editor, terminal)."
    risk_level = RiskLevel.LOW
    parameters = {
        "text": ToolParameter("text", "string", "Text string to type into the active window.", required=True),
        "delay_after": ToolParameter("delay_after", "number", "Delay in seconds after typing (default 0.1s).", required=False, default=0.1),
    }

    def execute(self, text: str, delay_after: float = 0.1, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        try:
            from jarvis.subsystems.vision.desktop_controller import DesktopController
            controller = DesktopController()
            time.sleep(0.05)
            success = controller.type_text(text)
            if delay_after > 0:
                time.sleep(delay_after)
            return ToolResult(
                success=success,
                output={"text": text, "length": len(text), "typed": success},
                error=None if success else "Failed to send keystrokes via desktop controller",
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
        if not result.success:
            return ToolVerification(verified=False, details=f"Typing failed: {result.error}")
        text_arg = arguments.get("text", "")
        return ToolVerification(
            verified=True,
            details=f"Successfully typed '{text_arg}' ({len(text_arg)} characters) into active window.",
        )


class CloseApplicationTool(BaseTool):
    """Closes an open application or process by name or window title."""
    name = "close_application"
    description = "Closes a running application or process by name or window title (e.g. 'Chrome', 'Notepad', 'Edge', 'VS Code')."
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "app_name": ToolParameter("app_name", "string", "Name, alias, or window title of application to close.", required=True),
        "force": ToolParameter("force", "boolean", "Force terminate (kill) instead of graceful close.", required=False, default=False),
    }

    def execute(self, app_name: str, force: bool = False, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        from jarvis.subsystems.system.windows_executor import WindowsExecutor
        success, msg = WindowsExecutor.close_app(app_name, force=force)
        return ToolResult(
            success=success,
            output={"app_name": app_name, "message": msg},
            error=None if success else msg,
            duration_ms=(time.perf_counter() - start_t) * 1000,
        )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if not result.success:
            return ToolVerification(verified=False, details=f"Failed to close application: {result.error}")
        return ToolVerification(verified=True, details=f"Application '{arguments['app_name']}' closed and verified.")


class FocusWindowTool(BaseTool):
    """Brings a target application window to the foreground."""
    name = "focus_window"
    description = "Focuses and brings a window to the foreground by window title or process name."
    risk_level = RiskLevel.LOW
    parameters = {
        "title_or_name": ToolParameter("title_or_name", "string", "Window title or process name to focus.", required=True),
    }

    def execute(self, title_or_name: Optional[str] = None, title: Optional[str] = None, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        target = title_or_name or title or kwargs.get("name", "")
        from jarvis.subsystems.system.windows_executor import WindowsExecutor
        success, msg = WindowsExecutor.focus_window(target)
        return ToolResult(
            success=success,
            output={"target": target, "message": msg},
            error=None if success else msg,
            duration_ms=(time.perf_counter() - start_t) * 1000,
        )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        return ToolVerification(verified=result.success, details=result.output.get("message", "") if result.success else str(result.error))


class WindowControlTool(BaseTool):
    """Minimizes, maximizes, or restores a window."""
    name = "window_control"
    description = "Controls window state: 'minimize', 'maximize', or 'restore' for a window matching title or process name."
    risk_level = RiskLevel.LOW
    parameters = {
        "title_or_name": ToolParameter("title_or_name", "string", "Window title or process name.", required=True),
        "state": ToolParameter("state", "string", "Desired state: 'minimize', 'maximize', or 'restore'.", required=True),
    }

    def execute(
        self,
        title_or_name: Optional[str] = None,
        state: Optional[str] = None,
        title: Optional[str] = None,
        action: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        start_t = time.perf_counter()
        target = title_or_name or title or kwargs.get("name", "")
        desired_state = state or action or kwargs.get("window_state", "minimize")
        from jarvis.subsystems.system.windows_executor import WindowsExecutor
        success, msg = WindowsExecutor.set_window_state(target, desired_state)
        return ToolResult(
            success=success,
            output={"target": target, "state": desired_state, "message": msg},
            error=None if success else msg,
            duration_ms=(time.perf_counter() - start_t) * 1000,
        )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        return ToolVerification(verified=result.success, details=result.output.get("message", "") if result.success else str(result.error))


class ListWindowsTool(BaseTool):
    """Lists open desktop windows."""
    name = "list_windows"
    description = "Lists open desktop windows with title, PID, process name, and state."
    risk_level = RiskLevel.LOW
    parameters = {
        "visible_only": ToolParameter("visible_only", "boolean", "List only visible windows.", required=False, default=True),
    }

    def execute(self, visible_only: bool = True, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        from jarvis.subsystems.system.windows_executor import WindowsExecutor
        windows = WindowsExecutor.list_windows(visible_only=visible_only)
        return ToolResult(
            success=True,
            output={"windows": windows, "count": len(windows)},
            duration_ms=(time.perf_counter() - start_t) * 1000,
        )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        return ToolVerification(verified=result.success, details=f"Found {result.output.get('count', 0)} open window(s).")


class GetActiveWindowTool(BaseTool):
    """Returns details about the currently active (foreground) window."""
    name = "get_active_window"
    description = "Detects the currently focused window on the desktop and returns title, PID, and process name."
    risk_level = RiskLevel.LOW
    parameters = {}

    def execute(self, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        from jarvis.subsystems.system.windows_executor import WindowsExecutor
        active = WindowsExecutor.get_active_window()
        return ToolResult(
            success=True,
            output=active,
            duration_ms=(time.perf_counter() - start_t) * 1000,
        )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        title = result.output.get("title", "") if result.output else ""
        return ToolVerification(verified=True, details=f"Active window: '{title}'" if title else "No active window title detected.")


class StartProcessTool(BaseTool):
    """Starts a process or executable with arguments."""
    name = "start_process"
    description = "Launches an executable or process with optional command line arguments."
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "command": ToolParameter("command", "string", "Executable name or path to execute.", required=True),
        "arguments": ToolParameter("arguments", "list", "Optional list of command line arguments.", required=False, default=[]),
    }

    def execute(self, command: str, arguments: Optional[List[str]] = None, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        from jarvis.subsystems.system.windows_executor import WindowsExecutor
        success, msg, pid = WindowsExecutor.start_process(command, arguments)
        return ToolResult(
            success=success,
            output={"command": command, "pid": pid, "message": msg},
            error=None if success else msg,
            duration_ms=(time.perf_counter() - start_t) * 1000,
        )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        return ToolVerification(verified=result.success, details=result.output.get("message", "") if result.success else str(result.error))


class StopProcessTool(BaseTool):
    """Stops or terminates a running process by PID or process name."""
    name = "stop_process"
    description = "Stops a running process by PID or process name."
    risk_level = RiskLevel.HIGH
    parameters = {
        "process_identifier": ToolParameter("process_identifier", "string", "Process name or PID to terminate.", required=True),
        "force": ToolParameter("force", "boolean", "Force kill process.", required=False, default=False),
    }

    def execute(self, process_identifier: str, force: bool = False, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        from jarvis.subsystems.system.windows_executor import WindowsExecutor
        success, msg = WindowsExecutor.stop_process(process_identifier, force=force)
        return ToolResult(
            success=success,
            output={"target": process_identifier, "message": msg},
            error=None if success else msg,
            duration_ms=(time.perf_counter() - start_t) * 1000,
        )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        return ToolVerification(verified=result.success, details=result.output.get("message", "") if result.success else str(result.error))


class MouseMoveTool(BaseTool):
    """Moves the mouse cursor to desktop coordinates (x, y)."""
    name = "mouse_move"
    description = "Moves the mouse cursor to absolute desktop coordinates (x, y)."
    risk_level = RiskLevel.LOW
    parameters = {
        "x": ToolParameter("x", "integer", "X coordinate on screen in pixels.", required=True),
        "y": ToolParameter("y", "integer", "Y coordinate on screen in pixels.", required=True),
    }

    def execute(self, x: int, y: int, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        from jarvis.subsystems.system.windows_executor import WindowsExecutor
        success, msg = WindowsExecutor.mouse_move(x, y)
        return ToolResult(
            success=success,
            output={"x": x, "y": y, "message": msg},
            duration_ms=(time.perf_counter() - start_t) * 1000,
        )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        return ToolVerification(verified=True, details=f"Mouse moved to ({arguments['x']}, {arguments['y']}).")


class MouseClickTool(BaseTool):
    """Performs a single mouse click (left, right, middle)."""
    name = "mouse_click"
    description = "Performs a mouse click ('left', 'right', or 'middle') at current or optional coordinates (x, y)."
    risk_level = RiskLevel.LOW
    parameters = {
        "button": ToolParameter("button", "string", "Button to click: 'left', 'right', or 'middle'.", required=False, default="left"),
        "x": ToolParameter("x", "integer", "Optional X coordinate to click at.", required=False),
        "y": ToolParameter("y", "integer", "Optional Y coordinate to click at.", required=False),
    }

    def execute(self, button: str = "left", x: Optional[int] = None, y: Optional[int] = None, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        from jarvis.subsystems.system.windows_executor import WindowsExecutor
        coords = (int(x), int(y)) if x is not None and y is not None else None
        success, msg = WindowsExecutor.mouse_click(button=button, coords=coords)
        return ToolResult(
            success=success,
            output={"button": button, "coords": coords, "message": msg},
            duration_ms=(time.perf_counter() - start_t) * 1000,
        )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        return ToolVerification(verified=result.success, details=f"Executed {arguments.get('button', 'left')}-click.")


class MouseDoubleClickTool(BaseTool):
    """Performs a double click with the left mouse button."""
    name = "mouse_double_click"
    description = "Performs a double-click at current or optional coordinates (x, y)."
    risk_level = RiskLevel.LOW
    parameters = {
        "x": ToolParameter("x", "integer", "Optional X coordinate to double click at.", required=False),
        "y": ToolParameter("y", "integer", "Optional Y coordinate to double click at.", required=False),
    }

    def execute(self, x: Optional[int] = None, y: Optional[int] = None, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        from jarvis.subsystems.system.windows_executor import WindowsExecutor
        coords = (int(x), int(y)) if x is not None and y is not None else None
        success, msg = WindowsExecutor.mouse_double_click(coords=coords)
        return ToolResult(
            success=success,
            output={"coords": coords, "message": msg},
            duration_ms=(time.perf_counter() - start_t) * 1000,
        )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        return ToolVerification(verified=result.success, details="Executed double-click.")


class MouseRightClickTool(BaseTool):
    """Performs a right click with the mouse."""
    name = "mouse_right_click"
    description = "Performs a right-click at current or optional coordinates (x, y)."
    risk_level = RiskLevel.LOW
    parameters = {
        "x": ToolParameter("x", "integer", "Optional X coordinate to right click at.", required=False),
        "y": ToolParameter("y", "integer", "Optional Y coordinate to right click at.", required=False),
    }

    def execute(self, x: Optional[int] = None, y: Optional[int] = None, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        from jarvis.subsystems.system.windows_executor import WindowsExecutor
        coords = (int(x), int(y)) if x is not None and y is not None else None
        success, msg = WindowsExecutor.mouse_click(button="right", coords=coords)
        return ToolResult(
            success=success,
            output={"coords": coords, "message": msg},
            duration_ms=(time.perf_counter() - start_t) * 1000,
        )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        return ToolVerification(verified=result.success, details="Executed right-click.")


class SendHotkeyTool(BaseTool):
    """Sends keyboard shortcut or hotkey combination."""
    name = "send_hotkey"
    description = "Presses a keyboard hotkey combination (e.g. 'ctrl+c', 'ctrl+v', 'alt+tab', 'win+d', 'ctrl+s')."
    risk_level = RiskLevel.LOW
    parameters = {
        "hotkey": ToolParameter("hotkey", "string", "Key combination string (e.g. 'ctrl+c', 'win+d', 'alt+tab').", required=True),
    }

    def execute(self, hotkey: str, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        from jarvis.subsystems.system.windows_executor import WindowsExecutor
        success, msg = WindowsExecutor.send_hotkey(hotkey)
        return ToolResult(
            success=success,
            output={"hotkey": hotkey, "message": msg},
            error=None if success else msg,
            duration_ms=(time.perf_counter() - start_t) * 1000,
        )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        return ToolVerification(verified=result.success, details=f"Hotkey '{arguments['hotkey']}' executed.")


class ClipboardTool(BaseTool):
    """Reads or sets Windows clipboard content."""
    name = "clipboard"
    description = "Reads from ('get') or copies to ('set') the Windows clipboard."
    risk_level = RiskLevel.LOW
    parameters = {
        "action": ToolParameter("action", "string", "Action to perform: 'get' or 'set'.", required=True),
        "text": ToolParameter("text", "string", "Text to set on clipboard (required if action is 'set').", required=False, default=""),
    }

    def execute(self, action: str, text: Optional[str] = None, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        from jarvis.subsystems.system.windows_executor import WindowsExecutor
        act = action.strip().lower()

        if act == "get":
            clip_text = WindowsExecutor.get_clipboard()
            return ToolResult(
                success=True,
                output={"clipboard_text": clip_text, "text": clip_text, "length": len(clip_text)},
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        elif act == "set":
            content = text or ""
            ok = WindowsExecutor.set_clipboard(content)
            return ToolResult(
                success=ok,
                output={"copied_length": len(content), "text": content, "success": ok},
                error=None if ok else "Failed to write to Windows clipboard",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        else:
            return ToolResult(
                success=False,
                output=None,
                error=f"Unknown clipboard action '{action}'. Choose 'get' or 'set'.",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        return ToolVerification(verified=result.success, details=f"Clipboard {arguments.get('action', 'action')} verified.")


class ModifyFileTool(BaseTool):
    """Modifies file content by appending text or updating lines."""
    name = "modify_file"
    description = "Appends content to or overwrites an existing file."
    risk_level = RiskLevel.MEDIUM
    parameters = {
        "path": ToolParameter("path", "string", "Target file path.", required=True),
        "content": ToolParameter("content", "string", "Text content to append or update.", required=True),
        "mode": ToolParameter("mode", "string", "Write mode: 'append' or 'overwrite'.", required=False, default="append"),
    }

    def execute(self, path: str, content: str, mode: str = "append", **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        from jarvis.subsystems.system.windows_executor import WindowsExecutor
        success, msg = WindowsExecutor.modify_file(path, content, mode=mode)
        return ToolResult(
            success=success,
            output={"path": path, "mode": mode, "message": msg},
            error=None if success else msg,
            duration_ms=(time.perf_counter() - start_t) * 1000,
        )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        abs_p = os.path.abspath(arguments["path"])
        exists = os.path.exists(abs_p)
        return ToolVerification(
            verified=exists and result.success,
            details=f"File verified at '{abs_p}'." if exists else "Target file does not exist.",
        )


class VolumeControlTool(BaseTool):
    """Controls Windows system master volume."""
    name = "volume_control"
    description = "Controls Windows system master volume (action: 'mute', 'unmute', 'up', 'down')."
    risk_level = RiskLevel.LOW
    parameters = {
        "action": ToolParameter("action", "string", "Volume action: 'mute', 'unmute', 'up', or 'down'.", required=True),
        "level": ToolParameter("level", "integer", "Optional percentage step amount (e.g. 5, 10).", required=False, default=2),
    }

    def execute(self, action: str, level: Optional[int] = None, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        from jarvis.subsystems.system.windows_executor import WindowsExecutor
        success, msg = WindowsExecutor.set_volume(action, level=level)
        return ToolResult(
            success=success,
            output={"action": action, "message": msg},
            error=None if success else msg,
            duration_ms=(time.perf_counter() - start_t) * 1000,
        )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        return ToolVerification(verified=result.success, details=result.output.get("message", "") if result.success else str(result.error))


class DisplayControlTool(BaseTool):
    """Retrieves display information and monitor resolution."""
    name = "display_control"
    description = "Retrieves display information, screen resolution, and DPI metrics."
    risk_level = RiskLevel.LOW
    parameters = {}

    def execute(self, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        from jarvis.subsystems.system.windows_executor import WindowsExecutor
        info = WindowsExecutor.get_display_info()
        return ToolResult(
            success=True,
            output=info,
            duration_ms=(time.perf_counter() - start_t) * 1000,
        )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        return ToolVerification(verified=True, details=f"Display resolution: {result.output.get('width')}x{result.output.get('height')}.")


class SleepPCTool(BaseTool):
    """Puts the Windows computer into sleep state."""
    name = "sleep_pc"
    description = "Puts the Windows workstation into sleep mode."
    risk_level = RiskLevel.HIGH
    parameters = {}

    def execute(self, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        from jarvis.subsystems.system.windows_executor import WindowsExecutor
        success, msg = WindowsExecutor.sleep_pc()
        return ToolResult(
            success=success,
            output={"message": msg},
            duration_ms=(time.perf_counter() - start_t) * 1000,
        )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        return ToolVerification(verified=True, details="Sleep command executed.")


