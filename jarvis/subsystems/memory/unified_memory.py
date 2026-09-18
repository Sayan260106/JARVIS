"""Unified Memory Architecture for JARVIS (Memory 2.0).

Integrates the three core memory tiers:
1. Short-term Session Memory (`self.session`): Active tasks, step history, "What were we doing?"
2. Long-term Semantic Memory (`self.semantic`): Explicit user preferences (Chrome, VS Code, dirs)
3. Task / Workflow Memory (`self.workflow`): Reusable execution sequences (e.g. "Open ECE Classroom")

Maintains full backward compatibility with Working, Episodic, and Knowledge memory.
"""

from __future__ import annotations
import os
import re
from typing import Any, Dict, List, Optional

from jarvis.subsystems.memory.schemas import (
    Episode,
    KnowledgeItem,
    MemorySearchResult,
    MemoryTier,
    ReusableWorkflow,
    SemanticPreference,
    SessionActivity,
)
from jarvis.subsystems.memory.session_memory import SessionMemory
from jarvis.subsystems.memory.semantic_memory import SemanticMemory
from jarvis.subsystems.memory.workflow_memory import WorkflowMemory
from jarvis.subsystems.memory.working_memory import WorkingMemory
from jarvis.subsystems.memory.long_term_memory import EpisodicMemory, KnowledgeMemory
from jarvis.subsystems.local.memory import ConversationMemory


class UnifiedMemoryManager:
    """Unified access point coordinating all 3 Memory 2.0 tiers and legacy stores."""

    def __init__(self, db_path: str = "data/jarvis_memory.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

        # Core Memory 2.0 Tiers
        self.session = SessionMemory(db_path=db_path)
        self.semantic = SemanticMemory(db_path=db_path)
        self.workflow = WorkflowMemory(db_path=db_path)

        # Legacy & Specialized Tiers
        self.conversation = ConversationMemory(db_path=db_path)
        self.working = WorkingMemory(db_path=db_path)
        self.episodic = EpisodicMemory(db_path=db_path)
        self.knowledge = KnowledgeMemory(db_path=db_path)

    # --- Level 1: Short-term Session Memory Helpers ---

    def what_were_we_doing(self) -> str:
        """Answers 'What were we doing?' by summarizing active goal and steps."""
        return self.session.what_were_we_doing()

    def record_activity(
        self,
        goal: str,
        step_name: str,
        action: str,
        status: str = "SUCCESS",
        details: str = "",
        task_id: Optional[str] = None,
    ) -> SessionActivity:
        """Records an action in the active session."""
        return self.session.record_activity(
            goal=goal,
            step_name=step_name,
            action=action,
            status=status,
            details=details,
            task_id=task_id,
        )

    # --- Level 2: Long-term Semantic Memory Helpers ---

    def get_preference(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Retrieves an explicit user preference (e.g. preferred_browser, preferred_editor)."""
        return self.semantic.get_preference(key, default=default)

    def set_preference(
        self, key: str, value: str, category: str = "general", context: Optional[str] = None
    ) -> SemanticPreference:
        """Sets an explicit, user-permitted preference."""
        return self.semantic.remember_preference(key, value, category=category, context=context, is_explicit=True)

    def list_preferences(self, category: Optional[str] = None) -> Dict[str, str]:
        """Lists explicit user preferences."""
        return self.semantic.list_preferences(category=category)

    # --- Level 3: Task / Workflow Memory Helpers ---

    def find_workflow(self, prompt: str) -> Optional[ReusableWorkflow]:
        """Searches workflow memory for a matching reusable workflow."""
        return self.workflow.find_matching_workflow(prompt)

    def save_workflow(
        self, name: str, trigger_patterns: List[str], steps: List[Dict[str, Any]], description: str = ""
    ) -> ReusableWorkflow:
        """Saves a reusable workflow template."""
        return self.workflow.save_workflow(name, trigger_patterns, steps, description=description)

    def list_workflows(self) -> List[ReusableWorkflow]:
        """Lists all registered reusable workflows."""
        return self.workflow.list_workflows()

    # --- Cross-Tier Context Synthesis ---

    def get_injected_context(self, query: str) -> str:
        """Constructs an integrated context block for LLM prompts."""
        context_blocks = []

        # 1. Active session state if asking about current progress
        if any(w in query.lower() for w in ["doing", "last", "progress", "status", "recent"]):
            act_text = self.what_were_we_doing()
            context_blocks.append(f"Current Session Status:\n{act_text}")

        # 2. Explicit User Preferences
        pref_inj = self.semantic.get_prompt_injection()
        if pref_inj:
            context_blocks.append(pref_inj)

        # 3. Matching Reusable Workflow
        matched_wf = self.find_workflow(query)
        if matched_wf:
            context_blocks.append(
                f"Matching Reusable Workflow: '{matched_wf.name}' ({len(matched_wf.steps)} steps registered)."
            )

        return "\n\n".join(context_blocks)

    # --- Backward-Compatible Search & Storage ---

    def search_all(self, query: str, limit: int = 5) -> List[MemorySearchResult]:
        """Searches across semantic preferences, episodic events, and knowledge base."""
        results: List[MemorySearchResult] = []

        # 1. Search Semantic Preferences
        pref_matches = self.semantic.search_preferences(query)
        for p in pref_matches:
            results.append(
                MemorySearchResult(
                    memory_type=MemoryTier.SEMANTIC,
                    id=f"pref_{p.key}",
                    title=f"User Preference: {p.key}",
                    snippet=f"{p.key}: {p.value}",
                    relevance_score=1.0,
                )
            )

        # 2. Search Knowledge Base (FTS5)
        know_items = self.knowledge.search(query, limit=limit)
        for item in know_items:
            snippet = item.content[:200] + ("..." if len(item.content) > 200 else "")
            results.append(
                MemorySearchResult(
                    memory_type=MemoryTier.KNOWLEDGE,
                    id=item.id,
                    title=item.title,
                    snippet=snippet,
                    relevance_score=0.9,
                    timestamp=item.created_at,
                    metadata={"tags": item.tags, "source": item.source},
                )
            )

        # 3. Search Episodic Events
        episodes = self.episodic.search_episodes(query, limit=limit)
        for ep in episodes:
            results.append(
                MemorySearchResult(
                    memory_type=MemoryTier.EPISODIC,
                    id=ep.id,
                    title=ep.title,
                    snippet=ep.summary,
                    relevance_score=0.8,
                    timestamp=ep.timestamp,
                    metadata={"key_facts": ep.key_facts},
                )
            )

        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results[:limit]

    def get_relevant_context(self, query: str) -> str:
        """Constructs an LLM context block of relevant long-term memories for injection."""
        results = self.search_all(query, limit=4)
        lines = []
        if results:
            lines.append("Relevant Long-Term Memories:")
            for r in results:
                lines.append(f"[{r.memory_type.value}] {r.title}: {r.snippet}")

        prefs = self.semantic.list_preferences()
        if prefs:
            pref_lines = [f"- {k}: {v}" for k, v in prefs.items()]
            if lines:
                lines.append("")
            lines.append("User Preferences:\n" + "\n".join(pref_lines))

        return "\n".join(lines)

    def remember_fact(self, key: str, value: str, context: Optional[str] = None) -> str:
        self.set_preference(key, value, context=context)
        return self.episodic.remember_preference(key, value, context)

    def store_knowledge(
        self,
        title: str,
        content: str,
        tags: Optional[List[str]] = None,
        source: str = "user_input",
    ) -> str:
        item = KnowledgeItem(
            title=title,
            content=content,
            tags=tags or [],
            source=source,
        )
        return self.knowledge.add_item(item)
