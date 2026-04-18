"""
Vault-AI Configuration
Loads settings from environment variables with sensible defaults.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Groq API
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    GROQ_API_URL: str = "https://api.groq.com/openai/v1/chat/completions"

    # Differential Privacy
    DP_EPSILON: float = float(os.getenv("DP_EPSILON", "1.0"))

    # Storage
    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")
    VAULT_DATA_DIR: str = os.getenv("VAULT_DATA_DIR", "./vault_data")

    # MLflow
    MLFLOW_TRACKING_URI: str = os.getenv("MLFLOW_TRACKING_URI", f"file:{os.path.abspath('./mlruns')}")

    # Encryption
    PBKDF2_ITERATIONS: int = 600_000
    AES_KEY_LENGTH: int = 32  # 256 bits

    # Embedding model
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # Document processing
    CHUNK_SIZE: int = 500  # words per chunk
    CHUNK_OVERLAP: int = 50  # overlapping words between chunks

    # RAG
    TOP_K_RESULTS: int = 3
