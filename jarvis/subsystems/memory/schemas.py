"""Memory schemas and data structures for JARVIS.

Defines models for:
1. Short-term Session Memory (current task, steps, "what were we doing?")
2. Long-term Semantic Memory (explicit user preferences & facts)
3. Task / Workflow Memory (reusable workflows like "Open ECE Classroom")
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any, Dict, List, Optional
import uuid


class MemoryTier(str, Enum):
    """Memory tiers for Memory 2.0."""
    # Memory 2.0 Core Tiers
    SESSION = "SESSION"            # Short-term active task, steps & history ("What were we doing?")
    SEMANTIC = "SEMANTIC"          # Explicit allowed preferences & long-term facts
    WORKFLOW = "WORKFLOW"          # Reusable task templates & workflows

    # Backward-compatible tiers
    CONVERSATION = "CONVERSATION"  # Short-term active chat turns
    WORKING = "WORKING"            # In-flight task scratchpad
    EPISODIC = "EPISODIC"          # Past events & sessions
    KNOWLEDGE = "KNOWLEDGE"        # Documents, notes, factual snippets


@dataclass
class SessionActivity:
    """Represents a recorded action or progress milestone in the active session."""
    id: str = field(default_factory=lambda: f"act_{uuid.uuid4().hex[:12]}")
    session_id: str = ""
    task_id: Optional[str] = None
    goal: str = ""
    step_name: str = ""
    action: str = ""
    status: str = "SUCCESS"        # "SUCCESS", "FAILED", "RUNNING", "PENDING"
    details: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "task_id": self.task_id,
            "goal": self.goal,
            "step_name": self.step_name,
            "action": self.action,
            "status": self.status,
            "details": self.details,
            "timestamp": self.timestamp,
        }


@dataclass
class SemanticPreference:
    """Represents an explicit, user-permitted preference or system setting."""
    key: str
    value: str
    category: str = "general"      # "browser", "editor", "filesystem", "academic", "general"
    is_explicit: bool = True       # True if explicitly permitted by user
    context: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "category": self.category,
            "is_explicit": self.is_explicit,
            "context": self.context,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class ReusableWorkflow:
    """Represents a captured reusable workflow template."""
    id: str = field(default_factory=lambda: f"wf_{uuid.uuid4().hex[:12]}")
    name: str = ""
    description: str = ""
    trigger_patterns: List[str] = field(default_factory=list)
    steps: List[Dict[str, Any]] = field(default_factory=list)
    success_count: int = 1
    last_used_at: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "trigger_patterns": self.trigger_patterns,
            "steps": self.steps,
            "success_count": self.success_count,
            "last_used_at": self.last_used_at,
            "created_at": self.created_at,
        }


@dataclass
class Episode:
    """Represents an episodic memory event, session summary, or user preference."""
    id: str = field(default_factory=lambda: f"ep_{uuid.uuid4().hex[:12]}")
    session_id: Optional[str] = None
    episode_type: str = "interaction"
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
    source: str = "user_input"
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
