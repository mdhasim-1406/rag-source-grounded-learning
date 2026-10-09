import re
import uuid
from pathlib import Path
from typing import List, Tuple, Optional
import pymupdf  # PyMuPDF
from ..config import settings
from ..models.schemas import SourceChunk


class DocumentIngestionService:
    def __init__(self, chunk_size: int = 400, chunk_overlap: int = 60):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def parse_pdf(self, file_path: Path) -> List[Tuple[int, str]]:
        """
        Parses PDF file page-by-page preserving page numbers and text layout.
        Returns list of (page_number, page_text).
        Raises ValueError if corrupted or cannot be parsed.
        """
        pages = []
        parsed = False
        last_error = None

        try:
            doc = pymupdf.open(file_path)
            for page_idx in range(len(doc)):
                page = doc[page_idx]
                raw_text = page.get_text("text")
                text = str(raw_text) if raw_text else ""
                if text.strip():
                    cleaned_text = self._clean_text(text)
                    pages.append((page_idx + 1, cleaned_text))
            doc.close()
            parsed = True
        except Exception as e:
            last_error = e

        if not parsed:
            try:
                import pypdf
                reader = pypdf.PdfReader(str(file_path))
                for page_idx, page in enumerate(reader.pages):
                    text = page.extract_text() or ""
                    if text.strip():
                        pages.append((page_idx + 1, self._clean_text(text)))
                parsed = True
            except Exception as e:
                raise ValueError(f"Corrupted or invalid PDF file: {last_error or e}") from e

        return pages

    def parse_text_or_markdown(self, content: str) -> List[Tuple[int, str]]:
        """Parses raw text or markdown into page 1 with cleaned content."""
        cleaned = self._clean_text(content)
        if not cleaned:
            return []
        return [(1, cleaned)]

    def chunk_document(self, source_id: str, workspace_id: str, source_title: str,
                       pages: List[Tuple[int, str]]) -> List[SourceChunk]:
        """
        Hierarchical Chunking with bounded chunk_size and chunk_overlap.
        Preserves exact page references for accurate citation.
        Guarantees every chunk has length <= chunk_size words/tokens.
        """
        chunks = []
        chunk_index = 0

        for page_num, text in pages:
            paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
            if not paragraphs:
                continue

            current_chunk_words: List[str] = []

            for para in paragraphs:
                words = para.split()
                if not words:
                    continue

                idx = 0
                while idx < len(words):
                    space_left = self.chunk_size - len(current_chunk_words)

                    if space_left <= 0:
                        chunk_text = " ".join(current_chunk_words)
                        chunks.append(SourceChunk(
                            id=str(uuid.uuid4()),
                            source_id=source_id,
                            workspace_id=workspace_id,
                            source_title=source_title,
                            chunk_index=chunk_index,
                            content=chunk_text,
                            page_number=page_num,
                            token_count=len(current_chunk_words)
                        ))
                        chunk_index += 1
                        overlap_words = current_chunk_words[-self.chunk_overlap:] if len(current_chunk_words) > self.chunk_overlap else list(current_chunk_words)
                        current_chunk_words = overlap_words
                        space_left = self.chunk_size - len(current_chunk_words)
                        if space_left <= 0:
                            current_chunk_words = []
                            space_left = self.chunk_size

                    take = min(space_left, len(words) - idx)
                    current_chunk_words.extend(words[idx:idx + take])
                    idx += take

            if current_chunk_words:
                chunk_text = " ".join(current_chunk_words)
                chunks.append(SourceChunk(
                    id=str(uuid.uuid4()),
                    source_id=source_id,
                    workspace_id=workspace_id,
                    source_title=source_title,
                    chunk_index=chunk_index,
                    content=chunk_text,
                    page_number=page_num,
                    token_count=len(current_chunk_words)
                ))
                chunk_index += 1

        return chunks

    def _clean_text(self, text: str) -> str:
        # Normalize non-breaking spaces and excessive whitespaces
        text = text.replace('\xa0', ' ').replace('\r\n', '\n')
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()


ingestion_service = DocumentIngestionService(
    chunk_size=settings.chunk_size,
    chunk_overlap=settings.chunk_overlap
)
