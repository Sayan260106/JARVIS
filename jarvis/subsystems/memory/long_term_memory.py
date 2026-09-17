"""Long-Term Memory Subsystems for JARVIS.

Implements Episodic Memory (past interactions, milestones, and user preferences)
and Knowledge Memory (documents, notes, and facts indexed via SQLite FTS5).
"""

from __future__ import annotations
import json
import os
import re
import sqlite3
import time
from typing import Any, Dict, List, Optional

from jarvis.subsystems.memory.schemas import Episode, KnowledgeItem, MemorySearchResult, MemoryTier


class EpisodicMemory:
    """Manages autobiographical and historical memories of past events, interactions, and preferences."""

    def __init__(self, db_path: str = "data/jarvis_memory.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id TEXT PRIMARY KEY,
                    session_id TEXT,
                    episode_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    key_facts TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    metadata TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    context TEXT,
                    updated_at REAL NOT NULL
                )
            """)
            conn.commit()

    def add_episode(self, episode: Episode) -> str:
        """Stores a new episodic event."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO episodes (id, session_id, episode_type, title, summary, key_facts, tags, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                episode.id,
                episode.session_id,
                episode.episode_type,
                episode.title,
                episode.summary,
                json.dumps(episode.key_facts),
                json.dumps(episode.tags),
                episode.timestamp,
                json.dumps(episode.metadata),
            ))
            conn.commit()
        return episode.id

    def remember_preference(self, key: str, value: str, context: Optional[str] = None) -> str:
        """Records an intentional user preference or personal fact."""
        now = time.time()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO user_preferences (key, value, context, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    context = excluded.context,
                    updated_at = excluded.updated_at
            """, (key, value, context, now))
            conn.commit()

        # Also log as an episode
        self.add_episode(
            Episode(
                episode_type="user_preference",
                title=f"Preference: {key}",
                summary=f"User stated {key} is {value}.",
                key_facts=[f"{key}: {value}"],
                tags=["preference", key.lower()],
                metadata={"context": context or ""},
            )
        )
        return key

    def get_preferences(self) -> Dict[str, str]:
        """Retrieves all stored user preferences."""
        prefs = {}
        with self._get_connection() as conn:
            rows = conn.execute("SELECT key, value FROM user_preferences ORDER BY updated_at ASC").fetchall()
            for r in rows:
                prefs[r["key"]] = r["value"]
        return prefs

    def get_recent_episodes(self, limit: int = 10, episode_type: Optional[str] = None) -> List[Episode]:
        """Retrieves recent episodes chronologically."""
        query = "SELECT * FROM episodes"
        params: List[Any] = []
        if episode_type:
            query += " WHERE episode_type = ?"
            params.append(episode_type)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        episodes = []
        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            for r in rows:
                episodes.append(
                    Episode(
                        id=r["id"],
                        session_id=r["session_id"],
                        episode_type=r["episode_type"],
                        title=r["title"],
                        summary=r["summary"],
                        key_facts=json.loads(r["key_facts"]),
                        tags=json.loads(r["tags"]),
                        timestamp=r["timestamp"],
                        metadata=json.loads(r["metadata"]),
                    )
                )
        return episodes

    def search_episodes(self, query: str, limit: int = 5) -> List[Episode]:
        """Searches episodes by keyword matching across title, summary, and facts."""
        tokens = [t.strip().lower() for t in query.split() if len(t.strip()) > 2]
        if not tokens:
            return self.get_recent_episodes(limit=limit)

        all_episodes = self.get_recent_episodes(limit=100)
        scored: List[tuple[int, Episode]] = []
        for ep in all_episodes:
            score = 0
            text_corpus = f"{ep.title} {ep.summary} {' '.join(ep.key_facts)} {' '.join(ep.tags)}".lower()
            for token in tokens:
                if token in text_corpus:
                    score += 1
            if score > 0:
                scored.append((score, ep))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [ep for _, ep in scored[:limit]]


class KnowledgeMemory:
    """Manages knowledge items, documents, and reference facts using SQLite FTS5."""

    def __init__(self, db_path: str = "data/jarvis_memory.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            # Metadata table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_items (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    source TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            # FTS5 virtual table for full-text search
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
                    id UNINDEXED,
                    title,
                    content,
                    tags,
                    source UNINDEXED
                )
            """)
            conn.commit()

    def add_item(self, item: KnowledgeItem) -> str:
        """Stores and indexes a knowledge item into SQLite FTS5."""
        tags_str = " ".join(item.tags)
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO knowledge_items (id, title, content, tags, source, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                item.id,
                item.title,
                item.content,
                json.dumps(item.tags),
                item.source,
                item.created_at,
                item.updated_at,
            ))
            conn.execute("""
                INSERT INTO knowledge_fts (id, title, content, tags, source)
                VALUES (?, ?, ?, ?, ?)
            """, (
                item.id,
                item.title,
                item.content,
                tags_str,
                item.source,
            ))
            conn.commit()
        return item.id

    def get_item(self, item_id: str) -> Optional[KnowledgeItem]:
        """Retrieves a knowledge item by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM knowledge_items WHERE id = ?", (item_id,)).fetchone()
            if row:
                return KnowledgeItem(
                    id=row["id"],
                    title=row["title"],
                    content=row["content"],
                    tags=json.loads(row["tags"]),
                    source=row["source"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
        return None

    def search(self, query: str, limit: int = 5) -> List[KnowledgeItem]:
        """Performs full-text search with BM25 ranking across title, content, and tags."""
        clean_tokens = [t.lower() for t in re.findall(r"[a-zA-Z0-9]+", query) if len(t) > 1]
        if not clean_tokens:
            clean_tokens = [t.lower() for t in re.findall(r"[a-zA-Z0-9]+", query)]
        if not clean_tokens:
            return self.list_items(limit=limit)

        fts_query = " OR ".join(clean_tokens)
        results: List[KnowledgeItem] = []

        with self._get_connection() as conn:
            try:
                rows = conn.execute("""
                    SELECT id FROM knowledge_fts
                    WHERE knowledge_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                """, (fts_query, limit)).fetchall()
                for r in rows:
                    item = self.get_item(r["id"])
                    if item:
                        results.append(item)
            except Exception:
                # Fallback to standard LIKE if query syntax fails
                like_pat = f"%{clean_tokens[0]}%"
                rows = conn.execute("""
                    SELECT id FROM knowledge_items
                    WHERE title LIKE ? OR content LIKE ?
                    LIMIT ?
                """, (like_pat, like_pat, limit)).fetchall()
                for r in rows:
                    item = self.get_item(r["id"])
                    if item:
                        results.append(item)

        return results

    def list_items(self, limit: int = 20) -> List[KnowledgeItem]:
        """Lists recent knowledge items."""
        items: List[KnowledgeItem] = []
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM knowledge_items ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
            for row in rows:
                items.append(
                    KnowledgeItem(
                        id=row["id"],
                        title=row["title"],
                        content=row["content"],
                        tags=json.loads(row["tags"]),
                        source=row["source"],
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                    )
                )
        return items

    def delete_item(self, item_id: str) -> bool:
        """Deletes a knowledge item from both metadata and FTS index."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM knowledge_fts WHERE id = ?", (item_id,))
            cur = conn.execute("DELETE FROM knowledge_items WHERE id = ?", (item_id,))
            conn.commit()
            return cur.rowcount > 0
