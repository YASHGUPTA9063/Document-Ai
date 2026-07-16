"""
Provider Interfaces
===================
Abstract base classes that define the contract every provider must implement.
All Feature Services (Layer 2) depend ONLY on these interfaces — never on
concrete vendor SDKs.

Provider Types:
    - LLMProvider       — Chat completions with tool calling
    - OCRProvider        — Document text extraction with bounding boxes
    - StorageProvider    — File/object storage (local, S3, GCS)
    - EmbeddingProvider  — Vector embedding generation (signature matching)
    - VisionProvider     — Image analysis (face/signature comparison)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from enum import Enum


# ─── Provider Health Status ──────────────────────────────────────────────────

class ProviderStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DOWN = "down"


# ─── Unified Response Types ─────────────────────────────────────────────────

@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""
    content: str
    tool_calls: list[dict] | None = None
    finish_reason: str = "stop"
    usage: dict = field(default_factory=dict)
    provider: str = ""              # Which provider served this request
    latency_ms: float = 0.0        # Round-trip latency
    raw_response: Any = None       # Original vendor response (for debugging)


@dataclass
class OCRResponse:
    """Standardized response from any OCR provider."""
    raw_text: str
    confidence: float
    pages: list[dict]
    blocks: list[dict]             # Bounding boxes for citation highlighting
    word_confidences: list[dict]
    document_annotation: Any = None
    provider: str = ""


@dataclass
class EmbeddingResponse:
    """Standardized response from any embedding provider."""
    embeddings: list[list[float]]
    model: str = ""
    provider: str = ""


# ─── Abstract Provider Interfaces ────────────────────────────────────────────

class LLMProvider(ABC):
    """
    Interface for Language Model providers.

    Replaces the current pattern where each activity imports:
        from mistralai.client import Mistral
        client = Mistral(api_key=settings.MISTRAL_API_KEY)
        response = await client.agents.complete_async(agent_id=..., messages=..., tools=...)

    New pattern:
        llm = registry.get_llm("mistral")
        response = await llm.chat(messages=..., system_prompt=..., tools=...)
    """

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        system_prompt: str = "",
        tools: list[dict] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        response_format: dict | None = None,
    ) -> LLMResponse:
        """Send a chat completion request with optional tool definitions."""
        ...

    @abstractmethod
    async def health_check(self) -> ProviderStatus:
        """Check if this provider is reachable and functional."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique provider identifier (e.g. 'mistral', 'openai')."""
        ...


class OCRProvider(ABC):
    """
    Interface for OCR / document text extraction.

    Replaces the current pattern in utils/ocr.py:
        client.ocr.process(model="mistral-ocr-latest", document=..., ...)

    New pattern:
        ocr = registry.get_ocr("mistral_ocr")
        result = await ocr.extract(file_path, pages=[0, 1])
    """

    @abstractmethod
    async def extract(
        self,
        file_path: str,
        pages: list[int] | None = None,
        include_blocks: bool = True,
    ) -> OCRResponse:
        """Extract text, confidence scores, and bounding blocks from a document."""
        ...

    @abstractmethod
    async def health_check(self) -> ProviderStatus:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...


class StorageProvider(ABC):
    """
    Interface for file/object storage.

    Replaces the current pattern in utils/file_handler.py:
        save_file(file, settings.STORAGE_DIR)

    New pattern:
        storage = registry.get_storage("local")
        key = await storage.save(data, "documents/abc123.pdf")
    """

    @abstractmethod
    async def save(self, data: bytes, key: str, metadata: dict | None = None) -> str:
        """Save data and return the storage key/path."""
        ...

    @abstractmethod
    async def get(self, key: str) -> bytes:
        """Retrieve data by key."""
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete data by key."""
        ...

    @abstractmethod
    async def get_signed_url(self, key: str, expires_seconds: int = 3600) -> str:
        """Generate a temporary access URL (for S3/GCS). Local returns file path."""
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if a key exists in storage."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...


class EmbeddingProvider(ABC):
    """
    Interface for vector embedding generation.

    Used for signature/face verification (DINOv2 embeddings).

    Replaces the current singleton pattern in utils/signature_verifier.py:
        verifier = DinoVerifier.get_instance()
        result = verifier.verify(doc_path, ref_path)

    New pattern:
        embedder = registry.get_embedding("dinov2")
        result = await embedder.embed_images([doc_path, ref_path])
    """

    @abstractmethod
    async def embed(self, inputs: list[str] | list[bytes]) -> EmbeddingResponse:
        """Generate embeddings for text strings or raw image bytes."""
        ...

    @abstractmethod
    async def embed_images(self, image_paths: list[str]) -> EmbeddingResponse:
        """Generate embeddings for image files (specialized for vision models)."""
        ...

    @abstractmethod
    async def health_check(self) -> ProviderStatus:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...


class VisionProvider(ABC):
    """
    Interface for image analysis tasks.

    Replaces the current pattern in utils/signature_verifier.py:
        response = await client.beta.conversations.start_async(
            agent_id=settings.SIGNATURE_VISION_AGENT_ID,
            inputs=[{"role": "user", "content": [image_parts]}],
        )

    New pattern:
        vision = registry.get_vision("mistral_vision")
        result = await vision.analyze(images=[doc_b64, ref_b64], prompt="Compare...")
    """

    @abstractmethod
    async def analyze(
        self,
        images: list[str],   # base64 strings, data URLs, or file paths
        prompt: str,
        response_format: dict | None = None,
    ) -> LLMResponse:
        """Analyze one or more images with a text prompt."""
        ...

    @abstractmethod
    async def health_check(self) -> ProviderStatus:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...
