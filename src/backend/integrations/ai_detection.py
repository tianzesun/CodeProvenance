"""
AI Detection Integration Clients for CodeProvenance
Provides typed clients for GPTZero and Grammarly APIs
"""

from pathlib import Path
from typing import Optional, Dict, Any, List
import httpx
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AISettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent.parent / ".env.local", extra="ignore"
    )

    GPTZERO_API_KEY: Optional[str] = None
    GRAMMARLY_API_KEY: Optional[str] = None


settings = AISettings()


class AIDetectionResult(BaseModel):
    """Standardized result format for AI detection analysis"""

    is_ai_generated: bool = Field(
        ..., description="Whether content is identified as AI generated"
    )
    probability: float = Field(..., ge=0.0, le=1.0, description="Probability score 0-1")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence score")
    sentences: Optional[List[Dict[str, Any]]] = Field(
        None, description="Per-sentence analysis"
    )
    provider: str = Field(..., description="API provider name (gptzero/grammarly)")


class GPTZeroClient:
    """
    Official GPTZero API Client
    Docs: https://gptzero.readme.io/reference/overview
    """

    BASE_URL = "https://api.gptzero.me/v2"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GPTZERO_API_KEY
        if not self.api_key:
            raise ValueError("GPTZero API key not configured")

        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={"X-Api-Key": self.api_key, "Content-Type": "application/json"},
            timeout=30.0,
        )

    async def analyze_text(self, text: str) -> AIDetectionResult:
        """Analyze text for AI generation probability"""
        response = await self.client.post("/predict/text", json={"document": text})
        response.raise_for_status()
        data = response.json()

        document = data["documents"][0]
        return AIDetectionResult(
            is_ai_generated=document["completely_generated_prob"] > 0.5,
            probability=document["completely_generated_prob"],
            confidence=document["average_probability"],
            sentences=document.get("sentences"),
            provider="gptzero",
        )

    async def close(self) -> None:
        await self.client.aclose()


class GrammarlyClient:
    """
    Grammarly Writing Assistance API Client
    Docs: https://developer.grammarly.com/docs/
    """

    BASE_URL = "https://api.grammarly.com/v1"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GRAMMARLY_API_KEY
        if not self.api_key:
            raise ValueError("Grammarly API key not configured")

        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def analyze_text(self, text: str) -> Dict[str, Any]:
        """Analyze text with Grammarly for grammar, tone, and plagiarism"""
        response = await self.client.post(
            "/text/check",
            json={"text": text, "dialect": "american", "domain": "academic"},
        )
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        await self.client.aclose()


async def get_ai_detection_client(provider: str = "gptzero") -> Any:
    """Factory method to get appropriate AI detection client"""
    if provider.lower() == "gptzero":
        return GPTZeroClient()
    elif provider.lower() == "grammarly":
        return GrammarlyClient()
    else:
        raise ValueError(f"Unsupported AI detection provider: {provider}")
