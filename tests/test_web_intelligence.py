"""Unit tests for Phase 7 — Web Intelligence Subsystem.

Verifies:
1. Query classification (needs_current_info decision gate).
2. Claim extraction across multiple answer streams.
3. Contradiction detection between divergent perspectives.
4. Evidence comparison and median clustering around ground truth.
5. Exact example reconciliation:
   ChatGPT: 27°C
   Gemini: 29°C
   Web source: 28°C
   JARVIS: "The sources differ slightly. The available measurements cluster around 28°C."
6. ResearchTopicTool integration in the registry.
"""

from __future__ import annotations
import unittest

from jarvis.subsystems.web.cross_checker import (
    Claim,
    Contradiction,
    CrossChecker,
    EvidenceComparison,
)
from jarvis.subsystems.web.research_subsystem import (
    WebIntelligenceSubsystem,
    ResearchResult,
)
from jarvis.tools.web_intelligence_tool import ResearchTopicTool


class TestWebIntelligence(unittest.TestCase):
    """Test suite for research routing, cross-checking, and evidence reconciliation."""

    def setUp(self):
        self.subsystem = WebIntelligenceSubsystem()
        self.checker = CrossChecker()

    def test_needs_current_info_routing_logic(self):
        """Verify routing decision tree:
        Need current info?
           /       \\
         NO         YES
         |           |
      Ollama       Browser / Web
        """
        # Queries needing current/live web information
        self.assertTrue(self.subsystem.needs_current_info("What is the weather in Tokyo right now?"))
        self.assertTrue(self.subsystem.needs_current_info("What is the current temperature in London?"))
        self.assertTrue(self.subsystem.needs_current_info("What's the latest stock price of NVIDIA?"))
        self.assertTrue(self.subsystem.needs_current_info("Give me the latest news on technology today."))
        self.assertTrue(self.subsystem.needs_current_info("Who is the current prime minister of the UK?"))

        # Queries handled by local Ollama / local machine control
        self.assertFalse(self.subsystem.needs_current_info("What is a binary search tree?"))
        self.assertFalse(self.subsystem.needs_current_info("Explain it like I'm preparing for GATE."))
        self.assertFalse(self.subsystem.needs_current_info("Lock the laptop."))
        self.assertFalse(self.subsystem.needs_current_info("How much RAM am I using?"))
        self.assertFalse(self.subsystem.needs_current_info("Organize my Downloads folder."))
        self.assertFalse(self.subsystem.needs_current_info("Is Ollama running?"))

    def test_claim_extraction(self):
        """Verify extracting structured claims and measurements from natural language answers."""
        text_chatgpt = "Temperature = 27°C\nConditions are mostly clear."
        text_gemini = "Current temperature is 29°C with light wind."
        text_web = "Live sensor reading: 28°C."

        claims_a = self.checker.extract_claims(text_chatgpt, "ChatGPT")
        claims_b = self.checker.extract_claims(text_gemini, "Gemini")
        claims_web = self.checker.extract_claims(text_web, "WebSource")

        self.assertTrue(any(c.numeric_value == 27.0 for c in claims_a))
        self.assertTrue(any(c.numeric_value == 29.0 for c in claims_b))
        self.assertTrue(any(c.numeric_value == 28.0 for c in claims_web))

    def test_contradiction_detection(self):
        """Verify conflicting numeric values trigger contradiction records."""
        claim_a = [Claim(source="ChatGPT", subject="temperature", raw_value="27°C", numeric_value=27.0, unit="°C")]
        claim_b = [Claim(source="Gemini", subject="temperature", raw_value="29°C", numeric_value=29.0, unit="°C")]

        contradictions = self.checker.detect_contradictions(claim_a, claim_b)
        self.assertEqual(len(contradictions), 1)
        self.assertEqual(contradictions[0].divergence, 2.0)
        self.assertIn("ChatGPT", contradictions[0].description)
        self.assertIn("Gemini", contradictions[0].description)

    def test_evidence_comparison_and_clustering(self):
        """Verify evidence clustering around the median and ground truth."""
        claims_a = [Claim(source="ChatGPT", subject="temperature", raw_value="27°C", numeric_value=27.0, unit="°C")]
        claims_b = [Claim(source="Gemini", subject="temperature", raw_value="29°C", numeric_value=29.0, unit="°C")]
        claims_web = [Claim(source="WebSource", subject="temperature", raw_value="28°C", numeric_value=28.0, unit="°C")]

        contradictions = self.checker.detect_contradictions(claims_a, claims_b)
        comparison = self.checker.compare_evidence(claims_a, claims_b, claims_web, contradictions)

        self.assertTrue(comparison.has_divergence)
        self.assertEqual(comparison.mean_numeric, 28.0)
        self.assertEqual(comparison.median_numeric, 28.0)
        self.assertGreaterEqual(comparison.confidence_score, 0.85)

    def test_exact_specification_reconciliation_example(self):
        """Verify the exact user scenario:
        ChatGPT: Temperature = 27°C
        Gemini: Temperature = 29°C
        Web source: 28°C
        JARVIS:
        "The sources differ slightly. The available measurements cluster around 28°C."
        """
        chatgpt_ans = "Temperature = 27°C"
        gemini_ans = "Temperature = 29°C"
        web_ans = "28°C"

        result = self.subsystem.research_and_synthesize(
            query="What is the temperature?",
            chatgpt_override=chatgpt_ans,
            gemini_override=gemini_ans,
            web_override=web_ans,
        )

        self.assertTrue("sources differ" in result.final_synthesis.lower())
        self.assertIn("28", result.final_synthesis)
        self.assertIn("cluster", result.final_synthesis)

    def test_research_topic_tool(self):
        """Verify ResearchTopicTool executes and produces structured verification."""
        tool = ResearchTopicTool()
        res = tool.execute(topic="Current temperature in Berlin")
        self.assertTrue(res.success)
        self.assertIn("final_synthesis", res.output)
        self.assertIn("confidence", res.output)

        ver = tool.verify({"topic": "Current temperature in Berlin"}, res)
        self.assertTrue(ver.verified)


if __name__ == "__main__":
    unittest.main()
