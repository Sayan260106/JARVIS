"""JARVIS Research Agent Subsystem (Phase 12).

Exports the end-to-end research pipeline and associated models.
"""

from __future__ import annotations
from typing import Optional

from jarvis.subsystems.research.agent import ResearchAgent
from jarvis.subsystems.research.analyzer import SourceComparator
from jarvis.subsystems.research.harvester import SourceHarvester
from jarvis.subsystems.research.planner import ResearchPlanner
from jarvis.subsystems.research.schemas import (
    Citation,
    ConflictType,
    DetectedConflict,
    ExtractedClaim,
    ResearchPlan,
    ResearchReport,
    SourceItem,
)
from jarvis.subsystems.research.synthesizer import ReportSynthesizer


_default_agent: Optional[ResearchAgent] = None


def get_research_agent() -> ResearchAgent:
    """Returns singleton instance of the ResearchAgent."""
    global _default_agent
    if _default_agent is None:
        _default_agent = ResearchAgent()
    return _default_agent


def research(
    question_or_topic: str,
    output_path: Optional[str] = None,
    output_dir: Optional[str] = None,
    max_sources: int = 6,
) -> ResearchReport:
    """Convenience functional interface to execute research pipeline."""
    agent = get_research_agent()
    return agent.run(
        question_or_topic=question_or_topic,
        output_path=output_path,
        output_dir=output_dir,
        max_sources=max_sources,
    )


__all__ = [
    "ResearchAgent",
    "ResearchPlanner",
    "SourceHarvester",
    "SourceComparator",
    "ReportSynthesizer",
    "ResearchPlan",
    "SourceItem",
    "ExtractedClaim",
    "DetectedConflict",
    "Citation",
    "ResearchReport",
    "ConflictType",
    "get_research_agent",
    "research",
]
