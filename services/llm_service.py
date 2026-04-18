"""
LLM Service
Groq API client for Llama-3 inference. Used consistently in both
local development and cloud deployment for simplicity.
"""

import httpx
from config import Config


class LLMService:
    """Groq API client for Llama-3 chat completions."""

    RAG_PROMPT_TEMPLATE = """You are a helpful and precise document assistant for VaultAI, a privacy-preserving system.
Answer the user's question based ONLY on the provided context documents.
If the information is not in the context, say "I don't have enough information in the uploaded documents to answer that."
Be concise and direct. Do not make up information.

IMPORTANT — Privacy Tokens:
The documents use privacy tokens like PERSON_001, LOCATION_001, EMAIL_001, etc.
These tokens ARE the actual data values — they are just masked for privacy.
Do NOT say the information is missing, unknown, or unspecified just because you see a token.
If the document says "Address: LOCATION_001, LOCATION_002" — the address IS specified. Just report it with the tokens as-is.
The user will decrypt the tokens separately to see the real values.

Context Documents:
{context}

User Question: {query}

Answer:"""

    def __init__(self, api_key: str = None, model: str = None):
        """
        Initialize the Groq API client.

        Args:
            api_key: Groq API key. Falls back to config/env.
            model: Model name. Default: llama-3.3-70b-versatile.
        """
        self.api_key = api_key or Config.GROQ_API_KEY
        self.model = model or Config.GROQ_MODEL
        self.api_url = Config.GROQ_API_URL

    @property
    def is_configured(self) -> bool:
        """Check if the API key is set."""
        return bool(self.api_key and self.api_key != "gsk_your_api_key_here")

    def generate(self, query: str, context: str) -> str:
        """
        Generate a RAG response using Groq API.

        Args:
            query: User's question.
            context: Retrieved document context (tokenized text).

        Returns:
            LLM-generated answer string.

        Raises:
            ConnectionError: If the API call fails.
            ValueError: If the API key is not configured.
        """
        if not self.is_configured:
            raise ValueError(
                "Groq API key not configured. "
                "Set GROQ_API_KEY in your .env file. "
                "Get a free key at https://console.groq.com"
            )

        prompt = self.RAG_PROMPT_TEMPLATE.format(context=context, query=query)

        try:
            response = httpx.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 1024,
                    "top_p": 0.9,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"]

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise ValueError("Invalid Groq API key. Check your GROQ_API_KEY.")
            elif e.response.status_code == 429:
                raise ConnectionError("Groq rate limit exceeded. Wait a moment and try again.")
            else:
                raise ConnectionError(f"Groq API error: {e.response.status_code} — {e.response.text}")
        except httpx.ConnectError:
            raise ConnectionError("Cannot reach Groq API. Check your internet connection.")
        except httpx.TimeoutException:
            raise ConnectionError("Groq API request timed out. Try again.")

    def test_connection(self) -> bool:
        """
        Test the Groq API connection with a minimal request.

        Returns:
            True if the connection is working.
        """
        try:
            response = httpx.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": "Hi"}],
                    "max_tokens": 5,
                },
                timeout=10.0,
            )
            return response.status_code == 200
        except Exception:
            return False
