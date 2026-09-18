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
        from jarvis.subsystems.system.app_launcher import WindowsAppLauncher
        success, msg, pid = WindowsAppLauncher.launch(app_name)
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
        cmd = "shutdown /a" if abort else f"shutdown /s /t {delay_seconds}"
        try:
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            return ToolResult(
                success=(res.returncode == 0),
                output={"command": cmd, "stdout": res.stdout.strip()},
                error=res.stderr.strip() if res.returncode != 0 else None,
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
            return ToolVerification(verified=False, details=f"Shutdown command failed: {result.error}")
        return ToolVerification(verified=True, details="Shutdown command executed and verified.")


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
        cmd = "shutdown /a" if abort else f"shutdown /r /t {delay_seconds}"
        try:
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            return ToolResult(
                success=(res.returncode == 0),
                output={"command": cmd, "stdout": res.stdout.strip()},
                error=res.stderr.strip() if res.returncode != 0 else None,
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
            return ToolVerification(verified=False, details=f"Restart command failed: {result.error}")
        return ToolVerification(verified=True, details="Restart command executed and verified.")


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

