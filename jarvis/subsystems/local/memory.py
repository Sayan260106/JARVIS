"""SQLite Conversation Memory for JARVIS.

Provides local persistent storage for multi-turn conversational history.
"""

from __future__ import annotations
import os
import sqlite3
import time
import uuid
from typing import Dict, List, Optional


class ConversationMemory:
    """Persistent SQLite database manager for chat history."""

    def __init__(self, db_path: str = "data/jarvis_memory.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Create sessions and messages tables if they do not exist."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    created_at REAL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp REAL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                )
            """)
            conn.commit()

    def create_session(self, title: Optional[str] = None) -> str:
        """Create a new conversational session."""
        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        now = time.time()
        title = title or f"Session {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(now))}"
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO sessions (id, title, created_at) VALUES (?, ?, ?)",
                (session_id, title, now),
            )
            conn.commit()
        return session_id

    def add_message(self, session_id: str, role: str, content: str) -> str:
        """Store a single message (role: 'user' | 'assistant') in the session."""
        msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        now = time.time()
        with self._get_connection() as conn:
            # Ensure session exists
            existing = conn.execute("SELECT id FROM sessions WHERE id = ?", (session_id,)).fetchone()
            if not existing:
                conn.execute(
                    "INSERT INTO sessions (id, title, created_at) VALUES (?, ?, ?)",
                    (session_id, f"Auto-Session {session_id}", now),
                )
            conn.execute(
                "INSERT INTO messages (id, session_id, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
                (msg_id, session_id, role, content, now),
            )
            conn.commit()
        return msg_id

    def get_history(self, session_id: str, limit: int = 10) -> List[Dict[str, str]]:
        """Retrieve recent conversation turns for context injection into Ollama."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT role, content FROM messages
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (session_id, limit),
            )
            rows = cursor.fetchall()
            # Reverse so chronological order (oldest -> newest)
            return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]

    def get_latest_session_id(self) -> str:
        """Return the most recent active session, or create one if none exists."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM sessions ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            if row:
                return row["id"]
        return self.create_session()

    def clear_session(self, session_id: str):
        """Remove all messages and session records for the given session ID."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()
