"""Comprehensive Test Suite for Phase 12: Research Agent.

Validates the complete research pipeline:
Question -> Research Planner -> Search -> Multiple Sources -> Extract -> Cross-check -> Summarize -> Citations -> Report
and ensures proper tool, skill, and capability integration.
"""

from __future__ import annotations
import os
import shutil
import unittest
from unittest.mock import MagicMock, patch

from jarvis.capabilities.plan import DefaultPlanCapability
from jarvis.capabilities.understand import DefaultUnderstandCapability
from jarvis.core.schemas import IntentCategory, SubsystemType
from jarvis.core.state import AgentSessionState
from jarvis.skills import get_default_skill_registry
from jarvis.skills.base import SkillContext
from jarvis.subsystems.research.agent import ResearchAgent
from jarvis.subsystems.research.analyzer import SourceComparator
from jarvis.subsystems.research.harvester import SourceHarvester
from jarvis.subsystems.research.planner import ResearchPlanner
from jarvis.subsystems.research.schemas import (
    ConflictType,
    DetectedConflict,
    ExtractedClaim,
    ResearchPlan,
    ResearchReport,
    SourceItem,
)
from jarvis.subsystems.research.synthesizer import ReportSynthesizer
from jarvis.tools import get_default_registry


class TestResearchAgentPipeline(unittest.TestCase):
    """Unit and integration tests for Research Agent components."""

    def setUp(self):
        self.test_reports_dir = os.path.join("tests", "temp_reports")
        os.makedirs(self.test_reports_dir, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.test_reports_dir):
            shutil.rmtree(self.test_reports_dir, ignore_errors=True)

    # ----------------------------------------------------------------------
    # 1. Research Planner
    # ----------------------------------------------------------------------
    def test_planner_topic_extraction_and_decomposition(self):
        planner = ResearchPlanner()
        query = "Research the latest developments in Quantum Computing and make me a report."
        core_topic = planner.extract_core_topic(query)
        self.assertEqual(core_topic, "Quantum Computing")

        plan = planner.plan(query)
        self.assertIsInstance(plan, ResearchPlan)
        self.assertEqual(plan.core_topic, "Quantum Computing")
        self.assertGreaterEqual(len(plan.sub_queries), 4)
        self.assertGreaterEqual(len(plan.angles), 4)
        self.assertIn("Executive Summary", plan.target_sections)
        self.assertTrue(any("fundamentals" in q for q in plan.sub_queries))
        self.assertTrue(any("breakthroughs" in q for q in plan.sub_queries))

    # ----------------------------------------------------------------------
    # 2. Source Harvester & HTML Text Extraction
    # ----------------------------------------------------------------------
    def test_harvester_html_extraction(self):
        harvester = SourceHarvester()
        raw_html = """
        <!DOCTYPE html>
        <html>
        <head><title>Quantum Milestones</title><style>.hidden { display: none; }</style></head>
        <body>
            <header><nav><a href="/">Home</a></nav></header>
            <h1>Quantum Breakthrough 2026</h1>
            <p>Researchers observed a <strong>35%</strong> speedup in quantum error correction.</p>
            <script>console.log("tracking code");</script>
            <div>System latency clocked at 45ms under continuous operation.</div>
            <footer>Copyright 2026</footer>
        </body>
        </html>
        """
        extracted = harvester.extract_text_from_html(raw_html)
        self.assertIn("Quantum Breakthrough 2026", extracted)
        self.assertIn("35%", extracted)
        self.assertIn("45ms", extracted)
        self.assertNotIn("console.log", extracted)
        self.assertNotIn(".hidden", extracted)
        self.assertNotIn("Copyright", extracted)

    def test_harvester_fallback_sources(self):
        harvester = SourceHarvester()
        plan = ResearchPlanner().plan("Solid State Batteries")
        sources = harvester.search_and_harvest(plan, max_total_sources=3, open_pages=False)
        self.assertGreaterEqual(len(sources), 2)
        for s in sources:
            self.assertIsInstance(s, SourceItem)
            self.assertTrue(s.url.startswith("http"))
            self.assertGreater(len(s.snippet), 10)

    # ----------------------------------------------------------------------
    # 3. Source Comparator & Conflict Detection
    # ----------------------------------------------------------------------
    def test_comparator_claim_extraction_and_conflict_detection(self):
        src1 = SourceItem(
            source_id="src_1",
            url="https://source-a.org/paper",
            title="Lab Alpha Benchmark",
            snippet="Our quantum processor reached a 35% efficiency improvement with 45ms response time.",
            body_text="Laboratory Alpha demonstrated 35% efficiency and 45ms latency. Commercial launch scheduled for 2026.",
        )
        src2 = SourceItem(
            source_id="src_2",
            url="https://source-b.com/audit",
            title="Independent Beta Audit",
            snippet="Audits dispute the claims, measuring only 15% efficiency and 120ms latency.",
            body_text="Audits observed 15% efficiency and 120ms latency. Target rollout revised to 2028 due to bottlenecks.",
        )

        comparator = SourceComparator()
        claims = comparator.extract_claims([src1, src2])
        self.assertGreaterEqual(len(claims), 4)

        conflicts = comparator.detect_conflicts(claims)
        self.assertGreaterEqual(len(conflicts), 1)

        # Check for numeric or timeline conflict
        conflict_types = [c.conflict_type for c in conflicts]
        self.assertTrue(
            ConflictType.NUMERIC_DIVERGENCE in conflict_types
            or ConflictType.DATE_TIMELINE in conflict_types
            or ConflictType.FACTUAL_POLARITY in conflict_types
        )

        # Validate conflict structure
        first_conf = conflicts[0]
        self.assertIsInstance(first_conf, DetectedConflict)
        self.assertNotEqual(first_conf.source_a_url, first_conf.source_b_url)
        self.assertGreater(len(first_conf.explanation), 5)

    # ----------------------------------------------------------------------
    # 4. Report Synthesizer & Citations
    # ----------------------------------------------------------------------
    def test_report_synthesizer_structure(self):
        plan = ResearchPlanner().plan("Neuromorphic Computing")
        src1 = SourceItem(
            source_id="s1",
            url="https://neuro-tech.org/spec",
            title="Neuromorphic Architecture Spec",
            snippet="Energy consumption dropped by 40% using spike-timing plasticity.",
            body_text="Energy consumption dropped by 40%. Full deployment slated for 2026.",
        )
        src2 = SourceItem(
            source_id="s2",
            url="https://chip-analyst.com/review",
            title="Neuromorphic Reality Check",
            snippet="Independent benchmarks recorded only 10% energy reduction.",
            body_text="Independent benchmarks recorded only 10% energy reduction. Deployment delayed to 2029.",
        )

        comparator = SourceComparator()
        claims = comparator.extract_claims([src1, src2])
        conflicts = comparator.detect_conflicts(claims)

        synthesizer = ReportSynthesizer()
        report = synthesizer.synthesize(plan, [src1, src2], claims, conflicts)

        self.assertIsInstance(report, ResearchReport)
        self.assertIn("Neuromorphic Computing", report.title)
        self.assertIn("Executive Summary", report.full_markdown)
        self.assertIn("References & Citations", report.full_markdown)
        self.assertIn("[^1]", report.full_markdown)
        self.assertIn("[^2]", report.full_markdown)
        self.assertEqual(len(report.citations), 2)
        self.assertIn(src1.url, report.full_markdown)
        self.assertIn(src2.url, report.full_markdown)

    # ----------------------------------------------------------------------
    # 5. Master ResearchAgent End-to-End Execution
    # ----------------------------------------------------------------------
    def test_research_agent_run_and_save_local_report(self):
        agent = ResearchAgent(default_output_dir=self.test_reports_dir)
        topic_query = "Research the latest developments in Fusion Energy and make me a report."
        report = agent.run(topic_query, open_pages=False)

        self.assertIsInstance(report, ResearchReport)
        self.assertEqual(report.topic, "Fusion Energy")
        self.assertIsNotNone(report.saved_path)
        self.assertTrue(os.path.exists(report.saved_path))
        self.assertTrue(report.saved_path.endswith(".md"))

        with open(report.saved_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("# Autonomous Research Report: Fusion Energy", content)
        self.assertIn("## Executive Summary", content)
        self.assertIn("## References & Citations", content)
        self.assertIn("Conflict", content)

    # ----------------------------------------------------------------------
    # 6. Deep Research & Compare Sources Tools
    # ----------------------------------------------------------------------
    def test_tools_deep_research_and_compare_sources(self):
        registry = get_default_registry()
        deep_res_tool = registry.get("deep_research")
        compare_tool = registry.get("compare_sources")

        self.assertIsNotNone(deep_res_tool)
        self.assertIsNotNone(compare_tool)

        # Execute DeepResearchTool
        custom_report_path = os.path.join(self.test_reports_dir, "Custom_Report.md")
        res1 = deep_res_tool.execute(topic="Autonomous Driving L4", output_path=custom_report_path, max_sources=3)
        self.assertTrue(res1.success)
        self.assertTrue(os.path.exists(custom_report_path))
        self.assertIn("executive_summary", res1.output)
        self.assertGreaterEqual(res1.output["sources_evaluated"], 1)

        # Execute CompareSourcesTool
        sources = [
            {"title": "Source Alpha", "url": "https://a.com", "snippet": "System throughput reaches 1000 tps in 2026."},
            {"title": "Source Beta", "url": "https://b.com", "snippet": "System throughput limited to 200 tps until 2029."},
        ]
        res2 = compare_tool.execute(sources=sources)
        self.assertTrue(res2.success)
        self.assertEqual(res2.output["sources_analyzed"], 2)
        self.assertGreaterEqual(res2.output["claims_extracted"], 2)
        self.assertGreaterEqual(res2.output["conflicts_count"], 1)

    # ----------------------------------------------------------------------
    # 7. Research Domain Skills
    # ----------------------------------------------------------------------
    def test_research_domain_skills(self):
        skill_reg = get_default_skill_registry()
        skill_topic = skill_reg.get("research.topic")
        skill_gather = skill_reg.get("research.gather_sources")
        skill_compare = skill_reg.get("research.compare_sources")
        skill_synth = skill_reg.get("research.synthesize_report")

        self.assertIsNotNone(skill_topic)
        self.assertIsNotNone(skill_gather)
        self.assertIsNotNone(skill_compare)
        self.assertIsNotNone(skill_synth)

        ctx = SkillContext()

        # Execute research.gather_sources
        res_gather = skill_gather.execute({"topic": "Carbon Nanotubes"}, ctx)
        self.assertTrue(res_gather.success)
        self.assertIsNotNone(ctx.get("gathered_sources"))

        # Execute research.compare_sources
        res_comp = skill_compare.execute({"topic": "Carbon Nanotubes"}, ctx)
        self.assertTrue(res_comp.success)
        self.assertIsNotNone(ctx.get("detected_conflicts"))

        # Execute research.synthesize_report
        out_report = os.path.join(self.test_reports_dir, "Nanotubes_Report.md")
        res_synth = skill_synth.execute({"topic": "Carbon Nanotubes", "output_path": out_report}, ctx)
        self.assertTrue(res_synth.success)
        self.assertTrue(os.path.exists(out_report))

    # ----------------------------------------------------------------------
    # 8. Understand & Plan Capability Integration
    # ----------------------------------------------------------------------
    def test_understand_and_plan_research_query(self):
        understand = DefaultUnderstandCapability()
        query = "Research the latest developments in Room-Temperature Superconductors and make me a report."
        objective = understand.understand(query, context={})

        self.assertEqual(objective.intent, IntentCategory.RESEARCH)
        self.assertEqual(objective.extracted_entities.get("action"), "deep_research")
        self.assertEqual(objective.extracted_entities.get("topic"), "Room-Temperature Superconductors")
        self.assertGreaterEqual(len(objective.sub_goals), 5)

        planner = DefaultPlanCapability()
        state = AgentSessionState(task_id="task_res_1")
        plan = planner.plan(objective, state)


        self.assertIsNotNone(plan)
        self.assertGreaterEqual(len(plan.steps), 1)
        self.assertEqual(plan.steps[0].tool_name, "deep_research")
        self.assertEqual(plan.steps[0].subsystem, SubsystemType.WEB)
        self.assertEqual(plan.steps[0].arguments["topic"], "Room-Temperature Superconductors")


if __name__ == "__main__":
    unittest.main()
