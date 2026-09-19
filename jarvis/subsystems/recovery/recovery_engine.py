"""Autonomous Recovery Engine for JARVIS (Phase 14).

Orchestrates the intelligent diagnostic and recovery pipeline:
Failure Observation -> Diagnostician ("Why?") -> Strategy Selection ->
Adaptation (Prerequisite Injection / Alternate Selector / Alternate Tool / Navigation / State Refresh) ->
Execution Plan Splicing & Bounded Retries.
"""

from __future__ import annotations
import os
from typing import Any, Dict, List, Optional

from jarvis.core.schemas import (
    Observation,
    PlanStep,
    RecoveryAction,
    RecoveryStrategy,
    StepStatus,
    SubsystemType,
    VerificationResult,
)
from jarvis.core.state import AgentSessionState
from jarvis.subsystems.recovery.diagnostician import FailureDiagnostician
from jarvis.subsystems.recovery.navigation_engine import AlternateNavigationEngine
from jarvis.subsystems.recovery.planner_adapter import PrerequisiteInjector
from jarvis.subsystems.recovery.schemas import FailureCategory, FailureDiagnosis
from jarvis.subsystems.recovery.selector_engine import AlternateSelectorEngine
from jarvis.subsystems.recovery.tool_fallback_engine import ToolFallbackEngine


class AutonomousRecoveryEngine:
    """Master intelligent recovery engine implementing Recovery 2.0."""

    def __init__(
        self,
        diagnostician: Optional[FailureDiagnostician] = None,
        selector_engine: Optional[AlternateSelectorEngine] = None,
        prerequisite_injector: Optional[PrerequisiteInjector] = None,
        tool_fallback_engine: Optional[ToolFallbackEngine] = None,
        navigation_engine: Optional[AlternateNavigationEngine] = None,
    ):
        self.diagnostician = diagnostician or FailureDiagnostician()
        self.selector_engine = selector_engine or AlternateSelectorEngine()
        self.prerequisite_injector = prerequisite_injector or PrerequisiteInjector()
        self.tool_fallback_engine = tool_fallback_engine or ToolFallbackEngine()
        self.navigation_engine = navigation_engine or AlternateNavigationEngine()

    def recover(
        self,
        step: PlanStep,
        observation: Observation,
        verification: VerificationResult,
        state: Optional[AgentSessionState] = None,
    ) -> RecoveryAction:
        """Diagnoses failure cause and selects an intelligent, bounded recovery action."""
        step.retry_count += 1
        step.status = StepStatus.FAILED

        # Rule 3: Bounded recovery loops. Strictly guard against infinite retry loops.
        if step.retry_count >= step.max_retries:
            return RecoveryAction(
                strategy=RecoveryStrategy.ESCALATE_TO_USER,
                explanation=(
                    f"Step '{step.description}' has failed {step.retry_count} times. "
                    f"Maximum retry limit ({step.max_retries}) reached."
                ),
                user_prompt=(
                    f"Action failed after {step.retry_count} attempts: {verification.reason}. "
                    f"Diagnosed issue cannot be automatically resolved. How would you like to proceed?"
                ),
            )

        # 1. Ask "Why did it fail?"
        ctx = state.context_state if state else {}
        diagnosis = self.diagnostician.diagnose(step, observation, verification, ctx)

        # 2. Scenario 1: Process / Application Not Running (e.g. Chrome not running -> Launch Chrome -> Retry)
        if diagnosis.category == FailureCategory.PROCESS_NOT_RUNNING:
            injected = self.prerequisite_injector.inject_prerequisites(step, diagnosis)
            step.status = StepStatus.PENDING
            return RecoveryAction(
                strategy=RecoveryStrategy.PREREQUISITE_INJECTION,
                explanation=f"Diagnosed root cause: {diagnosis.root_cause}. Injecting launch step and retrying.",
                injected_steps=injected,
                modified_step=step,
            )

        # 3. Scenario 2: Element Not Found / Course Renamed (e.g. Click 'ECE' -> Acronym/Search expansion)
        if diagnosis.category == FailureCategory.ELEMENT_NOT_FOUND:
            target = step.arguments.get("selector") or step.arguments.get("text") or step.arguments.get("element") or ""
            alternate = self.selector_engine.get_best_alternate(target)

            if alternate:
                if alternate.selector_type == "in_page_search":
                    # Course/element may be renamed; execute search fallback for matching course
                    modified = PlanStep.create(
                        description=f"Search in-page for matching course '{alternate.value}'",
                        subsystem=SubsystemType.WEB,
                        tool_name="browser_search_page",
                        arguments={"query": alternate.value},
                        expected_outcome=f"In-page search executed for matching course '{alternate.value}'.",
                        depends_on=step.depends_on,
                    )
                    return RecoveryAction(
                        strategy=RecoveryStrategy.ALTERNATE_SELECTOR,
                        explanation=f"Element '{target}' not found. Course may be renamed. Searching for '{alternate.value}'.",
                        modified_step=modified,
                    )
                else:
                    new_args = dict(step.arguments)
                    if "selector" in new_args:
                        new_args["selector"] = alternate.value
                    if "text" in new_args:
                        new_args["text"] = alternate.value

                    modified = PlanStep.create(
                        description=f"{step.description} (using alternate selector '{alternate.value}')",
                        subsystem=step.subsystem,
                        tool_name=step.tool_name,
                        arguments=new_args,
                        expected_outcome=step.expected_outcome,
                        depends_on=step.depends_on,
                    )
                    return RecoveryAction(
                        strategy=RecoveryStrategy.ALTERNATE_SELECTOR,
                        explanation=f"Element '{target}' not found (element/course may be renamed). Retrying with alternate selector: {alternate.description}.",
                        modified_step=modified,
                    )

            else:
                # Fallback to alternate tool
                fb_step = self.tool_fallback_engine.get_fallback_step(step, verification.reason)
                if fb_step:
                    return RecoveryAction(
                        strategy=RecoveryStrategy.SWITCH_TOOL,
                        explanation=f"Element locator failed. Switching to alternative tool route '{fb_step.tool_name}'.",
                        modified_step=fb_step,
                    )

        # 4. Navigation Failure -> Alternate Navigation Route
        if diagnosis.category == FailureCategory.NAVIGATION_FAILED:
            url = step.arguments.get("url", "")
            injected = self.navigation_engine.derive_alternate_navigation(step, url)
            step.status = StepStatus.PENDING
            return RecoveryAction(
                strategy=RecoveryStrategy.ALTERNATE_NAVIGATION,
                explanation=f"Navigation failure diagnosed: {diagnosis.root_cause}. Establishing base session and refreshing.",
                injected_steps=injected,
                modified_step=step,
            )

        # 5. Missing File -> Prerequisite Injection
        if diagnosis.category == FailureCategory.FILE_NOT_FOUND:
            injected = self.prerequisite_injector.inject_prerequisites(step, diagnosis)
            step.status = StepStatus.PENDING
            return RecoveryAction(
                strategy=RecoveryStrategy.PREREQUISITE_INJECTION,
                explanation=f"File missing on disk. Injected file creation prerequisite.",
                injected_steps=injected,
                modified_step=step,
            )

        # 6. Alternate Tool Fallback
        fb_step = self.tool_fallback_engine.get_fallback_step(step, verification.reason)
        if fb_step:
            return RecoveryAction(
                strategy=RecoveryStrategy.SWITCH_TOOL,
                explanation=f"Execution error diagnosed: {diagnosis.root_cause}. Switching to tool '{fb_step.tool_name}'.",
                modified_step=fb_step,
            )

        # 7. Default Argument Adaptation / State Refresh
        new_args = dict(step.arguments)
        new_args["_retry_mode"] = "adapted"
        step.arguments = new_args
        step.status = StepStatus.PENDING
        return RecoveryAction(
            strategy=RecoveryStrategy.RETRY_WITH_ADAPTED_ARGS,
            explanation=f"Attempting self-correction with adapted arguments.",
            modified_step=step,
        )
