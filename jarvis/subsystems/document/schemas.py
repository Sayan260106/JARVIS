"""Typed Schemas and Data Contracts for the Document Intelligence Subsystem.

Provides structural models for multi-format document parsing, hierarchical elements,
structure-preserving chunking, and exam-oriented synthesis.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import time
import uuid


class DocumentFormat(str, Enum):
    """Supported document formats."""
    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    TXT = "txt"
    MARKDOWN = "markdown"
    HTML = "html"
    IMAGE = "image"
    UNKNOWN = "unknown"


class ElementType(str, Enum):
    """Semantic structural element classification within documents."""
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST_ITEM = "list_item"
    TABLE = "table"
    CODE_BLOCK = "code_block"
    SLIDE_TITLE = "slide_title"
    SLIDE_CONTENT = "slide_content"
    METADATA = "metadata"


@dataclass
class DocumentElement:
    """A semantic building block within a parsed document."""
    element_type: ElementType
    content: str
    level: int = 1                         # Heading level 1-6, or list indent level
    page_number: int = 1                   # Page or slide number (1-indexed)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "element_type": self.element_type.value,
            "content": self.content,
            "level": self.level,
            "page_number": self.page_number,
            "metadata": self.metadata,
        }


@dataclass
class DocumentMetadata:
    """Document-level metadata."""
    title: str = "Untitled Document"
    author: Optional[str] = None
    creation_date: Optional[str] = None
    page_count: int = 1
    slide_count: int = 0
    format: DocumentFormat = DocumentFormat.UNKNOWN
    file_size_bytes: int = 0
    source_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "author": self.author,
            "creation_date": self.creation_date,
            "page_count": self.page_count,
            "slide_count": self.slide_count,
            "format": self.format.value,
            "file_size_bytes": self.file_size_bytes,
            "source_path": self.source_path,
        }


@dataclass
class ParsedDocument:
    """Complete parsed document with structured elements and raw text."""
    doc_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = "Untitled Document"
    metadata: DocumentMetadata = field(default_factory=DocumentMetadata)
    elements: List[DocumentElement] = field(default_factory=list)
    raw_text: str = ""

    def get_sections(self) -> List[Dict[str, Any]]:
        """Groups elements into hierarchical sections based on headings."""
        sections: List[Dict[str, Any]] = []
        current_section = {
            "title": "Introduction",
            "level": 1,
            "page_number": 1,
            "elements": [],
            "text": "",
        }

        for el in self.elements:
            if el.element_type in (ElementType.HEADING, ElementType.SLIDE_TITLE):
                if current_section["elements"] or current_section["title"] != "Introduction":
                    sections.append(current_section)
                current_section = {
                    "title": el.content.strip(),
                    "level": el.level,
                    "page_number": el.page_number,
                    "elements": [],
                    "text": "",
                }
            else:
                current_section["elements"].append(el)
                current_section["text"] += f"\n{el.content}"

        if current_section["elements"] or current_section["title"]:
            sections.append(current_section)

        return sections

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "title": self.title,
            "metadata": self.metadata.to_dict(),
            "element_count": len(self.elements),
            "raw_text_length": len(self.raw_text),
        }


@dataclass
class DocumentChunk:
    """Structure-aware chunk annotated with hierarchy and position."""
    chunk_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    doc_id: str = ""
    text: str = ""
    section_title: str = ""
    breadcrumbs: str = ""
    page_number: int = 1
    chunk_index: int = 0
    token_count: int = 0
    embedding: Optional[List[float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "text": self.text,
            "section_title": self.section_title,
            "breadcrumbs": self.breadcrumbs,
            "page_number": self.page_number,
            "chunk_index": self.chunk_index,
            "token_count": self.token_count,
            "has_embedding": self.embedding is not None,
        }


@dataclass
class ExamRevisionPack:
    """Comprehensive exam-oriented synthesis generated from documents."""
    course_or_subject: str
    documents_reviewed: List[str]
    high_yield_topics: List[str]
    key_definitions: List[Dict[str, str]]
    core_formulas_principles: List[str]
    sample_questions: List[Dict[str, Any]]
    revision_summary: str
    generated_at: float = field(default_factory=time.time)

    def to_markdown(self) -> str:
        """Formats the revision pack as a clean, structured study note document."""
        md = [
            f"# Exam Revision Pack: {self.course_or_subject}",
            f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.generated_at))}",
            f"**Reviewed Documents:** {', '.join(self.documents_reviewed)}",
            "",
            "## 1. High-Yield Topics",
        ]
        for topic in self.high_yield_topics:
            md.append(f"- [x] **{topic}**")

        md.extend([
            "",
            "## 2. Key Definitions & Terminologies",
        ])
        for item in self.key_definitions:
            term = item.get("term", "")
            definition = item.get("definition", "")
            md.append(f"- **{term}**: {definition}")

        if self.core_formulas_principles:
            md.extend([
                "",
                "## 3. Core Formulas & Principles",
            ])
            for formula in self.core_formulas_principles:
                md.append(f"```text\n{formula}\n```")

        md.extend([
            "",
            "## 4. Comprehensive Exam Summary",
            self.revision_summary,
            "",
            "## 5. Potential Exam Questions & Practice",
        ])
        for idx, q in enumerate(self.sample_questions, 1):
            q_text = q.get("question", "")
            q_ans = q.get("answer", "")
            q_type = q.get("type", "Conceptual")
            md.append(f"### Q{idx} ({q_type}): {q_text}")
            if q_ans:
                md.append(f"> **Key Answer Points:** {q_ans}")
            md.append("")

        return "\n".join(md)
