"""Web Intelligence Tool for JARVIS.

Exposes multi-source cross-checked research to the tool registry.
"""

from __future__ import annotations
import time
from typing import Any, Dict, Optional

from jarvis.tools.base import BaseTool, RiskLevel, ToolParameter, ToolResult, ToolVerification


class ResearchTopicTool(BaseTool):
    """Researches a topic across ChatGPT, Gemini, and web sources with cross-checking."""
    name = "research_topic"
    description = "Researches a real-time topic or query across multiple cloud sources and web ground-truth, cross-checking claims and reconciling contradictions."
    risk_level = RiskLevel.LOW
    parameters = {
        "topic": ToolParameter("topic", "string", "Topic or question to research.", required=True),
    }

    def execute(self, topic: str, **kwargs) -> ToolResult:
        start_t = time.perf_counter()
        try:
            from jarvis.subsystems.web.research_subsystem import WebIntelligenceSubsystem
            subsystem = WebIntelligenceSubsystem()
            result = subsystem.research_and_synthesize(topic.strip())

            output = {
                "topic": topic,
                "final_synthesis": result.final_synthesis,
                "confidence": result.confidence,
                "contradictions_found": len(result.contradictions),
                "chatgpt_perspective": result.chatgpt_answer[:300],
                "gemini_perspective": result.gemini_answer[:300],
                "web_evidence_snippet": result.web_evidence[:300],
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
            return ToolVerification(verified=False, details=f"Research failed: {result.error}")
        return ToolVerification(
            verified=True,
            details=f"Cross-checked research completed with confidence {result.output.get('confidence', 0):.2f}."
        )
