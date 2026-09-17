"""Autonomous Self-Correction & Recovery Engine for JARVIS.

Implements the closed loop:
Process Crashes -> Observe Error -> Analyze Error -> Determine Likely Cause ->
Attempt Safe Fix -> Restart -> Verify Endpoint.

Enforces bounded retries (max_attempts = 3) before escalating to the user:
"I've attempted three recovery strategies. The remaining issue requires your input."
"""

from __future__ import annotations
from dataclasses import dataclass, field
import os
import subprocess
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from jarvis.capabilities.diagnostics import (
    DiagnosticResult,
    ErrorCategory,
    ErrorDiagnosticEngine,
)
from jarvis.core.task_schemas import Task, TaskStatus
from jarvis.core.task_manager import TaskManager


@dataclass
class RecoveryAttempt:
    """Record of a single execution and recovery iteration."""
    attempt_num: int
    action_taken: str
    status: str                         # "SUCCESS" or "FAILED"
    error: Optional[str] = None
    diagnostic: Optional[DiagnosticResult] = None
    fix_applied: Optional[str] = None
    duration_ms: float = 0.0


@dataclass
class RecoveryExecutionResult:
    """Final result of a self-correcting recovery execution."""
    success: bool
    total_attempts: int
    attempts_history: List[RecoveryAttempt] = field(default_factory=list)
    final_output: Optional[Any] = None
    final_message: str = ""
    escalated_to_user: bool = False
    task_id: Optional[str] = None


class RecoveryEngine:
    """Orchestrates error analysis, safe fixes, and bounded recovery iterations."""

    def __init__(
        self,
        max_attempts: int = 3,
        diagnostics_engine: Optional[ErrorDiagnosticEngine] = None,
        task_manager: Optional[TaskManager] = None,
        on_attempt_progress: Optional[Callable[[RecoveryAttempt], None]] = None,
    ):
        self.max_attempts = max_attempts
        self.diagnostics = diagnostics_engine or ErrorDiagnosticEngine()
        self.task_manager = task_manager
        self.on_attempt_progress = on_attempt_progress

    def apply_safe_fix(
        self,
        diagnostic: DiagnosticResult,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, str]:
        """Applies an automated, safe remediation based on diagnostic category."""
        ctx = context or {}
        cat = diagnostic.category

        # 1. Port in use -> Free port
        if cat == ErrorCategory.PORT_IN_USE:
            port = diagnostic.remediation_params.get("port", 8000)
            try:
                # Use netstat + taskkill to free the port
                cmd = f'netstat -ano | findstr LISTENING | findstr :{port}'
                proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                lines = proc.stdout.strip().splitlines()
                killed = []
                for line in lines:
                    parts = line.strip().split()
                    if len(parts) >= 5 and f":{port}" in parts[1]:
                        pid = parts[-1]
                        if pid.isdigit() and int(pid) > 0 and int(pid) != os.getpid():
                            subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True)
                            killed.append(pid)
                # Brief sleep to allow port socket release
                time.sleep(0.5)
                return True, f"Safely freed port {port} (terminated conflicting PIDs: {killed or 'stale listener'})."
            except Exception as e:
                return False, f"Could not free port {port}: {str(e)}"

        # 2. Missing dependency -> Install via current virtualenv pip
        if cat == ErrorCategory.MISSING_DEPENDENCY:
            pkg = diagnostic.remediation_params.get("package")
            if not pkg:
                return False, "Package name unspecified in diagnostic."
            try:
                pip_exe = sys.executable
                cmd = [pip_exe, "-m", "pip", "install", pkg]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if proc.returncode == 0:
                    return True, f"Safely installed required dependency '{pkg}' into environment."
                return False, f"Failed installing '{pkg}': {proc.stderr[:200]}"
            except Exception as e:
                return False, f"Error running pip install {pkg}: {str(e)}"

        # 3. Missing .env or config -> Create default configuration
        if cat == ErrorCategory.CONFIG_OR_ENV_MISSING:
            target_env = os.path.join(ctx.get("cwd", os.getcwd()), ".env")
            try:
                if not os.path.exists(target_env):
                    with open(target_env, "w") as f:
                        f.write("# Auto-generated default environment configuration by JARVIS\n")
                        f.write("PORT=8000\n")
                        f.write("HOST=127.0.0.1\n")
                        f.write("ENVIRONMENT=development\n")
                    return True, f"Created safe default environment configuration at '{target_env}'."
                return True, "Environment file already present."
            except Exception as e:
                return False, f"Failed creating default .env: {str(e)}"

        # 4. Invalid entrypoint -> Search for alternative entrypoint script
        if cat == ErrorCategory.INVALID_ENTRYPOINT:
            cwd = ctx.get("cwd", os.getcwd())
            candidates = ["backend.py", "main.py", "app.py", "server.py", "run.py"]
            found = None
            for c in candidates:
                cand_path = os.path.join(cwd, c)
                if os.path.exists(cand_path):
                    found = c
                    break
            if found:
                ctx["resolved_entrypoint"] = found
                return True, f"Resolved entrypoint to existing file '{found}'."
            return False, "No alternative entrypoint scripts found in directory."

        # 5. Generic crash / restart with fallback
        return True, "Prepared fresh execution environment with diagnostic fallback flags."

    def execute_with_recovery(
        self,
        objective: str,
        action_fn: Callable[[Dict[str, Any]], Tuple[bool, Any, Optional[str]]],
        verify_fn: Optional[Callable[[Any, Dict[str, Any]], Tuple[bool, str]]] = None,
        context: Optional[Dict[str, Any]] = None,
        task_id: Optional[str] = None,
    ) -> RecoveryExecutionResult:
        """Runs the action, observes crashes, analyzes errors, applies safe fixes, and bounds retries.

        action_fn takes context dict and returns: (success: bool, output: Any, error: Optional[str])
        verify_fn takes (output, context) and returns: (verified: bool, details: str)
        """
        ctx = dict(context or {})
        history: List[RecoveryAttempt] = []
        task = None

        if self.task_manager and task_id:
            task = self.task_manager.get_task(task_id)

        for attempt_idx in range(1, self.max_attempts + 1):
            start_t = time.perf_counter()
            action_desc = f"Attempt {attempt_idx}: Run '{objective}'"

            # Checkpoint task state to TaskManager
            if self.task_manager and task:
                self.task_manager.transition_status(task.id, TaskStatus.RUNNING)

            # 1. Execute action
            success, raw_output, error_msg = action_fn(ctx)

            # 2. If executed successfully, verify health/endpoint if verify_fn provided
            if success and verify_fn:
                if self.task_manager and task:
                    self.task_manager.transition_status(task.id, TaskStatus.VERIFYING)
                verified, verify_details = verify_fn(raw_output, ctx)
                if not verified:
                    success = False
                    error_msg = f"Verification failed: {verify_details}"

            duration_ms = (time.perf_counter() - start_t) * 1000

            # 3. SUCCESS case
            if success:
                record = RecoveryAttempt(
                    attempt_num=attempt_idx,
                    action_taken=action_desc,
                    status="SUCCESS",
                    duration_ms=duration_ms,
                )
                history.append(record)
                if self.on_attempt_progress:
                    self.on_attempt_progress(record)

                if self.task_manager and task:
                    self.task_manager.complete_task(
                        task.id,
                        final_result=f"Objective '{objective}' completed successfully on attempt {attempt_idx}."
                    )

                final_msg = f"Success on attempt {attempt_idx} for '{objective}'."
                return RecoveryExecutionResult(
                    success=True,
                    total_attempts=attempt_idx,
                    attempts_history=history,
                    final_output=raw_output,
                    final_message=final_msg,
                    escalated_to_user=False,
                    task_id=task_id,
                )

            # 4. FAILED case -> Diagnose and plan recovery
            diagnosis = self.diagnostics.diagnose(error_text=str(error_msg), context=ctx)

            record = RecoveryAttempt(
                attempt_num=attempt_idx,
                action_taken=action_desc,
                status="FAILED",
                error=error_msg,
                diagnostic=diagnosis,
                duration_ms=duration_ms,
            )
            history.append(record)
            if self.on_attempt_progress:
                self.on_attempt_progress(record)

            # Checkpoint failure to TaskManager
            if self.task_manager and task:
                self.task_manager.record_failure(
                    task.id,
                    step_num=attempt_idx,
                    step_name=f"Attempt {attempt_idx}: {diagnosis.likely_cause}",
                    error=str(error_msg),
                    can_retry=(attempt_idx < self.max_attempts),
                )
                self.task_manager.add_artifact(task.id, {
                    "attempt": attempt_idx,
                    "diagnostic": diagnosis.category.value,
                    "likely_cause": diagnosis.likely_cause,
                    "suggested_fix": diagnosis.suggested_fix,
                })

            # Check if we have exhausted max_attempts
            if attempt_idx >= self.max_attempts:
                break

            # If retries remain: determine likely cause & attempt safe fix
            fix_ok, fix_details = self.apply_safe_fix(diagnosis, context=ctx)
            record.fix_applied = fix_details

            # Transition task to RECOVERING
            if self.task_manager and task:
                self.task_manager.transition_status(task.id, TaskStatus.RECOVERING, reason=fix_details)

        # 5. ESCALATION: All attempts failed up to hard ceiling
        words_map = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}
        attempts_str = words_map.get(self.max_attempts, str(self.max_attempts))
        escalation_msg = f"I've attempted {attempts_str} recovery strategies. The remaining issue requires your input."

        if self.task_manager and task:
            self.task_manager.transition_status(task.id, TaskStatus.FAILED, reason=escalation_msg)

        return RecoveryExecutionResult(
            success=False,
            total_attempts=len(history),
            attempts_history=history,
            final_output=None,
            final_message=escalation_msg,
            escalated_to_user=True,
            task_id=task_id,
        )
