"""Repository Inspector & Git Awareness Engine for JARVIS (Phase 13).

Provides full git status, branch awareness, diff inspection, commit preparation,
and security-gated remote push management.
"""

from __future__ import annotations
import os
import subprocess
from typing import List, Optional, Tuple

from jarvis.subsystems.coding.schemas import CommitPreparation, RepoInspection


class RepoInspector:
    """Inspects repository state, tracks branches and diffs, and manages commits with security gating."""

    def __init__(self, default_repo_path: str = "."):
        self.default_repo_path = os.path.abspath(default_repo_path)

    def _run_git(self, args: List[str], repo_path: Optional[str] = None) -> Tuple[int, str, str]:
        """Executes a git command in the target repository directory."""
        cwd = os.path.abspath(repo_path or self.default_repo_path)
        cmd = ["git"] + args
        try:
            res = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=15,
            )
            return res.returncode, res.stdout.strip(), res.stderr.strip()
        except Exception as e:
            return -1, "", str(e)

    def get_repo_root(self, repo_path: Optional[str] = None) -> str:
        """Finds the top-level root directory of the git repository."""
        code, out, _ = self._run_git(["rev-parse", "--show-toplevel"], repo_path)
        if code == 0 and out:
            return os.path.abspath(out)
        return os.path.abspath(repo_path or self.default_repo_path)

    def get_current_branch(self, repo_path: Optional[str] = None) -> str:
        """Identifies the active git branch name."""
        code, out, _ = self._run_git(["branch", "--show-current"], repo_path)
        if code == 0 and out:
            return out
        # Fallback for detached HEAD
        code, out, _ = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"], repo_path)
        return out if (code == 0 and out) else "unknown"

    def get_latest_commit_sha(self, repo_path: Optional[str] = None) -> str:
        """Retrieves short commit hash of HEAD."""
        code, out, _ = self._run_git(["rev-parse", "--short", "HEAD"], repo_path)
        return out if (code == 0 and out) else "0000000"

    def inspect(self, repo_path: Optional[str] = None) -> RepoInspection:
        """Performs a comprehensive inspection of repository awareness and working tree."""
        root = self.get_repo_root(repo_path)
        branch = self.get_current_branch(root)
        commit_sha = self.get_latest_commit_sha(root)

        code, status_raw, _ = self._run_git(["status", "--porcelain"], root)
        modified_files: List[str] = []
        untracked_files: List[str] = []
        staged_files: List[str] = []

        if code == 0 and status_raw:
            for line in status_raw.splitlines():
                if len(line) < 3:
                    continue
                index_stat = line[0]
                work_stat = line[1]
                fname = line[3:].strip().strip('"')

                if index_stat in ("M", "A", "D", "R"):
                    staged_files.append(fname)
                if work_stat in ("M", "D"):
                    modified_files.append(fname)
                elif index_stat == "?" and work_stat == "?":
                    untracked_files.append(fname)

        code_diff, diff_out, _ = self._run_git(["diff"], root)

        is_clean = len(modified_files) == 0 and len(untracked_files) == 0 and len(staged_files) == 0

        return RepoInspection(
            repo_path=root,
            branch=branch,
            commit_sha=commit_sha,
            is_clean=is_clean,
            status_output=status_raw,
            modified_files=modified_files,
            untracked_files=untracked_files,
            staged_files=staged_files,
            diff_output=diff_out if code_diff == 0 else "",
        )

    def get_diff(self, repo_path: Optional[str] = None, staged: bool = False, file_path: Optional[str] = None) -> str:
        """Extracts unified diff for modified or staged files."""
        args = ["diff"]
        if staged:
            args.append("--staged")
        if file_path:
            args.extend(["--", file_path])
        _, diff_out, _ = self._run_git(args, repo_path)
        return diff_out

    def stage_files(self, files: List[str], repo_path: Optional[str] = None) -> bool:
        """Stages specific modified files in git."""
        if not files:
            return True
        args = ["add"] + files
        code, _, _ = self._run_git(args, repo_path)
        return code == 0

    def prepare_commit(
        self,
        files: List[str],
        message: str,
        repo_path: Optional[str] = None,
        commit_now: bool = False,
    ) -> CommitPreparation:
        """Stages target files, generates diff preview, and optionally records commit."""
        root = self.get_repo_root(repo_path)
        branch = self.get_current_branch(root)

        # 1. Stage the files
        self.stage_files(files, root)

        # 2. Extract staged diff summary
        staged_diff = self.get_diff(root, staged=True)
        diff_lines = staged_diff.splitlines()
        summary = "\n".join(diff_lines[:30]) if diff_lines else "No staged changes."

        commit_sha = None
        if commit_now:
            code, out, _ = self._run_git(["commit", "-m", message], root)
            if code == 0:
                commit_sha = self.get_latest_commit_sha(root)

        return CommitPreparation(
            branch=branch,
            staged_files=files,
            commit_message=message,
            diff_summary=summary,
            commit_sha=commit_sha,
            push_permitted=False,
            push_gated=True,
            push_message="Autonomous push blocked. Explicit user confirmation required to push to remote.",
        )

    def push_to_remote(
        self,
        repo_path: Optional[str] = None,
        branch: Optional[str] = None,
        force_confirmed: bool = False,
    ) -> Tuple[bool, str]:
        """Gated remote push method. Strict safety block unless force_confirmed is True."""
        if not force_confirmed:
            return (
                False,
                "SECURITY GATE: Autonomous git push is strictly prohibited. "
                "Explicit user gate approval is required before publishing code to remotes."
            )

        root = self.get_repo_root(repo_path)
        target_branch = branch or self.get_current_branch(root)
        code, out, err = self._run_git(["push", "origin", target_branch], root)
        if code == 0:
            return True, f"Successfully pushed branch '{target_branch}' to origin."
        return False, f"Git push failed: {err or out}"
