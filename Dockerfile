FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir \
    streamlit==1.38.0 \
    python-dotenv==1.0.1 \
    presidio-analyzer==2.2.355 \
    presidio-anonymizer==2.2.355 \
    chromadb==0.4.24 \
    sentence-transformers==2.7.0 \
    cryptography==43.0.1 \
    httpx==0.27.2 \
    PyPDF2==3.0.1 \
    numpy==1.26.4 \
    plotly==5.24.1 \
    pandas==2.2.3 \
    setuptools==69.5.1

RUN pip install --no-cache-dir spacy==3.7.5
RUN python -m spacy download en_core_web_sm

COPY . .

RUN mkdir -p /tmp/chroma_data /tmp/vault_data /tmp/mlruns

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "streamlit_app.py", \
     "--server.port=8501", \
     "--server.headless=true", \
     "--server.address=0.0.0.0"]
