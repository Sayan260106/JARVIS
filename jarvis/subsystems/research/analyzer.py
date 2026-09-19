"""Source Analyzer and Conflict Detector for JARVIS Research Agent Subsystem (Phase 12).

Performs claim extraction, source comparison, cross-checking, and conflict detection
across multiple independent sources.
"""

from __future__ import annotations
import re
from typing import Any, Dict, List, Optional, Tuple
import uuid

from jarvis.subsystems.research.schemas import (
    ConflictType,
    DetectedConflict,
    ExtractedClaim,
    SourceItem,
)


class SourceComparator:
    """Extracts claims from harvested sources, performs cross-checks, and identifies contradictions."""

    # Common metrics patterns
    METRIC_PATTERNS = [
        # Latency / Time: 45ms, 120 ms, 2.5s
        (r"(\d+(?:\.\d+)?)\s*(ms|milliseconds|seconds|sec|s|minutes|min)\b", "latency"),
        # Percentages: 35%, 15.5 %
        (r"(\d+(?:\.\d+)?)\s*%", "efficiency_or_ratio"),
        # Timeline / Years: in 2026, by 2028, during 2025
        (r"\b(?:by|in|year|until|target)\s+(202[4-9]|203[0-9])\b", "timeline"),
        # Standalone years in future context: 2026, 2027, 2028
        (r"\b(202[4-9]|203[0-9])\b", "target_year"),
        # Throughput / Speed: 1000 tps, 500 req/s, 10 Gbps
        (r"(\d+(?:\.\d+)?)\s*(tps|gbps|mbps|req/s|ghz)\b", "throughput_or_speed"),
    ]

    # Keyword subject associations
    SUBJECT_KEYWORDS = {
        "latency": ["latency", "delay", "response time", "lag", "rtt"],
        "efficiency": ["efficiency", "performance increase", "improvement", "speedup", "accuracy", "gain"],
        "cost": ["cost", "price", "budget", "expense", "infrastructure"],
        "timeline": ["timeline", "rollout", "adoption", "deployment", "readiness", "availability", "release"],
        "scalability": ["scale", "scaling", "capacity", "limitations", "bottleneck", "nodes"],
    }

    def extract_claims(self, sources: List[SourceItem]) -> List[ExtractedClaim]:
        """Extracts structured atomic claims from each source's text and snippets."""
        all_claims: List[ExtractedClaim] = []

        for src in sources:
            combined_text = f"{src.title}\n{src.snippet}\n{src.body_text}"
            lines = [l.strip() for l in combined_text.splitlines() if l.strip()]
            
            # Extract claims line by line
            for line in lines:
                extracted_for_line = self._extract_claims_from_sentence(line, src)
                all_claims.extend(extracted_for_line)

        return all_claims

    def _extract_claims_from_sentence(self, sentence: str, source: SourceItem) -> List[ExtractedClaim]:
        """Extracts claims from a single sentence or line."""
        claims: List[ExtractedClaim] = []
        lower = sentence.lower()

        # Check for numeric metrics
        for pattern, default_subject in self.METRIC_PATTERNS:
            matches = re.finditer(pattern, sentence, flags=re.IGNORECASE)
            for m in matches:
                val_str = m.group(1)
                unit_str = m.group(2) if m.lastindex >= 2 else None
                try:
                    num_val = float(val_str)
                except ValueError:
                    continue

                # Determine refined subject based on surrounding context
                subject = default_subject
                for subj_key, kw_list in self.SUBJECT_KEYWORDS.items():
                    if any(kw in lower for kw in kw_list):
                        subject = subj_key
                        break

                claim = ExtractedClaim(
                    claim_id=f"claim_{uuid.uuid4().hex[:6]}",
                    source_id=source.source_id,
                    source_title=source.title,
                    source_url=source.url,
                    subject=subject,
                    assertion=sentence,
                    numeric_value=num_val,
                    unit=unit_str,
                    raw_text=sentence,
                )
                claims.append(claim)

        # Check for qualitative key-assertion sentences (e.g. bottlenecks, disputes, feasibility)
        qualitative_triggers = ["bottleneck", "dispute", "proves", "demonstrates", "fails to", "confirmed", "discredited"]
        if any(trig in lower for trig in qualitative_triggers):
            claims.append(
                ExtractedClaim(
                    claim_id=f"claim_{uuid.uuid4().hex[:6]}",
                    source_id=source.source_id,
                    source_title=source.title,
                    source_url=source.url,
                    subject="qualitative_assessment",
                    assertion=sentence,
                    numeric_value=None,
                    unit=None,
                    raw_text=sentence,
                )
            )

        return claims

    def detect_conflicts(self, claims: List[ExtractedClaim]) -> List[DetectedConflict]:
        """Cross-checks claims by subject across different sources to find conflicting information."""
        conflicts: List[DetectedConflict] = []
        claims_by_subject: Dict[str, List[ExtractedClaim]] = {}

        for c in claims:
            claims_by_subject.setdefault(c.subject, []).append(c)

        for subject, subject_claims in claims_by_subject.items():
            # Compare pairwise between different sources
            for i in range(len(subject_claims)):
                for j in range(i + 1, len(subject_claims)):
                    c1 = subject_claims[i]
                    c2 = subject_claims[j]

                    if c1.source_url == c2.source_url or c1.source_id == c2.source_id:
                        continue  # Do not cross-check within the exact same source

                    conflict = self._compare_claim_pair(c1, c2)
                    if conflict:
                        # Avoid duplicates
                        if not any(
                            existing.subject == conflict.subject
                            and existing.source_a_url == conflict.source_a_url
                            and existing.source_b_url == conflict.source_b_url
                            for existing in conflicts
                        ):
                            conflicts.append(conflict)

        return conflicts

    def _compare_claim_pair(self, c1: ExtractedClaim, c2: ExtractedClaim) -> Optional[DetectedConflict]:
        """Compares two claims on the same subject to detect divergences or contradictions."""
        # 1. Timeline / Year divergence
        if c1.subject in ("timeline", "target_year") and c2.subject in ("timeline", "target_year"):
            if c1.numeric_value and c2.numeric_value and c1.numeric_value != c2.numeric_value:
                diff_years = abs(c1.numeric_value - c2.numeric_value)
                if diff_years >= 1.0:
                    return DetectedConflict(
                        subject="Projected Timeline",
                        source_a_title=c1.source_title,
                        source_a_url=c1.source_url,
                        claim_a=f"{int(c1.numeric_value)} ({c1.assertion[:80]}...)",
                        source_b_title=c2.source_title,
                        source_b_url=c2.source_url,
                        claim_b=f"{int(c2.numeric_value)} ({c2.assertion[:80]}...)",
                        conflict_type=ConflictType.DATE_TIMELINE,
                        divergence=diff_years,
                        explanation=f"Discrepancy of {int(diff_years)} year(s) between projected milestones.",
                    )

        # 2. Quantitative / Metric divergence
        if c1.numeric_value is not None and c2.numeric_value is not None:
            v1, v2 = c1.numeric_value, c2.numeric_value
            denom = max(abs(v1), abs(v2), 1.0)
            rel_divergence = abs(v1 - v2) / denom

            # If divergence > 25% for same metric category
            if rel_divergence > 0.25:
                return DetectedConflict(
                    subject=c1.subject.replace("_", " ").title(),
                    source_a_title=c1.source_title,
                    source_a_url=c1.source_url,
                    claim_a=f"{v1}{c1.unit or ''} — {c1.assertion[:70]}...",
                    source_b_title=c2.source_title,
                    source_b_url=c2.source_url,
                    claim_b=f"{v2}{c2.unit or ''} — {c2.assertion[:70]}...",
                    conflict_type=ConflictType.NUMERIC_DIVERGENCE,
                    divergence=round(rel_divergence * 100, 1),
                    explanation=(
                        f"Significant divergence ({round(rel_divergence * 100, 1)}%) "
                        f"between {c1.source_title} ({v1}{c1.unit or ''}) "
                        f"and {c2.source_title} ({v2}{c2.unit or ''})."
                    ),
                )

        # 3. Qualitative polarity conflict (e.g. one says 'disputes' / 'fails', the other 'breakthrough' / 'confirms')
        t1_low = c1.assertion.lower()
        t2_low = c2.assertion.lower()
        negative_signals = ["dispute", "fail", "doubt", "limitation", "bottleneck", "prohibitive"]
        positive_signals = ["breakthrough", "demonstrate", "confirm", "increase", "milestone", "success"]

        has_neg_1 = any(s in t1_low for s in negative_signals)
        has_pos_1 = any(s in t1_low for s in positive_signals)
        has_neg_2 = any(s in t2_low for s in negative_signals)
        has_pos_2 = any(s in t2_low for s in positive_signals)

        if (has_pos_1 and has_neg_2) or (has_neg_1 and has_pos_2):
            return DetectedConflict(
                subject="Feasibility & Assessment",
                source_a_title=c1.source_title,
                source_a_url=c1.source_url,
                claim_a=c1.assertion[:90] + "...",
                source_b_title=c2.source_title,
                source_b_url=c2.source_url,
                claim_b=c2.assertion[:90] + "...",
                conflict_type=ConflictType.FACTUAL_POLARITY,
                divergence=None,
                explanation="Contrasting analytical stance: optimistic benchmark validation vs critical feasibility concerns.",
            )

        return None
