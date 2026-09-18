"""Windows Application Launcher & Smart Alias Resolver for JARVIS.

Supports protocol URIs (e.g. microsoft-edge:, spotify:) and executable paths.
"""

from __future__ import annotations
import os
import shutil
import subprocess
from typing import Dict, Optional, Tuple


class WindowsAppLauncher:
    """Resolves natural language app names to Windows executables and protocol URIs."""

    # Common Windows application aliases mapped to execution commands or protocol URIs
    KNOWN_APPS: Dict[str, Dict[str, str]] = {
        "edge": {"type": "protocol", "target": "microsoft-edge:"},
        "microsoft edge": {"type": "protocol", "target": "microsoft-edge:"},
        "msedge": {"type": "protocol", "target": "microsoft-edge:"},
        "spotify": {"type": "protocol", "target": "spotify:"},
        "code": {"type": "cmd", "target": "code"},
        "vs code": {"type": "cmd", "target": "code"},
        "vscode": {"type": "cmd", "target": "code"},
        "visual studio code": {"type": "cmd", "target": "code"},
        "notepad": {"type": "cmd", "target": "notepad.exe"},
        "calc": {"type": "cmd", "target": "calc.exe"},
        "calculator": {"type": "cmd", "target": "calc.exe"},
        "explorer": {"type": "cmd", "target": "explorer.exe"},
        "file explorer": {"type": "cmd", "target": "explorer.exe"},
        "terminal": {"type": "cmd", "target": "wt.exe"},
        "windows terminal": {"type": "cmd", "target": "wt.exe"},
        "powershell": {"type": "cmd", "target": "powershell.exe"},
        "cmd": {"type": "cmd", "target": "cmd.exe"},
        "chrome": {"type": "cmd", "target": "chrome.exe"},
        "google chrome": {"type": "cmd", "target": "chrome.exe"},
        "task manager": {"type": "cmd", "target": "taskmgr.exe"},
        "paint": {"type": "cmd", "target": "mspaint.exe"},
    }

    @classmethod
    def resolve_app(cls, app_name: str) -> Dict[str, str]:
        """Resolves raw application name to target type ('protocol' or 'cmd') and target string."""
        clean = app_name.strip().lower()
        if clean in cls.KNOWN_APPS:
            return cls.KNOWN_APPS[clean]

        # Check if user already provided a protocol URI
        if ":" in clean and not os.path.exists(app_name):
            return {"type": "protocol", "target": app_name}

        # Fallback to direct executable command
        return {"type": "cmd", "target": app_name}

    @classmethod
    def launch(cls, app_name: str, arguments: Optional[str] = None) -> Tuple[bool, str, Optional[int]]:
        """Launches the application on Windows.

        Returns:
            Tuple of (success: bool, description: str, pid: Optional[int])
        """
        spec = cls.resolve_app(app_name)
        target_type = spec["type"]
        target = spec["target"]

        if target_type == "protocol":
            try:
                os.startfile(target)
                return True, f"Launched application via protocol '{target}'", None
            except Exception as e:
                # If protocol fails, try shell command fallback
                try:
                    proc = subprocess.Popen(f"start {target}", shell=True)
                    return True, f"Launched application via shell 'start {target}'", proc.pid
                except Exception as ex2:
                    return False, f"Failed to launch protocol '{target}': {e} / {ex2}", None

        else:
            # Check if specific VS Code paths exist if 'code' command isn't directly resolved
            if target == "code" and not shutil.which("code"):
                vscode_path = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe")
                if os.path.exists(vscode_path):
                    target = f'"{vscode_path}"'

            cmd = f"{target} {arguments}" if arguments else target
            try:
                proc = subprocess.Popen(cmd, shell=True)
                return True, f"Launched process '{cmd}' (PID: {proc.pid})", proc.pid
            except Exception as e:
                return False, f"Failed to launch command '{cmd}': {e}", None
