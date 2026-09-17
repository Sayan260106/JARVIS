"""Unit tests verifying the Phase 0 JARVIS agent loop and the 5 capabilities."""

import unittest
from jarvis.core.schemas import (
    IntentCategory,
    RecoveryStrategy,
    StepStatus,
    PlanStep,
    SubsystemType,
)
from jarvis.core.state import LoopPhase, AgentSessionState
from jarvis.core.loop import JarvisAgentLoop
from jarvis.capabilities.act import DefaultActCapability, ToolRegistry
from jarvis.capabilities.base import ActCapability


class MockFailingActCapability(ActCapability):
    """Simulates an action that fails initially then succeeds upon retry."""

    def __init__(self, succeed_on_attempt: int = 2):
        self.attempts = 0
        self.succeed_on_attempt = succeed_on_attempt

    def execute(self, step: PlanStep, state: AgentSessionState):
        self.attempts += 1
        if self.attempts < self.succeed_on_attempt:
            return {"exit_code": 1, "error": "Connection timed out"}
        return {"exit_code": 0, "status": "success", "data": "recovered"}


class MockAlwaysFailingActCapability(ActCapability):
    """Simulates persistent failure to verify Rule 3 bounded recovery."""

    def __init__(self):
        self.attempts = 0

    def execute(self, step: PlanStep, state: AgentSessionState):
        self.attempts += 1
        return {"exit_code": 1, "error": "Fatal device unavailable"}


class TestJarvisAgentLoop(unittest.TestCase):

    def setUp(self):
        self.loop = JarvisAgentLoop()

    def test_standard_execution_pass(self):
        """Verify: Understand -> Plan -> Execute -> Observe -> Verify -> PASS -> Final Result."""
        state = self.loop.run("search the web for quantum computing breakthroughs")

        self.assertEqual(state.phase, LoopPhase.COMPLETED)
        self.assertIsNotNone(state.objective)
        self.assertEqual(state.objective.intent, IntentCategory.RESEARCH)
        self.assertIsNotNone(state.plan)
        self.assertEqual(len(state.plan.steps), 2)
        self.assertTrue(all(step.status == StepStatus.SUCCESS for step in state.plan.steps))
        self.assertIn("Successfully executed", state.final_result)

    def test_ambiguity_detection(self):
        """Verify: Empty or underspecified inputs pause at Understand phase."""
        state = self.loop.run("create")
        self.assertEqual(state.phase, LoopPhase.AWAITING_USER)
        self.assertTrue(state.objective.is_ambiguous)
        self.assertIn("missing specific target arguments", state.error_message)

    def test_recovery_self_correction(self):
        """Verify: Fail -> Recover with adapted args -> Retry -> PASS."""
        mock_act = MockFailingActCapability(succeed_on_attempt=2)
        loop = JarvisAgentLoop(act=mock_act)

        state = loop.run("run diagnostic check")

        self.assertEqual(state.phase, LoopPhase.COMPLETED)
        self.assertEqual(mock_act.attempts, 2)
        # Verify that recovery happened in history
        failed_record = state.history[0]
        self.assertFalse(failed_record.verification.passed)
        self.assertIsNotNone(failed_record.recovery)
        self.assertEqual(failed_record.recovery.strategy, RecoveryStrategy.RETRY_WITH_ADAPTED_ARGS)

    def test_bounded_recovery_escalation_rule3(self):
        """Verify Rule 3: Max 3 retry attempts before escalating to user."""
        mock_act = MockAlwaysFailingActCapability()
        loop = JarvisAgentLoop(act=mock_act)

        state = loop.run("run network reset")

        self.assertEqual(state.phase, LoopPhase.AWAITING_USER)
        self.assertEqual(mock_act.attempts, 3)
        self.assertIn("Action failed after 3 attempts", state.error_message)
        last_recovery = state.history[-1].recovery
        self.assertEqual(last_recovery.strategy, RecoveryStrategy.ESCALATE_TO_USER)
        self.assertIn("Maximum retry ceiling reached", last_recovery.explanation)


if __name__ == "__main__":
    unittest.main()
