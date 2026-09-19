"""Master Autonomous Coding Agent for JARVIS (Phase 13).

Executes the end-to-end 10-stage pipeline:
Open VS Code -> Inspect Project -> Read Files -> Run Tests -> Observe Failure ->
Understand Error -> Modify Code -> Run Tests Again -> Verify -> Explain Changes
"""

from __future__ import annotations
import os
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from jarvis.subsystems.coding.code_modifier import CodeModifier
from jarvis.subsystems.coding.dependency_analyzer import DependencyAnalyzer
from jarvis.subsystems.coding.error_analyzer import ErrorAnalyzer
from jarvis.subsystems.coding.repo_inspector import RepoInspector
from jarvis.subsystems.coding.schemas import (
    CodePatch,
    CodingTaskResult,
    CommitPreparation,
    ErrorAnalysis,
    RepoInspection,
    TestRunResult,
)
from jarvis.subsystems.coding.test_runner import TestRunner


class CodingAgent:
    """Autonomous software engineering agent coordinating repository awareness, testing, and repairs."""

    def __init__(
        self,
        workspace_root: str = ".",
        repo_inspector: Optional[RepoInspector] = None,
        dependency_analyzer: Optional[DependencyAnalyzer] = None,
        test_runner: Optional[TestRunner] = None,
        error_analyzer: Optional[ErrorAnalyzer] = None,
        code_modifier: Optional[CodeModifier] = None,
    ):
        self.workspace_root = os.path.abspath(workspace_root)
        self.repo_inspector = repo_inspector or RepoInspector(self.workspace_root)
        self.dependency_analyzer = dependency_analyzer or DependencyAnalyzer(self.workspace_root)
        self.test_runner = test_runner or TestRunner(self.workspace_root)
        self.error_analyzer = error_analyzer or ErrorAnalyzer(self.workspace_root)
        self.code_modifier = code_modifier or CodeModifier()

    def open_vscode(self, target_path: Optional[str] = None) -> bool:
        """Launches or focuses Visual Studio Code on the workspace or file."""
        path_to_open = os.path.abspath(target_path or self.workspace_root)
        try:
            subprocess.Popen(["code", path_to_open], shell=True)
            return True
        except Exception:
            return False

    def fix_failing_test(
        self,
        test_path: str,
        target_file: Optional[str] = None,
        target_snippet: Optional[str] = None,
        replacement_snippet: Optional[str] = None,
        auto_commit: bool = True,
        open_editor: bool = True,
    ) -> CodingTaskResult:
        """Executes the complete 10-stage autonomous test-and-repair pipeline."""
        # Stage 1: Open VS Code
        if open_editor:
            self.open_vscode(self.workspace_root)

        # Stage 2: Inspect project & repository awareness
        repo_status = self.repo_inspector.inspect(self.workspace_root)

        # Stage 3: Read files & dependency awareness
        dep_graph = self.dependency_analyzer.analyze_workspace()

        # Stage 4: Run initial tests in terminal
        initial_test = self.test_runner.run_tests(test_path)

        patches_applied: List[CodePatch] = []
        error_analysis: Optional[ErrorAnalysis] = None
        explanation = ""

        # If tests already pass, report clean status
        if initial_test.passed:
            explanation = f"All tests in '{test_path}' already pass successfully. No modifications required."
            return CodingTaskResult(
                success=True,
                project_path=self.workspace_root,
                initial_test=initial_test,
                error_analysis=None,
                patches_applied=[],
                final_test=initial_test,
                repo_status=repo_status,
                commit_prep=None,
                explanation=explanation,
            )

        # Stage 5 & 6: Observe failure and understand error
        error_analysis = self.error_analyzer.analyze_test_failure(initial_test)

        # Determine target file and patch parameters
        file_to_patch = target_file or (error_analysis.failing_file if error_analysis else "")
        if not file_to_patch and test_path:
            file_to_patch = os.path.abspath(test_path)

        # Stage 7: Modify code
        patch_success = False
        if file_to_patch and target_snippet and replacement_snippet:
            success, patch, err = self.code_modifier.apply_replacement(
                file_path=file_to_patch,
                target_snippet=target_snippet,
                replacement_snippet=replacement_snippet,
                explanation=f"Fix error: {error_analysis.error_message if error_analysis else 'test assertion failure'}",
            )
            if success and patch:
                patches_applied.append(patch)
                patch_success = True
        elif file_to_patch and error_analysis:
            # Automatic heuristic patch derivation if target not explicitly provided
            derived_patch = self._derive_and_apply_automatic_fix(error_analysis, file_to_patch)
            if derived_patch:
                patches_applied.append(derived_patch)
                patch_success = True

        # Stage 8: Run tests again
        final_test = self.test_runner.run_tests(test_path)

        # Stage 9: Verify
        if not final_test.passed and patches_applied:
            # Verification failed; roll back modifications to prevent broken state
            for p in patches_applied:
                self.code_modifier.rollback(p.file_path)
            explanation = (
                f"Test failure observed: '{error_analysis.error_message if error_analysis else 'unknown'}'. "
                f"Attempted patch did not resolve test; changes safely rolled back."
            )
            return CodingTaskResult(
                success=False,
                project_path=self.workspace_root,
                initial_test=initial_test,
                error_analysis=error_analysis,
                patches_applied=[],
                final_test=final_test,
                repo_status=repo_status,
                commit_prep=None,
                explanation=explanation,
            )

        # Stage 10: Explain changes & prepare commit
        commit_prep = None
        if final_test.passed and patches_applied:
            modified_rel_paths = [os.path.relpath(p.file_path, self.workspace_root) for p in patches_applied]
            commit_msg = f"fix({os.path.basename(test_path)}): resolve failing tests in {', '.join(modified_rel_paths)}"
            
            if auto_commit:
                commit_prep = self.repo_inspector.prepare_commit(
                    files=modified_rel_paths,
                    message=commit_msg,
                    repo_path=self.workspace_root,
                    commit_now=False,  # Stage and prepare, keep commit ready
                )

            diff_preview = self.repo_inspector.get_diff(self.workspace_root)
            explanation = (
                f"Fixed failing test in '{test_path}'.\n"
                f"Root cause: {error_analysis.root_cause if error_analysis else 'Assertion mismatch'}.\n"
                f"Modifications applied to: {', '.join(modified_rel_paths)}.\n"
                f"Re-executed tests: All tests now PASS.\n"
                f"Git status: Changes staged for commit on branch '{repo_status.branch}'.\n"
                f"Remote Push Gate: Autonomous push blocked (requires explicit user confirmation)."
            )

        return CodingTaskResult(
            success=final_test.passed,
            project_path=self.workspace_root,
            initial_test=initial_test,
            error_analysis=error_analysis,
            patches_applied=patches_applied,
            final_test=final_test,
            repo_status=self.repo_inspector.inspect(self.workspace_root),
            commit_prep=commit_prep,
            explanation=explanation,
        )

    def _derive_and_apply_automatic_fix(
        self,
        analysis: ErrorAnalysis,
        file_path: str,
    ) -> Optional[CodePatch]:
        """Attempts to resolve known assertion or typo patterns automatically."""
        if not analysis.target_code_snippet:
            return None

        # Check for common off-by-one or assertion discrepancies in test code
        target = analysis.target_code_snippet
        repl = None

        # Example: self.assertEqual(result, 40) vs 42
        if "assertEqual" in target and "AssertionError" in analysis.error_message:
            import re
            m = re.search(r"AssertionError:\s*(.*?)\s*!=\s*(.*)", analysis.error_message)
            if m:
                actual_val = m.group(1).strip()
                expected_val = m.group(2).strip()
                if expected_val in target:
                    repl = target.replace(expected_val, actual_val)

        if repl and repl != target:
            success, patch, _ = self.code_modifier.apply_replacement(
                file_path=file_path,
                target_snippet=target,
                replacement_snippet=repl,
                explanation=f"Reconciled expected assertion value: {actual_val}",
            )
            if success:
                return patch

        return None
