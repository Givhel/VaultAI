# Vault-AI 🛡️
**Privacy-Preserving Document Intelligence with ML-Ops Pipeline**

A privacy-first RAG (Retrieval-Augmented Generation) system that detects and encrypts PII in documents, supports differential privacy on embeddings, and tracks ML experiments via MLflow.

---

## 🚀 Quick Start

### 1. Clone and set up environment

```bash
git clone <your-repo>
cd vault_ai

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
```

### 2. Install dependencies

```bash
# With small spaCy model (faster, default)
make install

# With large spaCy model (better NER accuracy)
make install-lg
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env and add your GROQ_API_KEY (free at https://console.groq.com)
```

### 4. Run the app

```bash
make dev
# Open http://localhost:8501
```

---

## 🧠 NER Model Training (ML component)

Fine-tune a spaCy NER model on the AI4Privacy dataset for better PII detection:

```bash
# Quick training (30 epochs, 3000 samples, en_core_web_sm)
make train

# Full training (50 epochs, 5000 samples, en_core_web_lg — recommended)
make install-lg
make train-lg

# Custom training
python train_ner.py --samples 5000 --epochs 50 --base en_core_web_lg
```

After training completes:
1. Set `USE_TRAINED_NER=true` in `.env`
2. Restart the app — it will use your fine-tuned model automatically

View training metrics (loss, F1, precision, recall per entity type):
```bash
make mlflow
# Open http://localhost:5001 → vault-ai-ner-training experiment
```

---

## 📊 ML Experiments

The Experiments page (tab 4 in sidebar) tracks:

| Experiment | What it measures |
|---|---|
| Pipeline Runs | Upload latency, entity counts, processing time |
| Embedding Comparison | MiniLM-L6 vs L12 — similarity scores, embed time |
| Privacy-Utility Tradeoff | Epsilon sweep → cosine similarity degradation curve |
| PII Detection Confidence | Presidio score distributions, threshold sensitivity |
| Retrieval Quality | Precision@K, mean similarity, latency per query |

---

## 🏗️ Project Structure

```
vault_ai/
├── streamlit_app.py          # Home page
├── train_ner.py              # NER fine-tuning script (ML component)
├── config.py                 # Configuration
├── components.py             # Shared sidebar
├── pages/
│   ├── 1_📤_Upload.py        # Document upload pipeline
│   ├── 2_🔍_Query.py         # RAG query + decrypt
│   ├── 3_🔒_Vault.py         # Encrypted vault viewer
│   └── 4_📊_Experiments.py   # ML experiment dashboard
├── services/
│   ├── pii_detector.py       # PII detection (Presidio + trained NER)
│   ├── tokenizer.py          # PII tokenization
│   ├── encryption.py         # AES-256-GCM vault
│   ├── differential_privacy.py # Laplace noise injection
│   ├── vector_store.py       # ChromaDB + embeddings
│   ├── llm_service.py        # Groq/Llama-3 RAG
│   └── experiment_tracker.py # MLflow integration
├── models/
│   └── ner_pii/              # Fine-tuned NER model (created by train_ner.py)
├── tests/                    # Pytest test suite
├── requirements.txt
├── Makefile
├── Dockerfile
└── docker-compose.yml
```

---

## ⚙️ All Commands

```bash
# Setup
make install          # Install deps + download en_core_web_sm
make install-lg       # Install deps + download en_core_web_lg

# Run
make dev              # Start Streamlit on port 8501
make mlflow           # Start MLflow UI on port 5001

# ML Training
make train            # Train NER (small model, quick)
make train-lg         # Train NER (large model, better accuracy)

# Tests
make test             # Run all pytest tests

# Docker
make docker-up        # Build and start with Docker Compose
make docker-down      # Stop containers

# Cleanup
make clean            # Remove data dirs and caches
make clean-model      # Remove trained model
```

---

## ⚠️ Known Limitation

**Person name detection in fallback mode (Presidio + en_core_web_sm):**
spaCy's base model is trained on Western English corpora and reliably detects common Western names. It may miss South Asian, East Asian, or other non-Western names. Running `train_ner.py` fine-tunes the model on the AI4Privacy dataset which contains diverse name origins and resolves this limitation.

---

## 🔐 Environment Variables

| Variable | Default | Description |
|---|---|---|
| `GROQ_API_KEY` | — | **Required.** Get free at console.groq.com |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | LLM model name |
| `DP_EPSILON` | `1.0` | Differential privacy budget |
| `USE_TRAINED_NER` | `false` | Use fine-tuned NER after training |
| `MLFLOW_TRACKING_URI` | `file:./mlruns` | MLflow backend |
| `CHROMA_PERSIST_DIR` | `./chroma_data` | ChromaDB storage |
| `VAULT_DATA_DIR` | `./vault_data` | Encrypted vault storage |
