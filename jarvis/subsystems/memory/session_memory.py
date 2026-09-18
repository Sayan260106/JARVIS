"""Short-Term Session Memory for JARVIS.

Tracks the active task, in-flight steps, and recent progress to answer:
"What were we doing?" and provide active session awareness.
"""

from __future__ import annotations
from contextlib import contextmanager
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional
import uuid

from jarvis.subsystems.memory.schemas import SessionActivity


class SessionMemory:
    """Manages short-term active session state and recent activity history."""

    def __init__(self, db_path: str = "data/jarvis_memory.db"):
        self.db_path = db_path
        self._current_session_id: Optional[str] = None
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._init_db()

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
        """Create session_activities table if it does not exist."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS session_activities (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    task_id TEXT,
                    goal TEXT NOT NULL,
                    step_name TEXT,
                    action TEXT,
                    status TEXT NOT NULL,
                    details TEXT,
                    timestamp REAL NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sess_act_session ON session_activities(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sess_act_time ON session_activities(timestamp DESC)")
            conn.commit()

    def get_or_create_session(self, title: Optional[str] = None) -> str:
        """Returns current session ID or initializes a new session."""
        if not self._current_session_id:
            self._current_session_id = f"sess_{uuid.uuid4().hex[:12]}"
        return self._current_session_id

    def set_session_id(self, session_id: str) -> None:
        """Explicitly binds to a specific session ID."""
        self._current_session_id = session_id

    def record_activity(
        self,
        goal: str,
        step_name: str,
        action: str,
        status: str = "SUCCESS",
        details: str = "",
        task_id: Optional[str] = None,
    ) -> SessionActivity:
        """Records a step or milestone execution in the active session."""
        session_id = self.get_or_create_session()
        activity = SessionActivity(
            session_id=session_id,
            task_id=task_id,
            goal=goal,
            step_name=step_name,
            action=action,
            status=status,
            details=details,
            timestamp=time.time(),
        )

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO session_activities (
                    id, session_id, task_id, goal, step_name, action, status, details, timestamp
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                activity.id,
                activity.session_id,
                activity.task_id,
                activity.goal,
                activity.step_name,
                activity.action,
                activity.status,
                activity.details,
                activity.timestamp,
            ))
            conn.commit()

        return activity

    def get_recent_activities(self, limit: int = 5, session_only: bool = True) -> List[SessionActivity]:
        """Retrieves recent activities ordered descending by timestamp."""
        session_id = self.get_or_create_session()
        query = "SELECT * FROM session_activities"
        params: List[Any] = []

        if session_only:
            query += " WHERE session_id = ?"
            params.append(session_id)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        activities: List[SessionActivity] = []
        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            for r in rows:
                activities.append(
                    SessionActivity(
                        id=r["id"],
                        session_id=r["session_id"],
                        task_id=r["task_id"],
                        goal=r["goal"],
                        step_name=r["step_name"] or "",
                        action=r["action"] or "",
                        status=r["status"],
                        details=r["details"] or "",
                        timestamp=r["timestamp"],
                    )
                )

        return activities

    def what_were_we_doing(self) -> str:
        """Answers 'What were we doing?' by summarizing the active goal and recent steps."""
        recent = self.get_recent_activities(limit=5, session_only=True)
        if not recent:
            # Fall back to any recent activity across sessions
            recent = self.get_recent_activities(limit=3, session_only=False)

        if not recent:
            return "We haven't started any tasks yet in this session. I am ready for your next instruction."

        latest = recent[0]
        goal = latest.goal
        status = latest.status
        action = latest.action or latest.step_name or "in progress"

        steps_summary = [f"- {a.step_name or a.action} ({a.status})" for a in reversed(recent[:3])]

        response = (
            f"We were working on: '{goal}'.\n"
            f"Current status is {status}. The last completed action was '{action}'.\n"
            f"Recent actions:\n" + "\n".join(steps_summary)
        )
        return response
