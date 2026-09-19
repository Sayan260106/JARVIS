"""Research Planner for JARVIS Research Agent Subsystem (Phase 12).

Decomposes a research question or topic into structured angles, targeted sub-queries,
and report section blueprints.
"""

from __future__ import annotations
import re
from typing import List, Optional

from jarvis.subsystems.research.schemas import ResearchPlan


class ResearchPlanner:
    """Plans autonomous multi-source investigations from user questions."""

    PREFIX_PATTERNS = [
        r"^(?:please\s+)?research(?:\s+the)?(?:\s+latest)?(?:\s+developments)?(?:\s+in)?\s*",
        r"^(?:please\s+)?do(?:\s+some)?\s+research\s+(?:on|into|about)\s*",
        r"^(?:please\s+)?investigate\s*",
        r"^(?:please\s+)?find(?:\s+out)?\s+(?:information|details)\s+(?:on|about)\s*",
        r"^(?:please\s+)?make(?:\s+me)?\s+a\s+report\s+(?:on|about)\s*",
        r"^(?:please\s+)?prepare\s+a\s+research\s+dossier\s+(?:on|about)\s*",
        r"^(?:please\s+)?compile\s+a\s+research\s+report\s+(?:on|about)\s*",
    ]

    SUFFIX_PATTERNS = [
        r"\s+and\s+make(?:\s+me)?\s+a\s+report.*$",
        r"\s+and\s+write(?:\s+me)?\s+a\s+report.*$",
        r"\s+and\s+generate\s+a\s+report.*$",
        r"\s+and\s+give\s+me\s+a\s+summary.*$",
        r"\s+and\s+summarize(?:\s+it)?.*$",
    ]

    def extract_core_topic(self, query: str) -> str:
        """Extracts the pristine topic name from colloquial or imperative query strings."""
        topic = query.strip()
        
        # Strip prefixes
        for pattern in self.PREFIX_PATTERNS:
            topic = re.sub(pattern, "", topic, flags=re.IGNORECASE).strip()

        # Strip suffixes
        for pattern in self.SUFFIX_PATTERNS:
            topic = re.sub(pattern, "", topic, flags=re.IGNORECASE).strip()

        # Strip punctuation
        topic = topic.strip(".?!:;\"'")
        return topic or query.strip()

    def plan(self, question: str, max_sources_per_query: int = 3) -> ResearchPlan:
        """Generates a structured research plan with sub-queries and outline."""
        topic = self.extract_core_topic(question)

        sub_queries = [
            f"{topic} overview state of the art fundamentals",
            f"{topic} latest developments breakthroughs recent milestones",
            f"{topic} performance metrics benchmarks quantitative results",
            f"{topic} challenges controversies criticisms open problems",
            f"{topic} future roadmap commercial adoption implications",
        ]

        angles = [
            "Technical Foundations & Architectural Overview",
            "Recent Breakthroughs & Key Milestones",
            "Performance Claims & Quantitative Benchmarks",
            "Controversies, Conflicting Views & Technical Limitations",
            "Future Roadmap & Strategic Implications",
        ]

        target_sections = [
            "Executive Summary",
            "State of the Art & Technical Foundations",
            "Recent Breakthroughs & Key Developments",
            "Quantitative Claims & Benchmark Comparisons",
            "Conflicting Perspectives & Critical Challenges",
            "Future Outlook & Strategic Roadmap",
        ]

        return ResearchPlan(
            question=question,
            core_topic=topic,
            sub_queries=sub_queries,
            angles=angles,
            target_sections=target_sections,
            max_sources_per_query=max_sources_per_query,
        )
