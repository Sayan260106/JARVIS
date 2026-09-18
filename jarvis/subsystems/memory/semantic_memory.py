"""Long-Term Semantic Memory for JARVIS.

Stores facts and preferences that JARVIS is explicitly allowed to remember:
- Preferred browser (e.g. Chrome)
- Preferred editor (e.g. VS Code)
- Default project directory
- User-permitted settings & guidelines
"""

from __future__ import annotations
from contextlib import contextmanager
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional

from jarvis.subsystems.memory.schemas import SemanticPreference
from jarvis.subsystems.memory.vector_store import SQLiteVectorStore


DEFAULT_PREFERENCES: Dict[str, Dict[str, str]] = {
    "preferred_browser": {"value": "Chrome", "category": "browser", "context": "Default web browser for navigation and Google Classroom"},
    "preferred_editor": {"value": "VS Code", "category": "editor", "context": "Default editor for source code and projects"},
    "default_project_dir": {"value": "d:/JARVIS", "category": "filesystem", "context": "Primary workspace root directory"},
    "academic_profile": {"value": "institutional", "category": "academic", "context": "Default profile for academic and college services"},
}


class SemanticMemory:
    """Manages explicit user preferences, allowed system settings, and long-term facts."""

    def __init__(self, db_path: str = "data/jarvis_memory.db", vector_store: Optional[SQLiteVectorStore] = None):
        self.db_path = db_path
        self.vector_store = vector_store or SQLiteVectorStore(db_path=db_path)
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._init_db()
        self._seed_defaults()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self):
        """Creates semantic_preferences table if it does not exist."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS semantic_preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    category TEXT NOT NULL,
                    is_explicit INTEGER NOT NULL DEFAULT 1,
                    context TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            conn.commit()

    def _seed_defaults(self):
        """Pre-seeds standard user preferences if not already configured."""
        now = time.time()
        with self._get_connection() as conn:
            for key, data in DEFAULT_PREFERENCES.items():
                conn.execute("""
                    INSERT OR IGNORE INTO semantic_preferences (
                        key, value, category, is_explicit, context, created_at, updated_at
                    )
                    VALUES (?, ?, ?, 1, ?, ?, ?)
                """, (
                    key,
                    data["value"],
                    data["category"],
                    data["context"],
                    now,
                    now,
                ))
            conn.commit()

    def remember_preference(
        self,
        key: str,
        value: str,
        category: str = "general",
        context: Optional[str] = None,
        is_explicit: bool = True,
    ) -> SemanticPreference:
        """Stores or updates an explicit user preference."""
        clean_key = key.strip().lower().replace(" ", "_")
        now = time.time()

        pref = SemanticPreference(
            key=clean_key,
            value=value.strip(),
            category=category,
            is_explicit=is_explicit,
            context=context,
            created_at=now,
            updated_at=now,
        )

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO semantic_preferences (
                    key, value, category, is_explicit, context, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    category = excluded.category,
                    is_explicit = excluded.is_explicit,
                    context = excluded.context,
                    updated_at = excluded.updated_at
            """, (
                pref.key,
                pref.value,
                pref.category,
                1 if pref.is_explicit else 0,
                pref.context,
                pref.created_at,
                pref.updated_at,
            ))
            conn.commit()

        return pref

    def get_preference(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Retrieves an explicit user preference by key."""
        clean_key = key.strip().lower().replace(" ", "_")
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT value FROM semantic_preferences WHERE key = ?", (clean_key,)
            ).fetchone()
            if row:
                return row["value"]
        return default

    def list_preferences(self, category: Optional[str] = None) -> Dict[str, str]:
        """Returns all explicit user preferences, optionally filtered by category."""
        query = "SELECT key, value FROM semantic_preferences"
        params: List[Any] = []
        if category:
            query += " WHERE category = ?"
            params.append(category)

        prefs: Dict[str, str] = {}
        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            for r in rows:
                prefs[r["key"]] = r["value"]
        return prefs

    def forget_preference(self, key: str) -> bool:
        """Deletes an explicit user preference."""
        clean_key = key.strip().lower().replace(" ", "_")
        with self._get_connection() as conn:
            cur = conn.execute("DELETE FROM semantic_preferences WHERE key = ?", (clean_key,))
            conn.commit()
            return cur.rowcount > 0

    def search_preferences(self, query: str) -> List[SemanticPreference]:
        """Searches preferences by keyword in key, value, or context."""
        words = query.lower().split()
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM semantic_preferences").fetchall()
            results: List[SemanticPreference] = []
            for r in rows:
                text_block = f"{r['key']} {r['value']} {r['category']} {r['context'] or ''}".lower()
                if any(w in text_block for w in words):
                    results.append(
                        SemanticPreference(
                            key=r["key"],
                            value=r["value"],
                            category=r["category"],
                            is_explicit=bool(r["is_explicit"]),
                            context=r["context"],
                            created_at=r["created_at"],
                            updated_at=r["updated_at"],
                        )
                    )
            return results

    def get_prompt_injection(self) -> str:
        """Formats active explicit preferences for injection into system context."""
        prefs = self.list_preferences()
        if not prefs:
            return ""
        lines = ["Explicit User Preferences:"]
        for k, v in prefs.items():
            lines.append(f"- {k.replace('_', ' ').title()}: {v}")
        return "\n".join(lines)
