"""
Experiment Tracker Service
MLflow integration for tracking ML experiments across the Vault-AI pipeline.

Tracks four categories of genuine ML metrics:
  1. Embedding model comparison (MiniLM-L6 vs MiniLM-L12)
  2. Privacy-utility tradeoff (epsilon vs retrieval similarity)
  3. PII detection confidence distribution and threshold sensitivity
  4. Retrieval quality (precision@k, mean similarity, latency)
"""

import os
import mlflow
from mlflow.tracking import MlflowClient
from config import Config


class ExperimentTracker:
    """MLflow-based experiment tracker for Vault-AI ML pipeline."""

    EXPERIMENT_NAME    = "vault-ai-pipeline"
    EXP_EMBEDDING      = "vault-ai-embedding-comparison"
    EXP_PRIVACY        = "vault-ai-privacy-utility"
    EXP_PII            = "vault-ai-pii-detection"
    EXP_RETRIEVAL      = "vault-ai-retrieval-quality"

    def __init__(self):
        tracking_uri = Config.MLFLOW_TRACKING_URI
        mlflow.set_tracking_uri(tracking_uri)
        self._client = MlflowClient(tracking_uri=tracking_uri)
        for exp_name in [
            self.EXPERIMENT_NAME, self.EXP_EMBEDDING,
            self.EXP_PRIVACY, self.EXP_PII, self.EXP_RETRIEVAL,
        ]:
            if self._client.get_experiment_by_name(exp_name) is None:
                mlflow.create_experiment(exp_name)

    # ── 1. Upload (pipeline run) ──────────────────────────────────────────────

    def log_upload(
        self,
        doc_name: str,
        num_entities: int,
        processing_time: float,
        num_chunks: int,
        epsilon: float,
        doc_stats: dict = None,
        entity_scores: list = None,   # list of Presidio confidence scores
        embedding_model: str = None,
    ):
        """Log a document upload with full ML metrics."""
        mlflow.set_experiment(self.EXPERIMENT_NAME)
        with mlflow.start_run(run_name=f"upload_{doc_name[:30]}"):
            mlflow.log_params({
                "document": doc_name[:100],
                "operation": "upload",
                "dp_epsilon": str(epsilon),
                "embedding_model": embedding_model or Config.EMBEDDING_MODEL,
            })
            mlflow.log_metrics({
                "pii_entities_detected": num_entities,
                "processing_time_sec": round(processing_time, 3),
                "num_chunks": num_chunks,
            })
            if doc_stats:
                mlflow.log_metrics({
                    "word_count": doc_stats.get("word_count", 0),
                    "char_count": doc_stats.get("char_count", 0),
                })
            # PII confidence stats
            if entity_scores:
                mlflow.log_metrics({
                    "pii_avg_confidence": round(sum(entity_scores) / len(entity_scores), 3),
                    "pii_min_confidence": round(min(entity_scores), 3),
                    "pii_max_confidence": round(max(entity_scores), 3),
                    "pii_high_confidence_count": sum(1 for s in entity_scores if s >= 0.8),
                    "pii_low_confidence_count":  sum(1 for s in entity_scores if s < 0.6),
                })

        # Also log to PII experiment for cross-run analysis
        self.log_pii_detection(
            doc_name=doc_name,
            entities_detected=num_entities,
            entity_scores=entity_scores or [],
            threshold_used=0.4,
            processing_time=processing_time,
        )

    # ── 2. Query (retrieval quality) ─────────────────────────────────────────

    def log_query(
        self,
        query_preview: str,
        latency: float,
        num_results: int,
        similarity_scores: list = None,   # cosine similarity per retrieved chunk
        model: str = None,
    ):
        """Log a query with retrieval quality metrics."""
        mlflow.set_experiment(self.EXPERIMENT_NAME)
        with mlflow.start_run(run_name="query"):
            mlflow.log_params({
                "query_preview": query_preview[:50],
                "operation": "query",
                "llm_model": model or Config.GROQ_MODEL,
            })
            metrics = {
                "query_latency_sec": round(latency, 3),
                "retrieval_results": num_results,
            }
            if similarity_scores:
                metrics.update({
                    "top1_similarity":  round(similarity_scores[0], 3),
                    "mean_similarity":  round(sum(similarity_scores) / len(similarity_scores), 3),
                    "min_similarity":   round(min(similarity_scores), 3),
                })
            mlflow.log_metrics(metrics)

        # Also log to retrieval experiment
        self.log_retrieval_quality(
            query_preview=query_preview,
            latency=latency,
            num_results=num_results,
            similarity_scores=similarity_scores or [],
            model=model or Config.GROQ_MODEL,
        )

    # ── 3. Embedding model comparison experiment ──────────────────────────────

    def log_embedding_experiment(
        self,
        model_name: str,
        doc_name: str,
        query: str,
        similarity_scores: list,
        embedding_time_sec: float,
        epsilon: float,
        num_chunks: int,
    ):
        """
        Log one run of an embedding model comparison.
        Run with different model_name values to compare MiniLM-L6 vs L12.
        """
        mlflow.set_experiment(self.EXP_EMBEDDING)
        with mlflow.start_run(run_name=f"embed_{model_name.split('/')[-1][:20]}"):
            mlflow.log_params({
                "model_name":  model_name,
                "document":    doc_name[:80],
                "query":       query[:80],
                "dp_epsilon":  str(epsilon),
                "num_chunks":  str(num_chunks),
            })
            metrics = {
                "embedding_time_sec": round(embedding_time_sec, 3),
                "num_chunks": num_chunks,
            }
            if similarity_scores:
                metrics.update({
                    "top1_similarity":  round(similarity_scores[0], 3),
                    "mean_similarity":  round(sum(similarity_scores) / len(similarity_scores), 3),
                    "min_similarity":   round(min(similarity_scores), 3),
                    "precision_at_1":   1.0 if similarity_scores[0] > 0.5 else 0.0,
                    "precision_at_3":   round(sum(1 for s in similarity_scores[:3] if s > 0.5) / min(3, len(similarity_scores)), 3),
                })
            mlflow.log_metrics(metrics)

    # ── 4. Privacy-utility tradeoff experiment ────────────────────────────────

    def log_privacy_utility(
        self,
        epsilon: float,
        similarity_before_noise: float,
        similarity_after_noise: float,
        noise_scale: float,
        doc_name: str,
    ):
        """
        Log one epsilon setting in the privacy-utility tradeoff curve.
        Run across multiple epsilon values to generate the tradeoff curve.
        """
        mlflow.set_experiment(self.EXP_PRIVACY)
        with mlflow.start_run(run_name=f"epsilon_{epsilon}"):
            mlflow.log_params({
                "document":   doc_name[:80],
                "epsilon":    str(epsilon),
            })
            utility_drop = round(similarity_before_noise - similarity_after_noise, 4)
            mlflow.log_metrics({
                "epsilon":                  epsilon,
                "noise_scale":              round(noise_scale, 4),
                "similarity_before_noise":  round(similarity_before_noise, 4),
                "similarity_after_noise":   round(similarity_after_noise, 4),
                "utility_drop":             utility_drop,
                "utility_retention_pct":    round((1 - utility_drop) * 100, 2),
            })

    # ── 5. PII detection experiment ───────────────────────────────────────────

    def log_pii_detection(
        self,
        doc_name: str,
        entities_detected: int,
        entity_scores: list,
        threshold_used: float,
        processing_time: float,
    ):
        """Log PII detection metrics for confidence analysis."""
        mlflow.set_experiment(self.EXP_PII)
        with mlflow.start_run(run_name=f"pii_{doc_name[:25]}"):
            mlflow.log_params({
                "document":        doc_name[:80],
                "threshold_used":  str(threshold_used),
            })
            metrics = {
                "entities_detected":   entities_detected,
                "threshold_used":      threshold_used,
                "processing_time_sec": round(processing_time, 3),
            }
            if entity_scores:
                metrics.update({
                    "avg_confidence":        round(sum(entity_scores) / len(entity_scores), 3),
                    "min_confidence":        round(min(entity_scores), 3),
                    "max_confidence":        round(max(entity_scores), 3),
                    "high_conf_count":       sum(1 for s in entity_scores if s >= 0.8),
                    "medium_conf_count":     sum(1 for s in entity_scores if 0.6 <= s < 0.8),
                    "low_conf_count":        sum(1 for s in entity_scores if s < 0.6),
                    "score_std":             round(float(__import__('statistics').stdev(entity_scores)) if len(entity_scores) > 1 else 0.0, 3),
                })
            mlflow.log_metrics(metrics)

    # ── 6. Retrieval quality experiment ───────────────────────────────────────

    def log_retrieval_quality(
        self,
        query_preview: str,
        latency: float,
        num_results: int,
        similarity_scores: list,
        model: str,
    ):
        """Log retrieval quality metrics for a query."""
        mlflow.set_experiment(self.EXP_RETRIEVAL)
        with mlflow.start_run(run_name=f"retrieval_{query_preview[:20]}"):
            mlflow.log_params({
                "query":       query_preview[:80],
                "llm_model":   model,
                "top_k":       str(num_results),
            })
            metrics = {
                "latency_sec":   round(latency, 3),
                "num_retrieved": num_results,
            }
            if similarity_scores:
                above_threshold = [s for s in similarity_scores if s > 0.5]
                metrics.update({
                    "top1_similarity":   round(similarity_scores[0], 3),
                    "mean_similarity":   round(sum(similarity_scores) / len(similarity_scores), 3),
                    "min_similarity":    round(min(similarity_scores), 3),
                    "precision_at_k":    round(len(above_threshold) / len(similarity_scores), 3),
                    "relevant_chunks":   len(above_threshold),
                })
            mlflow.log_metrics(metrics)

    # ── Getters ───────────────────────────────────────────────────────────────

    def get_runs(self, max_results: int = 100, experiment_name: str = None) -> list:
        exp_name = experiment_name or self.EXPERIMENT_NAME
        experiment = self._client.get_experiment_by_name(exp_name)
        if experiment is None:
            return []
        runs = self._client.search_runs(
            experiment_ids=[experiment.experiment_id],
            order_by=["start_time DESC"],
            max_results=max_results,
        )
        return [
            {
                "run_id":    run.info.run_id,
                "run_name":  run.info.run_name or "unnamed",
                "status":    run.info.status,
                "start_time": run.info.start_time,
                "params":    dict(run.data.params),
                "metrics":   dict(run.data.metrics),
            }
            for run in runs
        ]

    def get_all_experiments_runs(self) -> dict:
        """Get runs from all experiments keyed by experiment name."""
        return {
            "pipeline":   self.get_runs(experiment_name=self.EXPERIMENT_NAME),
            "embedding":  self.get_runs(experiment_name=self.EXP_EMBEDDING),
            "privacy":    self.get_runs(experiment_name=self.EXP_PRIVACY),
            "pii":        self.get_runs(experiment_name=self.EXP_PII),
            "retrieval":  self.get_runs(experiment_name=self.EXP_RETRIEVAL),
        }

    def get_metrics_summary(self) -> dict:
        runs = self.get_runs(max_results=100)
        if not runs:
            return {"total_runs": 0}

        uploads = [r for r in runs if r["params"].get("operation") == "upload"]
        queries  = [r for r in runs if r["params"].get("operation") == "query"]

        summary = {
            "total_runs":    len(runs),
            "total_uploads": len(uploads),
            "total_queries": len(queries),
        }

        if uploads:
            entities   = [r["metrics"].get("pii_entities_detected", 0) for r in uploads]
            proc_times = [r["metrics"].get("processing_time_sec", 0)   for r in uploads]
            summary["avg_entities_per_doc"]   = round(sum(entities) / len(entities), 1)
            summary["avg_processing_time"]    = round(sum(proc_times) / len(proc_times), 3)
            summary["total_entities_detected"] = int(sum(entities))

        if queries:
            latencies = [r["metrics"].get("query_latency_sec", 0) for r in queries]
            sims      = [r["metrics"].get("top1_similarity", 0)   for r in queries if "top1_similarity" in r["metrics"]]
            summary["avg_query_latency"]    = round(sum(latencies) / len(latencies), 3)
            if sims:
                summary["avg_top1_similarity"] = round(sum(sims) / len(sims), 3)

        return summary
