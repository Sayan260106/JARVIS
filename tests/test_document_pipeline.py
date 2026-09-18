"""Unit and Integration Tests for Phase 4: Document Intelligence.

Verifies:
1. Multi-format parsing (PDF, DOCX, PPTX, TXT, Markdown, HTML).
2. Structure detection (headings, sections, paragraphs, lists, tables).
3. Structure-aware chunking with hierarchy breadcrumbs.
4. Embedding and hybrid vector retrieval in SQLite.
5. Document intelligence operations (summarize, explain, extract topics, notes, questions, compare, exam prep).
6. Typed document tools registration and execution verification.
7. End-to-end plan decomposition for:
   "Find Lecture 3 and 4 PDF and summarize them for my upcoming exam."
"""

from __future__ import annotations
import io
import os
import shutil
import tempfile
import unittest

from jarvis.capabilities.plan import DefaultPlanCapability
from jarvis.capabilities.understand import DefaultUnderstandCapability
from jarvis.core.schemas import SubsystemType, IntentCategory
from jarvis.core.state import AgentSessionState
from jarvis.subsystems.document.analyzer import DocumentAnalyzer
from jarvis.subsystems.document.chunker import DocumentChunker
from jarvis.subsystems.document.parsers import (
    DocumentParserFactory,
    HTMLParser,
    MarkdownParser,
    PDFParser,
    TextParser,
)
from jarvis.subsystems.document.retriever import DocumentIndex
from jarvis.subsystems.document.schemas import (
    DocumentFormat,
    ElementType,
    ParsedDocument,
)
from jarvis.tools import get_default_registry


def _create_minimal_valid_pdf_bytes(title: str, text: str) -> bytes:
    """Generates a minimal, standards-compliant single-page PDF with text."""
    content_stream = f"BT /F1 12 Tf 50 700 Td ({title}) Tj 0 -20 Td ({text}) Tj ET"
    stream_bytes = content_stream.encode("latin-1")
    stream_len = len(stream_bytes)

    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> >>\nendobj\n"
        b"4 0 obj\n<< /Length " + str(stream_len).encode("ascii") + b" >>\nstream\n"
        + stream_bytes +
        b"\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f \n"
        b"0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000266 00000 n \n"
        b"trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n380\n%%EOF\n"
    )
    return pdf


class TestDocumentPipeline(unittest.TestCase):
    """Test suite for Document Intelligence subsystem."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="jarvis_doc_test_")
        self.db_path = os.path.join(self.test_dir, "test_doc_vectors.db")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_pdf_parsing_and_text_extraction(self):
        """Verify PDF parser reads PDF bytes, extracts title, page count, and elements."""
        pdf_bytes = _create_minimal_valid_pdf_bytes(
            title="Lecture 3: Signal Processing",
            text="Nyquist sampling theorem states that sampling rate must be double the maximum frequency."
        )
        pdf_path = os.path.join(self.test_dir, "Lecture_3.pdf")
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)

        parser = PDFParser()
        doc = parser.parse(pdf_path)

        self.assertIsInstance(doc, ParsedDocument)
        self.assertEqual(doc.metadata.format, DocumentFormat.PDF)
        self.assertGreaterEqual(doc.metadata.page_count, 1)
        self.assertTrue("Nyquist" in doc.raw_text or "Signal Processing" in doc.raw_text)

    def test_markdown_and_html_parsing(self):
        """Verify Markdown and HTML parsing with structural element classification."""
        md_content = """# Unit 1: Control Systems
## Lecture 4: State Space Representation
State space analysis is a modern approach for multi-input multi-output systems.

- Controllability
- Observability
- Stability

```python
x_dot = A * x + B * u
```
"""
        md_path = os.path.join(self.test_dir, "lecture_4.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        doc_md = MarkdownParser().parse(md_path)
        self.assertEqual(doc_md.metadata.format, DocumentFormat.MARKDOWN)
        headings = [el.content for el in doc_md.elements if el.element_type == ElementType.HEADING]
        self.assertIn("Unit 1: Control Systems", headings)
        self.assertIn("Lecture 4: State Space Representation", headings)

        html_content = """<!DOCTYPE html>
<html>
<head><title>ECE Course Notes</title></head>
<body>
<h1>Digital Signal Processing</h1>
<p>Fourier Transform maps time-domain signals to frequency spectra.</p>
<ul>
  <li>DFT</li>
  <li>FFT</li>
</ul>
</body>
</html>"""
        doc_html = HTMLParser().parse(html_content.encode("utf-8"))
        self.assertEqual(doc_html.title, "ECE Course Notes")
        self.assertIn("Fourier Transform", doc_html.raw_text)

    def test_structure_aware_chunking(self):
        """Verify chunker preserves heading context in breadcrumbs."""
        md_content = """# ECE 401
## Frequency Response
Bode plots display the magnitude and phase of a frequency response function against log frequency.
Gain margin and phase margin indicate system stability margins.

## Transfer Functions
The Laplace transform of an output divided by the Laplace transform of the input with zero initial conditions.
"""
        doc = MarkdownParser().parse(md_content)
        chunker = DocumentChunker(target_chunk_tokens=50, overlap_tokens=10)
        chunks = chunker.chunk_document(doc)

        self.assertGreaterEqual(len(chunks), 2)
        # Check that breadcrumbs include parent hierarchy
        has_bode = any("Frequency Response" in c.breadcrumbs for c in chunks)
        self.assertTrue(has_bode)

    def test_vector_indexing_and_hybrid_retrieval(self):
        """Verify chunks can be indexed in SQLite and retrieved via hybrid search."""
        md_content = """# Communication Engineering
## Modulation Techniques
Amplitude Modulation (AM) varies the instantaneous amplitude of a high-frequency carrier wave.
Frequency Modulation (FM) provides superior noise immunity compared to AM.

## Kalman Filtering
An optimal recursive data processing algorithm that estimates state vectors from noisy measurement streams.
"""
        doc = MarkdownParser().parse(md_content)
        chunker = DocumentChunker(target_chunk_tokens=50)
        chunks = chunker.chunk_document(doc)

        index = DocumentIndex(db_path=self.db_path)
        count = index.index_chunks(chunks, doc_id=doc.doc_id)
        self.assertGreaterEqual(count, 2)

        # Retrieval for "Kalman"
        matches = index.hybrid_search("Kalman Filtering state estimation", top_k=2)
        self.assertTrue(len(matches) > 0)
        self.assertIn("Kalman", matches[0].text)

    def test_document_intelligence_operations(self):
        """Verify all document operations: summarize, explain, topics, notes, questions, exam prep."""
        md_content = """# Modern Digital Communications
## Lecture 3: Information Theory and Channel Capacity
Claude Shannon proved that the maximum rate at which information can be transmitted error-free over a channel
is given by Shannon's Theorem: C = B * log2(1 + SNR).

## Lecture 4: Error Correction Codes
Hamming codes can detect up to two-bit errors or correct one-bit errors without retransmission.
Reed-Solomon codes are non-binary cyclic error-correcting codes used extensively in digital storage.
"""
        doc = MarkdownParser().parse(md_content)
        analyzer = DocumentAnalyzer()

        # 1. Summarize
        summary = analyzer.summarize(doc, mode="bullet")
        self.assertIsInstance(summary, str)
        self.assertTrue(len(summary) > 0)

        # 2. Explain
        explanation = analyzer.explain(doc, "Shannon")
        self.assertIn("Shannon", explanation)

        # 3. Extract Topics
        topics = analyzer.extract_important_topics(doc, top_n=5)
        self.assertIsInstance(topics, list)
        self.assertTrue(any("Information" in t or "Error" in t for t in topics))

        # 4. Generate Notes (Cornell)
        notes = analyzer.generate_notes(doc, style="cornell")
        self.assertIn("Cornell", notes)

        # 5. Generate Questions
        questions = analyzer.generate_questions(doc, count=2)
        self.assertEqual(len(questions), 2)
        self.assertIn("question", questions[0])

        # 6. Exam-Oriented Summarization
        pack = analyzer.exam_oriented_summarization([doc], course_or_subject="Digital Communications")
        self.assertEqual(pack.course_or_subject, "Digital Communications")
        self.assertTrue(len(pack.high_yield_topics) > 0)
        self.assertTrue(len(pack.sample_questions) > 0)

        md_pack = pack.to_markdown()
        self.assertIn("# Exam Revision Pack: Digital Communications", md_pack)
        self.assertIn("High-Yield Topics", md_pack)

    def test_document_tools_registration_and_execution(self):
        """Verify typed document tools in registry and their execution."""
        registry = get_default_registry()
        expected_tools = [
            "document_read",
            "document_chunk",
            "document_index",
            "document_retrieve",
            "document_summarize",
            "document_extract_topics",
            "document_generate_notes",
            "document_generate_questions",
            "document_answer_question",
            "document_compare",
            "document_exam_prep",
        ]
        for t_name in expected_tools:
            tool = registry.get(t_name)
            self.assertIsNotNone(tool, f"Tool '{t_name}' not found in registry")

        # Test document_read and document_summarize on a sample file
        doc_file = os.path.join(self.test_dir, "sample.txt")
        with open(doc_file, "w", encoding="utf-8") as f:
            f.write("Signals and Systems\nLinear Time-Invariant (LTI) systems are characterized by impulse response.")

        read_tool = registry.get("document_read")
        res_read = read_tool.execute({"file_path": doc_file})
        self.assertTrue(res_read.success)
        ver_read = read_tool.verify({"file_path": doc_file}, res_read)
        self.assertTrue(ver_read.verified)

        prep_tool = registry.get("document_exam_prep")
        res_prep = prep_tool.execute({
            "file_paths": [doc_file],
            "course_or_subject": "Signals and Systems",
            "save_to_path": os.path.join(self.test_dir, "notes.md"),
        })
        self.assertTrue(res_prep.success)
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "notes.md")))

    def test_target_lecture_search_and_exam_summarize_plan(self):
        """Verify the complete user target scenario:
        'Find Lecture 3 and 4 PDF and summarize them for my upcoming exam.'
        Decomposes across Browser locate/download to Document read/chunk/index/topics/exam prep.
        """
        user_input = "Find Lecture 3 and 4 PDF and summarize them for my upcoming exam."
        understand = DefaultUnderstandCapability()
        objective = understand.understand(user_input, {})

        self.assertEqual(objective.extracted_entities.get("action"), "lecture_study_and_summarize")
        self.assertEqual(objective.extracted_entities.get("materials"), ["Lecture 3", "Lecture 4"])
        self.assertEqual(objective.extracted_entities.get("target_type"), "pdf")

        planner = DefaultPlanCapability()
        plan = planner.plan(objective, AgentSessionState(task_id="test_lecture_study"))

        tool_names = [s.tool_name for s in plan.steps]
        subsystems = [s.subsystem for s in plan.steps]

        # Verify Browser locate/download
        self.assertIn("browser_open", tool_names)
        self.assertIn("browser_detect_session", tool_names)
        self.assertIn("browser_navigate", tool_names)
        self.assertIn("browser_detect_pdfs", tool_names)
        self.assertIn("browser_download", tool_names)

        # Verify Document pipeline steps
        self.assertIn("document_read", tool_names)
        self.assertIn("document_chunk", tool_names)
        self.assertIn("document_index", tool_names)
        self.assertIn("document_extract_topics", tool_names)
        self.assertIn("document_exam_prep", tool_names)

        # Verify SubsystemType.DOCUMENT is actively used
        self.assertIn(SubsystemType.DOCUMENT, subsystems)
        self.assertIn(SubsystemType.WEB, subsystems)


if __name__ == "__main__":
    unittest.main()
