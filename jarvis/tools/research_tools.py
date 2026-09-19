"""Research Tools for JARVIS (Phase 12).

Provides tool wrappers for deep multi-source research, cross-checking, and report synthesis.
"""

from __future__ import annotations
import time
from typing import Any, Dict, List, Optional

from jarvis.subsystems.research import (
    ResearchAgent,
    ResearchReport,
    get_research_agent,
)
from jarvis.tools.base import (
    BaseTool,
    RiskLevel,
    ToolParameter,
    ToolResult,
    ToolVerification,
)


class DeepResearchTool(BaseTool):
    """Executes an autonomous multi-source research investigation and generates a cited report."""
    name = "deep_research"
    description = (
        "Conducts deep research on a question or topic: searches web, opens pages, extracts claims, "
        "cross-checks for conflicting information, produces a formatted cited report, and saves it locally."
    )
    risk_level = RiskLevel.LOW
    parameters = {
        "topic": ToolParameter("topic", "string", "Question or subject to research in depth.", required=True),
        "output_path": ToolParameter("output_path", "string", "Optional custom destination path for the report markdown.", required=False, default=None),
        "max_sources": ToolParameter("max_sources", "integer", "Maximum independent sources to analyze (default: 5).", required=False, default=5),
    }

    def execute(self, topic: str, output_path: Optional[str] = None, max_sources: int = 5, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        try:
            agent = get_research_agent()
            report: ResearchReport = agent.run(
                question_or_topic=topic,
                output_path=output_path,
                max_sources=int(max_sources),
            )

            output = {
                "topic": report.topic,
                "title": report.title,
                "saved_path": report.saved_path,
                "sources_evaluated": len(report.citations),
                "conflicts_detected": len(report.conflicts),
                "executive_summary": report.executive_summary,
                "citations": [c.to_dict() for c in report.citations],
                "conflicts": [conf.to_dict() for conf in report.conflicts],
                "report_preview": report.full_markdown[:500] + "...",
            }
            return ToolResult(
                success=True,
                output=output,
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e),
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if not result.success:
            return ToolVerification(verified=False, details=f"Deep research failed: {result.error}")
        data = result.output or {}
        return ToolVerification(
            verified=True,
            details=(
                f"Deep research completed for '{data.get('topic')}'. Evaluated {data.get('sources_evaluated')} sources, "
                f"detected {data.get('conflicts_detected')} conflicts, saved to '{data.get('saved_path')}'."
            ),
        )


class CompareSourcesTool(BaseTool):
    """Compares claims across multiple texts or sources to detect divergences and contradictions."""
    name = "compare_sources"
    description = "Compares multi-source evidence and flags numerical discrepancies, timeline differences, or opposing claims."
    risk_level = RiskLevel.LOW
    parameters = {
        "sources": ToolParameter("sources", "list", "List of source dicts (with title, url, snippet/body) or text strings.", required=True),
    }

    def execute(self, sources: List[Any], **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        try:
            from jarvis.subsystems.research.analyzer import SourceComparator
            from jarvis.subsystems.research.schemas import SourceItem
            import uuid

            source_items: List[SourceItem] = []
            for i, src in enumerate(sources):
                if isinstance(src, dict):
                    source_items.append(
                        SourceItem(
                            source_id=src.get("source_id", f"src_{i+1}"),
                            url=src.get("url", f"https://source{i+1}.example.com"),
                            title=src.get("title", f"Source {i+1}"),
                            snippet=src.get("snippet", src.get("body", "")),
                            body_text=src.get("body_text", src.get("body", "")),
                        )
                    )
                elif isinstance(src, str):
                    source_items.append(
                        SourceItem(
                            source_id=f"src_{i+1}",
                            url=f"https://source{i+1}.example.com",
                            title=f"Source {i+1}",
                            snippet=src,
                            body_text=src,
                        )
                    )

            comparator = SourceComparator()
            claims = comparator.extract_claims(source_items)
            conflicts = comparator.detect_conflicts(claims)

            output = {
                "sources_analyzed": len(source_items),
                "claims_extracted": len(claims),
                "conflicts_count": len(conflicts),
                "conflicts": [c.to_dict() for c in conflicts],
            }
            return ToolResult(
                success=True,
                output=output,
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e),
                duration_ms=(time.perf_counter() - start_t) * 1000,
            )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if not result.success:
            return ToolVerification(verified=False, details=f"Source comparison failed: {result.error}")
        return ToolVerification(
            verified=True,
            details=f"Comparison analyzed {result.output.get('sources_analyzed', 0)} sources and detected {result.output.get('conflicts_count', 0)} conflicts."
        )
