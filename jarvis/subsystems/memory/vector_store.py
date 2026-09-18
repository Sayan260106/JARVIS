"""Vector Store and Cosine Similarity Retrieval for JARVIS.

Stores dense embedding vectors in SQLite and performs semantic similarity search
to power the "Embedding model -> Memory retrieval" architecture.
"""

from __future__ import annotations
from contextlib import contextmanager
import json
import math
import os
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple


class SQLiteVectorStore:
    """Stores high-dimensional vector embeddings in SQLite with top-k cosine similarity search."""

    def __init__(self, db_path: str = "data/jarvis_memory.db"):
        self.db_path = db_path
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
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_vectors (
                    id TEXT PRIMARY KEY,
                    vector_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            conn.commit()

    def store_vector(self, item_id: str, vector: List[float], metadata: Optional[Dict[str, Any]] = None) -> None:
        """Stores or updates an embedding vector associated with item_id."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO memory_vectors (id, vector_json, metadata_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    vector_json = excluded.vector_json,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
            """, (
                item_id,
                json.dumps(vector),
                json.dumps(metadata or {}),
                time.time(),
            ))
            conn.commit()

    def get_vector(self, item_id: str) -> Optional[List[float]]:
        """Retrieve the raw vector for a specific item_id."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT vector_json FROM memory_vectors WHERE id = ?", (item_id,)).fetchone()
            if row:
                return json.loads(row["vector_json"])
        return None

    def similarity_search(
        self, query_vector: List[float], top_k: int = 5
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """Perform top-k cosine similarity search against all stored vectors.

        Returns:
            List of tuples: (item_id, similarity_score, metadata) sorted descending.
        """
        if not query_vector:
            return []

        q_norm = math.sqrt(sum(x * x for x in query_vector))
        if q_norm == 0:
            return []

        scored: List[Tuple[str, float, Dict[str, Any]]] = []

        with self._get_connection() as conn:
            rows = conn.execute("SELECT id, vector_json, metadata_json FROM memory_vectors").fetchall()
            for r in rows:
                item_id = r["id"]
                vec = json.loads(r["vector_json"])
                meta = json.loads(r["metadata_json"])

                # Compute cosine similarity
                dot_product = sum(a * b for a, b in zip(query_vector, vec))
                v_norm = math.sqrt(sum(x * x for x in vec))
                if v_norm > 0:
                    sim = dot_product / (q_norm * v_norm)
                    scored.append((item_id, float(sim), meta))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
