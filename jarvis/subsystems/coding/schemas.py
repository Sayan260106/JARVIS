"""Data schemas for JARVIS Coding Agent Subsystem (Phase 13).

Defines typed data contracts governing:
- Repository awareness (git status, diff, branches, commits)
- File dependency graphs
- Test execution and failure isolation
- Error analysis and root cause identification
- Code modification and safe patching
- Gated commit and push controls
"""

from __future__ import annotations
from dataclasses import dataclass, field
import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class ErrorCategory(str, Enum):
    """Categorization of test and runtime execution failures."""
    ASSERTION_FAILURE = "ASSERTION_FAILURE"
    SYNTAX_ERROR = "SYNTAX_ERROR"
    TYPE_ERROR = "TYPE_ERROR"
    ATTRIBUTE_ERROR = "ATTRIBUTE_ERROR"
    NAME_ERROR = "NAME_ERROR"
    IMPORT_ERROR = "IMPORT_ERROR"
    INDEX_KEY_ERROR = "INDEX_KEY_ERROR"
    RUNTIME_EXCEPTION = "RUNTIME_EXCEPTION"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    UNKNOWN = "UNKNOWN"


@dataclass
class RepoInspection:
    """Repository awareness snapshot of current project state."""
    repo_path: str
    branch: str
    commit_sha: str
    is_clean: bool
    status_output: str
    modified_files: List[str] = field(default_factory=list)
    untracked_files: List[str] = field(default_factory=list)
    staged_files: List[str] = field(default_factory=list)
    diff_output: str = ""
    timestamp: str = field(default_factory=lambda: datetime.datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "repo_path": self.repo_path,
            "branch": self.branch,
            "commit_sha": self.commit_sha,
            "is_clean": self.is_clean,
            "modified_files": self.modified_files,
            "untracked_files": self.untracked_files,
            "staged_files": self.staged_files,
            "has_diff": bool(self.diff_output),
            "timestamp": self.timestamp,
        }


@dataclass
class FileDependencyGraph:
    """File dependency awareness across repository modules."""
    imports_by_file: Dict[str, List[str]] = field(default_factory=dict)
    dependents_by_file: Dict[str, List[str]] = field(default_factory=dict)
    test_mapping: Dict[str, List[str]] = field(default_factory=dict)

    def get_dependencies(self, file_path: str) -> List[str]:
        return self.imports_by_file.get(file_path, [])

    def get_dependents(self, file_path: str) -> List[str]:
        return self.dependents_by_file.get(file_path, [])

    def get_associated_tests(self, file_path: str) -> List[str]:
        return self.test_mapping.get(file_path, [])


@dataclass
class TestRunResult:
    """Observation and telemetry from automated test execution."""
    command: str
    passed: bool
    returncode: int
    output: str
    failed_tests: List[str] = field(default_factory=list)
    tracebacks: List[str] = field(default_factory=list)
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command": self.command,
            "passed": self.passed,
            "returncode": self.returncode,
            "failed_tests_count": len(self.failed_tests),
            "failed_tests": self.failed_tests,
            "duration_ms": self.duration_ms,
        }


@dataclass
class ErrorAnalysis:
    """Diagnostic understanding of a failing test or code error."""
    error_type: ErrorCategory
    error_message: str
    failing_file: str
    failing_line: Optional[int]
    failing_function: Optional[str] = None
    root_cause: str = ""
    suggested_fix: str = ""
    target_code_snippet: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_type": self.error_type.value,
            "error_message": self.error_message,
            "failing_file": self.failing_file,
            "failing_line": self.failing_line,
            "failing_function": self.failing_function,
            "root_cause": self.root_cause,
            "suggested_fix": self.suggested_fix,
        }


@dataclass
class CodePatch:
    """Targeted modification applied to a source file."""
    file_path: str
    target_snippet: str
    replacement_snippet: str
    explanation: str
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    patch_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "patch_id": self.patch_id,
            "file_path": self.file_path,
            "explanation": self.explanation,
            "line_start": self.line_start,
            "line_end": self.line_end,
        }


@dataclass
class CommitPreparation:
    """Staged files and commit metadata ready for version control."""
    branch: str
    staged_files: List[str]
    commit_message: str
    diff_summary: str
    commit_sha: Optional[str] = None
    push_permitted: bool = False
    push_gated: bool = True
    push_message: str = "Autonomous push blocked. Explicit user gate approval required."

    def to_dict(self) -> Dict[str, Any]:
        return {
            "branch": self.branch,
            "staged_files": self.staged_files,
            "commit_message": self.commit_message,
            "commit_sha": self.commit_sha,
            "push_permitted": self.push_permitted,
            "push_gated": self.push_gated,
            "push_message": self.push_message,
        }


@dataclass
class CodingTaskResult:
    """Comprehensive outcome of the 10-stage autonomous coding agent pipeline."""
    success: bool
    project_path: str
    initial_test: TestRunResult
    error_analysis: Optional[ErrorAnalysis]
    patches_applied: List[CodePatch]
    final_test: TestRunResult
    repo_status: RepoInspection
    commit_prep: Optional[CommitPreparation]
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "project_path": self.project_path,
            "tests_originally_passed": self.initial_test.passed,
            "tests_finally_passed": self.final_test.passed,
            "patches_count": len(self.patches_applied),
            "modified_files": [p.file_path for p in self.patches_applied],
            "commit_prepared": self.commit_prep is not None,
            "explanation": self.explanation,
        }
