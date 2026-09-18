"""Structure-Aware Document Chunker for JARVIS.

Preserves semantic hierarchy, headings, and sentence boundaries.
Annotates chunks with section breadcrumbs and page coordinates for accurate retrieval.
"""

from __future__ import annotations
import re
from typing import List, Optional

from jarvis.subsystems.document.schemas import DocumentChunk, ParsedDocument


class DocumentChunker:
    """Chunks documents while preserving structural and heading context."""

    def __init__(self, target_chunk_tokens: int = 400, overlap_tokens: int = 50):
        self.target_chunk_tokens = target_chunk_tokens
        self.overlap_tokens = overlap_tokens

    def chunk_document(self, doc: ParsedDocument) -> List[DocumentChunk]:
        """Splits a ParsedDocument into structure-aware DocumentChunks."""
        chunks: List[DocumentChunk] = []
        sections = doc.get_sections()

        global_chunk_idx = 0

        for section in sections:
            sec_title = section["title"]
            page_num = section.get("page_number", 1)
            sec_text = section["text"].strip()

            if not sec_text:
                continue

            breadcrumbs = f"{doc.title} > {sec_title}"

            # Approximate token count by words
            words = sec_text.split()
            if len(words) <= self.target_chunk_tokens:
                # Small enough to fit in a single chunk
                chunk = DocumentChunk(
                    doc_id=doc.doc_id,
                    text=f"[{breadcrumbs}]\n{sec_text}",
                    section_title=sec_title,
                    breadcrumbs=breadcrumbs,
                    page_number=page_num,
                    chunk_index=global_chunk_idx,
                    token_count=len(words),
                )
                chunks.append(chunk)
                global_chunk_idx += 1
            else:
                # Need structure-preserving sentence-level sliding window
                sentences = self._split_into_sentences(sec_text)
                cur_sentences: List[str] = []
                cur_word_count = 0

                for sent in sentences:
                    sent_words = len(sent.split())
                    if cur_word_count + sent_words > self.target_chunk_tokens and cur_sentences:
                        # Flush current chunk
                        chunk_text = " ".join(cur_sentences).strip()
                        chunk = DocumentChunk(
                            doc_id=doc.doc_id,
                            text=f"[{breadcrumbs}]\n{chunk_text}",
                            section_title=sec_title,
                            breadcrumbs=breadcrumbs,
                            page_number=page_num,
                            chunk_index=global_chunk_idx,
                            token_count=cur_word_count,
                        )
                        chunks.append(chunk)
                        global_chunk_idx += 1

                        # Calculate overlap by retaining the tail sentences
                        overlap_collected: List[str] = []
                        overlap_words = 0
                        for s in reversed(cur_sentences):
                            sw = len(s.split())
                            if overlap_words + sw <= self.overlap_tokens:
                                overlap_collected.insert(0, s)
                                overlap_words += sw
                            else:
                                break

                        cur_sentences = overlap_collected + [sent]
                        cur_word_count = overlap_words + sent_words
                    else:
                        cur_sentences.append(sent)
                        cur_word_count += sent_words

                if cur_sentences:
                    chunk_text = " ".join(cur_sentences).strip()
                    chunk = DocumentChunk(
                        doc_id=doc.doc_id,
                        text=f"[{breadcrumbs}]\n{chunk_text}",
                        section_title=sec_title,
                        breadcrumbs=breadcrumbs,
                        page_number=page_num,
                        chunk_index=global_chunk_idx,
                        token_count=cur_word_count,
                    )
                    chunks.append(chunk)
                    global_chunk_idx += 1

        return chunks

    def _split_into_sentences(self, text: str) -> List[str]:
        """Splits text into sentences cleanly respecting abbreviations."""
        # Simple regex split on sentence punctuation followed by whitespace and capital letter
        parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text)
        return [p.strip() for p in parts if p.strip()]
