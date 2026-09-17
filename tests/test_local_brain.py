"""Unit and integration tests for JARVIS Phase 1: Local Brain.

Verifies:
1. Ollama local LLM integration.
2. SQLite multi-turn conversational memory.
3. The exact Phase 1 milestone conversation sequence:
   - "Jarvis." -> "Yes?"
   - "What is a binary search tree?" -> Technical explanation + SQLite persistence.
   - "Explain it like I'm preparing for GATE." -> Context-aware GATE exam preparation answer.
"""

import os
import unittest
from jarvis.subsystems.local.ollama_client import OllamaClient
from jarvis.subsystems.local.memory import ConversationMemory
from jarvis.subsystems.local.tts import LocalTTS
from jarvis.capabilities.conversation import ConversationEngine


class TestLocalBrain(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.db_path = "data/test_jarvis_memory.db"
        cls.memory = ConversationMemory(db_path=cls.db_path)
        cls.ollama = OllamaClient(model="qwen2.5:3b")
        # Disable audio device playback during unit test execution
        cls.tts = LocalTTS(enabled=False)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.db_path):
            try:
                os.remove(cls.db_path)
            except Exception:
                pass

    def setUp(self):
        self.session_id = self.memory.create_session("Milestone Test Session")
        self.engine = ConversationEngine(
            ollama_client=self.ollama,
            memory=self.memory,
            tts=self.tts,
            session_id=self.session_id,
            speak_output=False,
        )

    def test_ollama_connectivity(self):
        """Verify local Ollama server is running and qwen2.5:3b is available."""
        self.assertTrue(self.ollama.is_available(), "Ollama server is not reachable on localhost:11434")
        models = self.ollama.list_models()
        self.assertTrue(any("qwen2.5:3b" in m for m in models), f"qwen2.5:3b not found in models: {models}")

    def test_sqlite_memory(self):
        """Verify message insertion, chronological retrieval, and multi-turn retention."""
        sess = self.memory.create_session("Unit Test")
        self.memory.add_message(sess, "user", "Test question 1")
        self.memory.add_message(sess, "assistant", "Test answer 1")
        self.memory.add_message(sess, "user", "Test question 2")

        history = self.memory.get_history(sess, limit=5)
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[0]["content"], "Test question 1")
        self.assertEqual(history[1]["role"], "assistant")
        self.assertEqual(history[1]["content"], "Test answer 1")
        self.assertEqual(history[2]["content"], "Test question 2")

    def test_milestone_wake_word(self):
        """Milestone Turn 0: User says 'Jarvis.' -> System responds 'Yes?'."""
        response = self.engine.process_turn("Jarvis.")
        self.assertEqual(response, "Yes?")

    def test_milestone_conversation_sequence(self):
        """Full Milestone sequence:
        1. 'Jarvis.' -> 'Yes?'
        2. 'What is a binary search tree?' -> Answers and stores in SQLite.
        3. 'Explain it like I'm preparing for GATE.' -> Follow-up context-aware answer.
        """
        # Turn 1: Wake word
        r1 = self.engine.process_turn("Jarvis.")
        self.assertEqual(r1, "Yes?")

        # Turn 2: Technical question
        r2 = self.engine.process_turn("What is a binary search tree?")
        self.assertTrue(len(r2) > 30, "Response should be a detailed technical explanation")
        lower_r2 = r2.lower()
        self.assertTrue(
            any(w in lower_r2 for w in ["node", "left", "right", "binary search tree", "bst", "subtree"]),
            f"Expected BST concepts in response: {r2[:150]}",
        )

        # Verify Turn 2 saved in SQLite
        history = self.memory.get_history(self.session_id)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[0]["content"], "What is a binary search tree?")
        self.assertEqual(history[1]["role"], "assistant")

        # Turn 3: Contextual follow-up
        r3 = self.engine.process_turn("Explain it like I'm preparing for GATE.")
        self.assertTrue(len(r3) > 30, "Response should contain GATE exam preparation insights")
        lower_r3 = r3.lower()
        self.assertTrue(
            any(w in lower_r3 for w in ["gate", "complexity", "o(h)", "o(n)", "worst", "height", "traversal", "avl", "inorder", "search"]),
            f"Expected GATE exam context in response: {r3[:150]}",
        )

        # Verify all turns saved in SQLite
        updated_history = self.memory.get_history(self.session_id)
        self.assertEqual(len(updated_history), 4)


if __name__ == "__main__":
    unittest.main()
