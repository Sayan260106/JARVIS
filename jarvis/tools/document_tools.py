"""Typed Agent Tools for Document Intelligence.

Provides tools for multi-format reading, chunking, vector indexing, retrieval,
summarization, topic extraction, Cornell notes, questions, Q&A, and exam preparation.
"""

from __future__ import annotations
import os
import time
from typing import Any, Dict, List, Optional

from jarvis.subsystems.document.analyzer import DocumentAnalyzer
from jarvis.subsystems.document.chunker import DocumentChunker
from jarvis.subsystems.document.parsers import DocumentParserFactory
from jarvis.subsystems.document.retriever import DocumentIndex
from jarvis.subsystems.document.schemas import ParsedDocument
from jarvis.tools.base import (
    BaseTool,
    PermissionLevel,
    RiskLevel,
    ToolParameter,
    ToolResult,
    ToolVerification,
)


class DocumentReadTool(BaseTool):
    """Parses documents (PDF, DOCX, PPTX, TXT, MD, HTML) and extracts structure."""
    name = "document_read"
    description = "Read and parse a document (PDF, DOCX, PPTX, TXT, Markdown, HTML) into structured elements."
    risk_level = RiskLevel.LOW
    permission_level = PermissionLevel.LEVEL_0_READ

    parameters = [
        ToolParameter("file_path", "string", "Path to the document file on disk", required=True),
        ToolParameter("format_hint", "string", "Optional format hint (pdf, docx, pptx, txt, md, html)", required=False),
    ]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        start_time = time.time()
        file_path = arguments.get("file_path", "")
        hint = arguments.get("format_hint")

        if not os.path.exists(file_path):
            return ToolResult(
                success=False,
                output=None,
                error=f"Document file does not exist: {file_path}",
                duration_ms=(time.time() - start_time) * 1000,
            )

        try:
            doc = DocumentParserFactory.parse_document(file_path, format_hint=hint)
            result = {
                "doc_id": doc.doc_id,
                "title": doc.title,
                "format": doc.metadata.format.value,
                "page_count": doc.metadata.page_count,
                "slide_count": doc.metadata.slide_count,
                "element_count": len(doc.elements),
                "raw_text_preview": doc.raw_text[:300] + ("..." if len(doc.raw_text) > 300 else ""),
                "sections": [s["title"] for s in doc.get_sections()[:8]],
            }
            return ToolResult(
                success=True,
                output=result,
                duration_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Failed to parse document: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000,
            )

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if result.success and result.output and result.output.get("doc_id"):
            return ToolVerification(
                verified=True,
                details=f"Parsed {result.output.get('format')} '{result.output.get('title')}' with {result.output.get('element_count')} elements.",
            )
        return ToolVerification(verified=False, details=result.error or "Document parsing failed.")


class DocumentChunkTool(BaseTool):
    """Splits a document into structure-aware chunks with section breadcrumbs."""
    name = "document_chunk"
    description = "Chunk a document while preserving section boundaries and heading context."
    risk_level = RiskLevel.LOW
    permission_level = PermissionLevel.LEVEL_0_READ

    parameters = [
        ToolParameter("file_path", "string", "Path to document file", required=True),
        ToolParameter("target_tokens", "integer", "Target words/tokens per chunk", required=False, default=400),
        ToolParameter("overlap_tokens", "integer", "Overlap words/tokens between chunks", required=False, default=50),
    ]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        start = time.time()
        file_path = arguments.get("file_path", "")
        target_tokens = int(arguments.get("target_tokens", 400))
        overlap_tokens = int(arguments.get("overlap_tokens", 50))

        if not os.path.exists(file_path):
            return ToolResult(success=False, output=None, error=f"File not found: {file_path}")

        try:
            doc = DocumentParserFactory.parse_document(file_path)
            chunker = DocumentChunker(target_chunk_tokens=target_tokens, overlap_tokens=overlap_tokens)
            chunks = chunker.chunk_document(doc)
            return ToolResult(
                success=True,
                output={
                    "doc_id": doc.doc_id,
                    "title": doc.title,
                    "chunk_count": len(chunks),
                    "first_chunk_preview": chunks[0].text[:200] if chunks else "",
                },
                duration_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.time() - start) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if result.success and result.output.get("chunk_count", 0) >= 0:
            return ToolVerification(
                verified=True, details=f"Generated {result.output.get('chunk_count')} structure-aware chunks."
            )
        return ToolVerification(verified=False, details=result.error or "Chunking failed.")


class DocumentIndexTool(BaseTool):
    """Embeds document chunks and stores them in a local SQLite vector store."""
    name = "document_index"
    description = "Index document chunks into semantic vector store for hybrid retrieval."
    risk_level = RiskLevel.MEDIUM
    permission_level = PermissionLevel.LEVEL_1_REVERSIBLE_WRITE

    parameters = [
        ToolParameter("file_path", "string", "Path to document file to index", required=True),
        ToolParameter("db_path", "string", "Optional database path", required=False, default="data/document_intelligence.db"),
    ]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        start = time.time()
        file_path = arguments.get("file_path", "")
        db_path = arguments.get("db_path", "data/document_intelligence.db")

        if not os.path.exists(file_path):
            return ToolResult(success=False, output=None, error=f"File not found: {file_path}")

        try:
            doc = DocumentParserFactory.parse_document(file_path)
            chunker = DocumentChunker()
            chunks = chunker.chunk_document(doc)
            index = DocumentIndex(db_path=db_path)
            indexed_count = index.index_chunks(chunks, doc_id=doc.doc_id)
            return ToolResult(
                success=True,
                output={
                    "doc_id": doc.doc_id,
                    "title": doc.title,
                    "indexed_chunks": indexed_count,
                    "db_path": db_path,
                },
                duration_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.time() - start) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if result.success and result.output.get("indexed_chunks", 0) > 0:
            return ToolVerification(
                verified=True, details=f"Indexed {result.output.get('indexed_chunks')} chunks into vector database."
            )
        return ToolVerification(verified=False, details=result.error or "Indexing failed.")


class DocumentRetrieveTool(BaseTool):
    """Retrieves top-k relevant document chunks using hybrid semantic search."""
    name = "document_retrieve"
    description = "Retrieve relevant document passages for a query using hybrid cosine and lexical search."
    risk_level = RiskLevel.LOW
    permission_level = PermissionLevel.LEVEL_0_READ

    parameters = [
        ToolParameter("query", "string", "Search query or question", required=True),
        ToolParameter("top_k", "integer", "Number of chunks to retrieve", required=False, default=3),
        ToolParameter("doc_id", "string", "Optional doc_id filter", required=False),
        ToolParameter("db_path", "string", "Database path", required=False, default="data/document_intelligence.db"),
    ]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        start = time.time()
        query = arguments.get("query", "")
        top_k = int(arguments.get("top_k", 3))
        doc_id = arguments.get("doc_id")
        db_path = arguments.get("db_path", "data/document_intelligence.db")

        try:
            index = DocumentIndex(db_path=db_path)
            chunks = index.hybrid_search(query, top_k=top_k, doc_id=doc_id)
            results = [c.to_dict() for c in chunks]
            return ToolResult(
                success=True,
                output={"query": query, "retrieved_count": len(results), "chunks": results},
                duration_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.time() - start) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if result.success:
            return ToolVerification(
                verified=True, details=f"Retrieved {result.output.get('retrieved_count')} chunks for query."
            )
        return ToolVerification(verified=False, details=result.error or "Retrieval failed.")


class DocumentSummarizeTool(BaseTool):
    """Summarizes a document in comprehensive, executive, or bullet mode."""
    name = "document_summarize"
    description = "Generate an executive, comprehensive, or bulleted summary of a document."
    risk_level = RiskLevel.LOW
    permission_level = PermissionLevel.LEVEL_0_READ

    parameters = [
        ToolParameter("file_path", "string", "Path to document file", required=True),
        ToolParameter("mode", "string", "Summary style: comprehensive, executive, bullet", required=False, default="comprehensive"),
        ToolParameter("max_words", "integer", "Approximate word budget", required=False, default=300),
    ]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        start = time.time()
        file_path = arguments.get("file_path", "")
        mode = arguments.get("mode", "comprehensive")
        max_words = int(arguments.get("max_words", 300))

        if not os.path.exists(file_path):
            return ToolResult(success=False, output=None, error=f"File not found: {file_path}")

        try:
            doc = DocumentParserFactory.parse_document(file_path)
            analyzer = DocumentAnalyzer()
            summary = analyzer.summarize(doc, mode=mode, max_words=max_words)
            return ToolResult(
                success=True,
                output={"title": doc.title, "mode": mode, "summary": summary},
                duration_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.time() - start) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if result.success and result.output.get("summary"):
            return ToolVerification(verified=True, details="Document summary generated successfully.")
        return ToolVerification(verified=False, details=result.error or "Summarization failed.")


class DocumentExtractTopicsTool(BaseTool):
    """Extracts core topics, formulas, and themes from a document."""
    name = "document_extract_topics"
    description = "Extract key topics, conceptual themes, and high-yield concepts from a document."
    risk_level = RiskLevel.LOW
    permission_level = PermissionLevel.LEVEL_0_READ

    parameters = [
        ToolParameter("file_path", "string", "Path to document file", required=True),
        ToolParameter("top_n", "integer", "Number of topics to extract", required=False, default=8),
    ]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        start = time.time()
        file_path = arguments.get("file_path", "")
        top_n = int(arguments.get("top_n", 8))

        if not os.path.exists(file_path):
            return ToolResult(success=False, output=None, error=f"File not found: {file_path}")

        try:
            doc = DocumentParserFactory.parse_document(file_path)
            analyzer = DocumentAnalyzer()
            topics = analyzer.extract_important_topics(doc, top_n=top_n)
            return ToolResult(
                success=True,
                output={"title": doc.title, "topics": topics},
                duration_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.time() - start) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if result.success and result.output.get("topics"):
            return ToolVerification(
                verified=True, details=f"Extracted {len(result.output.get('topics'))} core topics."
            )
        return ToolVerification(verified=False, details=result.error or "Topic extraction failed.")


class DocumentGenerateNotesTool(BaseTool):
    """Generates Cornell or hierarchical study notes from a document."""
    name = "document_generate_notes"
    description = "Generate structured study notes (Cornell style or hierarchical outline) from a document."
    risk_level = RiskLevel.MEDIUM
    permission_level = PermissionLevel.LEVEL_1_REVERSIBLE_WRITE

    parameters = [
        ToolParameter("file_path", "string", "Path to document file", required=True),
        ToolParameter("style", "string", "Notes style: cornell or outline", required=False, default="cornell"),
        ToolParameter("save_to_path", "string", "Optional file path to save the generated notes markdown", required=False),
    ]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        start = time.time()
        file_path = arguments.get("file_path", "")
        style = arguments.get("style", "cornell")
        save_path = arguments.get("save_to_path")

        if not os.path.exists(file_path):
            return ToolResult(success=False, output=None, error=f"File not found: {file_path}")

        try:
            doc = DocumentParserFactory.parse_document(file_path)
            analyzer = DocumentAnalyzer()
            notes = analyzer.generate_notes(doc, style=style)

            saved_path_actual = None
            if save_path:
                os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(notes)
                saved_path_actual = save_path

            return ToolResult(
                success=True,
                output={"title": doc.title, "style": style, "notes": notes, "saved_to": saved_path_actual},
                duration_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.time() - start) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if result.success and result.output.get("notes"):
            return ToolVerification(verified=True, details="Study notes generated successfully.")
        return ToolVerification(verified=False, details=result.error or "Note generation failed.")


class DocumentGenerateQuestionsTool(BaseTool):
    """Generates practice and exam questions with answer keys."""
    name = "document_generate_questions"
    description = "Generate exam-level conceptual and practice questions with answer guidelines from a document."
    risk_level = RiskLevel.LOW
    permission_level = PermissionLevel.LEVEL_0_READ

    parameters = [
        ToolParameter("file_path", "string", "Path to document file", required=True),
        ToolParameter("count", "integer", "Number of questions to generate", required=False, default=5),
    ]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        start = time.time()
        file_path = arguments.get("file_path", "")
        count = int(arguments.get("count", 5))

        if not os.path.exists(file_path):
            return ToolResult(success=False, output=None, error=f"File not found: {file_path}")

        try:
            doc = DocumentParserFactory.parse_document(file_path)
            analyzer = DocumentAnalyzer()
            questions = analyzer.generate_questions(doc, count=count)
            return ToolResult(
                success=True,
                output={"title": doc.title, "question_count": len(questions), "questions": questions},
                duration_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.time() - start) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if result.success and result.output.get("questions"):
            return ToolVerification(
                verified=True, details=f"Generated {len(result.output.get('questions'))} study questions."
            )
        return ToolVerification(verified=False, details=result.error or "Question generation failed.")


class DocumentAnswerQuestionTool(BaseTool):
    """Answers questions strictly grounded in document text."""
    name = "document_answer_question"
    description = "Answer questions grounded strictly in document contents."
    risk_level = RiskLevel.LOW
    permission_level = PermissionLevel.LEVEL_0_READ

    parameters = [
        ToolParameter("question", "string", "The question to answer", required=True),
        ToolParameter("file_path", "string", "Path to document file", required=True),
    ]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        start = time.time()
        question = arguments.get("question", "")
        file_path = arguments.get("file_path", "")

        if not os.path.exists(file_path):
            return ToolResult(success=False, output=None, error=f"File not found: {file_path}")

        try:
            doc = DocumentParserFactory.parse_document(file_path)
            analyzer = DocumentAnalyzer()
            answer = analyzer.answer_question(question, doc)
            return ToolResult(
                success=True,
                output={"question": question, "answer": answer, "source_document": doc.title},
                duration_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.time() - start) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if result.success and result.output.get("answer"):
            return ToolVerification(verified=True, details="Question answered based on document context.")
        return ToolVerification(verified=False, details=result.error or "Answer generation failed.")


class DocumentCompareTool(BaseTool):
    """Compares multiple documents identifying common themes and differences."""
    name = "document_compare"
    description = "Compare multiple documents for commonalities, conceptual differences, and progression."
    risk_level = RiskLevel.LOW
    permission_level = PermissionLevel.LEVEL_0_READ

    parameters = [
        ToolParameter("file_paths", "array", "List of paths to document files", required=True),
    ]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        start = time.time()
        file_paths = arguments.get("file_paths", [])

        if not isinstance(file_paths, list) or len(file_paths) < 2:
            return ToolResult(success=False, output=None, error="Provide at least two document paths to compare.")

        try:
            docs = [DocumentParserFactory.parse_document(p) for p in file_paths if os.path.exists(p)]
            if len(docs) < 2:
                return ToolResult(success=False, output=None, error="At least two valid documents are required.")

            analyzer = DocumentAnalyzer()
            comparison = analyzer.compare_documents(docs)
            return ToolResult(
                success=True,
                output=comparison,
                duration_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.time() - start) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if result.success and result.output.get("comparison_summary"):
            return ToolVerification(verified=True, details="Multi-document comparison completed successfully.")
        return ToolVerification(verified=False, details=result.error or "Document comparison failed.")


class DocumentExamPrepTool(BaseTool):
    """Generates an end-to-end exam revision pack across one or more documents."""
    name = "document_exam_prep"
    description = "Generate an exam revision pack including high-yield topics, formulas, sample questions, and revision notes."
    risk_level = RiskLevel.MEDIUM
    permission_level = PermissionLevel.LEVEL_1_REVERSIBLE_WRITE

    parameters = [
        ToolParameter("file_paths", "array", "List of document paths to study for the exam", required=True),
        ToolParameter("course_or_subject", "string", "Course or subject name (e.g. ECE, Computer Networks)", required=False, default="Upcoming Exam"),
        ToolParameter("save_to_path", "string", "Optional markdown file path to save the complete revision pack", required=False),
    ]

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        start = time.time()
        file_paths = arguments.get("file_paths", [])
        course = arguments.get("course_or_subject", "Upcoming Exam")
        save_path = arguments.get("save_to_path")

        if isinstance(file_paths, str):
            file_paths = [file_paths]

        docs: List[ParsedDocument] = []
        for p in file_paths:
            if os.path.exists(p):
                docs.append(DocumentParserFactory.parse_document(p))

        if not docs:
            return ToolResult(success=False, output=None, error="No valid document files found at provided paths.")

        try:
            analyzer = DocumentAnalyzer()
            pack = analyzer.exam_oriented_summarization(docs, course_or_subject=course)
            md_content = pack.to_markdown()

            saved_file = None
            if save_path:
                os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(md_content)
                saved_file = save_path

            return ToolResult(
                success=True,
                output={
                    "course": course,
                    "documents_count": len(docs),
                    "high_yield_topics": pack.high_yield_topics,
                    "sample_questions_count": len(pack.sample_questions),
                    "saved_to": saved_file,
                    "markdown_preview": md_content[:600],
                },
                duration_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return ToolResult(success=False, output=None, error=str(e), duration_ms=(time.time() - start) * 1000)

    def verify(self, arguments: Dict[str, Any], result: ToolResult) -> ToolVerification:
        if result.success and result.output.get("high_yield_topics"):
            return ToolVerification(
                verified=True,
                details=f"Exam revision pack generated with {len(result.output.get('high_yield_topics'))} high-yield topics.",
            )
        return ToolVerification(verified=False, details=result.error or "Exam preparation failed.")
