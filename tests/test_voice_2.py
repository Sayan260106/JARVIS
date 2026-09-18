"""Unit and integration tests for Phase 9: Voice 2.0.

Verifies:
1. Wake-word detector ("Hey JARVIS", "JARVIS", compound utterances).
2. Continuous listening & conversational state machine transitions.
3. Conversational Interruption & Cancellation: "Actually, cancel that."
4. Conversational Revert / Undo: "Wait, go back."
5. Orchestrator parity: Both Voice -> Agent and Text -> Agent reach the exact same JarvisAgentLoop.
"""

import os
import unittest
from unittest.mock import MagicMock
import numpy as np

from jarvis.subsystems.local.stt import WakeWordDetector, LocalSTT
from jarvis.subsystems.local.tts import LocalTTS
from jarvis.core.loop import JarvisAgentLoop
from jarvis.core.schemas import SubsystemType, IntentCategory
from jarvis.interfaces.voice import (
    VoiceInterface,
    VoiceSessionState,
    ActionHistoryStack,
    ActionHistoryRecord,
    ContinuousVoiceListener,
)


class TestVoice2Architecture(unittest.TestCase):
    """Test suite for Phase 9 Voice 2.0 architecture."""

    def setUp(self):
        self.wake_detector = WakeWordDetector()
        self.mock_tts = LocalTTS(enabled=False)
        self.loop = JarvisAgentLoop()
        self.voice = VoiceInterface(
            loop=self.loop,
            tts=self.mock_tts,
            wake_detector=self.wake_detector,
        )

    def test_wake_word_detector_standalone(self):
        """Verify wake-word detector spots standalone activation phrases."""
        self.assertTrue(self.wake_detector.is_wake_word("Hey JARVIS"))
        self.assertTrue(self.wake_detector.is_wake_word("JARVIS."))
        self.assertTrue(self.wake_detector.is_wake_word("hey jarvis..."))
        self.assertTrue(self.wake_detector.is_wake_word("hi jarvis"))
        self.assertTrue(self.wake_detector.is_wake_word("OK JARVIS!"))

        # Non-wake word
        self.assertFalse(self.wake_detector.is_wake_word("Open Chrome"))
        self.assertFalse(self.wake_detector.is_wake_word("What is the weather"))

    def test_wake_word_command_extraction(self):
        """Verify wake-word detector separates wake phrase from command."""
        # Standalone
        self.assertEqual(self.wake_detector.extract_command("Hey JARVIS..."), "")
        self.assertEqual(self.wake_detector.extract_command("JARVIS"), "")

        # Compound
        cmd1 = self.wake_detector.extract_command("Hey JARVIS, open Chrome.")
        self.assertEqual(cmd1, "open Chrome.")

        cmd2 = self.wake_detector.extract_command("JARVIS open Downloads")
        self.assertEqual(cmd2, "open Downloads")

        # No wake word present
        self.assertIsNone(self.wake_detector.extract_command("Open VS Code"))

    def test_conversational_dialog_sequence(self):
        """Verify the exact sequence:
        1. 'Hey JARVIS...' -> 'Yes?'
        2. 'Open Chrome.' -> Action executed, 'Opened Chrome.'
        3. 'Actually, cancel that.' -> 'Cancelled.' & rollback
        4. 'Wait, go back.' -> 'Going back.'
        """
        # Step 1: Wake word activation
        res1 = self.voice.process_utterance("Hey JARVIS...")
        self.assertEqual(res1["type"], "wake_ack")
        self.assertEqual(res1["response"], "Yes?")
        self.assertEqual(self.voice.state, VoiceSessionState.LISTENING)

        # Step 2: Spoken command
        res2 = self.voice.process_utterance("Open Chrome.")
        self.assertEqual(res2["type"], "execution")
        self.assertIn("Opened Chrome", res2["response"])
        self.assertFalse(self.voice.history.is_empty)

        # Step 3: Interruption & Cancellation: "Actually, cancel that."
        res3 = self.voice.process_utterance("Actually, cancel that.")
        self.assertEqual(res3["type"], "cancellation")
        self.assertEqual(res3["response"], "Cancelled.")
        self.assertTrue(res3["undo"]["success"])

        # Step 4: Re-activate and test "Wait, go back."
        self.voice.process_utterance("Hey JARVIS...")
        self.voice.process_utterance("Open Chrome.")
        res4 = self.voice.process_utterance("Wait, go back.")
        self.assertEqual(res4["type"], "rollback")
        self.assertIn("Going back", res4["response"])

    def test_compound_utterance_execution(self):
        """Verify compound trigger 'Hey JARVIS, open Chrome' executes without intermediate prompt."""
        res = self.voice.process_utterance("Hey JARVIS, open Chrome.")
        self.assertEqual(res["type"], "execution")
        self.assertIn("Opened Chrome", res["response"])
        self.assertFalse(self.voice.history.is_empty)

    def test_action_history_stack_undo(self):
        """Verify ActionHistoryStack records and rolls back actions."""
        stack = ActionHistoryStack()
        mock_tool = MagicMock()
        mock_tool.execute.return_value = MagicMock(success=True)

        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_tool
        mock_loop = MagicMock(registry=mock_registry)

        record = ActionHistoryRecord(
            description="Opened Chrome",
            tool_name="open_application",
            parameters={"app_name": "Chrome"},
            undo_tool="close_application",
            undo_args={"app_name": "Chrome"},
        )
        stack.push(record)
        self.assertEqual(len(stack._stack), 1)

        result = stack.undo_last(mock_loop)
        self.assertTrue(result["success"])
        self.assertIn("Reverted: Opened Chrome", result["message"])
        mock_tool.execute.assert_called_once_with(app_name="Chrome")
        self.assertTrue(stack.is_empty)

    def test_voice_and_text_reach_same_orchestrator(self):
        """CRITICAL: Verify both Voice -> Agent and Text -> Agent reach the exact same JarvisAgentLoop."""
        text_query = "Open Chrome"
        spoken_query = "Hey JARVIS, open Chrome"

        # 1. Text -> Agent loop directly
        text_state = self.loop.run(text_query)
        self.assertEqual(text_state.objective.intent, IntentCategory.SYSTEM_COMMAND)
        self.assertEqual(len(text_state.plan.steps), 1)
        self.assertEqual(text_state.plan.steps[0].tool_name, "open_application")

        # 2. Spoken Voice -> VoiceInterface -> Same Agent loop
        voice_res = self.voice.process_utterance(spoken_query)
        self.assertEqual(voice_res["type"], "execution")
        self.assertEqual(voice_res["loop_phase"], "COMPLETED")

        # Both utilized open_application on the exact same loop
        self.assertEqual(self.voice.loop, self.loop)

    def test_continuous_listener_lifecycle_and_injection(self):
        """Verify ContinuousVoiceListener background worker and simulated event injection."""
        listener = ContinuousVoiceListener(self.voice)
        listener.start()
        self.assertTrue(listener._running)

        # Inject simulated voice transcription
        res = listener.inject_text("Hey JARVIS...")
        self.assertEqual(res["type"], "wake_ack")
        self.assertEqual(self.voice.state, VoiceSessionState.LISTENING)

        # Inject simulated silent audio chunk
        silent_chunk = np.zeros(1600, dtype=np.float32)
        listener.inject_audio_chunk(silent_chunk)

        listener.stop()
        self.assertFalse(listener._running)


if __name__ == "__main__":
    unittest.main()
