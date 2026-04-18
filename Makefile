.PHONY: install install-lg dev test lint clean docker-up docker-down mlflow train train-lg

# ── Setup ──────────────────────────────────────────────────────────────────
install:
	pip install -r requirements.txt
	python -m spacy download en_core_web_sm

install-lg:
	pip install -r requirements.txt
	python -m spacy download en_core_web_lg

# ── Run app ────────────────────────────────────────────────────────────────
dev:
	streamlit run streamlit_app.py --server.port 8501

# ── NER Training ───────────────────────────────────────────────────────────
train:
	python train_ner.py --samples 3000 --epochs 30 --base en_core_web_sm

train-lg:
	python train_ner.py --samples 5000 --epochs 50 --base en_core_web_lg

# ── MLflow UI ──────────────────────────────────────────────────────────────
mlflow:
	mlflow ui --backend-store-uri ./mlruns --port 5001

# ── Tests ──────────────────────────────────────────────────────────────────
test:
	pytest tests/ -v --tb=short

# ── Docker ─────────────────────────────────────────────────────────────────
docker-up:
	docker-compose up --build -d

docker-down:
	docker-compose down

# ── Clean ──────────────────────────────────────────────────────────────────
clean:
	rm -rf chroma_data/ vault_data/ mlruns/ __pycache__/ .pytest_cache/

clean-model:
	rm -rf models/ner_pii/
