"""
Document Processor Service
Extracts text from PDF and TXT files, then splits into overlapping chunks
for embedding and vector storage.
"""

from io import BytesIO
from PyPDF2 import PdfReader
from config import Config


class DocumentProcessor:
    """Extract text from documents and split into overlapping chunks."""

    def __init__(self, chunk_size: int = None, chunk_overlap: int = None):
        """
        Initialize the document processor.

        Args:
            chunk_size: Number of words per chunk (default from config).
            chunk_overlap: Number of overlapping words between chunks.
        """
        self.chunk_size = chunk_size or Config.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or Config.CHUNK_OVERLAP

    def extract_text(self, file_bytes: bytes, filename: str) -> str:
        """
        Extract text content from a file.

        Args:
            file_bytes: Raw file bytes.
            filename: Original filename (used to determine format).

        Returns:
            Extracted text as a string.

        Raises:
            ValueError: If file format is not supported.
        """
        lower_name = filename.lower()

        if lower_name.endswith(".pdf"):
            return self._extract_pdf(file_bytes)
        elif lower_name.endswith(".txt"):
            return file_bytes.decode("utf-8", errors="replace")
        elif lower_name.endswith(".md"):
            return file_bytes.decode("utf-8", errors="replace")
        else:
            raise ValueError(f"Unsupported file format: {filename}. Use PDF, TXT, or MD.")

    def _extract_pdf(self, file_bytes: bytes) -> str:
        """Extract text from PDF bytes."""
        reader = PdfReader(BytesIO(file_bytes))
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        return "\n".join(text_parts)

    def chunk_text(self, text: str) -> list[str]:
        """
        Split text into overlapping chunks by word count.

        Args:
            text: Full document text.

        Returns:
            List of text chunks.
        """
        words = text.split()
        if not words:
            return []

        chunks = []
        step = self.chunk_size - self.chunk_overlap

        for i in range(0, len(words), step):
            chunk_words = words[i:i + self.chunk_size]
            chunk = " ".join(chunk_words)
            if chunk.strip():
                chunks.append(chunk)

            # Stop if we've processed all words
            if i + self.chunk_size >= len(words):
                break

        return chunks

    def get_document_stats(self, text: str) -> dict:
        """
        Get statistics about a document.

        Args:
            text: Document text.

        Returns:
            Dictionary with word_count, char_count, line_count.
        """
        return {
            "word_count": len(text.split()),
            "char_count": len(text),
            "line_count": text.count("\n") + 1,
        }
