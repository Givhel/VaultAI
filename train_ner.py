#!/usr/bin/env python3
"""
train_ner.py — Fine-tune a spaCy NER model for PII detection.

Dataset : ai4privacy/pii-masking-400k (Hugging Face)
Base    : en_core_web_sm  (upgraded to en_core_web_lg for better accuracy)
Tracks  : precision, recall, F1 per entity type → MLflow
Saves   : best model to models/ner_pii/  + MLflow model registry

Usage:
    python train_ner.py                        # default 30 epochs, 3000 samples
    python train_ner.py --epochs 50            # more epochs
    python train_ner.py --samples 5000         # more training data
    python train_ner.py --base en_core_web_lg  # better base model
    python train_ner.py --no-gpu               # force CPU
"""

import argparse
import json
import os
import random
import time
from pathlib import Path

import mlflow
import mlflow.spacy
import spacy
from spacy.tokens import DocBin
from spacy.training import Example
from spacy.util import minibatch, compounding
from datasets import load_dataset

# ── Entity type mapping: AI4Privacy label → spaCy label ──────────────────────
LABEL_MAP = {
    "FIRSTNAME":      "PERSON",
    "LASTNAME":       "PERSON",
    "FULLNAME":       "PERSON",
    "NAME":           "PERSON",
    "EMAIL":          "EMAIL_ADDRESS",
    "EMAILADDRESS":   "EMAIL_ADDRESS",
    "PHONENUMBER":    "PHONE_NUMBER",
    "PHONE":          "PHONE_NUMBER",
    "CREDITCARDNUMBER": "CREDIT_CARD",
    "CREDITCARD":     "CREDIT_CARD",
    "SSN":            "US_SSN",
    "SOCIALSECURITY": "US_SSN",
    "STREET":         "LOCATION",
    "CITY":           "LOCATION",
    "STATE":          "LOCATION",
    "ZIPCODE":        "LOCATION",
    "COUNTRY":        "LOCATION",
    "ADDRESS":        "LOCATION",
    "LOCATION":       "LOCATION",
    "DATE":           "DATE_TIME",
    "DATEOFBIRTH":    "DATE_TIME",
    "TIME":           "DATE_TIME",
    "IPADDRESS":      "IP_ADDRESS",
    "IP":             "IP_ADDRESS",
    "USERNAME":       "NRP",
    "PASSWORD":       "NRP",
    "IDCARD":         "US_DRIVER_LICENSE",
    "DRIVERLICENSE":  "US_DRIVER_LICENSE",
    "PASSPORT":       "US_PASSPORT",
    "PASSPORTNUMBER": "US_PASSPORT",
    "IBAN":           "IBAN_CODE",
    "ACCOUNTNUMBER":  "US_BANK_NUMBER",
    "BANKNUMBER":     "US_BANK_NUMBER",
}

TARGET_LABELS = list(set(LABEL_MAP.values()))


# ── Dataset loading and conversion ───────────────────────────────────────────

def load_ai4privacy(num_samples: int = 3000, split: str = "train"):
    """
    Load AI4Privacy dataset from Hugging Face and convert to spaCy format.
    Returns list of (text, {"entities": [(start, end, label), ...]}) tuples.
    """
    print(f"📥 Loading AI4Privacy dataset ({num_samples} samples)...")
    ds = load_dataset(
        "ai4privacy/pii-masking-400k",
        split=split,
        streaming=True,
        trust_remote_code=True,
    )

    training_data = []
    skipped = 0

    for i, row in enumerate(ds):
        if len(training_data) >= num_samples:
            break

        text = row.get("source_text", "")
        masks = row.get("privacy_mask", [])

        if not text or not masks:
            continue

        entities = []
        for mask in masks:
            raw_label = mask.get("label", "").upper().replace("_", "").replace("-", "")
            spacy_label = LABEL_MAP.get(raw_label)
            if not spacy_label:
                continue

            start = mask.get("start", -1)
            end   = mask.get("end",   -1)
            if start < 0 or end <= start or end > len(text):
                continue

            entities.append((start, end, spacy_label))

        # Remove overlapping spans (keep first)
        entities = _remove_overlapping(entities)

        if entities:
            training_data.append((text, {"entities": entities}))
        else:
            skipped += 1

    print(f"✅ Loaded {len(training_data)} training examples ({skipped} skipped — no valid entities)")
    return training_data


def _remove_overlapping(entities: list) -> list:
    """Remove overlapping entity spans, keeping the first occurrence."""
    entities = sorted(entities, key=lambda e: e[0])
    result = []
    last_end = -1
    for start, end, label in entities:
        if start >= last_end:
            result.append((start, end, label))
            last_end = end
    return result


def to_spacy_docbin(nlp, training_data: list, path: Path):
    """Convert training data to spaCy DocBin format."""
    db = DocBin()
    errors = 0
    for text, annotations in training_data:
        doc = nlp.make_doc(text)
        try:
            example = Example.from_dict(doc, annotations)
            db.add(example.reference)
        except Exception:
            errors += 1
    if errors:
        print(f"  ⚠️  {errors} examples skipped during DocBin conversion")
    db.to_disk(path)
    return db


# ── Model setup ───────────────────────────────────────────────────────────────

def build_model(base_model: str = "en_core_web_sm") -> spacy.language.Language:
    """Load base model and configure NER for PII labels."""
    print(f"🧠 Loading base model: {base_model}")
    nlp = spacy.load(base_model)

    # Remove existing NER and add fresh one with PII labels
    if "ner" in nlp.pipe_names:
        nlp.remove_pipe("ner")

    ner = nlp.add_pipe("ner", last=True)
    for label in TARGET_LABELS:
        ner.add_label(label)

    print(f"✅ NER configured with {len(TARGET_LABELS)} entity types: {TARGET_LABELS}")
    return nlp


# ── Training loop ─────────────────────────────────────────────────────────────

def train(
    nlp,
    train_data: list,
    val_data: list,
    output_dir: Path,
    n_epochs: int = 30,
    batch_size_start: int = 4,
    batch_size_end: int = 32,
    dropout: float = 0.35,
    experiment_name: str = "vault-ai-ner-training",
):
    # 🔥 ADD THIS
    print("⚙️ Initializing the model...")
    optimizer = nlp.initialize()
    
    """Fine-tune NER and log all metrics to MLflow."""

    mlflow.set_tracking_uri(f"file:{os.path.abspath('./mlruns')}")
    if mlflow.get_experiment_by_name(experiment_name) is None:
        mlflow.create_experiment(experiment_name)
    mlflow.set_experiment(experiment_name)

    output_dir.mkdir(parents=True, exist_ok=True)

    with mlflow.start_run(run_name=f"ner_finetune_{n_epochs}ep_{len(train_data)}samples"):

        # Log hyperparameters
        mlflow.log_params({
            "base_model":        nlp.meta.get("name", "unknown"),
            "n_epochs":          n_epochs,
            "train_samples":     len(train_data),
            "val_samples":       len(val_data),
            "dropout":           dropout,
            "batch_size_start":  batch_size_start,
            "batch_size_end":    batch_size_end,
            "target_labels":     ",".join(TARGET_LABELS),
            "n_labels":          len(TARGET_LABELS),
        })

        # Disable all pipes except NER during training
        other_pipes = [p for p in nlp.pipe_names if p != "ner"]
        best_f1 = 0.0
        best_epoch = 0

        print(f"\n🚀 Training for {n_epochs} epochs on {len(train_data)} examples...\n")
        start_time = time.time()

        with nlp.disable_pipes(*other_pipes):
            optimizer = nlp.resume_training()

            for epoch in range(1, n_epochs + 1):
                random.shuffle(train_data)
                losses = {}

                batches = minibatch(
                    train_data,
                    size=compounding(batch_size_start, batch_size_end, 1.001),
                )
                for batch in batches:
                    examples = []
                    for text, annotations in batch:
                        doc = nlp.make_doc(text)
                        try:
                            example = Example.from_dict(doc, annotations)
                            examples.append(example)
                        except Exception:
                            continue
                    if examples:
                        nlp.update(examples, drop=dropout, losses=losses)

                # ── Evaluate on validation set ────────────────────────
                scores = _evaluate(nlp, val_data)
                f1    = scores["f1"]
                prec  = scores["precision"]
                rec   = scores["recall"]
                loss  = losses.get("ner", 0.0)

                # Log per-epoch metrics
                mlflow.log_metrics({
                    "train_loss":         round(loss, 4),
                    "val_precision":      round(prec, 4),
                    "val_recall":         round(rec, 4),
                    "val_f1":             round(f1, 4),
                }, step=epoch)

                # Log per-entity-type F1
                for label, label_scores in scores.get("per_entity", {}).items():
                    safe_label = label.lower().replace("_", "")
                    mlflow.log_metric(f"f1_{safe_label}", round(label_scores.get("f1", 0), 4), step=epoch)

                elapsed = time.time() - start_time
                print(
                    f"Epoch {epoch:3d}/{n_epochs} | "
                    f"Loss: {loss:7.2f} | "
                    f"P: {prec:.3f}  R: {rec:.3f}  F1: {f1:.3f} | "
                    f"⏱ {elapsed:.0f}s"
                )

                # Save best model
                if f1 > best_f1:
                    best_f1    = f1
                    best_epoch = epoch
                    nlp.to_disk(output_dir)
                    print(f"  💾 New best model saved (F1={best_f1:.4f})")

        total_time = time.time() - start_time

        # Log summary
        mlflow.log_metrics({
            "best_val_f1":    round(best_f1, 4),
            "best_epoch":     best_epoch,
            "training_time_sec": round(total_time, 1),
        })

        # Log model artifact
        mlflow.log_artifacts(str(output_dir), artifact_path="ner_model")

        print(f"\n✅ Training complete!")
        print(f"   Best F1: {best_f1:.4f} at epoch {best_epoch}")
        print(f"   Model saved to: {output_dir}")
        print(f"   Total time: {total_time:.0f}s")

    return best_f1


# ── Evaluation ────────────────────────────────────────────────────────────────

def _evaluate(nlp, val_data: list) -> dict:
    """Compute precision, recall, F1 on validation set."""
    tp_total = fp_total = fn_total = 0
    per_entity = {label: {"tp": 0, "fp": 0, "fn": 0} for label in TARGET_LABELS}

    for text, annotations in val_data:
        doc = nlp(text)
        pred_ents = {(e.start_char, e.end_char, e.label_) for e in doc.ents}
        true_ents = set()
        for start, end, label in annotations.get("entities", []):
            if label in TARGET_LABELS:
                true_ents.add((start, end, label))

        for ent in pred_ents:
            if ent in true_ents:
                tp_total += 1
                per_entity[ent[2]]["tp"] += 1
            else:
                fp_total += 1
                per_entity[ent[2]]["fp"] += 1

        for ent in true_ents:
            if ent not in pred_ents:
                fn_total += 1
                per_entity[ent[2]]["fn"] += 1

    prec = tp_total / (tp_total + fp_total + 1e-9)
    rec  = tp_total / (tp_total + fn_total + 1e-9)
    f1   = 2 * prec * rec / (prec + rec + 1e-9)

    per_entity_scores = {}
    for label, counts in per_entity.items():
        tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
        p = tp / (tp + fp + 1e-9)
        r = tp / (tp + fn + 1e-9)
        f = 2 * p * r / (p + r + 1e-9)
        per_entity_scores[label] = {"precision": p, "recall": r, "f1": f}

    return {"precision": prec, "recall": rec, "f1": f1, "per_entity": per_entity_scores}


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Fine-tune spaCy NER for PII detection")
    parser.add_argument("--samples",  type=int,   default=3000,          help="Training samples to use")
    parser.add_argument("--epochs",   type=int,   default=30,            help="Training epochs")
    parser.add_argument("--base",     type=str,   default="en_core_web_sm", help="Base spaCy model")
    parser.add_argument("--output",   type=str,   default="models/ner_pii", help="Output directory")
    parser.add_argument("--val-split",type=float, default=0.15,          help="Validation split fraction")
    parser.add_argument("--dropout",  type=float, default=0.35,          help="Dropout rate")
    parser.add_argument("--no-gpu",   action="store_true",               help="Force CPU training")
    args = parser.parse_args()

    if not args.no_gpu:
        gpu = spacy.prefer_gpu()
        print(f"🖥️  GPU: {'enabled' if gpu else 'not available, using CPU'}")

    # Load and split data
    all_data = load_ai4privacy(num_samples=args.samples)

    val_size  = int(len(all_data) * args.val_split)
    random.shuffle(all_data)
    val_data   = all_data[:val_size]
    train_data = all_data[val_size:]

    print(f"📊 Train: {len(train_data)}  |  Val: {len(val_data)}")

    # Build model
    nlp = build_model(base_model=args.base)

    # Train
    output_dir = Path(args.output)
    best_f1 = train(
        nlp=nlp,
        train_data=train_data,
        val_data=val_data,
        output_dir=output_dir,
        n_epochs=args.epochs,
        dropout=args.dropout,
    )

    print(f"\n🎯 Done. Best validation F1: {best_f1:.4f}")
    print(f"📂 Model saved to: {output_dir}")
    print(f"   Use it in Vault-AI by setting: USE_TRAINED_NER=true in .env")


if __name__ == "__main__":
    main()
