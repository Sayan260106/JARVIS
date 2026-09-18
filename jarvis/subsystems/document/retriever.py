"""Vector Embedding & Hybrid Retrieval for Document Intelligence.

Stores document chunk embeddings in SQLite with cosine similarity and lexical
BM25/token scoring for pinpoint technical term and formula retrieval.
"""

from __future__ import annotations
from contextlib import contextmanager
import json
import math
import os
import re
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple

from jarvis.core.llm_provider import LLMProvider, ModelRole
from jarvis.subsystems.document.schemas import DocumentChunk


class DocumentIndex:
    """Manages document vector indexing and hybrid retrieval."""

    def __init__(self, db_path: str = "data/document_intelligence.db", llm_provider: Optional[LLMProvider] = None):
        self.db_path = db_path
        self.llm_provider = llm_provider
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
                CREATE TABLE IF NOT EXISTS document_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    doc_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    section_title TEXT,
                    breadcrumbs TEXT,
                    page_number INTEGER,
                    chunk_index INTEGER,
                    token_count INTEGER,
                    vector_json TEXT,
                    created_at REAL NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_doc_id ON document_chunks(doc_id)")
            conn.commit()

    def index_chunks(self, chunks: List[DocumentChunk], doc_id: Optional[str] = None) -> int:
        """Indexes a list of chunks, embedding each with LLMProvider."""
        indexed_count = 0
        with self._get_connection() as conn:
            for chunk in chunks:
                target_doc_id = doc_id or chunk.doc_id
                vec: Optional[List[float]] = chunk.embedding

                # Compute embedding if not provided and provider is present
                if vec is None and self.llm_provider:
                    try:
                        vec = self.llm_provider.embed(chunk.text, role=ModelRole.EMBEDDING)
                    except Exception:
                        vec = None

                vec_json = json.dumps(vec) if vec is not None else None

                conn.execute("""
                    INSERT INTO document_chunks (
                        chunk_id, doc_id, text, section_title, breadcrumbs,
                        page_number, chunk_index, token_count, vector_json, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(chunk_id) DO UPDATE SET
                        text = excluded.text,
                        section_title = excluded.section_title,
                        breadcrumbs = excluded.breadcrumbs,
                        page_number = excluded.page_number,
                        chunk_index = excluded.chunk_index,
                        token_count = excluded.token_count,
                        vector_json = excluded.vector_json,
                        created_at = excluded.created_at
                """, (
                    chunk.chunk_id,
                    target_doc_id,
                    chunk.text,
                    chunk.section_title,
                    chunk.breadcrumbs,
                    chunk.page_number,
                    chunk.chunk_index,
                    chunk.token_count,
                    vec_json,
                    time.time(),
                ))
                indexed_count += 1
            conn.commit()
        return indexed_count

    def similarity_search(
        self, query: str, top_k: int = 5, doc_id: Optional[str] = None
    ) -> List[Tuple[DocumentChunk, float]]:
        """Dense semantic search via vector embeddings and cosine similarity."""
        if not self.llm_provider:
            return [(c, 1.0) for c in self.keyword_search(query, top_k, doc_id)]

        try:
            q_vec = self.llm_provider.embed(query, role=ModelRole.EMBEDDING)
        except Exception:
            return [(c, 1.0) for c in self.keyword_search(query, top_k, doc_id)]

        q_norm = math.sqrt(sum(x * x for x in q_vec))
        if q_norm == 0:
            return []

        scored: List[Tuple[DocumentChunk, float]] = []

        query_sql = "SELECT * FROM document_chunks"
        params: List[Any] = []
        if doc_id:
            query_sql += " WHERE doc_id = ?"
            params.append(doc_id)

        with self._get_connection() as conn:
            rows = conn.execute(query_sql, params).fetchall()
            for r in rows:
                v_raw = r["vector_json"]
                if not v_raw:
                    continue
                vec = json.loads(v_raw)
                dot = sum(a * b for a, b in zip(q_vec, vec))
                v_norm = math.sqrt(sum(x * x for x in vec))
                if v_norm > 0:
                    sim = dot / (q_norm * v_norm)
                    c = DocumentChunk(
                        chunk_id=r["chunk_id"],
                        doc_id=r["doc_id"],
                        text=r["text"],
                        section_title=r["section_title"],
                        breadcrumbs=r["breadcrumbs"],
                        page_number=r["page_number"],
                        chunk_index=r["chunk_index"],
                        token_count=r["token_count"],
                    )
                    scored.append((c, float(sim)))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def keyword_search(
        self, query: str, top_k: int = 5, doc_id: Optional[str] = None
    ) -> List[DocumentChunk]:
        """Lexical keyword search matching words in text."""
        words = set(re.findall(r"\w+", query.lower()))
        if not words:
            return []

        query_sql = "SELECT * FROM document_chunks"
        params: List[Any] = []
        if doc_id:
            query_sql += " WHERE doc_id = ?"
            params.append(doc_id)

        scored: List[Tuple[DocumentChunk, int]] = []
        with self._get_connection() as conn:
            rows = conn.execute(query_sql, params).fetchall()
            for r in rows:
                txt = r["text"].lower()
                matches = sum(1 for w in words if w in txt)
                if matches > 0:
                    c = DocumentChunk(
                        chunk_id=r["chunk_id"],
                        doc_id=r["doc_id"],
                        text=r["text"],
                        section_title=r["section_title"],
                        breadcrumbs=r["breadcrumbs"],
                        page_number=r["page_number"],
                        chunk_index=r["chunk_index"],
                        token_count=r["token_count"],
                    )
                    scored.append((c, matches))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [c for c, _ in scored[:top_k]]

    def hybrid_search(
        self, query: str, top_k: int = 5, doc_id: Optional[str] = None, alpha: float = 0.7
    ) -> List[DocumentChunk]:
        """Combines dense cosine similarity with keyword frequency."""
        semantic_results = self.similarity_search(query, top_k=top_k * 2, doc_id=doc_id)
        if not semantic_results:
            return self.keyword_search(query, top_k=top_k, doc_id=doc_id)

        sem_scores = {c.chunk_id: score for c, score in semantic_results}
        chunks_map = {c.chunk_id: c for c, _ in semantic_results}

        # Also get keyword scores
        words = set(re.findall(r"\w+", query.lower()))
        combined: List[Tuple[DocumentChunk, float]] = []

        for cid, chunk in chunks_map.items():
            sem = sem_scores.get(cid, 0.0)
            txt = chunk.text.lower()
            kw = (sum(1 for w in words if w in txt) / max(1, len(words))) if words else 0.0
            final_score = alpha * sem + (1 - alpha) * kw
            combined.append((chunk, final_score))

        combined.sort(key=lambda x: x[1], reverse=True)
        return [c for c, _ in combined[:top_k]]

    def get_chunks_for_doc(self, doc_id: str) -> List[DocumentChunk]:
        """Retrieves all chunks for a document in sequential order."""
        chunks: List[DocumentChunk] = []
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM document_chunks WHERE doc_id = ? ORDER BY chunk_index ASC", (doc_id,)
            ).fetchall()
            for r in rows:
                chunks.append(
                    DocumentChunk(
                        chunk_id=r["chunk_id"],
                        doc_id=r["doc_id"],
                        text=r["text"],
                        section_title=r["section_title"],
                        breadcrumbs=r["breadcrumbs"],
                        page_number=r["page_number"],
                        chunk_index=r["chunk_index"],
                        token_count=r["token_count"],
                    )
                )
        return chunks
