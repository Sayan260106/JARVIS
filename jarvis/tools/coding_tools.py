"""Coding & Version Control Tools for JARVIS (Phase 13).

Provides tools for autonomous test diagnosis, repository inspection, commit preparation,
and security-gated remote pushes.
"""

from __future__ import annotations
import time
from typing import Any, Dict, List, Optional

from jarvis.subsystems.coding import (
    CodingAgent,
    RepoInspector,
    get_coding_agent,
    run_coding_agent,
)
from jarvis.tools.base import (
    BaseTool,
    PermissionLevel,
    RiskLevel,
    ToolParameter,
    ToolResult,
    ToolVerification,
)


class CodingAgentTool(BaseTool):
    """Executes the autonomous 10-stage coding agent pipeline to fix failing tests."""
    name = "run_coding_agent"
    description = (
        "Opens project in VS Code, inspects repository, runs tests, understands errors, "
        "modifies code safely with AST checks, re-runs tests to verify, and prepares git commits."
    )
    risk_level = RiskLevel.MEDIUM
    permission_level = PermissionLevel.LEVEL_1_REVERSIBLE_WRITE
    parameters = {
        "test_path": ToolParameter("test_path", "string", "Path or module of the failing test suite.", required=True),
        "target_file": ToolParameter("target_file", "string", "Optional target source file to modify.", required=False, default=None),
        "target_snippet": ToolParameter("target_snippet", "string", "Optional code snippet to replace.", required=False, default=None),
        "replacement_snippet": ToolParameter("replacement_snippet", "string", "Optional fixed replacement code snippet.", required=False, default=None),
        "workspace_root": ToolParameter("workspace_root", "string", "Workspace project root directory.", required=False, default="."),
        "open_editor": ToolParameter("open_editor", "boolean", "Whether to launch/focus VS Code.", required=False, default=True),
    }

    def execute(
        self,
        test_path: str,
        target_file: Optional[str] = None,
        target_snippet: Optional[str] = None,
        replacement_snippet: Optional[str] = None,
        workspace_root: str = ".",
        open_editor: bool = True,
        **kwargs,
    ) -> ToolResult:
        start_t = time.perf_counter()
        try:
            agent = CodingAgent(workspace_root=workspace_root)
            result = agent.fix_failing_test(
                test_path=test_path,
                target_file=target_file,
                target_snippet=target_snippet,
                replacement_snippet=replacement_snippet,
                open_editor=open_editor,
            )

            output = {
                "success": result.success,
                "project_path": result.project_path,
                "initial_tests_passed": result.initial_test.passed,
                "final_tests_passed": result.final_test.passed,
                "modified_files": [p.file_path for p in result.patches_applied],
                "patches_applied": [p.to_dict() for p in result.patches_applied],
                "commit_prepared": result.commit_prep.to_dict() if result.commit_prep else None,
                "explanation": result.explanation,
            }
            return ToolResult(
                success=result.success,
                output=output,
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
            return ToolVerification(verified=False, details=f"Coding agent failed: {result.error}")
        data = result.output or {}
        return ToolVerification(
            verified=data.get("final_tests_passed", False),
            details=f"Coding agent finished: Tests pass={data.get('final_tests_passed')}, modified={len(data.get('modified_files', []))} files.",
        )


class GitInspectTool(BaseTool):
    """Inspects repository awareness: branch, commit SHA, modified files, and git diff."""
    name = "git_inspect"
    description = "Queries git status, active branch, HEAD commit, uncommitted files, and working tree diff."
    risk_level = RiskLevel.LOW
    permission_level = PermissionLevel.LEVEL_0_READ
    parameters = {
        "repo_path": ToolParameter("repo_path", "string", "Repository root path (default: current workspace).", required=False, default="."),
    }

    def execute(self, repo_path: str = ".", **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        try:
            inspector = RepoInspector(repo_path)
            inspection = inspector.inspect(repo_path)
            return ToolResult(
                success=True,
                output=inspection.to_dict(),
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
            return ToolVerification(verified=False, details=f"Git inspect failed: {result.error}")
        return ToolVerification(
            verified=True,
            details=f"Repository inspected on branch '{result.output.get('branch')}'. Clean={result.output.get('is_clean')}.",
        )


class GitCommitPrepTool(BaseTool):
    """Stages modified files and prepares a git commit message with diff summary."""
    name = "git_prepare_commit"
    description = "Stages modified files and generates a git commit preparation summary with diff preview."
    risk_level = RiskLevel.MEDIUM
    permission_level = PermissionLevel.LEVEL_1_REVERSIBLE_WRITE
    parameters = {
        "files": ToolParameter("files", "list", "List of relative file paths to stage.", required=True),
        "message": ToolParameter("message", "string", "Commit message to prepare.", required=True),
        "repo_path": ToolParameter("repo_path", "string", "Repository root directory.", required=False, default="."),
    }

    def execute(self, files: List[str], message: str, repo_path: str = ".", **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        try:
            inspector = RepoInspector(repo_path)
            prep = inspector.prepare_commit(files=files, message=message, repo_path=repo_path, commit_now=False)
            return ToolResult(
                success=True,
                output=prep.to_dict(),
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
            return ToolVerification(verified=False, details=f"Commit prep failed: {result.error}")
        return ToolVerification(
            verified=True,
            details=f"Commit prepared for branch '{result.output.get('branch')}' with {len(result.output.get('staged_files', []))} files.",
        )


class GitPushTool(BaseTool):
    """Gated git push tool. Strictly blocks autonomous git push without explicit user approval."""
    name = "git_push"
    description = "Pushes committed changes to remote repository. Requires explicit security gate confirmation."
    risk_level = RiskLevel.HIGH
    permission_level = PermissionLevel.LEVEL_2_EXTERNAL_ACTION
    parameters = {
        "branch": ToolParameter("branch", "string", "Branch to push (optional).", required=False, default=None),
        "repo_path": ToolParameter("repo_path", "string", "Repository directory.", required=False, default="."),
        "confirmed": ToolParameter("confirmed", "boolean", "User confirmation flag for remote push.", required=False, default=False),
    }

    def build_confirmation_preview(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Preview payload required by Level 2 permission gatekeeper."""
        return {
            "action": "git_push",
            "branch": arguments.get("branch") or "current",
            "repo_path": arguments.get("repo_path", "."),
            "warning": "This operation will publish code commits to the remote git repository.",
        }

    def execute(self, branch: Optional[str] = None, repo_path: str = ".", confirmed: bool = False, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        if not confirmed:
            return ToolResult(
                success=False,
                output=None,
                error="SECURITY GATE: Autonomous git push is strictly prohibited. Set confirmed=True after explicit user approval.",
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

        try:
            inspector = RepoInspector(repo_path)
            success, msg = inspector.push_to_remote(repo_path=repo_path, branch=branch, force_confirmed=True)
            return ToolResult(
                success=success,
                output={"status": "pushed" if success else "failed", "message": msg},
                error=None if success else msg,
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
            return ToolVerification(verified=False, details=f"Push blocked or failed: {result.error}")
        return ToolVerification(verified=True, details="Remote git push successfully confirmed and executed.")
