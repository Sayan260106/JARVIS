"""Data schemas for JARVIS Research Agent Subsystem (Phase 12).

Defines the typed contracts governing the research pipeline:
Question -> Research Planner -> Search -> Multiple Sources -> Extract -> Cross-check -> Summarize -> Citations -> Report
"""

from __future__ import annotations
from dataclasses import dataclass, field
import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class ConflictType(str, Enum):
    """Classification of conflicts detected between sources."""
    NUMERIC_DIVERGENCE = "NUMERIC_DIVERGENCE"
    DATE_TIMELINE = "DATE_TIMELINE"
    FACTUAL_POLARITY = "FACTUAL_POLARITY"
    TERMINOLOGY_MISMATCH = "TERMINOLOGY_MISMATCH"
    GENERAL_DISAGREEMENT = "GENERAL_DISAGREEMENT"


@dataclass
class ResearchPlan:
    """Decomposition of a research question into targeted angles and sub-queries."""
    question: str
    core_topic: str
    sub_queries: List[str] = field(default_factory=list)
    angles: List[str] = field(default_factory=list)
    target_sections: List[str] = field(default_factory=list)
    max_sources_per_query: int = 3
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "question": self.question,
            "core_topic": self.core_topic,
            "sub_queries": self.sub_queries,
            "angles": self.angles,
            "target_sections": self.target_sections,
            "max_sources_per_query": self.max_sources_per_query,
        }


@dataclass
class SourceItem:
    """An individual source retrieved during search and opened for extraction."""
    source_id: str
    url: str
    title: str
    snippet: str
    body_text: str = ""
    source_type: str = "web"  # "web", "cloud_llm", "local_knowledge", "academic"
    confidence: float = 0.8
    published_date: Optional[str] = None
    accessed_timestamp: str = field(default_factory=lambda: datetime.datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "url": self.url,
            "title": self.title,
            "snippet": self.snippet,
            "source_type": self.source_type,
            "confidence": self.confidence,
            "published_date": self.published_date,
            "accessed_timestamp": self.accessed_timestamp,
        }


@dataclass
class ExtractedClaim:
    """An atomic factual claim extracted from a specific source."""
    claim_id: str
    source_id: str
    source_title: str
    source_url: str
    subject: str
    assertion: str
    numeric_value: Optional[float] = None
    unit: Optional[str] = None
    raw_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "source_id": self.source_id,
            "source_title": self.source_title,
            "source_url": self.source_url,
            "subject": self.subject,
            "assertion": self.assertion,
            "numeric_value": self.numeric_value,
            "unit": self.unit,
            "raw_text": self.raw_text,
        }


@dataclass
class DetectedConflict:
    """A detected conflict, divergence, or contradiction between claims."""
    subject: str
    source_a_title: str
    source_a_url: str
    claim_a: str
    source_b_title: str
    source_b_url: str
    claim_b: str
    conflict_type: ConflictType = ConflictType.GENERAL_DISAGREEMENT
    divergence: Optional[float] = None
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subject": self.subject,
            "source_a_title": self.source_a_title,
            "source_a_url": self.source_a_url,
            "claim_a": self.claim_a,
            "source_b_title": self.source_b_title,
            "source_b_url": self.source_b_url,
            "claim_b": self.claim_b,
            "conflict_type": self.conflict_type.value,
            "divergence": self.divergence,
            "explanation": self.explanation,
        }


@dataclass
class Citation:
    """A formatted citation referencing an evidence source."""
    index: int
    title: str
    url: str
    source_type: str
    accessed_date: str
    snippet: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "title": self.title,
            "url": self.url,
            "source_type": self.source_type,
            "accessed_date": self.accessed_date,
            "snippet": self.snippet,
        }


@dataclass
class ResearchReport:
    """The synthesized end-to-end research report."""
    topic: str
    title: str
    executive_summary: str
    sections: Dict[str, str] = field(default_factory=dict)
    conflicts: List[DetectedConflict] = field(default_factory=list)
    citations: List[Citation] = field(default_factory=list)
    full_markdown: str = ""
    saved_path: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "title": self.title,
            "executive_summary": self.executive_summary,
            "sections": self.sections,
            "conflicts_count": len(self.conflicts),
            "citations_count": len(self.citations),
            "saved_path": self.saved_path,
            "created_at": self.created_at,
        }
