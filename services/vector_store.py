"""
Vector Store Service
ChromaDB wrapper for storing and querying document embeddings.
Uses sentence-transformers for embedding generation.
"""

import chromadb
import numpy as np
from sentence_transformers import SentenceTransformer
from config import Config


class VectorStore:
    """ChromaDB-based vector store with sentence-transformer embeddings."""

    COLLECTION_NAME = "vault_documents"

    def __init__(self, persist_dir: str = None, embedding_model: str = None):
        """
        Initialize ChromaDB client and embedding model.

        Args:
            persist_dir: Directory for persistent ChromaDB storage.
            embedding_model: Name of the sentence-transformer model.
        """
        self._persist_dir = persist_dir or Config.CHROMA_PERSIST_DIR
        self._client = chromadb.PersistentClient(path=self._persist_dir)
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        self._embedder = SentenceTransformer(embedding_model or Config.EMBEDDING_MODEL)

    def _refresh_collection(self):
        """Re-create client and collection from scratch (handles stale references after external deletion)."""
        self._client = chromadb.PersistentClient(path=self._persist_dir)
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def generate_embeddings(self, texts: list[str]) -> list[np.ndarray]:
        """
        Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of numpy embedding arrays.
        """
        embeddings = self._embedder.encode(texts, show_progress_bar=False)
        return [emb for emb in embeddings]

    def add_documents(
        self,
        doc_id: str,
        chunks: list[str],
        embeddings: list[list[float]],
        metadata: dict = None,
    ):
        """
        Add document chunks to the vector store.

        Args:
            doc_id: Unique document identifier.
            chunks: List of text chunks.
            embeddings: List of embedding vectors (as lists of floats).
            metadata: Optional metadata for each chunk.
        """
        ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [{"doc_id": doc_id, "chunk_index": i, **(metadata or {})} for i in range(len(chunks))]

        try:
            self._collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=chunks,
                metadatas=metadatas,
            )
        except Exception:
            self._refresh_collection()
            self._collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=chunks,
                metadatas=metadatas,
            )

    def query(self, query_text: str, n_results: int = None) -> dict:
        """
        Query the vector store with a text query.

        Args:
            query_text: The user's query string.
            n_results: Number of results to return (default from config).

        Returns:
            ChromaDB query results with documents, distances, and metadata.
        """
        n = n_results or Config.TOP_K_RESULTS
        query_embedding = self._embedder.encode(query_text).tolist()

        try:
            count = self._collection.count()
        except Exception:
            self._refresh_collection()
            count = self._collection.count()

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(n, count) if count > 0 else n,
            include=["documents", "distances", "metadatas"],
        )
        return results

    def get_stats(self) -> dict:
        """Get vector store statistics."""
        try:
            count = self._collection.count()
        except Exception:
            self._refresh_collection()
            count = self._collection.count()
        return {
            "total_chunks": count,
            "collection_name": self.COLLECTION_NAME,
            "persist_dir": self._persist_dir,
        }

    def clear(self):
        """Delete all documents from the collection."""
        try:
            self._client.delete_collection(self.COLLECTION_NAME)
        except Exception:
            pass
        self._refresh_collection()

    def has_documents(self) -> bool:
        """Check if the vector store has any documents."""
        try:
            return self._collection.count() > 0
        except Exception:
            self._refresh_collection()
            return self._collection.count() > 0

