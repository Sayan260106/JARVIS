"""Multi-Format Document Parsers and Structural Extraction.

Supports PDF, DOCX, PPTX, TXT, Markdown, HTML webpages, and image OCR hooks.
Provides robust fallbacks (e.g. pure-Python zipfile/xml parsing) to guarantee
parsing availability across all environments.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
import html
import io
import os
import re
from typing import Any, Dict, List, Optional
import xml.etree.ElementTree as ET
import zipfile

from jarvis.subsystems.document.schemas import (
    DocumentElement,
    DocumentFormat,
    DocumentMetadata,
    ElementType,
    ParsedDocument,
)


class BaseDocumentParser(ABC):
    """Abstract interface for all document parsers."""

    @abstractmethod
    def parse(self, file_path_or_content: str | bytes, source_path: str = "") -> ParsedDocument:
        """Parses the input into a structured ParsedDocument."""
        pass


class PDFParser(BaseDocumentParser):
    """Extracts text, pages, headings, and bookmarks from PDF files."""

    def parse(self, file_path_or_content: str | bytes, source_path: str = "") -> ParsedDocument:
        raw_text_parts: List[str] = []
        elements: List[DocumentElement] = []
        page_count = 0
        title = "Untitled PDF Document"

        # Determine source
        stream: io.BytesIO
        actual_path = ""
        if isinstance(file_path_or_content, str):
            actual_path = file_path_or_content
            if not os.path.exists(file_path_or_content):
                raise FileNotFoundError(f"PDF file not found: {file_path_or_content}")
            with open(file_path_or_content, "rb") as f:
                stream = io.BytesIO(f.read())
        else:
            actual_path = source_path
            stream = io.BytesIO(file_path_or_content)

        file_size = stream.getbuffer().nbytes
        if actual_path:
            title = os.path.splitext(os.path.basename(actual_path))[0].replace("_", " ").title()

        # Try pypdf first
        parsed_via_pypdf = False
        try:
            import pypdf
            reader = pypdf.PdfReader(stream)
            page_count = len(reader.pages)

            # Metadata extraction
            if reader.metadata:
                if reader.metadata.title:
                    title = reader.metadata.title
                elements.append(
                    DocumentElement(
                        element_type=ElementType.METADATA,
                        content=f"Title: {title}, Author: {reader.metadata.author or 'Unknown'}",
                        page_number=1,
                    )
                )

            for p_idx, page in enumerate(reader.pages, 1):
                page_text = page.extract_text() or ""
                raw_text_parts.append(page_text)

                lines = [l.strip() for l in page_text.splitlines() if l.strip()]
                for line in lines:
                    # Detect headings: short line, capitalized, or starts with Lecture/Chapter/Section
                    if (
                        len(line) < 80
                        and (
                            re.match(r"^(?:lecture|chapter|unit|section|module|part)\s+\d+", line, re.I)
                            or (line.isupper() and len(line) > 3)
                            or re.match(r"^\d+(?:\.\d+)*\s+[A-Z]", line)
                        )
                    ):
                        elements.append(
                            DocumentElement(
                                element_type=ElementType.HEADING,
                                content=line,
                                level=2 if "." in line else 1,
                                page_number=p_idx,
                            )
                        )
                    elif line.startswith(("-", "*", "•")):
                        elements.append(
                            DocumentElement(
                                element_type=ElementType.LIST_ITEM,
                                content=line.lstrip("-*• ").strip(),
                                page_number=p_idx,
                            )
                        )
                    else:
                        elements.append(
                            DocumentElement(
                                element_type=ElementType.PARAGRAPH,
                                content=line,
                                page_number=p_idx,
                            )
                        )

            parsed_via_pypdf = True
        except Exception:
            pass

        # Fallback to stream regex extraction if pypdf was unavailable or extracted empty
        if not parsed_via_pypdf or not raw_text_parts or not "".join(raw_text_parts).strip():
            stream.seek(0)
            raw_data = stream.read()
            # Extract parenthesized strings Tj / TJ
            matches = re.findall(rb"\((.*?)\)\s*Tj", raw_data)
            fallback_text = " ".join(m.decode("latin-1", errors="ignore") for m in matches)
            if fallback_text.strip():
                raw_text_parts = [fallback_text]
                for line in fallback_text.splitlines():
                    cleaned = line.strip()
                    if cleaned:
                        elements.append(
                            DocumentElement(
                                element_type=ElementType.PARAGRAPH,
                                content=cleaned,
                                page_number=1,
                            )
                        )
                page_count = max(1, page_count)

        full_raw = "\n\n".join(raw_text_parts)
        meta = DocumentMetadata(
            title=title,
            page_count=max(1, page_count),
            format=DocumentFormat.PDF,
            file_size_bytes=file_size,
            source_path=actual_path,
        )

        return ParsedDocument(
            title=title,
            metadata=meta,
            elements=elements,
            raw_text=full_raw,
        )


class DocxParser(BaseDocumentParser):
    """Extracts headings, paragraphs, and tables from DOCX files."""

    def parse(self, file_path_or_content: str | bytes, source_path: str = "") -> ParsedDocument:
        elements: List[DocumentElement] = []
        raw_text_parts: List[str] = []
        actual_path = file_path_or_content if isinstance(file_path_or_content, str) else source_path
        title = os.path.splitext(os.path.basename(actual_path))[0].title() if actual_path else "Untitled Document"

        stream = (
            open(file_path_or_content, "rb")
            if isinstance(file_path_or_content, str)
            else io.BytesIO(file_path_or_content)
        )

        parsed_via_lib = False
        try:
            import docx
            doc = docx.Document(stream)
            for p in doc.paragraphs:
                txt = p.text.strip()
                if not txt:
                    continue
                raw_text_parts.append(txt)
                style_name = p.style.name.lower() if p.style else ""
                if "heading" in style_name or "title" in style_name:
                    lvl = 1
                    m = re.search(r"\d+", style_name)
                    if m:
                        lvl = int(m.group(0))
                    elements.append(DocumentElement(element_type=ElementType.HEADING, content=txt, level=lvl))
                elif p.text.startswith(("-", "*", "•")):
                    elements.append(DocumentElement(element_type=ElementType.LIST_ITEM, content=txt.lstrip("-*• ")))
                else:
                    elements.append(DocumentElement(element_type=ElementType.PARAGRAPH, content=txt))

            for table in doc.tables:
                rows_data = []
                for row in table.rows:
                    row_txt = [c.text.strip() for c in row.cells]
                    rows_data.append(" | ".join(row_txt))
                table_content = "\n".join(rows_data)
                if table_content.strip():
                    raw_text_parts.append(table_content)
                    elements.append(DocumentElement(element_type=ElementType.TABLE, content=table_content))

            parsed_via_lib = True
        except Exception:
            pass

        # Native fallback: Parse word/document.xml inside docx zip container
        if not parsed_via_lib:
            try:
                stream.seek(0)
                with zipfile.ZipFile(stream) as zf:
                    xml_content = zf.read("word/document.xml")
                    tree = ET.fromstring(xml_content)
                    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                    for p_elem in tree.iterfind(".//w:p", ns):
                        texts = [t.text for t in p_elem.iterfind(".//w:t", ns) if t.text]
                        para_txt = "".join(texts).strip()
                        if para_txt:
                            raw_text_parts.append(para_txt)
                            elements.append(DocumentElement(element_type=ElementType.PARAGRAPH, content=para_txt))
            except Exception:
                pass

        if hasattr(stream, "close") and isinstance(file_path_or_content, str):
            stream.close()

        full_raw = "\n\n".join(raw_text_parts)
        meta = DocumentMetadata(
            title=title,
            format=DocumentFormat.DOCX,
            file_size_bytes=len(full_raw),
            source_path=actual_path,
        )

        return ParsedDocument(title=title, metadata=meta, elements=elements, raw_text=full_raw)


class PptxParser(BaseDocumentParser):
    """Extracts slides, slide titles, bullet points, and notes from PPTX presentations."""

    def parse(self, file_path_or_content: str | bytes, source_path: str = "") -> ParsedDocument:
        elements: List[DocumentElement] = []
        raw_text_parts: List[str] = []
        actual_path = file_path_or_content if isinstance(file_path_or_content, str) else source_path
        title = os.path.splitext(os.path.basename(actual_path))[0].title() if actual_path else "Presentation"
        slide_count = 0

        stream = (
            open(file_path_or_content, "rb")
            if isinstance(file_path_or_content, str)
            else io.BytesIO(file_path_or_content)
        )

        parsed_via_lib = False
        try:
            import pptx
            prs = pptx.Presentation(stream)
            slide_count = len(prs.slides)
            for s_idx, slide in enumerate(prs.slides, 1):
                slide_title = ""
                if slide.shapes.title and slide.shapes.title.text:
                    slide_title = slide.shapes.title.text.strip()
                    elements.append(
                        DocumentElement(
                            element_type=ElementType.SLIDE_TITLE,
                            content=slide_title,
                            level=1,
                            page_number=s_idx,
                        )
                    )
                    raw_text_parts.append(f"Slide {s_idx}: {slide_title}")

                for shape in slide.shapes:
                    if shape.has_text_frame and shape != slide.shapes.title:
                        for paragraph in shape.text_frame.paragraphs:
                            p_txt = paragraph.text.strip()
                            if p_txt:
                                raw_text_parts.append(p_txt)
                                elements.append(
                                    DocumentElement(
                                        element_type=ElementType.SLIDE_CONTENT,
                                        content=p_txt,
                                        level=paragraph.level + 1,
                                        page_number=s_idx,
                                    )
                                )
            parsed_via_lib = True
        except Exception:
            pass

        # Native fallback: Parse ppt/slides/slide*.xml inside pptx zip container
        if not parsed_via_lib:
            try:
                stream.seek(0)
                with zipfile.ZipFile(stream) as zf:
                    slide_files = sorted(
                        [f for f in zf.namelist() if f.startswith("ppt/slides/slide") and f.endswith(".xml")]
                    )
                    slide_count = len(slide_files)
                    for s_idx, sf in enumerate(slide_files, 1):
                        content = zf.read(sf)
                        tree = ET.fromstring(content)
                        ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
                        texts = [t.text for t in tree.iterfind(".//a:t", ns) if t.text]
                        if texts:
                            slide_title = texts[0].strip()
                            elements.append(
                                DocumentElement(
                                    element_type=ElementType.SLIDE_TITLE,
                                    content=slide_title,
                                    level=1,
                                    page_number=s_idx,
                                )
                            )
                            raw_text_parts.append(f"Slide {s_idx}: {slide_title}")
                            for body in texts[1:]:
                                if body.strip():
                                    raw_text_parts.append(body.strip())
                                    elements.append(
                                        DocumentElement(
                                            element_type=ElementType.SLIDE_CONTENT,
                                            content=body.strip(),
                                            level=2,
                                            page_number=s_idx,
                                        )
                                    )
            except Exception:
                pass

        if hasattr(stream, "close") and isinstance(file_path_or_content, str):
            stream.close()

        full_raw = "\n\n".join(raw_text_parts)
        meta = DocumentMetadata(
            title=title,
            format=DocumentFormat.PPTX,
            slide_count=max(1, slide_count),
            page_count=max(1, slide_count),
            file_size_bytes=len(full_raw),
            source_path=actual_path,
        )

        return ParsedDocument(title=title, metadata=meta, elements=elements, raw_text=full_raw)


class MarkdownParser(BaseDocumentParser):
    """Parses Markdown text into structured headings, lists, tables, and paragraphs."""

    def parse(self, file_path_or_content: str | bytes, source_path: str = "") -> ParsedDocument:
        content = ""
        actual_path = ""
        if isinstance(file_path_or_content, str):
            if os.path.exists(file_path_or_content):
                actual_path = file_path_or_content
                with open(file_path_or_content, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            else:
                content = file_path_or_content
        else:
            content = file_path_or_content.decode("utf-8", errors="ignore")
            actual_path = source_path

        elements: List[DocumentElement] = []
        title = "Markdown Document"
        lines = content.splitlines()
        in_code_block = False
        code_buffer: List[str] = []

        for line in lines:
            stripped = line.strip()

            # Code fence toggle
            if stripped.startswith("```"):
                if in_code_block:
                    elements.append(
                        DocumentElement(element_type=ElementType.CODE_BLOCK, content="\n".join(code_buffer))
                    )
                    code_buffer = []
                    in_code_block = False
                else:
                    in_code_block = True
                continue

            if in_code_block:
                code_buffer.append(line)
                continue

            if not stripped:
                continue

            # Heading check: e.g. # Title, ## Subtitle
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
            if heading_match:
                level = len(heading_match.group(1))
                h_text = heading_match.group(2).strip()
                if level == 1 and title == "Markdown Document":
                    title = h_text
                elements.append(DocumentElement(element_type=ElementType.HEADING, content=h_text, level=level))
            elif re.match(r"^(?:[-*+]|\d+\.)\s+(.+)$", stripped):
                m = re.match(r"^(?:[-*+]|\d+\.)\s+(.+)$", stripped)
                elements.append(DocumentElement(element_type=ElementType.LIST_ITEM, content=m.group(1).strip()))
            elif "|" in stripped and ("---" in stripped or stripped.startswith("|")):
                elements.append(DocumentElement(element_type=ElementType.TABLE, content=stripped))
            else:
                elements.append(DocumentElement(element_type=ElementType.PARAGRAPH, content=stripped))

        meta = DocumentMetadata(
            title=title,
            format=DocumentFormat.MARKDOWN,
            file_size_bytes=len(content.encode("utf-8")),
            source_path=actual_path,
        )

        return ParsedDocument(title=title, metadata=meta, elements=elements, raw_text=content)


class TextParser(BaseDocumentParser):
    """Parses plain text files, detecting paragraphs and basic structures."""

    def parse(self, file_path_or_content: str | bytes, source_path: str = "") -> ParsedDocument:
        content = ""
        actual_path = ""
        if isinstance(file_path_or_content, str):
            if os.path.exists(file_path_or_content):
                actual_path = file_path_or_content
                for enc in ["utf-8", "utf-16", "latin-1"]:
                    try:
                        with open(file_path_or_content, "r", encoding=enc) as f:
                            content = f.read()
                            break
                    except Exception:
                        continue
            else:
                content = file_path_or_content
        else:
            content = file_path_or_content.decode("utf-8", errors="ignore")
            actual_path = source_path

        title = os.path.splitext(os.path.basename(actual_path))[0].title() if actual_path else "Text Document"
        elements: List[DocumentElement] = []
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]

        for p in paragraphs:
            lines = p.splitlines()
            first_line = lines[0].strip()
            # If first line looks like a header (short, title-cased or capitalized)
            if len(first_line) < 60 and (first_line.isupper() or len(lines) > 1 and first_line.endswith(":")):
                elements.append(DocumentElement(element_type=ElementType.HEADING, content=first_line, level=2))
                body = "\n".join(lines[1:]).strip()
                if body:
                    elements.append(DocumentElement(element_type=ElementType.PARAGRAPH, content=body))
            elif first_line.startswith(("-", "*", "•")):
                for l in lines:
                    elements.append(DocumentElement(element_type=ElementType.LIST_ITEM, content=l.lstrip("-*• ").strip()))
            else:
                elements.append(DocumentElement(element_type=ElementType.PARAGRAPH, content=p))

        meta = DocumentMetadata(
            title=title,
            format=DocumentFormat.TXT,
            file_size_bytes=len(content.encode("utf-8")),
            source_path=actual_path,
        )

        return ParsedDocument(title=title, metadata=meta, elements=elements, raw_text=content)


class HTMLParser(BaseDocumentParser):
    """Extracts articles, headings, paragraphs, and tables from HTML webpages."""

    def parse(self, file_path_or_content: str | bytes, source_path: str = "") -> ParsedDocument:
        content = ""
        actual_path = ""
        if isinstance(file_path_or_content, str):
            if os.path.exists(file_path_or_content):
                actual_path = file_path_or_content
                with open(file_path_or_content, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            else:
                content = file_path_or_content
        else:
            content = file_path_or_content.decode("utf-8", errors="ignore")
            actual_path = source_path

        elements: List[DocumentElement] = []
        title = "Webpage Document"
        raw_text_parts: List[str] = []

        parsed_via_bs4 = False
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, "html.parser")

            # Remove scripts, styles, noscript
            for tag in soup(["script", "style", "noscript", "svg", "nav", "footer"]):
                tag.decompose()

            if soup.title and soup.title.string:
                title = soup.title.string.strip()

            for elem in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "table"]):
                txt = elem.get_text(separator=" ", strip=True)
                if not txt:
                    continue
                raw_text_parts.append(txt)

                if elem.name.startswith("h"):
                    lvl = int(elem.name[1])
                    elements.append(DocumentElement(element_type=ElementType.HEADING, content=txt, level=lvl))
                elif elem.name == "li":
                    elements.append(DocumentElement(element_type=ElementType.LIST_ITEM, content=txt))
                elif elem.name == "table":
                    elements.append(DocumentElement(element_type=ElementType.TABLE, content=txt))
                else:
                    elements.append(DocumentElement(element_type=ElementType.PARAGRAPH, content=txt))

            parsed_via_bs4 = True
        except Exception:
            pass

        # Regex fallback if beautifulsoup fails
        if not parsed_via_bs4:
            # Strip tags
            t_match = re.search(r"<title>(.*?)</title>", content, re.I | re.S)
            if t_match:
                title = html.unescape(t_match.group(1)).strip()

            clean = re.sub(r"<(script|style).*?>.*?</\1>", "", content, flags=re.I | re.S)
            clean = re.sub(r"<[^>]+>", " ", clean)
            clean = html.unescape(clean)
            lines = [l.strip() for l in clean.splitlines() if l.strip()]
            for l in lines:
                raw_text_parts.append(l)
                elements.append(DocumentElement(element_type=ElementType.PARAGRAPH, content=l))

        full_raw = "\n\n".join(raw_text_parts)
        meta = DocumentMetadata(
            title=title,
            format=DocumentFormat.HTML,
            file_size_bytes=len(content.encode("utf-8")),
            source_path=actual_path,
        )

        return ParsedDocument(title=title, metadata=meta, elements=elements, raw_text=full_raw)


class DocumentParserFactory:
    """Detects format and returns appropriate BaseDocumentParser instance."""

    _parsers = {
        DocumentFormat.PDF: PDFParser(),
        DocumentFormat.DOCX: DocxParser(),
        DocumentFormat.PPTX: PptxParser(),
        DocumentFormat.TXT: TextParser(),
        DocumentFormat.MARKDOWN: MarkdownParser(),
        DocumentFormat.HTML: HTMLParser(),
    }

    @classmethod
    def get_parser(cls, path_or_content: str | bytes, format_hint: Optional[str] = None) -> BaseDocumentParser:
        fmt = cls.detect_format(path_or_content, format_hint)
        return cls._parsers.get(fmt, cls._parsers[DocumentFormat.TXT])

    @classmethod
    def detect_format(cls, path_or_content: str | bytes, format_hint: Optional[str] = None) -> DocumentFormat:
        if format_hint:
            h = format_hint.lower().lstrip(".")
            if h in ("pdf", "application/pdf"):
                return DocumentFormat.PDF
            if h in ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"):
                return DocumentFormat.DOCX
            if h in ("pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"):
                return DocumentFormat.PPTX
            if h in ("md", "markdown"):
                return DocumentFormat.MARKDOWN
            if h in ("html", "htm"):
                return DocumentFormat.HTML
            if h in ("txt", "text"):
                return DocumentFormat.TXT

        if isinstance(path_or_content, str):
            ext = os.path.splitext(path_or_content)[1].lower()
            if ext == ".pdf":
                return DocumentFormat.PDF
            if ext == ".docx":
                return DocumentFormat.DOCX
            if ext == ".pptx":
                return DocumentFormat.PPTX
            if ext in (".md", ".markdown"):
                return DocumentFormat.MARKDOWN
            if ext in (".html", ".htm"):
                return DocumentFormat.HTML
            if ext in (".txt", ".log", ".csv", ".json"):
                return DocumentFormat.TXT

        if isinstance(path_or_content, bytes):
            if path_or_content.startswith(b"%PDF"):
                return DocumentFormat.PDF
            if path_or_content.startswith(b"PK\x03\x04"):
                # Could be docx or pptx
                if b"word/" in path_or_content:
                    return DocumentFormat.DOCX
                if b"ppt/" in path_or_content:
                    return DocumentFormat.PPTX
            if b"<html" in path_or_content.lower() or b"<!doctype html" in path_or_content.lower():
                return DocumentFormat.HTML

        return DocumentFormat.TXT

    @classmethod
    def parse_document(
        cls, file_path_or_content: str | bytes, source_path: str = "", format_hint: Optional[str] = None
    ) -> ParsedDocument:
        """One-stop helper to automatically detect format and parse into ParsedDocument."""
        parser = cls.get_parser(file_path_or_content, format_hint)
        return parser.parse(file_path_or_content, source_path=source_path)
