"""Unified Memory Architecture for JARVIS.

Integrates Conversation, Working, Episodic, and Knowledge memory into a single
cohesive facade backed by SQLite.
"""

from __future__ import annotations
import os
from typing import Any, Dict, List, Optional

from jarvis.subsystems.memory.schemas import (
    Episode,
    KnowledgeItem,
    MemorySearchResult,
    MemoryTier,
)
from jarvis.subsystems.memory.working_memory import WorkingMemory
from jarvis.subsystems.memory.long_term_memory import EpisodicMemory, KnowledgeMemory
from jarvis.subsystems.local.memory import ConversationMemory


class UnifiedMemoryManager:
    """Unified access point coordinating all 4 memory tiers."""

    def __init__(self, db_path: str = "data/jarvis_memory.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

        self.conversation = ConversationMemory(db_path=db_path)
        self.working = WorkingMemory(db_path=db_path)
        self.episodic = EpisodicMemory(db_path=db_path)
        self.knowledge = KnowledgeMemory(db_path=db_path)

    def search_all(self, query: str, limit: int = 5) -> List[MemorySearchResult]:
        """Searches across episodic, knowledge, and preferences for relevant context."""
        results: List[MemorySearchResult] = []

        # 1. Search Preferences
        prefs = self.episodic.get_preferences()
        q_lower = query.lower()
        for k, v in prefs.items():
            if k.lower() in q_lower or any(token in f"{k} {v}".lower() for token in q_lower.split()):
                results.append(
                    MemorySearchResult(
                        memory_type=MemoryTier.EPISODIC,
                        id=f"pref_{k}",
                        title=f"User Preference: {k}",
                        snippet=f"{k}: {v}",
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
        if not results:
            # Check if there are general user preferences to include
            prefs = self.episodic.get_preferences()
            if not prefs:
                return ""
            pref_lines = [f"- {k}: {v}" for k, v in prefs.items()]
            return "User Preferences:\n" + "\n".join(pref_lines)

        lines = ["Relevant Long-Term Memories:"]
        for r in results:
            lines.append(f"[{r.memory_type.value}] {r.title}: {r.snippet}")
        return "\n".join(lines)

    def remember_fact(self, key: str, value: str, context: Optional[str] = None) -> str:
        """Stores a user fact or preference into long-term memory."""
        return self.episodic.remember_preference(key, value, context)

    def store_knowledge(
        self,
        title: str,
        content: str,
        tags: Optional[List[str]] = None,
        source: str = "user_input",
    ) -> str:
        """Stores a document or reference note into knowledge memory."""
        item = KnowledgeItem(
            title=title,
            content=content,
            tags=tags or [],
            source=source,
        )
        return self.knowledge.add_item(item)
