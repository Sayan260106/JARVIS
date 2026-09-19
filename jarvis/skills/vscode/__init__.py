"""Visual Studio Code Skills for Phase 11.

Domain: vscode/
Skills:
- vscode.open_file
- vscode.open_workspace
- vscode.run_terminal_command
"""

from __future__ import annotations
import os
import subprocess
from typing import Any, Dict, List, Optional
from jarvis.skills.base import (
    BaseSkill,
    PreconditionResult,
    RecoveryAction,
    RecoveryStrategy,
    SkillContext,
    SkillParameter,
    SkillResult,
    VerificationResult,
)
from jarvis.subsystems.system.windows_executor import WindowsExecutor


class VSCodeOpenFileSkill(BaseSkill):
    name = "vscode.open_file"
    domain = "vscode"
    capability = "Launches or focuses VS Code and opens a target file."
    required_tools = ["open_application", "open_file"]
    parameters = {
        "file_path": SkillParameter("file_path", "path", "File path to open in VS Code", required=True),
        "line_number": SkillParameter("line_number", "integer", "Optional line number to jump to", required=False, default=None),
    }

    def execute(self, params: Dict[str, Any], context: SkillContext) -> SkillResult:
        fpath = os.path.abspath(params["file_path"])
        line = params.get("line_number")
        target_arg = f"{fpath}:{line}" if line else fpath

        # Create file if it doesn't exist
        if not os.path.exists(fpath):
            os.makedirs(os.path.dirname(fpath) or ".", exist_ok=True)
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(f"# Created by JARVIS\n")

        # Launch via 'code <file_path>'
        try:
            subprocess.Popen(["code", "-g", target_arg], shell=True)
            context.set("active_editor_file", fpath)
            return SkillResult(
                success=True,
                output=f"Opened file '{os.path.basename(fpath)}' in Visual Studio Code.",
                artifacts={"file_path": fpath, "editor": "Visual Studio Code"},
            )
        except Exception as e:
            # Fallback to system open
            WindowsExecutor.launch_app(fpath)
            return SkillResult(
                success=True,
                output=f"Opened '{fpath}' via system file handler.",
                artifacts={"file_path": fpath},
            )

    def verify(self, params: Dict[str, Any], result: SkillResult, context: SkillContext) -> VerificationResult:
        fpath = params.get("file_path", "")
        if fpath and os.path.exists(fpath):
            return VerificationResult(passed=True, evidence=f"File verified on disk at {fpath}")
        return VerificationResult(passed=False, explanation=f"File {fpath} does not exist.")


class VSCodeOpenWorkspaceSkill(BaseSkill):
    name = "vscode.open_workspace"
    domain = "vscode"
    capability = "Opens a project directory workspace in VS Code."
    required_tools = ["open_application"]
    parameters = {
        "workspace_folder": SkillParameter("workspace_folder", "path", "Project folder directory", required=True),
    }

    def execute(self, params: Dict[str, Any], context: SkillContext) -> SkillResult:
        folder = os.path.abspath(params["workspace_folder"])
        os.makedirs(folder, exist_ok=True)

        try:
            subprocess.Popen(["code", folder], shell=True)
            context.set("active_workspace", folder)
            return SkillResult(success=True, output=f"Opened workspace '{os.path.basename(folder)}' in VS Code.", artifacts={"workspace": folder})
        except Exception as e:
            return SkillResult(success=False, error=f"Failed to open workspace in VS Code: {e}")


class VSCodeRunTerminalSkill(BaseSkill):
    name = "vscode.run_terminal_command"
    domain = "vscode"
    capability = "Runs a shell command in workspace terminal."
    required_tools = ["run_command"]
    parameters = {
        "command": SkillParameter("command", "string", "Shell command to run", required=True),
        "cwd": SkillParameter("cwd", "path", "Working directory", required=False, default="."),
    }

    def execute(self, params: Dict[str, Any], context: SkillContext) -> SkillResult:
        cmd = params["command"]
        cwd = os.path.abspath(params.get("cwd", "."))

        if self.registry:
            tool = self.registry.get("run_command")
            if tool:
                res = tool.execute(command=cmd, cwd=cwd)
                return SkillResult(success=res.success, output=res.output, artifacts={"command": cmd})

        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
        return SkillResult(
            success=(res.returncode == 0),
            output=res.stdout or res.stderr,
            artifacts={"returncode": res.returncode},
        )
