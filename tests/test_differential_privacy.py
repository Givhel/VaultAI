"""Tests for Differential Privacy service."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from services.differential_privacy import DifferentialPrivacy


class TestDifferentialPrivacy:
    """Test Laplace noise injection and privacy budget tracking."""

    def test_noise_changes_embedding(self):
        dp = DifferentialPrivacy(epsilon=1.0)
        original = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
        noisy = dp.add_noise(original)
        assert not np.array_equal(original, noisy)

    def test_output_is_normalized(self):
        dp = DifferentialPrivacy(epsilon=1.0)
        embedding = np.random.randn(384)
        noisy = dp.add_noise(embedding)
        norm = np.linalg.norm(noisy)
        assert abs(norm - 1.0) < 1e-6

    def test_lower_epsilon_more_noise(self):
        """Lower epsilon should produce larger deviations on average."""
        embedding = np.ones(384) / np.sqrt(384)  # Unit vector
        n_trials = 100

        dp_high = DifferentialPrivacy(epsilon=5.0)
        dp_low = DifferentialPrivacy(epsilon=0.1)

        diffs_high = []
        diffs_low = []

        for _ in range(n_trials):
            noisy_h = dp_high.add_noise(embedding.copy())
            noisy_l = dp_low.add_noise(embedding.copy())
            diffs_high.append(np.linalg.norm(noisy_h - embedding))
            diffs_low.append(np.linalg.norm(noisy_l - embedding))

        # On average, low epsilon should cause more deviation
        assert np.mean(diffs_low) > np.mean(diffs_high)

    def test_privacy_budget_tracking(self):
        dp = DifferentialPrivacy(epsilon=1.0)
        embedding = np.random.randn(384)

        assert dp.privacy_budget_used == 0
        dp.add_noise(embedding)
        assert dp.privacy_budget_used == 1.0
        dp.add_noise(embedding)
        assert dp.privacy_budget_used == 2.0

    def test_batch_noise(self):
        dp = DifferentialPrivacy(epsilon=1.0)
        embeddings = [np.random.randn(384) for _ in range(5)]
        noisy = dp.add_noise_batch(embeddings)
        assert len(noisy) == 5
        assert dp._queries_count == 5

    def test_noise_scale(self):
        dp = DifferentialPrivacy(epsilon=2.0, sensitivity=1.0)
        assert dp.noise_scale == 0.5

    def test_stats(self):
        dp = DifferentialPrivacy(epsilon=1.5)
        stats = dp.get_stats()
        assert stats["epsilon"] == 1.5
        assert stats["queries_count"] == 0
        assert "noise_scale" in stats

    def test_shape_preserved(self):
        dp = DifferentialPrivacy(epsilon=1.0)
        embedding = np.random.randn(768)
        noisy = dp.add_noise(embedding)
        assert noisy.shape == embedding.shape
