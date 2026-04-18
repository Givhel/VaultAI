"""
Differential Privacy Service
Injects calibrated Laplace noise into embeddings before storage in the vector database.
This prevents reconstruction of original text from stored embeddings.
"""

import numpy as np
from config import Config


class DifferentialPrivacy:
    """Laplace mechanism for ε-differential privacy on embeddings."""

    def __init__(self, epsilon: float = None, sensitivity: float = 1.0):
        """
        Initialize the DP engine.

        Args:
            epsilon: Privacy parameter. Lower = more privacy, more noise.
                     Default from config (1.0).
            sensitivity: L2 sensitivity of the embedding function.
                         For normalized embeddings, this is 1.0.
        """
        self.epsilon = epsilon or Config.DP_EPSILON
        self.sensitivity = sensitivity
        self._queries_count = 0

    def add_noise(self, embedding: np.ndarray) -> np.ndarray:
        """
        Add calibrated Laplace noise to an embedding vector.

        The scale is determined by sensitivity/epsilon (Laplace mechanism).
        After noise injection, the embedding is re-normalized to unit length.

        Args:
            embedding: Original embedding vector (numpy array).

        Returns:
            Noisy embedding vector (same shape, unit normalized).
        """
        scale = self.sensitivity / self.epsilon
        noise = np.random.laplace(loc=0.0, scale=scale, size=embedding.shape)
        noisy_embedding = embedding + noise

        # Re-normalize to unit length to preserve cosine similarity properties
        norm = np.linalg.norm(noisy_embedding)
        if norm > 0:
            noisy_embedding = noisy_embedding / norm

        self._queries_count += 1
        return noisy_embedding

    def add_noise_batch(self, embeddings: list[np.ndarray]) -> list[np.ndarray]:
        """
        Add noise to a batch of embeddings.

        Args:
            embeddings: List of embedding vectors.

        Returns:
            List of noisy embedding vectors.
        """
        return [self.add_noise(emb) for emb in embeddings]

    @property
    def privacy_budget_used(self) -> float:
        """Total privacy budget consumed (ε × number of queries)."""
        return self._queries_count * self.epsilon

    @property
    def noise_scale(self) -> float:
        """Current Laplace noise scale parameter."""
        return self.sensitivity / self.epsilon

    def get_stats(self) -> dict:
        """Return privacy statistics."""
        return {
            "epsilon": self.epsilon,
            "sensitivity": self.sensitivity,
            "noise_scale": round(self.noise_scale, 4),
            "queries_count": self._queries_count,
            "budget_used": round(self.privacy_budget_used, 4),
        }
