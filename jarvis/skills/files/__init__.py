"""File System & Organization Skills for Phase 11.

Domain: files/
Skills:
- files.organize
- files.search
- files.safe_delete
"""

from __future__ import annotations
import fnmatch
import os
import shutil
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


class FilesOrganizeSkill(BaseSkill):
    name = "files.organize"
    domain = "files"
    capability = "Categorizes and moves files in a directory into structured subfolders by extension."
    required_tools = ["batch_organize_files"]
    parameters = {
        "directory": SkillParameter("directory", "path", "Target directory to organize", required=True),
    }

    def execute(self, params: Dict[str, Any], context: SkillContext) -> SkillResult:
        dir_path = os.path.abspath(params["directory"])
        if not os.path.exists(dir_path):
            return SkillResult(success=False, error=f"Directory '{dir_path}' does not exist.")

        if self.registry:
            tool = self.registry.get("batch_organize_files")
            if tool:
                res = tool.execute(directory=dir_path)
                return SkillResult(success=res.success, output=res.output, artifacts={"directory": dir_path})

        # Built-in organization fallback
        moved_count = 0
        categories = {
            "Documents": [".pdf", ".docx", ".txt", ".pptx", ".xlsx", ".md"],
            "Images": [".png", ".jpg", ".jpeg", ".gif", ".svg"],
            "Code": [".py", ".js", ".ts", ".html", ".css", ".json", ".sql"],
            "Archives": [".zip", ".tar", ".gz", ".7z"],
        }
        for item in os.listdir(dir_path):
            item_path = os.path.join(dir_path, item)
            if os.path.isfile(item_path):
                ext = os.path.splitext(item)[1].lower()
                target_folder = "Misc"
                for cat, exts in categories.items():
                    if ext in exts:
                        target_folder = cat
                        break
                target_dir = os.path.join(dir_path, target_folder)
                os.makedirs(target_dir, exist_ok=True)
                shutil.move(item_path, os.path.join(target_dir, item))
                moved_count += 1

        msg = f"Organized {moved_count} file(s) into categorized subdirectories in '{dir_path}'."
        return SkillResult(success=True, output=msg, artifacts={"directory": dir_path, "moved_count": moved_count})

    def verify(self, params: Dict[str, Any], result: SkillResult, context: SkillContext) -> VerificationResult:
        dir_path = params.get("directory", "")
        if os.path.exists(dir_path):
            return VerificationResult(passed=True, evidence=f"Organized directory verified: {dir_path}")
        return VerificationResult(passed=False, explanation=f"Directory {dir_path} not found.")


class FilesSearchSkill(BaseSkill):
    name = "files.search"
    domain = "files"
    capability = "Searches for files matching name or content pattern across a directory."
    required_tools = ["search_files"]
    parameters = {
        "query": SkillParameter("query", "string", "File name pattern or search query", required=True),
        "directory": SkillParameter("directory", "path", "Root directory to search", required=False, default="."),
    }

    def execute(self, params: Dict[str, Any], context: SkillContext) -> SkillResult:
        query = params["query"]
        root_dir = os.path.abspath(params.get("directory", "."))
        pattern = f"*{query}*" if "*" not in query else query

        res = self.invoke_tool("search_files", directory=root_dir, pattern=pattern)
        if res and res.success:
            matches = res.output.get("matches", []) if isinstance(res.output, dict) else []
            context.set("search_matches", matches)
            return SkillResult(
                success=True,
                output=f"Found {len(matches)} matching file(s) for '{query}'.",
                artifacts={"query": query, "matches": matches},
            )

        matches = []
        for root, _, files in os.walk(root_dir):
            for f in files:
                if fnmatch.fnmatch(f.lower(), f"*{query.lower()}*"):
                    matches.append(os.path.join(root, f))
                if len(matches) >= 20:
                    break
            if len(matches) >= 20:
                break

        context.set("search_matches", matches)
        return SkillResult(
            success=True,
            output=f"Found {len(matches)} matching file(s) for '{query}'.",
            artifacts={"query": query, "matches": matches},
        )


class FilesSafeDeleteSkill(BaseSkill):
    name = "files.safe_delete"
    domain = "files"
    capability = "Performs guarded deletion of files or temporary items with safety confirmation check."
    required_tools = ["safe_delete_projects"]
    parameters = {
        "target_path": SkillParameter("target_path", "path", "Path of file or directory to delete", required=True),
        "confirmed": SkillParameter("confirmed", "boolean", "Confirmation flag", required=False, default=False),
    }

    def execute(self, params: Dict[str, Any], context: SkillContext) -> SkillResult:
        target = os.path.abspath(params["target_path"])
        confirmed = bool(params.get("confirmed", False))

        if not confirmed:
            return SkillResult(
                success=False,
                error=f"Confirmation required: Deletion of '{target}' is permanent. Pass confirmed=True to proceed.",
            )

        if not os.path.exists(target):
            return SkillResult(success=False, error=f"Target '{target}' does not exist.")

        if os.path.isdir(target):
            shutil.rmtree(target)
        else:
            os.remove(target)

        return SkillResult(success=True, output=f"Safely deleted '{target}'.", artifacts={"target": target})
