"""Document Intelligence Subsystem for JARVIS.

Handles multi-format parsing, structure-preserving chunking, hybrid vector retrieval,
and semantic document operations (summarization, exam prep, notes, and Q&A).
"""

from jarvis.subsystems.document.schemas import (
    DocumentFormat,
    ElementType,
    DocumentElement,
    DocumentMetadata,
    ParsedDocument,
    DocumentChunk,
    ExamRevisionPack,
)
from jarvis.subsystems.document.parsers import (
    BaseDocumentParser,
    PDFParser,
    DocxParser,
    PptxParser,
    TextParser,
    MarkdownParser,
    HTMLParser,
    DocumentParserFactory,
)
from jarvis.subsystems.document.chunker import DocumentChunker
from jarvis.subsystems.document.retriever import DocumentIndex
from jarvis.subsystems.document.analyzer import DocumentAnalyzer

__all__ = [
    "DocumentFormat",
    "ElementType",
    "DocumentElement",
    "DocumentMetadata",
    "ParsedDocument",
    "DocumentChunk",
    "ExamRevisionPack",
    "BaseDocumentParser",
    "PDFParser",
    "DocxParser",
    "PptxParser",
    "TextParser",
    "MarkdownParser",
    "HTMLParser",
    "DocumentParserFactory",
    "DocumentChunker",
    "DocumentIndex",
    "DocumentAnalyzer",
]
