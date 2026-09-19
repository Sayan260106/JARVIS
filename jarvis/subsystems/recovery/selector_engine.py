"""Alternate Selector Engine for Autonomous Recovery 2.0 (Phase 14).

Computes alternate locators, acronym expansions, semantic course mappings,
and in-page search fallback queries when target elements fail to be found.
"""

from __future__ import annotations
import re
from typing import Dict, List, Optional

from jarvis.subsystems.recovery.schemas import AlternateSelector


class AlternateSelectorEngine:
    """Generates structural, semantic, and fuzzy alternate selectors."""

    ACRONYM_DICTIONARY: Dict[str, List[str]] = {
        "ece": [
            "Electronics and Communication Engineering",
            "Electronics and Communication",
            "Electronics & Communication",
            "Electronics...",
            "Electronics",
        ],
        "cse": [
            "Computer Science and Engineering",
            "Computer Science",
            "Computer Science & Engineering",
            "CS...",
            "Computer...",
        ],
        "ee": [
            "Electrical Engineering",
            "Electrical & Electronics",
            "Electrical...",
        ],
        "eee": [
            "Electrical and Electronics Engineering",
            "Electrical & Electronics",
        ],
        "mech": [
            "Mechanical Engineering",
            "Mechanical...",
        ],
        "it": [
            "Information Technology",
            "Info Tech",
        ],
        "ai": [
            "Artificial Intelligence",
            "AI and Machine Learning",
        ],
        "ml": [
            "Machine Learning",
            "Machine Learning Specialization",
        ],
    }

    def generate_alternates(self, original_target: str) -> List[AlternateSelector]:
        """Generates a ranked list of alternate selectors and search queries."""
        alternates: List[AlternateSelector] = []
        clean = original_target.strip().strip("'\"")
        lower = clean.lower()

        # 1. Acronym & Semantic Expansion (e.g. "ECE" -> "Electronics and Communication Engineering", "Electronics...")
        if lower in self.ACRONYM_DICTIONARY:
            expansions = self.ACRONYM_DICTIONARY[lower]
            for exp in expansions:
                alternates.append(
                    AlternateSelector(
                        selector_type="acronym_expansion",
                        value=exp,
                        confidence=0.95,
                        description=f"Semantic acronym expansion for '{clean}' -> '{exp}'",
                    )
                )

        # Reverse check: if target is full name, generate acronym
        for acr, full_names in self.ACRONYM_DICTIONARY.items():
            if any(lower in fn.lower() for fn in full_names):
                alternates.append(
                    AlternateSelector(
                        selector_type="acronym_contraction",
                        value=acr.upper(),
                        confidence=0.85,
                        description=f"Acronym contraction for '{clean}' -> '{acr.upper()}'",
                    )
                )

        # 2. Structural Role & ARIA Locators
        alternates.append(
            AlternateSelector(
                selector_type="aria",
                value=f"[aria-label*='{clean}' i]",
                confidence=0.88,
                description=f"Case-insensitive ARIA label containing '{clean}'",
            )
        )
        alternates.append(
            AlternateSelector(
                selector_type="css",
                value=f"button:has-text('{clean}'), a:has-text('{clean}')",
                confidence=0.85,
                description=f"Interactive elements containing text '{clean}'",
            )
        )

        # 3. Fuzzy & Truncation Patterns (e.g. "Electronics...")
        if len(clean) > 3:
            first_word = clean.split()[0]
            alternates.append(
                AlternateSelector(
                    selector_type="fuzzy_text",
                    value=f"{first_word}...",
                    confidence=0.80,
                    description=f"Truncated display pattern: '{first_word}...'",
                )
            )

        # 4. In-Page Search Fallback
        # When element isn't directly visible, fallback to searching for it in the search input
        search_query = expansions[0] if (lower in self.ACRONYM_DICTIONARY and expansions) else clean
        alternates.append(
            AlternateSelector(
                selector_type="in_page_search",
                value=search_query,
                confidence=0.75,
                description=f"Execute in-page course/content search for '{search_query}'",
            )
        )

        return alternates

    def get_best_alternate(self, original_target: str) -> Optional[AlternateSelector]:
        """Selects the highest confidence alternate selector."""
        alternates = self.generate_alternates(original_target)
        return alternates[0] if alternates else None
