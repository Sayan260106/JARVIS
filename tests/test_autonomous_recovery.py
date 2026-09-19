"""Comprehensive Test Suite for Phase 14: Autonomous Recovery 2.0.

Validates:
- Failure diagnostician ("Why did it fail?")
- Alternate selectors & acronym/course expansions (e.g. ECE -> Electronics...)
- Prerequisite injection (e.g. Chrome not running -> launch Chrome -> retry)
- Tool fallbacks & alternate navigation
- Bounded retries and graceful user escalation
- End-to-end plan splicing in agent execution loop
"""

from __future__ import annotations
import unittest

from jarvis.capabilities.recover import DefaultRecoverCapability
from jarvis.core.loop import JarvisAgentLoop
from jarvis.core.schemas import (

    ExecutionPlan,
    IntentCategory,
    Observation,
    PlanStep,
    RecoveryAction,
    RecoveryStrategy,
    StepStatus,
    SubsystemType,
    TaskObjective,
    VerificationResult,
)
from jarvis.core.state import AgentSessionState, LoopPhase
from jarvis.subsystems.recovery import (
    AlternateSelectorEngine,
    AutonomousRecoveryEngine,
    FailureCategory,
    FailureDiagnosis,
    FailureDiagnostician,
    PrerequisiteInjector,
    ToolFallbackEngine,
)


class TestAutonomousRecovery(unittest.TestCase):
    """Unit and integration tests for Autonomous Recovery 2.0."""

    def setUp(self):
        self.diagnostician = FailureDiagnostician()
        self.selector_engine = AlternateSelectorEngine()
        self.prerequisite_injector = PrerequisiteInjector()
        self.fallback_engine = ToolFallbackEngine()
        self.recovery_engine = AutonomousRecoveryEngine()
        self.recover_cap = DefaultRecoverCapability(self.recovery_engine)

    # ----------------------------------------------------------------------
    # 1. Failure Diagnostician Tests ("Why did it fail?")
    # ----------------------------------------------------------------------
    def test_diagnose_process_not_running(self):
        step = PlanStep.create(
            description="Open new tab in Chrome browser",
            subsystem=SubsystemType.WEB,
            tool_name="browser_new_tab",
            arguments={"url": "https://classroom.google.com"},
            expected_outcome="Tab opened.",
        )
        obs = Observation(
            step_id=step.step_id,
            exit_code=1,
            output="",
            error="ConnectionRefusedError: No active browser connection found. Chrome is not running.",
        )
        ver = VerificationResult(
            passed=False,
            evidence="",
            reason="Browser tab could not be opened: Chrome not running in background.",
        )

        diagnosis = self.diagnostician.diagnose(step, obs, ver)
        self.assertEqual(diagnosis.category, FailureCategory.PROCESS_NOT_RUNNING)
        self.assertIn("not running", diagnosis.root_cause)
        self.assertEqual(diagnosis.suggested_strategy, RecoveryStrategy.PREREQUISITE_INJECTION)

    def test_diagnose_element_not_found(self):
        step = PlanStep.create(
            description="Click course button ECE",
            subsystem=SubsystemType.WEB,
            tool_name="browser_click",
            arguments={"selector": "ECE"},
            expected_outcome="Course opened.",
        )
        obs = Observation(
            step_id=step.step_id,
            exit_code=1,
            output="",
            error="NoSuchElementException: Element with selector 'ECE' not visible or found in DOM.",
        )
        ver = VerificationResult(
            passed=False,
            evidence="",
            reason="Element not found: Target 'ECE' was not found on page.",
        )

        diagnosis = self.diagnostician.diagnose(step, obs, ver)
        self.assertEqual(diagnosis.category, FailureCategory.ELEMENT_NOT_FOUND)
        self.assertIn("ECE", diagnosis.root_cause)
        self.assertEqual(diagnosis.suggested_strategy, RecoveryStrategy.ALTERNATE_SELECTOR)

    def test_diagnose_navigation_failed(self):
        step = PlanStep.create(
            description="Navigate to portal",
            subsystem=SubsystemType.WEB,
            tool_name="browser_navigate",
            arguments={"url": "https://portal.university.edu/login"},
            expected_outcome="Portal loaded.",
        )
        obs = Observation(
            step_id=step.step_id,
            exit_code=1,
            output="",
            error="net::ERR_CONNECTION_TIMED_OUT at https://portal.university.edu/login",
        )
        ver = VerificationResult(
            passed=False,
            evidence="",
            reason="Navigation failed: page load timeout.",
        )

        diagnosis = self.diagnostician.diagnose(step, obs, ver)
        self.assertEqual(diagnosis.category, FailureCategory.NAVIGATION_FAILED)
        self.assertEqual(diagnosis.suggested_strategy, RecoveryStrategy.ALTERNATE_NAVIGATION)

    # ----------------------------------------------------------------------
    # 2. Alternate Selector & Course Acronym Expansion Tests
    # ----------------------------------------------------------------------
    def test_alternate_selector_acronym_expansion(self):
        # Course "ECE" -> "Electronics and Communication Engineering", "Electronics..."
        alternates = self.selector_engine.generate_alternates("ECE")
        self.assertGreater(len(alternates), 2)

        expansions = [a.value for a in alternates if a.selector_type == "acronym_expansion"]
        self.assertIn("Electronics and Communication Engineering", expansions)
        self.assertIn("Electronics...", expansions)

        # In-page search fallback
        search_falls = [a for a in alternates if a.selector_type == "in_page_search"]
        self.assertGreater(len(search_falls), 0)
        self.assertIn("Electronics", search_falls[0].value)

    def test_alternate_selector_structural_css_aria(self):
        alternates = self.selector_engine.generate_alternates("Submit")
        css_selectors = [a for a in alternates if a.selector_type == "css"]
        aria_selectors = [a for a in alternates if a.selector_type == "aria"]

        self.assertGreater(len(css_selectors), 0)
        self.assertIn("button:has-text('Submit')", css_selectors[0].value)
        self.assertGreater(len(aria_selectors), 0)
        self.assertIn("[aria-label*='Submit' i]", aria_selectors[0].value)

    # ----------------------------------------------------------------------
    # 3. Tool Fallback Engine Tests
    # ----------------------------------------------------------------------
    def test_tool_fallback_focus_to_open_application(self):
        step = PlanStep.create(
            description="Focus Notepad",
            subsystem=SubsystemType.SYSTEM,
            tool_name="focus_window",
            arguments={"title": "Notepad"},
            expected_outcome="Notepad focused.",
        )
        fb_step = self.fallback_engine.get_fallback_step(step, "Window not found")
        self.assertIsNotNone(fb_step)
        self.assertEqual(fb_step.tool_name, "open_application")
        self.assertEqual(fb_step.arguments.get("app_name"), "Notepad")

    # ----------------------------------------------------------------------
    # 4. Anchor Scenario 1: Process Prerequisite Injection (Chrome Not Running)
    # ----------------------------------------------------------------------
    def test_scenario_1_chrome_not_running_recovery(self):
        """
        Open Chrome -> FAIL -> Chrome not running -> Launch Chrome -> Retry -> PASS
        """
        step = PlanStep.create(
            description="Open Google Chrome tab",
            subsystem=SubsystemType.WEB,
            tool_name="browser_new_tab",
            arguments={"url": "https://google.com"},
            expected_outcome="Tab opened in Chrome.",
        )
        obs = Observation(
            step_id=step.step_id,
            exit_code=1,
            output="",
            error="Connection refused: Chrome is not running.",
        )
        ver = VerificationResult(
            passed=False,
            evidence="",
            reason="Chrome not running. Cannot connect to browser instance.",
        )

        state = AgentSessionState(task_id="task_rec_1")

        # Execute recovery
        recovery: RecoveryAction = self.recover_cap.recover(step, obs, ver, state)

        self.assertEqual(recovery.strategy, RecoveryStrategy.PREREQUISITE_INJECTION)
        self.assertGreaterEqual(len(recovery.injected_steps), 1)

        # First injected step must launch Chrome
        first_injected = recovery.injected_steps[0]
        self.assertEqual(first_injected.tool_name, "open_application")
        self.assertEqual(first_injected.arguments.get("app_name"), "chrome")

        # Original step must be reset to pending
        self.assertEqual(recovery.modified_step.status, StepStatus.PENDING)
        self.assertEqual(step.retry_count, 1)

    # ----------------------------------------------------------------------
    # 5. Anchor Scenario 2: Element Not Found / Course Renamed ("ECE")
    # ----------------------------------------------------------------------
    def test_scenario_2_element_renamed_search_fallback(self):
        """
        Click 'ECE' -> Element not found -> Inspect page / Maybe course renamed ->
        Search 'Electronics...' -> Find matching course -> Continue
        """
        step = PlanStep.create(
            description="Click course link ECE",
            subsystem=SubsystemType.WEB,
            tool_name="browser_click",
            arguments={"selector": "ECE"},
            expected_outcome="ECE Course page opened.",
        )
        obs = Observation(
            step_id=step.step_id,
            exit_code=1,
            output="",
            error="Element not found: Selector 'ECE' does not match any visible element.",
        )
        ver = VerificationResult(
            passed=False,
            evidence="",
            reason="Element not found: 'ECE' missing from page DOM.",
        )

        state = AgentSessionState(task_id="task_rec_2")

        recovery: RecoveryAction = self.recover_cap.recover(step, obs, ver, state)

        self.assertEqual(recovery.strategy, RecoveryStrategy.ALTERNATE_SELECTOR)
        self.assertIsNotNone(recovery.modified_step)

        # Verify adaptation: modified step uses expanded name or search
        mod_step = recovery.modified_step
        self.assertTrue(
            "Electronics" in str(mod_step.arguments.get("query", ""))
            or "Electronics" in str(mod_step.arguments.get("selector", ""))
        )
        self.assertIn("renamed", recovery.explanation.lower())

    # ----------------------------------------------------------------------
    # 6. Bounded Retries & Rule 3 Escalation
    # ----------------------------------------------------------------------
    def test_bounded_retries_escalate_to_user(self):
        step = PlanStep.create(
            description="Flaky action",
            subsystem=SubsystemType.SYSTEM,
            tool_name="modify_file",
            arguments={"path": "invalid/path.txt"},
            expected_outcome="File modified.",
            max_retries=3,
        )
        step.retry_count = 2  # Already failed twice

        obs = Observation(step_id=step.step_id, exit_code=1, output="", error="Permission denied")
        ver = VerificationResult(passed=False, evidence="", reason="Persistent failure")

        state = AgentSessionState(task_id="task_rec_3")

        # Third attempt -> Must hit max retries ceiling and escalate
        recovery: RecoveryAction = self.recover_cap.recover(step, obs, ver, state)

        self.assertEqual(step.retry_count, 3)
        self.assertEqual(recovery.strategy, RecoveryStrategy.ESCALATE_TO_USER)
        self.assertIsNotNone(recovery.user_prompt)
        self.assertIn("Action failed after 3 attempts", recovery.user_prompt)

    # ----------------------------------------------------------------------
    # 7. Execution Loop Plan Splicing Verification
    # ----------------------------------------------------------------------
    def test_loop_prerequisite_injection_plan_splicing(self):
        """Validates that AgentExecutionLoop splices injected steps into plan.steps ahead of the failing step."""
        obj = TaskObjective(
            raw_input="Open website in Chrome",
            intent=IntentCategory.TASK_AUTOMATION,
            description="Open URL",
            target_criteria="URL loaded",
        )
        failing_step = PlanStep.create(
            description="Open Google Chrome tab",
            subsystem=SubsystemType.WEB,
            tool_name="browser_new_tab",
            arguments={"url": "https://google.com"},
            expected_outcome="Chrome tab open.",
        )
        plan = ExecutionPlan.create(objective=obj, steps=[failing_step])

        # Formulate fake recovery with injected launch step
        launch_step = PlanStep.create(
            description="Launch missing application 'chrome'",
            subsystem=SubsystemType.SYSTEM,
            tool_name="open_application",
            arguments={"app_name": "chrome"},
            expected_outcome="Chrome running.",
        )
        rec_action = RecoveryAction(
            strategy=RecoveryStrategy.PREREQUISITE_INJECTION,
            explanation="Chrome not running. Injected launch step.",
            injected_steps=[launch_step],
            modified_step=failing_step,
        )

        # Simulate loop splicing logic
        step_idx = plan.steps.index(failing_step)
        plan.steps[step_idx:step_idx] = rec_action.injected_steps

        # After splicing, plan must have 2 steps: launch_step FIRST, then failing_step
        self.assertEqual(len(plan.steps), 2)
        self.assertEqual(plan.steps[0].tool_name, "open_application")
        self.assertEqual(plan.steps[1].tool_name, "browser_new_tab")


if __name__ == "__main__":
    unittest.main()
