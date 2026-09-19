"""Research & Web Intelligence Skills for JARVIS (Phase 11 & Phase 12).

Domain: research/
Skills:
- research.topic
- research.gather_sources
- research.compare_sources
- research.synthesize_report
"""

from __future__ import annotations
import os
from typing import Any, Dict, List, Optional
from jarvis.skills.base import (
    BaseSkill,
    PreconditionResult,
    RecoveryAction,
    RecoveryStrategy,
    SkillContext,
    SkillParameter,
    SkillResult,
    VerificationResult,
)


class ResearchTopicSkill(BaseSkill):
    name = "research.topic"
    domain = "research"
    capability = "Performs autonomous deep multi-source research, cross-checks claims, detects conflicts, and synthesizes findings."
    required_tools = ["deep_research"]
    parameters = {
        "topic": SkillParameter("topic", "string", "Subject or query to research", required=True),
        "max_sources": SkillParameter("max_sources", "integer", "Number of sources to query", required=False, default=5),
        "output_path": SkillParameter("output_path", "path", "Optional file destination for the cited report", required=False, default=None),
    }

    def execute(self, params: Dict[str, Any], context: SkillContext) -> SkillResult:
        topic = params["topic"]
        max_s = int(params.get("max_sources", 5))
        out_path = params.get("output_path")

        # 1. Try via registered tool if present
        if self.registry:
            tool = self.registry.get("deep_research") or self.registry.get("research_topic")
            if tool:
                res = tool.execute(topic=topic, max_sources=max_s, output_path=out_path)
                if res.success and res.output:
                    context.set("research_findings", res.output.get("executive_summary") or res.output.get("final_synthesis"))
                    context.set("research_report_path", res.output.get("saved_path"))
                    context.set("research_report_data", res.output)
                    return SkillResult(
                        success=True,
                        output=f"Deep research completed on '{topic}'. Saved to: {res.output.get('saved_path')}",
                        artifacts={"topic": topic, "report": res.output},
                    )

        # 2. Direct subsystem invocation
        from jarvis.subsystems.research import get_research_agent
        agent = get_research_agent()
        report = agent.run(question_or_topic=topic, output_path=out_path, max_sources=max_s)
        context.set("research_findings", report.executive_summary)
        context.set("research_report_path", report.saved_path)
        context.set("research_report_data", report.to_dict())

        return SkillResult(
            success=True,
            output=f"Deep research completed on '{topic}'. Evaluated {len(report.citations)} sources, found {len(report.conflicts)} conflicts. Saved to: {report.saved_path}",
            artifacts={"topic": topic, "saved_path": report.saved_path, "conflicts": len(report.conflicts)},
        )


class ResearchGatherSourcesSkill(BaseSkill):
    name = "research.gather_sources"
    domain = "research"
    capability = "Collects URLs, academic papers, and reference links for a topic."
    required_tools = ["browser_search_page"]
    parameters = {
        "topic": SkillParameter("topic", "string", "Search topic", required=True),
    }

    def execute(self, params: Dict[str, Any], context: SkillContext) -> SkillResult:
        topic = params["topic"]
        from jarvis.subsystems.research.planner import ResearchPlanner
        from jarvis.subsystems.research.harvester import SourceHarvester

        planner = ResearchPlanner()
        plan = planner.plan(topic)
        harvester = SourceHarvester()
        sources = harvester.search_and_harvest(plan, max_total_sources=4, open_pages=False)

        source_list = [s.to_dict() for s in sources]
        context.set("gathered_sources", source_list)
        return SkillResult(
            success=True,
            output=f"Gathered {len(sources)} source references for '{topic}'.",
            artifacts={"topic": topic, "sources": source_list},
        )


class ResearchCompareSourcesSkill(BaseSkill):
    name = "research.compare_sources"
    domain = "research"
    capability = "Cross-checks multiple sources on a topic and identifies discrepancies, numeric divergences, or contradictions."
    required_tools = ["compare_sources"]
    parameters = {
        "sources": SkillParameter("sources", "list", "List of source dicts or text strings", required=False, default=None),
        "topic": SkillParameter("topic", "string", "Optional topic to look up if sources not supplied", required=False, default=None),
    }

    def execute(self, params: Dict[str, Any], context: SkillContext) -> SkillResult:
        sources = params.get("sources") or context.get("gathered_sources")
        topic = params.get("topic") or "General Comparison"

        from jarvis.subsystems.research.analyzer import SourceComparator
        from jarvis.subsystems.research.harvester import SourceHarvester
        from jarvis.subsystems.research.planner import ResearchPlanner

        comparator = SourceComparator()
        if not sources:
            plan = ResearchPlanner().plan(topic)
            harvested = SourceHarvester().search_and_harvest(plan, max_total_sources=3, open_pages=False)
        else:
            from jarvis.subsystems.research.schemas import SourceItem
            harvested = []
            for i, s in enumerate(sources):
                if isinstance(s, dict):
                    harvested.append(SourceItem(
                        source_id=s.get("source_id", f"src_{i+1}"),
                        url=s.get("url", f"https://source{i+1}.example.com"),
                        title=s.get("title", f"Source {i+1}"),
                        snippet=s.get("snippet", ""),
                        body_text=s.get("body_text", s.get("snippet", "")),
                    ))

        claims = comparator.extract_claims(harvested)
        conflicts = comparator.detect_conflicts(claims)

        context.set("detected_conflicts", [c.to_dict() for c in conflicts])
        return SkillResult(
            success=True,
            output=f"Extracted {len(claims)} claims and detected {len(conflicts)} conflicting statements across {len(harvested)} sources.",
            artifacts={"conflicts_count": len(conflicts), "conflicts": [c.to_dict() for c in conflicts]},
        )


class ResearchSynthesizeReportSkill(BaseSkill):
    name = "research.synthesize_report"
    domain = "research"
    capability = "Synthesizes research notes and cross-checked findings into a formatted markdown report."
    required_tools = ["create_file"]
    parameters = {
        "topic": SkillParameter("topic", "string", "Report title", required=True),
        "output_path": SkillParameter("output_path", "path", "Optional file destination", required=False, default=None),
    }

    def execute(self, params: Dict[str, Any], context: SkillContext) -> SkillResult:
        topic = params["topic"]
        out_path = params.get("output_path") or f"reports/Research_{topic.replace(' ', '_')}.md"

        existing_path = context.get("research_report_path")
        if existing_path and os.path.exists(existing_path) and not params.get("output_path"):
            return SkillResult(
                success=True,
                output=f"Report already synthesized and saved to '{existing_path}'.",
                artifacts={"report_path": existing_path},
            )

        from jarvis.subsystems.research import get_research_agent
        agent = get_research_agent()
        report = agent.run(question_or_topic=topic, output_path=out_path)

        return SkillResult(
            success=True,
            output=f"Report synthesized with {len(report.citations)} citations and saved to '{report.saved_path}'.",
            artifacts={"report_path": report.saved_path, "citations_count": len(report.citations)},
        )
