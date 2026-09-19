"""JARVIS Coding Agent Subsystem (Phase 13).

Exports autonomous coding agent, repository inspection, dependency analysis,
test runner, error diagnostics, and code modification.
"""

from __future__ import annotations
from typing import Optional

from jarvis.subsystems.coding.agent import CodingAgent
from jarvis.subsystems.coding.code_modifier import CodeModifier
from jarvis.subsystems.coding.dependency_analyzer import DependencyAnalyzer
from jarvis.subsystems.coding.error_analyzer import ErrorAnalyzer
from jarvis.subsystems.coding.repo_inspector import RepoInspector
from jarvis.subsystems.coding.schemas import (
    CodePatch,
    CodingTaskResult,
    CommitPreparation,
    ErrorAnalysis,
    ErrorCategory,
    FileDependencyGraph,
    RepoInspection,
    TestRunResult,
)
from jarvis.subsystems.coding.test_runner import TestRunner


_default_agent: Optional[CodingAgent] = None


def get_coding_agent(workspace_root: str = ".") -> CodingAgent:
    """Returns a singleton or configured instance of CodingAgent."""
    global _default_agent
    if _default_agent is None:
        _default_agent = CodingAgent(workspace_root=workspace_root)
    return _default_agent


def run_coding_agent(
    test_path: str,
    target_file: Optional[str] = None,
    target_snippet: Optional[str] = None,
    replacement_snippet: Optional[str] = None,
    workspace_root: str = ".",
    open_editor: bool = True,
) -> CodingTaskResult:
    """Functional convenience entry point to run the coding pipeline."""
    agent = get_coding_agent(workspace_root=workspace_root)
    return agent.fix_failing_test(
        test_path=test_path,
        target_file=target_file,
        target_snippet=target_snippet,
        replacement_snippet=replacement_snippet,
        open_editor=open_editor,
    )


__all__ = [
    "CodingAgent",
    "RepoInspector",
    "DependencyAnalyzer",
    "TestRunner",
    "ErrorAnalyzer",
    "CodeModifier",
    "RepoInspection",
    "FileDependencyGraph",
    "TestRunResult",
    "ErrorAnalysis",
    "CodePatch",
    "CommitPreparation",
    "CodingTaskResult",
    "ErrorCategory",
    "get_coding_agent",
    "run_coding_agent",
]
