"""Code Modification & AST-Validated Patching Engine for JARVIS Coding Agent (Phase 13).

Applies surgical code replacements, verifies syntax integrity using Python AST,
and supports automated file rollback.
"""

from __future__ import annotations
import ast
import os
import shutil
from typing import Dict, Optional, Tuple

from jarvis.subsystems.coding.schemas import CodePatch


class CodeModifier:
    """Safely patches source code files with AST verification and rollback protection."""

    def __init__(self):
        self._backups: Dict[str, str] = {}

    def backup(self, file_path: str) -> bool:
        """Stores a snapshot of the original file content for rollback."""
        abs_p = os.path.abspath(file_path)
        if not os.path.exists(abs_p):
            return False
        with open(abs_p, "r", encoding="utf-8", errors="ignore") as f:
            self._backups[abs_p] = f.read()
        return True

    def rollback(self, file_path: str) -> bool:
        """Restores file content from previous backup if available."""
        abs_p = os.path.abspath(file_path)
        if abs_p in self._backups:
            with open(abs_p, "w", encoding="utf-8") as f:
                f.write(self._backups[abs_p])
            return True
        return False

    def validate_syntax(self, code_text: str, file_path: str = "<patch>") -> Tuple[bool, Optional[str]]:
        """Parses python syntax using AST to guard against syntax errors."""
        try:
            ast.parse(code_text, filename=file_path)
            return True, None
        except SyntaxError as se:
            return False, f"SyntaxError at line {se.lineno}: {se.msg}"
        except Exception as e:
            return False, str(e)

    def apply_replacement(
        self,
        file_path: str,
        target_snippet: str,
        replacement_snippet: str,
        explanation: str = "Code bug fix",
    ) -> Tuple[bool, Optional[CodePatch], Optional[str]]:
        """Applies a target snippet replacement with AST syntax validation."""
        abs_p = os.path.abspath(file_path)
        if not os.path.exists(abs_p):
            return False, None, f"File '{abs_p}' does not exist."

        # Create backup
        self.backup(abs_p)

        with open(abs_p, "r", encoding="utf-8", errors="ignore") as f:
            original_content = f.read()

        if target_snippet not in original_content:
            return False, None, f"Target snippet not found in '{os.path.basename(abs_p)}'."

        candidate_content = original_content.replace(target_snippet, replacement_snippet, 1)

        # Validate syntax if python file
        if abs_p.endswith(".py"):
            valid, err = self.validate_syntax(candidate_content, abs_p)
            if not valid:
                return False, None, f"Refusing patch due to syntax invalidity: {err}"

        # Write to disk
        try:
            with open(abs_p, "w", encoding="utf-8") as f:
                f.write(candidate_content)

            patch = CodePatch(
                file_path=abs_p,
                target_snippet=target_snippet,
                replacement_snippet=replacement_snippet,
                explanation=explanation,
            )
            return True, patch, None
        except Exception as e:
            self.rollback(abs_p)
            return False, None, f"Failed writing patch to disk: {e}"
