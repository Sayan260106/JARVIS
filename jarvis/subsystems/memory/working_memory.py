"""Working Memory Subsystem for JARVIS.

Provides fast ephemeral scratchpad memory for in-flight tasks and multi-step plans.
Backed by an in-memory dictionary and persistent SQLite table.
"""

from __future__ import annotations
import json
import os
import sqlite3
import time
from typing import Any, Dict, Optional


class WorkingMemory:
    """Manages active task state and ephemeral scratchpad variables."""

    def __init__(self, db_path: str = "data/jarvis_memory.db"):
        self.db_path = db_path
        self._cache: Dict[str, Dict[str, Any]] = {}
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS working_memory (
                    task_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    updated_at REAL NOT NULL,
                    PRIMARY KEY(task_id, key)
                )
            """)
            conn.commit()

    def set(self, task_id: str, key: str, value: Any) -> None:
        """Stores a variable in working memory for the specified task."""
        now = time.time()
        if task_id not in self._cache:
            self._cache[task_id] = {}
        self._cache[task_id][key] = value

        encoded = json.dumps(value)
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO working_memory (task_id, key, value, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(task_id, key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
            """, (task_id, key, encoded, now))
            conn.commit()

    def get(self, task_id: str, key: str, default: Any = None) -> Any:
        """Retrieves a variable from working memory."""
        if task_id in self._cache and key in self._cache[task_id]:
            return self._cache[task_id][key]

        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT value FROM working_memory WHERE task_id = ? AND key = ?",
                (task_id, key),
            ).fetchone()
            if row:
                try:
                    val = json.loads(row["value"])
                    if task_id not in self._cache:
                        self._cache[task_id] = {}
                    self._cache[task_id][key] = val
                    return val
                except Exception:
                    return row["value"]
        return default

    def get_all(self, task_id: str) -> Dict[str, Any]:
        """Retrieves all working memory variables for a task."""
        data: Dict[str, Any] = {}
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT key, value FROM working_memory WHERE task_id = ?",
                (task_id,),
            ).fetchall()
            for r in rows:
                try:
                    data[r["key"]] = json.loads(r["value"])
                except Exception:
                    data[r["key"]] = r["value"]
        self._cache[task_id] = data
        return data

    def delete(self, task_id: str, key: str) -> bool:
        """Removes a key from working memory."""
        if task_id in self._cache and key in self._cache[task_id]:
            del self._cache[task_id][key]

        with self._get_connection() as conn:
            cur = conn.execute(
                "DELETE FROM working_memory WHERE task_id = ? AND key = ?",
                (task_id, key),
            )
            conn.commit()
            return cur.rowcount > 0

    def clear(self, task_id: str) -> int:
        """Clears all working memory for a completed or cancelled task."""
        if task_id in self._cache:
            del self._cache[task_id]

        with self._get_connection() as conn:
            cur = conn.execute(
                "DELETE FROM working_memory WHERE task_id = ?",
                (task_id,),
            )
            conn.commit()
            return cur.rowcount
