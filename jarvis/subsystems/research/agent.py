"""Master Research Agent for JARVIS (Phase 12).

Implements the complete autonomous research pipeline:
Question -> Research Planner -> Search -> Multiple Sources -> Extract -> Cross-check -> Summarize -> Citations -> Report
"""

from __future__ import annotations
import datetime
import os
import re
from typing import Any, Dict, List, Optional

from jarvis.subsystems.research.analyzer import SourceComparator
from jarvis.subsystems.research.harvester import SourceHarvester
from jarvis.subsystems.research.planner import ResearchPlanner
from jarvis.subsystems.research.schemas import (
    DetectedConflict,
    ExtractedClaim,
    ResearchPlan,
    ResearchReport,
    SourceItem,
)
from jarvis.subsystems.research.synthesizer import ReportSynthesizer


class ResearchAgent:
    """Autonomous research agent executing the full 8-stage research pipeline."""

    def __init__(
        self,
        planner: Optional[ResearchPlanner] = None,
        harvester: Optional[SourceHarvester] = None,
        comparator: Optional[SourceComparator] = None,
        synthesizer: Optional[ReportSynthesizer] = None,
        default_output_dir: str = "reports",
    ):
        self.planner = planner or ResearchPlanner()
        self.harvester = harvester or SourceHarvester()
        self.comparator = comparator or SourceComparator()
        self.synthesizer = synthesizer or ReportSynthesizer()
        self.default_output_dir = default_output_dir

    def run(
        self,
        question_or_topic: str,
        output_path: Optional[str] = None,
        output_dir: Optional[str] = None,
        max_sources: int = 6,
        open_pages: bool = True,
    ) -> ResearchReport:
        """Executes the full research pipeline and saves the cited report to disk."""
        # 1. Question -> Research Planner
        plan = self.planner.plan(question_or_topic)

        # 2. Search -> Multiple Sources -> Extract text from pages
        sources = self.harvester.search_and_harvest(
            plan=plan,
            max_total_sources=max_sources,
            open_pages=open_pages,
        )

        # 3. Extract claims across sources
        claims = self.comparator.extract_claims(sources)

        # 4. Cross-check claims & detect conflicting information
        conflicts = self.comparator.detect_conflicts(claims)

        # 5. Summarize & Citations -> Report Synthesis
        report = self.synthesizer.synthesize(
            plan=plan,
            sources=sources,
            claims=claims,
            conflicts=conflicts,
        )

        # 6. Save report locally to disk
        target_path = output_path or self._generate_report_filename(
            plan.core_topic,
            output_dir or self.default_output_dir,
        )
        self._save_report(report, target_path)

        return report

    def _generate_report_filename(self, topic: str, output_dir: str) -> str:
        """Generates a clean filesystem-safe report path."""
        safe_topic = re.sub(r"[^\w\-_]", "_", topic).strip("_")
        safe_topic = re.sub(r"_+", "_", safe_topic)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Research_{safe_topic}_{timestamp}.md"
        return os.path.join(output_dir, filename)

    def _save_report(self, report: ResearchReport, filepath: str) -> str:
        """Writes report markdown to local filesystem."""
        directory = os.path.dirname(filepath)
        if directory:
            os.makedirs(directory, exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(report.full_markdown)

        report.saved_path = os.path.abspath(filepath)
        return report.saved_path
