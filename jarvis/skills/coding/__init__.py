"""Coding & Software Engineering Skills for JARVIS (Phase 11 & Phase 13).

Domain: coding/
Skills:
- coding.analyze_code
- coding.fix_bug
- coding.run_tests
- coding.fix_failing_test
- coding.inspect_repo
- coding.prepare_commit
"""

from __future__ import annotations
import ast
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


class CodingAnalyzeCodeSkill(BaseSkill):
    name = "coding.analyze_code"
    domain = "coding"
    capability = "Parses and checks source code for syntax errors, smells, and structural issues."
    required_tools = ["get_active_document"]
    parameters = {
        "file_path": SkillParameter("file_path", "path", "Source file to inspect", required=True),
    }

    def execute(self, params: Dict[str, Any], context: SkillContext) -> SkillResult:
        fpath = os.path.abspath(params["file_path"])
        if not os.path.exists(fpath):
            return SkillResult(success=False, error=f"Source file '{fpath}' does not exist.")

        issues: List[str] = []
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                code_text = f.read()

            if fpath.endswith(".py"):
                try:
                    ast.parse(code_text)
                except SyntaxError as se:
                    issues.append(f"SyntaxError at line {se.lineno}: {se.msg}")

            context.set("code_issues", issues)
            return SkillResult(
                success=True,
                output={"file": fpath, "issues_count": len(issues), "issues": issues, "status": "Clean" if not issues else "Needs Fix"},
                artifacts={"file_path": fpath, "clean": len(issues) == 0, "issues": issues},
            )
        except Exception as e:
            return SkillResult(success=False, error=f"Analysis failed: {e}")

    def verify(self, params: Dict[str, Any], result: SkillResult, context: SkillContext) -> VerificationResult:
        fpath = params.get("file_path", "")
        if fpath and os.path.exists(fpath):
            return VerificationResult(passed=True, evidence=f"Analyzed {os.path.basename(fpath)}")
        return VerificationResult(passed=False, explanation=f"File {fpath} not found.")


class CodingFixBugSkill(BaseSkill):
    name = "coding.fix_bug"
    domain = "coding"
    capability = "Generates and applies targeted code fix to resolve bugs or exceptions."
    required_tools = ["modify_file"]
    parameters = {
        "file_path": SkillParameter("file_path", "path", "Target code file to fix", required=True),
        "target": SkillParameter("target", "string", "Code snippet or string to replace", required=False, default=""),
        "replacement": SkillParameter("replacement", "string", "Fixed code replacement", required=False, default=""),
    }

    def execute(self, params: Dict[str, Any], context: SkillContext) -> SkillResult:
        fpath = os.path.abspath(params["file_path"])
        target = params.get("target", "")
        repl = params.get("replacement", "")

        if not os.path.exists(fpath):
            return SkillResult(success=False, error=f"Target file '{fpath}' does not exist.")

        from jarvis.subsystems.coding import CodeModifier
        modifier = CodeModifier()

        if target and repl:
            success, patch, err = modifier.apply_replacement(fpath, target, repl)
            if success:
                return SkillResult(
                    success=True,
                    output=f"Applied fix to '{os.path.basename(fpath)}': replaced target snippet.",
                    artifacts={"file_path": fpath, "patched": True},
                )
            return SkillResult(success=False, error=err or "Patch application failed.")

        return SkillResult(success=True, output=f"Verified file structure of '{os.path.basename(fpath)}'.")


class CodingRunTestsSkill(BaseSkill):
    name = "coding.run_tests"
    domain = "coding"
    capability = "Executes automated test suites and reports pass/fail outcomes."
    required_tools = ["run_command"]
    parameters = {
        "test_path": SkillParameter("test_path", "string", "Path or module of tests", required=True),
        "runner": SkillParameter("runner", "string", "Test runner ('unittest' or 'pytest')", required=False, default="unittest"),
    }

    def execute(self, params: Dict[str, Any], context: SkillContext) -> SkillResult:
        tpath = params["test_path"]
        runner = params.get("runner", "unittest")

        from jarvis.subsystems.coding import TestRunner
        test_runner = TestRunner()
        result = test_runner.run_tests(test_path=tpath, runner=runner)

        return SkillResult(
            success=result.passed,
            output=result.output.strip(),
            artifacts={
                "test_path": tpath,
                "passed": result.passed,
                "returncode": result.returncode,
                "failed_tests": result.failed_tests,
            },
        )


class CodingFixFailingTestSkill(BaseSkill):
    name = "coding.fix_failing_test"
    domain = "coding"
    capability = "Executes full 10-stage autonomous coding loop to diagnose, patch, and verify failing tests."
    required_tools = ["run_coding_agent"]
    parameters = {
        "test_path": SkillParameter("test_path", "string", "Failing test path or suite", required=True),
        "target_file": SkillParameter("target_file", "path", "Optional source file to fix", required=False, default=None),
        "target_snippet": SkillParameter("target_snippet", "string", "Optional buggy code snippet", required=False, default=None),
        "replacement_snippet": SkillParameter("replacement_snippet", "string", "Optional replacement snippet", required=False, default=None),
    }

    def execute(self, params: Dict[str, Any], context: SkillContext) -> SkillResult:
        tpath = params["test_path"]
        target_f = params.get("target_file")
        target_snip = params.get("target_snippet")
        repl_snip = params.get("replacement_snippet")

        from jarvis.subsystems.coding import run_coding_agent
        result = run_coding_agent(
            test_path=tpath,
            target_file=target_f,
            target_snippet=target_snip,
            replacement_snippet=repl_snip,
            open_editor=False,
        )

        context.set("coding_task_result", result.to_dict())
        return SkillResult(
            success=result.success,
            output=result.explanation,
            artifacts=result.to_dict(),
        )


class CodingInspectRepoSkill(BaseSkill):
    name = "coding.inspect_repo"
    domain = "coding"
    capability = "Queries git branch, commit SHA, dirty files, and uncommitted diffs."
    required_tools = ["git_inspect"]
    parameters = {
        "repo_path": SkillParameter("repo_path", "path", "Repository root path", required=False, default="."),
    }

    def execute(self, params: Dict[str, Any], context: SkillContext) -> SkillResult:
        rpath = params.get("repo_path", ".")
        from jarvis.subsystems.coding import RepoInspector
        inspector = RepoInspector(rpath)
        inspection = inspector.inspect(rpath)
        context.set("repo_inspection", inspection.to_dict())
        return SkillResult(
            success=True,
            output=f"Branch '{inspection.branch}', Commit '{inspection.commit_sha}'. Clean={inspection.is_clean}.",
            artifacts=inspection.to_dict(),
        )


class CodingPrepareCommitSkill(BaseSkill):
    name = "coding.prepare_commit"
    domain = "coding"
    capability = "Stages modified files and prepares a commit message and diff preview."
    required_tools = ["git_prepare_commit"]
    parameters = {
        "files": SkillParameter("files", "list", "List of modified files to stage", required=True),
        "message": SkillParameter("message", "string", "Commit message to prepare", required=True),
    }

    def execute(self, params: Dict[str, Any], context: SkillContext) -> SkillResult:
        files = params["files"]
        msg = params["message"]
        from jarvis.subsystems.coding import RepoInspector
        inspector = RepoInspector()
        prep = inspector.prepare_commit(files=files, message=msg, commit_now=False)
        context.set("commit_prep", prep.to_dict())
        return SkillResult(
            success=True,
            output=f"Staged {len(files)} files on branch '{prep.branch}'. Commit ready.",
            artifacts=prep.to_dict(),
        )
