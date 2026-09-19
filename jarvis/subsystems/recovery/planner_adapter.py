"""Prerequisite Injector for Autonomous Recovery 2.0 (Phase 14).

Injects prerequisite precursor steps into execution plans when an action fails
due to missing applications, unopened processes, or uninitialized files.
"""

from __future__ import annotations
import os
from typing import Any, Dict, List, Optional

from jarvis.core.schemas import PlanStep, SubsystemType
from jarvis.subsystems.recovery.schemas import FailureCategory, FailureDiagnosis


class PrerequisiteInjector:
    """Creates prerequisite PlanSteps to prepare environment before retrying failing actions."""

    def inject_prerequisites(
        self,
        failing_step: PlanStep,
        diagnosis: FailureDiagnosis,
    ) -> List[PlanStep]:
        """Formulates prerequisite steps that establish the required runtime state."""
        injected: List[PlanStep] = []

        # Scenario 1: Target application / Chrome is not running
        if diagnosis.category == FailureCategory.PROCESS_NOT_RUNNING:
            app_name = diagnosis.context_snapshot.get("app_name", "chrome")
            launch_step = PlanStep.create(
                description=f"Launch missing application '{app_name}'",
                subsystem=SubsystemType.SYSTEM,
                tool_name="open_application",
                arguments={"app_name": app_name},
                expected_outcome=f"Application '{app_name}' launched and active.",
                depends_on=[],
            )
            injected.append(launch_step)

            # Optional: Add small settling step or state refresh
            if "browser" in failing_step.tool_name or app_name == "chrome":
                state_refresh = PlanStep.create(
                    description=f"Verify browser connection and acquire state",
                    subsystem=SubsystemType.WEB,
                    tool_name="browser_get_state",
                    arguments={},
                    expected_outcome="Browser connection confirmed and DOM initialized.",
                    depends_on=[launch_step.step_id],
                )
                injected.append(state_refresh)

        # Scenario 2: Target file is missing
        elif diagnosis.category == FailureCategory.FILE_NOT_FOUND:
            fpath = diagnosis.context_snapshot.get("file_path", "missing_file")
            create_step = PlanStep.create(
                description=f"Initialize missing file at '{os.path.basename(fpath)}'",
                subsystem=SubsystemType.SYSTEM,
                tool_name="create_file",
                arguments={"path": fpath, "content": "# Initialized by JARVIS Recovery\n"},
                expected_outcome=f"File '{fpath}' created on disk.",
                depends_on=[],
            )
            injected.append(create_step)

        # Scenario 3: Target window not active
        elif diagnosis.category == FailureCategory.WINDOW_NOT_FOUND:
            w_title = diagnosis.context_snapshot.get("window_title", "application")
            launch_step = PlanStep.create(
                description=f"Launch application for window '{w_title}'",
                subsystem=SubsystemType.SYSTEM,
                tool_name="open_application",
                arguments={"app_name": w_title},
                expected_outcome=f"Application '{w_title}' launched.",
                depends_on=[],
            )
            injected.append(launch_step)

        return injected
