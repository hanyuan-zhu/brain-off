"""
Embedding service using DashScope API.
"""
from typing import List, Optional
import httpx
from src.config import settings


class EmbeddingService:
    """Service for generating text embeddings using DashScope API."""

    def __init__(self):
        self.api_key = settings.dashscope_api_key
        self.base_url = settings.dashscope_base_url
        self.model = settings.dashscope_embedding_model
        self.client = httpx.AsyncClient(timeout=30.0)

    async def generate(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Input text to embed

        Returns:
            List of floats representing the embedding vector
        """
        embeddings = await self.generate_batch([text])
        return embeddings[0]

    async def generate_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batch.

        Args:
            texts: List of input texts to embed

        Returns:
            List of embedding vectors
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "input": texts
        }

        response = await self.client.post(
            f"{self.base_url}/embeddings",
            headers=headers,
            json=payload
        )
        response.raise_for_status()

        data = response.json()
        embeddings = [item["embedding"] for item in data["data"]]
        return embeddings

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# Global embedding service instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get or create the global embedding service instance."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
