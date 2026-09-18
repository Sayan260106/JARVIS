"""Test Suite for JARVIS Personality System (Phase 11).

Verifies:
- Personality traits: Tone, Humor, Formality, Warmth, Confidence, Curiosity, EmotionalState
- Task success -> slightly positive response
- Task failure -> calm explanation
- Repeated failure -> mild frustration-style wording
- User appreciation -> warm response
- Guardrails: Interaction layer only; no claims of artificial consciousness
"""

import unittest
from jarvis.core.personality import PersonalityEngine, PersonalityConfig, EmotionalState
from jarvis.capabilities.conversation import ConversationEngine


class TestPersonalityEngine(unittest.TestCase):
    """Tests the personality interaction layer and emotional transitions."""

    def setUp(self):
        self.engine = PersonalityEngine()

    def test_personality_traits_configuration(self):
        """Verify personality traits are accessible and configurable."""
        config = PersonalityConfig(
            tone="polite_witty",
            humor=0.4,
            formality=0.8,
            warmth=0.7,
            confidence=0.95,
            curiosity=0.6,
        )
        engine = PersonalityEngine(config=config)
        self.assertEqual(engine.config.tone, "polite_witty")
        self.assertEqual(engine.config.humor, 0.4)
        self.assertEqual(engine.config.formality, 0.8)
        self.assertEqual(engine.config.warmth, 0.7)
        self.assertEqual(engine.config.confidence, 0.95)
        self.assertEqual(engine.config.curiosity, 0.6)
        self.assertEqual(engine.current_state, EmotionalState.NEUTRAL)

    def test_task_success_produces_slightly_positive_response(self):
        """Task success should trigger a slightly positive, orderly phrasing."""
        response = self.engine.on_task_success("Directory Organization")
        self.assertEqual(self.engine.current_state, EmotionalState.PLEASED)
        self.assertIn("completed cleanly, sir", response.lower())
        self.assertIn("everything is in order", response.lower())
        self.assertEqual(self.engine.consecutive_failures, 0)

    def test_task_failure_produces_calm_explanation(self):
        """First task failure should trigger a calm, collected diagnostic response."""
        response = self.engine.on_task_failure("Start Backend", "Port 8000 already in use")
        self.assertEqual(self.engine.current_state, EmotionalState.CALM_ANALYTIC)
        self.assertIn("encountered an impediment", response)
        self.assertIn("Port 8000 already in use", response)
        self.assertIn("investigating the cause", response)
        self.assertEqual(self.engine.consecutive_failures, 1)

    def test_repeated_failure_produces_mild_frustration_style_wording(self):
        """Repeated failure should trigger mild frustration-style wording without claiming consciousness."""
        response = self.engine.on_repeated_failure("Verify Endpoint", attempts=3, error="Connection Refused")
        self.assertEqual(self.engine.current_state, EmotionalState.MILDLY_PERPLEXED)
        self.assertIn("3th consecutive failure", response)
        self.assertIn("Connection Refused", response)
        self.assertIn("I suggest we inspect the configuration before continuing", response)
        # Ensure no artificial claims of consciousness or fake feelings
        self.assertNotIn("I'm angry", response)
        self.assertNotIn("I am hurt", response)

    def test_user_appreciation_produces_warm_response(self):
        """Expressions of appreciation should trigger warm, courteous responses."""
        self.assertTrue(self.engine.is_user_appreciation("Thank you Jarvis!"))
        self.assertTrue(self.engine.is_user_appreciation("Great job, Jarvis"))
        self.assertTrue(self.engine.is_user_appreciation("Awesome work"))

        response = self.engine.on_user_appreciation("Thank you Jarvis")
        self.assertEqual(self.engine.current_state, EmotionalState.WARM_APPRECIATIVE)
        self.assertIn("pleasure to be of service, sir", response.lower())

    def test_conversation_engine_appreciation_hook(self):
        """ConversationEngine should intercept appreciation and respond warmly."""
        conv = ConversationEngine(enable_tools=False, speak_output=False)
        reply = conv.process_turn("Thank you Jarvis!")
        self.assertIn("pleasure to be of service, sir", reply.lower())


if __name__ == "__main__":
    unittest.main()
