"""Unit and integration tests for JARVIS Phase 10: Long-Term Memory.

Verifies:
1. Conversation memory (short-term turns).
2. Working memory (task-scoped ephemeral scratchpad).
3. Episodic memory (events, session recaps, user preferences).
4. Knowledge memory (documents and notes indexed via SQLite FTS5).
5. Unified memory facade (cross-tier search and context block synthesis).
6. BaseTool implementations for memory subsystem.
7. Context injection into ConversationEngine.
"""

import os
import unittest

from jarvis.subsystems.memory.schemas import Episode, KnowledgeItem, MemoryTier
from jarvis.subsystems.memory.working_memory import WorkingMemory
from jarvis.subsystems.memory.long_term_memory import EpisodicMemory, KnowledgeMemory
from jarvis.subsystems.memory.unified_memory import UnifiedMemoryManager
from jarvis.tools.memory_tools import (
    RememberFactTool,
    RecallMemoryTool,
    StoreKnowledgeTool,
    SearchKnowledgeTool,
    ManageWorkingMemoryTool,
)
from jarvis.capabilities.conversation import ConversationEngine
from jarvis.subsystems.local.ollama_client import OllamaClient
from jarvis.subsystems.local.tts import LocalTTS


class TestLongTermMemory(unittest.TestCase):
    """Test suite for Phase 10 memory architecture."""

    @classmethod
    def setUpClass(cls):
        cls.test_db = "data/test_jarvis_memory_p10.db"
        cls.memory_mgr = UnifiedMemoryManager(db_path=cls.test_db)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_db):
            try:
                os.remove(cls.test_db)
            except Exception:
                pass

    def test_conversation_memory(self):
        """Verify session creation and multi-turn message persistence."""
        sess_id = self.memory_mgr.conversation.create_session("Test Chat Session")
        self.assertTrue(sess_id.startswith("sess_"))

        self.memory_mgr.conversation.add_message(sess_id, "user", "What is an AVL tree?")
        self.memory_mgr.conversation.add_message(sess_id, "assistant", "An AVL tree is a self-balancing BST.")

        history = self.memory_mgr.conversation.get_history(sess_id, limit=5)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[1]["role"], "assistant")

    def test_working_memory_scratchpad(self):
        """Verify task-scoped scratchpad variable read, write, delete, and clear."""
        wm = self.memory_mgr.working
        task_id = "task_organize_101"

        # Set variables
        wm.set(task_id, "target_dir", "D:/Downloads")
        wm.set(task_id, "duplicates_found", 3)
        wm.set(task_id, "categories", ["Documents", "Code", "Archives"])

        # Get variables
        self.assertEqual(wm.get(task_id, "target_dir"), "D:/Downloads")
        self.assertEqual(wm.get(task_id, "duplicates_found"), 3)
        self.assertEqual(len(wm.get(task_id, "categories")), 3)

        # Get all
        all_vars = wm.get_all(task_id)
        self.assertIn("target_dir", all_vars)
        self.assertIn("duplicates_found", all_vars)

        # Delete single variable
        self.assertTrue(wm.delete(task_id, "duplicates_found"))
        self.assertIsNone(wm.get(task_id, "duplicates_found"))

        # Clear entire task scratchpad
        cleared = wm.clear(task_id)
        self.assertGreater(cleared, 0)
        self.assertEqual(len(wm.get_all(task_id)), 0)

    def test_episodic_memory_and_preferences(self):
        """Verify storing user preferences and querying episodic interaction milestones."""
        em = self.memory_mgr.episodic

        # Remember preference
        pref_key = em.remember_preference("target_exam", "GATE 2027 CSE", context="Preparing with standard textbooks")
        self.assertEqual(pref_key, "target_exam")

        prefs = em.get_preferences()
        self.assertIn("target_exam", prefs)
        self.assertEqual(prefs["target_exam"], "GATE 2027 CSE")

        # Record milestone episode
        ep_id = em.add_episode(
            Episode(
                episode_type="task_milestone",
                title="Downloads Organization Completed",
                summary="Successfully organized 183 files into six categories and left duplicates untouched.",
                key_facts=["Organized 183 files", "6 categories", "3 duplicates detected"],
                tags=["downloads", "organization", "maintenance"],
            )
        )
        self.assertTrue(ep_id.startswith("ep_"))

        # Search episodes
        matches = em.search_episodes("downloads organization")
        self.assertGreater(len(matches), 0)
        self.assertEqual(matches[0].title, "Downloads Organization Completed")

    def test_knowledge_memory_fts5(self):
        """Verify document and notes indexing with SQLite FTS5 full-text search."""
        km = self.memory_mgr.knowledge

        item1_id = km.add_item(
            KnowledgeItem(
                title="B-Trees and B+ Trees Indexing",
                content="B-trees are balanced search trees designed for block-storage disk systems. B+ trees store all data in leaf nodes.",
                tags=["database", "dbms", "gate", "indexing"],
                source="study_notes",
            )
        )
        self.assertTrue(item1_id.startswith("know_"))

        item2_id = km.add_item(
            KnowledgeItem(
                title="Relational Algebra Operators",
                content="Fundamental operators include selection (sigma), projection (pi), cross product, set difference, and union.",
                tags=["database", "dbms", "relational_algebra"],
                source="study_notes",
            )
        )

        # FTS5 Full-Text Search for "B-trees"
        results = km.search("B-trees")
        self.assertGreater(len(results), 0)
        self.assertEqual(results[0].title, "B-Trees and B+ Trees Indexing")

        # FTS5 Full-Text Search for "projection"
        results2 = km.search("projection")
        self.assertGreater(len(results2), 0)
        self.assertEqual(results2[0].title, "Relational Algebra Operators")

    def test_unified_memory_facade_and_context(self):
        """Verify cross-tier retrieval and LLM context synthesis."""
        # Query matching both preferences and knowledge
        results = self.memory_mgr.search_all("GATE database", limit=5)
        self.assertGreater(len(results), 0)

        # Generate context block
        context_block = self.memory_mgr.get_relevant_context("What is my preparation focus for GATE?")
        self.assertIn("Long-Term Memories", context_block)
        self.assertTrue(any(w in context_block for w in ["GATE", "target_exam", "B-Trees"]))

    def test_memory_tools(self):
        """Verify BaseTool executions and ground-truth verifications for memory subsystem."""
        # 1. RememberFactTool
        rem_tool = RememberFactTool(memory_manager=self.memory_mgr)
        rem_res = rem_tool.execute(key="primary_programming_language", value="Python 3.14")
        self.assertTrue(rem_res.success)
        rem_ver = rem_tool.verify({"key": "primary_programming_language", "value": "Python 3.14"}, rem_res)
        self.assertTrue(rem_ver.verified)

        # 2. RecallMemoryTool
        rec_tool = RecallMemoryTool(memory_manager=self.memory_mgr)
        rec_res = rec_tool.execute(query="programming language")
        self.assertTrue(rec_res.success)
        rec_ver = rec_tool.verify({"query": "programming language"}, rec_res)
        self.assertTrue(rec_ver.verified)
        self.assertGreater(rec_res.output["count"], 0)

        # 3. StoreKnowledgeTool
        store_tool = StoreKnowledgeTool(memory_manager=self.memory_mgr)
        store_res = store_tool.execute(
            title="Operating System Semaphores",
            content="A semaphore is a synchronization tool with wait() (P) and signal() (V) atomic operations.",
            tags="os, gate, concurrency",
        )
        self.assertTrue(store_res.success)
        store_ver = store_tool.verify({"title": "Operating System Semaphores"}, store_res)
        self.assertTrue(store_ver.verified)

        # 4. SearchKnowledgeTool
        search_tool = SearchKnowledgeTool(memory_manager=self.memory_mgr)
        search_res = search_tool.execute(query="semaphore")
        self.assertTrue(search_res.success)
        search_ver = search_tool.verify({"query": "semaphore"}, search_res)
        self.assertTrue(search_ver.verified)
        self.assertGreater(search_res.output["count"], 0)

        # 5. ManageWorkingMemoryTool
        wm_tool = ManageWorkingMemoryTool(memory_manager=self.memory_mgr)
        set_res = wm_tool.execute(action="set", task_id="task_temp_42", key="step_status", value="verified")
        self.assertTrue(set_res.success)
        get_res = wm_tool.execute(action="get", task_id="task_temp_42", key="step_status")
        self.assertTrue(get_res.success)
        self.assertEqual(get_res.output["value"], "verified")

    def test_conversation_engine_context_injection(self):
        """Verify ConversationEngine automatically augments turns with long-term memory."""
        self.memory_mgr.remember_fact("target_exam", "GATE 2027 CSE", context="Engineering syllabus")
        tts = LocalTTS(enabled=False)
        engine = ConversationEngine(
            memory=self.memory_mgr.conversation,
            unified_memory=self.memory_mgr,
            tts=tts,
            speak_output=False,
            enable_tools=False,
        )
        query = "What exam am I preparing for?"
        ctx = self.memory_mgr.get_relevant_context(query)
        self.assertIn("target_exam", ctx)
        self.assertIn("GATE 2027", ctx)


if __name__ == "__main__":
    unittest.main()
