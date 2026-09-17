"""Persistent Task Manager for JARVIS.

Provides SQLite persistence and full lifecycle operations for long-running tasks.
"""

from __future__ import annotations
import json
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional

from jarvis.core.task_schemas import Task, TaskPriority, TaskStatus


from contextlib import contextmanager


class TaskStore:
    """SQLite-backed storage repository for tasks."""

    def __init__(self, db_path: str = "data/jarvis_tasks.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._init_db()

    @contextmanager
    def _connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self):
        """Initializes the tasks table."""
        with self._connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    objective TEXT NOT NULL,
                    status TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    current_step INTEGER,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    data_json TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_updated ON tasks(updated_at DESC)")
            conn.commit()

    def save(self, task: Task) -> Task:
        """Inserts or updates a task record."""
        task.updated_at = time.time()
        data_json = json.dumps(task.to_dict())
        with self._connection() as conn:
            conn.execute("""
                INSERT INTO tasks (id, objective, status, priority, current_step, retry_count, created_at, updated_at, data_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    objective=excluded.objective,
                    status=excluded.status,
                    priority=excluded.priority,
                    current_step=excluded.current_step,
                    retry_count=excluded.retry_count,
                    updated_at=excluded.updated_at,
                    data_json=excluded.data_json
            """, (
                task.id,
                task.objective,
                task.status.value,
                task.priority.value,
                task.current_step,
                task.retry_count,
                task.created_at,
                task.updated_at,
                data_json,
            ))
        return task

    def get(self, task_id: str) -> Optional[Task]:
        """Retrieves a task by ID."""
        with self._connection() as conn:
            cursor = conn.execute("SELECT data_json FROM tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if not row:
                return None
            data = json.loads(row["data_json"])
            return Task.from_dict(data)

    def list_all(
        self,
        status: Optional[TaskStatus] = None,
        limit: int = 50,
    ) -> List[Task]:
        """Queries tasks optionally filtered by status."""
        query = "SELECT data_json FROM tasks"
        params: List[Any] = []
        if status:
            query += " WHERE status = ?"
            params.append(status.value)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)

        with self._connection() as conn:
            cursor = conn.execute(query, tuple(params))
            rows = cursor.fetchall()
            return [Task.from_dict(json.loads(r["data_json"])) for r in rows]

    def delete(self, task_id: str) -> bool:
        """Deletes a task by ID."""
        with self._connection() as conn:
            cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            return cursor.rowcount > 0


class TaskManager:
    """Manages task lifecycle, state transitions, step advancement, and recovery."""

    def __init__(self, store: Optional[TaskStore] = None, db_path: str = "data/jarvis_tasks.db"):
        self.store = store or TaskStore(db_path=db_path)

    def create_task(
        self,
        objective: str,
        context: Optional[Dict[str, Any]] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        plan: Optional[List[Dict[str, Any]]] = None,
    ) -> Task:
        """Initializes a new task in PENDING state."""
        task = Task(
            objective=objective,
            status=TaskStatus.PENDING,
            priority=priority,
            context=context or {},
            plan=plan or [],
        )
        return self.store.save(task)

    def get_task(self, task_id: str) -> Optional[Task]:
        """Fetches a task from store."""
        return self.store.get(task_id)

    def update_task(self, task: Task) -> Task:
        """Saves current in-memory task state to persistent store."""
        return self.store.save(task)

    def transition_status(
        self,
        task_id: str,
        new_status: TaskStatus,
        reason: Optional[str] = None,
    ) -> Task:
        """Transitions task status with timestamp and optional status reason."""
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"Task '{task_id}' not found.")
        task.status = new_status
        if reason:
            task.context["status_reason"] = reason
        return self.store.save(task)

    def set_plan(self, task_id: str, plan_steps: List[Dict[str, Any]]) -> Task:
        """Assigns planned steps to the task and transitions to PLANNING or RUNNING."""
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"Task '{task_id}' not found.")
        task.plan = plan_steps
        task.status = TaskStatus.PLANNING
        return self.store.save(task)

    def advance_step(
        self,
        task_id: str,
        step_num: int,
        step_name: str,
        result: Optional[Any] = None,
    ) -> Task:
        """Records a successful step, advances current_step, and transitions to RUNNING."""
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"Task '{task_id}' not found.")

        task.current_step = step_num
        task.status = TaskStatus.RUNNING

        step_record = {
            "step_num": step_num,
            "name": step_name,
            "status": "SUCCESS",
            "result": result,
            "completed_at": time.time(),
        }
        task.completed_steps.append(step_record)
        return self.store.save(task)

    def record_failure(
        self,
        task_id: str,
        step_num: int,
        step_name: str,
        error: str,
        can_retry: bool = True,
    ) -> Task:
        """Records a failed step attempt and transitions to RECOVERING or FAILED."""
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"Task '{task_id}' not found.")

        task.current_step = step_num
        task.retry_count += 1

        failed_record = {
            "step_num": step_num,
            "name": step_name,
            "status": "FAILED",
            "error": error,
            "retry_attempt": task.retry_count,
            "timestamp": time.time(),
        }
        task.failed_steps.append(failed_record)

        if can_retry and task.retry_count <= task.max_retries:
            task.status = TaskStatus.RECOVERING
        else:
            task.status = TaskStatus.FAILED

        return self.store.save(task)

    def add_artifact(self, task_id: str, artifact: Any) -> Task:
        """Attaches an artifact (file path, metadata dict, or summary) to the task."""
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"Task '{task_id}' not found.")

        if isinstance(artifact, str):
            record = {"path": artifact, "timestamp": time.time()}
        elif isinstance(artifact, dict):
            record = dict(artifact)
            if "timestamp" not in record:
                record["timestamp"] = time.time()
        else:
            record = {"artifact": str(artifact), "timestamp": time.time()}

        task.artifacts.append(record)
        return self.store.save(task)

    def complete_task(self, task_id: str, final_result: Any) -> Task:
        """Marks task as COMPLETED with the final synthesized result."""
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"Task '{task_id}' not found.")
        task.status = TaskStatus.COMPLETED
        task.final_result = final_result
        return self.store.save(task)

    def cancel_task(self, task_id: str, reason: Optional[str] = None) -> Task:
        """Cancels an active or pending task."""
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"Task '{task_id}' not found.")
        task.status = TaskStatus.CANCELLED
        if reason:
            task.context["cancellation_reason"] = reason
        return self.store.save(task)

    def resume_task(self, task_id: str) -> Task:
        """Resumes an interrupted or paused task back into RUNNING."""
        task = self.get_task(task_id)
        if not task:
            raise ValueError(f"Task '{task_id}' not found.")
        if task.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            raise ValueError(f"Cannot resume task '{task_id}' in state {task.status.value}")
        task.status = TaskStatus.RUNNING
        return self.store.save(task)

    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        limit: int = 50,
    ) -> List[Task]:
        """Lists tasks from store."""
        return self.store.list_all(status=status, limit=limit)
