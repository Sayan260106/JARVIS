"""Task / Workflow Memory for JARVIS.

Captures previous successful workflows into reusable templates:
e.g. "Open ECE Classroom" becomes a reusable, parameterizable workflow
with step sequences, trigger patterns, and usage telemetry.
"""

from __future__ import annotations
from contextlib import contextmanager
import json
import os
import re
import sqlite3
import time
from typing import Any, Dict, List, Optional

from jarvis.subsystems.memory.schemas import ReusableWorkflow


DEFAULT_WORKFLOWS = [
    {
        "name": "Open ECE Classroom",
        "description": "Opens Google Chrome with institutional profile and navigates directly to ECE course page.",
        "trigger_patterns": [
            r"\b(?:open|enter|launch|go\s+to)\s+ece\s+classroom\b",
            r"\bece\s+classroom\b",
            r"\bopen\s+ece\b",
        ],
        "steps": [
            {"tool": "browser_open", "arguments": {"channel": "chrome", "profile_name": "institutional"}},
            {"tool": "browser_detect_session", "arguments": {"service": "google"}},
            {"tool": "browser_navigate", "arguments": {"url": "https://classroom.google.com"}},
            {"tool": "browser_click", "arguments": {"selector": "ECE", "wait_for_nav": True}},
        ],
    },
    {
        "name": "Lock Computer",
        "description": "Locks the Windows workstation.",
        "trigger_patterns": [
            r"^lock\s*(?:the\s+)?(?:pc|computer|workstation)$",
        ],
        "steps": [
            {"tool": "lock_pc", "arguments": {}},
        ],
    },
    {
        "name": "Organize Downloads",
        "description": "Inspects downloads folder, detects duplicates, and sorts files by category.",
        "trigger_patterns": [
            r"\b(?:organize|sort|clean(?:\s+up)?)\s+(?:the\s+)?downloads\b",
        ],
        "steps": [
            {"tool": "inspect_directory", "arguments": {"path": "downloads"}},
            {"tool": "detect_duplicates", "arguments": {"path": "downloads"}},
            {"tool": "batch_organize_files", "arguments": {"path": "downloads"}},
        ],
    },
]


class WorkflowMemory:
    """Manages reusable task workflows and parameterized action graphs."""

    def __init__(self, db_path: str = "data/jarvis_memory.db"):
        self.db_path = db_path
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
        """Creates reusable_workflows table if it does not exist."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reusable_workflows (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    trigger_patterns_json TEXT NOT NULL,
                    steps_json TEXT NOT NULL,
                    success_count INTEGER NOT NULL DEFAULT 1,
                    last_used_at REAL NOT NULL,
                    created_at REAL NOT NULL
                )
            """)
            conn.commit()

    def _seed_defaults(self):
        """Seeds default standard workflows like Open ECE Classroom."""
        now = time.time()
        with self._get_connection() as conn:
            for wf in DEFAULT_WORKFLOWS:
                wf_id = f"wf_{wf['name'].lower().replace(' ', '_')}"
                conn.execute("""
                    INSERT OR IGNORE INTO reusable_workflows (
                        id, name, description, trigger_patterns_json, steps_json,
                        success_count, last_used_at, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                """, (
                    wf_id,
                    wf["name"],
                    wf["description"],
                    json.dumps(wf["trigger_patterns"]),
                    json.dumps(wf["steps"]),
                    now,
                    now,
                ))
            conn.commit()

    def save_workflow(
        self,
        name: str,
        trigger_patterns: List[str],
        steps: List[Dict[str, Any]],
        description: str = "",
    ) -> ReusableWorkflow:
        """Saves or updates a reusable workflow."""
        now = time.time()
        wf_id = f"wf_{name.lower().replace(' ', '_')}"
        wf = ReusableWorkflow(
            id=wf_id,
            name=name.strip(),
            description=description.strip(),
            trigger_patterns=trigger_patterns,
            steps=steps,
            success_count=1,
            last_used_at=now,
            created_at=now,
        )

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO reusable_workflows (
                    id, name, description, trigger_patterns_json, steps_json,
                    success_count, last_used_at, created_at
                )
                VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    description = excluded.description,
                    trigger_patterns_json = excluded.trigger_patterns_json,
                    steps_json = excluded.steps_json,
                    last_used_at = excluded.last_used_at
            """, (
                wf.id,
                wf.name,
                wf.description,
                json.dumps(wf.trigger_patterns),
                json.dumps(wf.steps),
                wf.last_used_at,
                wf.created_at,
            ))
            conn.commit()

        return wf

    def get_workflow(self, name: str) -> Optional[ReusableWorkflow]:
        """Retrieves a workflow by exact name."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM reusable_workflows WHERE LOWER(name) = LOWER(?)", (name.strip(),)
            ).fetchone()
            if row:
                return self._row_to_workflow(row)
        return None

    def list_workflows(self) -> List[ReusableWorkflow]:
        """Lists all registered reusable workflows."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM reusable_workflows ORDER BY success_count DESC").fetchall()
            return [self._row_to_workflow(r) for r in rows]

    def find_matching_workflow(self, prompt: str) -> Optional[ReusableWorkflow]:
        """Matches a user prompt against registered trigger patterns."""
        norm = prompt.strip().lower()
        workflows = self.list_workflows()

        # 1. Check exact or trigger pattern regex
        for wf in workflows:
            for pattern in wf.trigger_patterns:
                try:
                    if re.search(pattern, norm, re.IGNORECASE):
                        self.record_usage(wf.name)
                        return wf
                except Exception:
                    if pattern.lower() in norm:
                        self.record_usage(wf.name)
                        return wf

        # 2. Fuzzy name containment
        for wf in workflows:
            if wf.name.lower() in norm:
                self.record_usage(wf.name)
                return wf

        return None

    def record_usage(self, name: str) -> None:
        """Increments the success counter and updates the last used timestamp."""
        now = time.time()
        with self._get_connection() as conn:
            conn.execute("""
                UPDATE reusable_workflows
                SET success_count = success_count + 1, last_used_at = ?
                WHERE LOWER(name) = LOWER(?)
            """, (now, name.strip()))
            conn.commit()

    def delete_workflow(self, name: str) -> bool:
        """Deletes a reusable workflow."""
        with self._get_connection() as conn:
            cur = conn.execute("DELETE FROM reusable_workflows WHERE LOWER(name) = LOWER(?)", (name.strip(),))
            conn.commit()
            return cur.rowcount > 0

    def _row_to_workflow(self, row: sqlite3.Row) -> ReusableWorkflow:
        return ReusableWorkflow(
            id=row["id"],
            name=row["name"],
            description=row["description"] or "",
            trigger_patterns=json.loads(row["trigger_patterns_json"]),
            steps=json.loads(row["steps_json"]),
            success_count=row["success_count"],
            last_used_at=row["last_used_at"],
            created_at=row["created_at"],
        )
