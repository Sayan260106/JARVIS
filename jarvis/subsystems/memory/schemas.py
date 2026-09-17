"""Memory schemas and data structures for JARVIS.

Defines models for Conversation, Working, Episodic, and Knowledge memory.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any, Dict, List, Optional
import uuid


class MemoryTier(str, Enum):
    """The four functional memory tiers."""
    CONVERSATION = "CONVERSATION"  # Short-term active chat turns
    WORKING = "WORKING"            # In-flight task scratchpad
    EPISODIC = "EPISODIC"          # Past events, sessions, user preferences
    KNOWLEDGE = "KNOWLEDGE"        # Documents, notes, factual snippets


@dataclass
class Episode:
    """Represents an episodic memory event, session summary, or user preference."""
    id: str = field(default_factory=lambda: f"ep_{uuid.uuid4().hex[:12]}")
    session_id: Optional[str] = None
    episode_type: str = "interaction"  # "interaction", "user_preference", "task_milestone", "system_event"
    title: str = ""
    summary: str = ""
    key_facts: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class KnowledgeItem:
    """Represents an indexed document, note, cheatsheet, or reference fact."""
    id: str = field(default_factory=lambda: f"know_{uuid.uuid4().hex[:12]}")
    title: str = ""
    content: str = ""
    tags: List[str] = field(default_factory=list)
    source: str = "user_input"  # "user_input", "document", "web", "task_output"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class WorkingMemoryEntry:
    """Represents a key-value entry in a task's ephemeral working memory."""
    task_id: str
    key: str
    value: Any
    updated_at: float = field(default_factory=time.time)


@dataclass
class MemorySearchResult:
    """Normalized search result across memory tiers."""
    memory_type: MemoryTier
    id: str
    title: str
    snippet: str
    relevance_score: float = 1.0
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
