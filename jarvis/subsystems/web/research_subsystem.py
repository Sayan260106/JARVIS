"""Web Intelligence Research Subsystem for JARVIS.

Maintains Ollama as the central brain while leveraging ChatGPT, Gemini,
and web search harvesters as auxiliary research providers.

Enforces:
Answer A + Answer B + Source Evidence + Question
     ↓
Claim extraction
     ↓
Contradiction detection
     ↓
Evidence comparison
     ↓
Confidence estimation
     ↓
Final synthesis
"""

from __future__ import annotations
from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional

from jarvis.subsystems.local.ollama_client import OllamaClient
from jarvis.subsystems.web.providers import (
    ChatGPTProvider,
    GeminiProvider,
    WebSearchHarvester,
)
from jarvis.subsystems.web.cross_checker import (
    CrossChecker,
    EvidenceComparison,
    Contradiction,
    Claim,
)


@dataclass
class ResearchResult:
    """Structured report returned by the Web Intelligence subsystem."""
    query: str
    chatgpt_answer: str
    gemini_answer: str
    web_evidence: str
    claims: List[Claim] = field(default_factory=list)
    contradictions: List[Contradiction] = field(default_factory=list)
    confidence: float = 0.5
    synthesis_prompt: str = ""
    final_synthesis: str = ""


class WebIntelligenceSubsystem:
    """Coordinates cloud research providers and cross-checking synthesis for JARVIS."""

    # Keywords triggering real-time web intelligence
    LIVE_INFO_KEYWORDS = [
        "weather", "temperature", "forecast", "stock", "price", "news",
        "latest", "current", "today", "score", "match", "recent",
        "who is the current", "who is the prime minister", "who is the president",
        "release date", "exchange rate", "live", "how hot is", "how cold is",
    ]

    # Patterns that belong strictly to local commands or fundamental static concepts
    LOCAL_OR_STATIC_KEYWORDS = [
        "binary search tree", "recursion", "dynamic programming", "data structure",
        "algorithm", "gate exam", "explain gate", "what is o(n)",
        "lock the laptop", "lock pc", "restart", "shutdown",
        "how much ram", "cpu usage", "is ollama running", "open edge",
        "open vs code", "open spotify", "organize downloads", "create a folder",
        "take a screenshot", "move this pdf", "find my dbms notes",
    ]

    def __init__(
        self,
        ollama_client: Optional[OllamaClient] = None,
        chatgpt_provider: Optional[ChatGPTProvider] = None,
        gemini_provider: Optional[GeminiProvider] = None,
        search_harvester: Optional[WebSearchHarvester] = None,
        cross_checker: Optional[CrossChecker] = None,
    ):
        self.ollama = ollama_client or OllamaClient()
        self.chatgpt = chatgpt_provider or ChatGPTProvider()
        self.gemini = gemini_provider or GeminiProvider()
        self.harvester = search_harvester or WebSearchHarvester()
        self.cross_checker = cross_checker or CrossChecker()

    def needs_current_info(self, query: str) -> bool:
        """Determines whether a user query requires real-time web intelligence.

        Decision Tree:
        Need current info?
           /       \\
         NO         YES
         |           |
      Ollama       Browser / Web
        """
        lower = query.lower()

        # Check explicit local or static triggers first
        for kw in self.LOCAL_OR_STATIC_KEYWORDS:
            if kw in lower:
                return False

        # Check real-time or live info triggers
        for kw in self.LIVE_INFO_KEYWORDS:
            if re.search(rf"\b{re.escape(kw)}\b", lower):
                return True

        return False

    def research_and_synthesize(
        self,
        query: str,
        chatgpt_override: Optional[str] = None,
        gemini_override: Optional[str] = None,
        web_override: Optional[str] = None,
    ) -> ResearchResult:
        """Executes the full research, claim extraction, cross-checking, and Ollama synthesis pipeline."""
        # 1. Fetch auxiliary perspectives
        answer_a = chatgpt_override if chatgpt_override is not None else self.chatgpt.query(query)
        answer_b = gemini_override if gemini_override is not None else self.gemini.query(query)

        # 2. Harvest ground-truth web evidence
        if web_override is not None:
            web_evidence = web_override
        else:
            harvested = self.harvester.search(query, max_results=3)
            web_evidence = " | ".join(s["snippet"] for s in harvested) if harvested else "No web snippets available."

        # 3. Claim Extraction
        claims_a = self.cross_checker.extract_claims(answer_a, source_name="ChatGPT")
        claims_b = self.cross_checker.extract_claims(answer_b, source_name="Gemini")
        web_claims = self.cross_checker.extract_claims(web_evidence, source_name="WebSource")

        # 4. Contradiction Detection
        contradictions = self.cross_checker.detect_contradictions(claims_a, claims_b, web_claims)

        # 5. Evidence Comparison & Clustering
        comparison = self.cross_checker.compare_evidence(claims_a, claims_b, web_claims, contradictions)

        # 6. Confidence Estimation
        confidence = comparison.confidence_score

        # 7. Construct synthesis prompt for Ollama
        synthesis_prompt = self.cross_checker.build_synthesis_prompt(
            question=query,
            answer_a=answer_a,
            answer_b=answer_b,
            web_evidence=web_evidence,
            comparison=comparison,
        )

        # 8. Final Synthesis: Query local Ollama brain with deterministic fallback
        final_synthesis = ""
        try:
            ollama_response = self.ollama.chat(
                [{"role": "user", "content": synthesis_prompt}],
                system_prompt="You are JARVIS. Synthesize a concise, authoritative answer based strictly on the provided cross-checked evidence.",
            )
            if ollama_response and not ollama_response.strip().startswith("{"):
                final_synthesis = ollama_response.strip()
        except Exception:
            pass

        # If Ollama is offline or produces raw fallback, use high-fidelity deterministic synthesis
        if not final_synthesis:
            final_synthesis = self.cross_checker.synthesize_direct(query, comparison)

        return ResearchResult(
            query=query,
            chatgpt_answer=answer_a,
            gemini_answer=answer_b,
            web_evidence=web_evidence,
            claims=comparison.all_claims,
            contradictions=contradictions,
            confidence=confidence,
            synthesis_prompt=synthesis_prompt,
            final_synthesis=final_synthesis,
        )
