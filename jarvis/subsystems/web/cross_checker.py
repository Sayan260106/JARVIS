"""Cross-Checker & Evidence Reconciliation Engine for Web Intelligence.

Implements the multi-stage pipeline:
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
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class Claim:
    """An individual atomic claim extracted from a source."""
    source: str
    subject: str
    raw_value: str
    numeric_value: Optional[float] = None
    unit: Optional[str] = None
    original_text: str = ""


@dataclass
class Contradiction:
    """A detected conflict between two or more claims."""
    subject: str
    source_a: str
    value_a: str
    source_b: str
    value_b: str
    divergence: Optional[float] = None
    description: str = ""


@dataclass
class EvidenceComparison:
    """Aggregated evidence matrix comparing claims and web corroboration."""
    subject: str
    all_claims: List[Claim] = field(default_factory=list)
    contradictions: List[Contradiction] = field(default_factory=list)
    has_divergence: bool = False
    mean_numeric: Optional[float] = None
    median_numeric: Optional[float] = None
    unit: Optional[str] = None
    corroborating_source: Optional[str] = None
    confidence_score: float = 0.5


class CrossChecker:
    """Extracts claims, flags contradictions, and compares evidence."""

    # Regex patterns for values (temperatures, percentages, numbers, currencies)
    NUMERIC_PATTERNS = [
        # Temperatures: 27°C, 27 °C, 27 C, 27 degrees
        r"(-?\d+(?:\.\d+)?)\s*(?:°\s*[CF]|deg(?:rees)?(?:\s*[CF])?|°)",
        # Percentages: 85%
        r"(\d+(?:\.\d+)?)\s*%",
        # Currencies: $100, €50
        r"[\$€£¥]\s*(\d+(?:\.\d+)?)",
        # Generic standalone numbers with context
        r"\b(-?\d+(?:\.\d+)?)\b",
    ]

    def extract_claims(self, text: str, source_name: str) -> List[Claim]:
        """Extracts structured claims and numerical measurements from a source's response."""
        claims = []
        lines = [l.strip() for l in text.splitlines() if l.strip()]

        for line in lines:
            # 1. Temperature detection (e.g. 27°C, 29°C, 28°C)
            temp_match = re.search(r"(-?\d+(?:\.\d+)?)\s*(?:°\s*C|deg(?:rees)?\s*C|°)", line, re.IGNORECASE)
            if temp_match:
                val = float(temp_match.group(1))
                claims.append(Claim(
                    source=source_name,
                    subject="temperature",
                    raw_value=f"{val:g}°C",
                    numeric_value=val,
                    unit="°C",
                    original_text=line,
                ))
                continue

            # 2. Key-value assignment (e.g. "Temperature = 27°C" or "Speed: 100 km/h")
            kv_match = re.search(r"([A-Za-z0-9_\s]+)\s*[:=]\s*([^\n\r,]+)", line)
            if kv_match:
                subj = kv_match.group(1).strip().lower()
                val_str = kv_match.group(2).strip()

                # Extract number if present
                num = None
                num_match = re.search(r"(-?\d+(?:\.\d+)?)", val_str)
                if num_match:
                    try:
                        num = float(num_match.group(1))
                    except ValueError:
                        pass

                claims.append(Claim(
                    source=source_name,
                    subject=subj,
                    raw_value=val_str,
                    numeric_value=num,
                    original_text=line,
                ))
                continue

            # 3. Direct number with context
            for pat in self.NUMERIC_PATTERNS:
                m = re.search(pat, line)
                if m:
                    try:
                        val = float(m.group(1))
                        claims.append(Claim(
                            source=source_name,
                            subject="measurement",
                            raw_value=str(val),
                            numeric_value=val,
                            original_text=line,
                        ))
                        break
                    except ValueError:
                        pass

        # If no specific regex matched, record top-level textual claim
        if not claims and text.strip():
            claims.append(Claim(
                source=source_name,
                subject="statement",
                raw_value=text.strip()[:120],
                original_text=text.strip(),
            ))

        return claims

    def detect_contradictions(
        self,
        claims_a: List[Claim],
        claims_b: List[Claim],
        web_claims: Optional[List[Claim]] = None,
    ) -> List[Contradiction]:
        """Compares claims across sources to detect conflicting values or stances."""
        contradictions = []
        all_web = web_claims or []

        for ca in claims_a:
            for cb in claims_b:
                # Same subject or both numerical measurements
                if ca.subject == cb.subject or (ca.numeric_value is not None and cb.numeric_value is not None):
                    if ca.numeric_value is not None and cb.numeric_value is not None:
                        diff = abs(ca.numeric_value - cb.numeric_value)
                        if diff > 0.001:
                            contradictions.append(Contradiction(
                                subject=ca.subject,
                                source_a=ca.source,
                                value_a=ca.raw_value,
                                source_b=cb.source,
                                value_b=cb.raw_value,
                                divergence=diff,
                                description=f"{ca.source} reported {ca.raw_value} while {cb.source} reported {cb.raw_value} (divergence of {diff:g}).",
                            ))
                    elif ca.raw_value.lower() != cb.raw_value.lower():
                        contradictions.append(Contradiction(
                            subject=ca.subject,
                            source_a=ca.source,
                            value_a=ca.raw_value,
                            source_b=cb.source,
                            value_b=cb.raw_value,
                            description=f"{ca.source} states '{ca.raw_value}' but {cb.source} states '{cb.raw_value}'.",
                        ))

        return contradictions

    def compare_evidence(
        self,
        claims_a: List[Claim],
        claims_b: List[Claim],
        web_claims: List[Claim],
        contradictions: List[Contradiction],
    ) -> EvidenceComparison:
        """Aggregates all claims and clusters measurements around ground truth."""
        all_claims = claims_a + claims_b + web_claims
        numeric_vals = [c.numeric_value for c in all_claims if c.numeric_value is not None]

        unit = None
        for c in all_claims:
            if c.unit:
                unit = c.unit
                break

        has_div = len(contradictions) > 0
        mean_val = None
        median_val = None

        if numeric_vals:
            mean_val = round(sum(numeric_vals) / len(numeric_vals), 1)
            sorted_v = sorted(numeric_vals)
            median_val = sorted_v[len(sorted_v) // 2]

        subj = all_claims[0].subject if all_claims else "general"

        # Estimate confidence
        # High confidence if web evidence corroborates or numeric values are closely clustered
        confidence = self.estimate_confidence(contradictions, numeric_vals, bool(web_claims))

        return EvidenceComparison(
            subject=subj,
            all_claims=all_claims,
            contradictions=contradictions,
            has_divergence=has_div,
            mean_numeric=mean_val,
            median_numeric=median_val,
            unit=unit,
            confidence_score=confidence,
        )

    def estimate_confidence(
        self,
        contradictions: List[Contradiction],
        numeric_values: List[float],
        has_web_evidence: bool,
    ) -> float:
        """Computes statistical confidence score in range [0.1, 0.98]."""
        base_confidence = 0.85 if has_web_evidence else 0.70

        if not contradictions:
            return min(0.98, base_confidence + 0.10)

        # Check spread / variance
        if numeric_values and len(numeric_values) >= 2:
            spread = max(numeric_values) - min(numeric_values)
            if spread <= 2.0:
                # Tight cluster (e.g. 27, 28, 29) -> high confidence in cluster center
                return 0.90
            elif spread <= 5.0:
                return 0.75
            else:
                return 0.50

        return 0.60

    def build_synthesis_prompt(
        self,
        question: str,
        answer_a: str,
        answer_b: str,
        web_evidence: str,
        comparison: EvidenceComparison,
    ) -> str:
        """Constructs the structured reasoning prompt for local Ollama."""
        lines = [
            "You are JARVIS's central synthesis engine.",
            "Synthesize an accurate, unified answer to the user's question using the cross-checked multi-source research below.",
            "",
            f"QUESTION: {question}",
            "",
            "SOURCES REVIEWED:",
            f"- ChatGPT Perspective: {answer_a}",
            f"- Gemini Perspective: {answer_b}",
            f"- Primary Web Source: {web_evidence}",
            "",
            "CROSS-CHECK ANALYSIS:",
        ]

        if comparison.has_divergence:
            lines.append("- Divergence Detected: The sources differ slightly in reported values.")
            for c in comparison.contradictions:
                lines.append(f"  * {c.description}")
            if comparison.median_numeric is not None:
                unit_str = comparison.unit or ""
                lines.append(f"- Cluster Center: Available measurements cluster around {comparison.median_numeric:g}{unit_str}.")
        else:
            lines.append("- Consensus: Sources are in substantial agreement.")

        lines.extend([
            f"- Confidence Score: {comparison.confidence_score:.2f}",
            "",
            "INSTRUCTIONS FOR SYNTHESIS:",
            "1. Do NOT pick one source arbitrarily.",
            "2. If sources differ slightly, state exactly: 'The sources differ slightly. The available measurements cluster around <cluster_center>.'",
            "3. Provide a direct, authoritative, and concise final response.",
        ])

        return "\n".join(lines)

    def synthesize_direct(
        self,
        question: str,
        comparison: EvidenceComparison,
    ) -> str:
        """Deterministic synthesis generator matching JARVIS specification."""
        if comparison.has_divergence and comparison.median_numeric is not None:
            unit_str = comparison.unit or ""
            med = comparison.median_numeric
            # Format nicely as int if whole number
            med_str = f"{int(med)}" if med == int(med) else f"{med:g}"
            return f"The sources differ slightly. The available measurements cluster around {med_str}{unit_str}."

        if comparison.all_claims:
            top_val = comparison.all_claims[0].raw_value
            return f"The available sources indicate that {comparison.subject} is {top_val}."

        return "The available research indicates general consensus across web sources."
