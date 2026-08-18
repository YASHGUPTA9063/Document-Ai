"""
Provider Registry
=================
Singleton registry that manages all configured provider instances.
Initialized from config at startup. Provides access to individual
providers and fallback chains.

Usage:
    # At startup (in lifespan):
    registry = ProviderRegistry.from_config(config)

    # In any feature service:
    registry = ProviderRegistry.get()
    llm = registry.get_llm("mistral")              # Single provider
    llm_chain = registry.get_llm_chain("classifier") # Fallback chain
    ocr_chain = registry.get_ocr_chain("default")    # OCR fallback chain
"""

import logging
from typing import Any
from platform_core.providers.interfaces import (
    LLMProvider,
    OCRProvider,
    StorageProvider,
    EmbeddingProvider,
    VisionProvider,
    ProviderStatus,
)
from platform_core.resilience.fallback import FallbackChain

logger = logging.getLogger(__name__)


class ProviderNotFoundError(Exception):
    """Raised when a requested provider is not registered."""
    pass


# Maps provider type strings to their implementation classes.
# New providers register themselves here.
PROVIDER_CLASSES: dict[str, dict[str, type]] = {
    "llm": {},
    "ocr": {},
    "storage": {},
    "embedding": {},
    "vision": {},
}


def _register_builtin_providers():
    """Register all built-in provider classes. Called once at import time."""
    # LLM providers
    try:
        from platform_core.providers.llm.mistral import MistralLLM
        PROVIDER_CLASSES["llm"]["mistral"] = MistralLLM
    except ImportError:
        pass

    # vLLM fallback re-extraction (branch-vm3 feature, provider-wrapped)
    try:
        from platform_core.providers.llm.vllm_fallback import VLLMFallbackProvider
        PROVIDER_CLASSES["llm"]["vllm_fallback"] = VLLMFallbackProvider
    except ImportError:
        pass

    # OCR providers
    try:
        from platform_core.providers.ocr.mistral_ocr import MistralOCR
        PROVIDER_CLASSES["ocr"]["mistral_ocr"] = MistralOCR
    except ImportError:
        pass

    # Vision providers
    try:
        from platform_core.providers.vision.mistral_vision import MistralVision
        PROVIDER_CLASSES["vision"]["mistral_vision"] = MistralVision
    except ImportError:
        pass

    # Storage providers
    try:
        from platform_core.providers.storage.local import LocalStorage
        PROVIDER_CLASSES["storage"]["local"] = LocalStorage
    except ImportError:
        pass

    # Embedding providers
    try:
        from platform_core.providers.embedding.dinov2 import DINOv2Embedding
        PROVIDER_CLASSES["embedding"]["dinov2"] = DINOv2Embedding
    except ImportError:
        pass


class ProviderRegistry:
    """
    Singleton registry that holds all configured providers.

    Provides two access patterns:
        1. get_llm("mistral") — Direct access to a named provider
        2. get_llm_chain("classifier") — Fallback chain for a specific purpose
    """

    _instance: "ProviderRegistry | None" = None

    def __init__(self):
        self._llm_providers: dict[str, LLMProvider] = {}
        self._ocr_providers: dict[str, OCRProvider] = {}
        self._storage_providers: dict[str, StorageProvider] = {}
        self._embedding_providers: dict[str, EmbeddingProvider] = {}
        self._vision_providers: dict[str, VisionProvider] = {}
        self._fallback_chains: dict[str, list[str]] = {}
        self._default_llm: str = ""
        self._default_ocr: str = ""
        self._default_storage: str = ""
        self._default_vision: str = ""

    @classmethod
    def get(cls) -> "ProviderRegistry":
        """Get the singleton registry instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset the singleton (for testing)."""
        cls._instance = None

    # ─── Registration ────────────────────────────────────────────────────

    def register_llm(self, name: str, provider: LLMProvider):
        self._llm_providers[name] = provider
        if not self._default_llm:
            self._default_llm = name
        logger.info(f"[Registry] Registered LLM provider: {name}")

    def register_ocr(self, name: str, provider: OCRProvider):
        self._ocr_providers[name] = provider
        if not self._default_ocr:
            self._default_ocr = name
        logger.info(f"[Registry] Registered OCR provider: {name}")

    def register_storage(self, name: str, provider: StorageProvider):
        self._storage_providers[name] = provider
        if not self._default_storage:
            self._default_storage = name
        logger.info(f"[Registry] Registered Storage provider: {name}")

    def register_embedding(self, name: str, provider: EmbeddingProvider):
        self._embedding_providers[name] = provider
        logger.info(f"[Registry] Registered Embedding provider: {name}")

    def register_vision(self, name: str, provider: VisionProvider):
        self._vision_providers[name] = provider
        if not self._default_vision:
            self._default_vision = name
        logger.info(f"[Registry] Registered Vision provider: {name}")

    def set_fallback_chains(self, chains: dict[str, list[str]]):
        """Set fallback chain definitions from config."""
        self._fallback_chains = chains
        logger.info(f"[Registry] Loaded {len(chains)} fallback chain definitions")

    # ─── Direct Access ───────────────────────────────────────────────────

    def get_llm(self, name: str | None = None) -> LLMProvider:
        """Get a specific LLM provider by name, or the default."""
        name = name or self._default_llm
        if name not in self._llm_providers:
            raise ProviderNotFoundError(
                f"LLM provider '{name}' not registered. "
                f"Available: {list(self._llm_providers.keys())}"
            )
        return self._llm_providers[name]

    def get_ocr(self, name: str | None = None) -> OCRProvider:
        """Get a specific OCR provider by name, or the default."""
        name = name or self._default_ocr
        if name not in self._ocr_providers:
            raise ProviderNotFoundError(
                f"OCR provider '{name}' not registered. "
                f"Available: {list(self._ocr_providers.keys())}"
            )
        return self._ocr_providers[name]

    def get_storage(self, name: str | None = None) -> StorageProvider:
        name = name or self._default_storage
        if name not in self._storage_providers:
            raise ProviderNotFoundError(
                f"Storage provider '{name}' not registered. "
                f"Available: {list(self._storage_providers.keys())}"
            )
        return self._storage_providers[name]

    def get_embedding(self, name: str) -> EmbeddingProvider:
        if name not in self._embedding_providers:
            raise ProviderNotFoundError(
                f"Embedding provider '{name}' not registered. "
                f"Available: {list(self._embedding_providers.keys())}"
            )
        return self._embedding_providers[name]

    def get_vision(self, name: str | None = None) -> VisionProvider:
        name = name or self._default_vision
        if name not in self._vision_providers:
            raise ProviderNotFoundError(
                f"Vision provider '{name}' not registered. "
                f"Available: {list(self._vision_providers.keys())}"
            )
        return self._vision_providers[name]

    # ─── Fallback Chains ─────────────────────────────────────────────────

    def get_llm_chain(self, purpose: str = "default") -> FallbackChain[LLMProvider]:
        """Get the LLM fallback chain for a specific purpose (e.g., 'classifier')."""
        chain_key = f"llm.{purpose}"
        chain_names = self._fallback_chains.get(
            chain_key, self._fallback_chains.get("llm.default", [self._default_llm])
        )
        providers = [
            self._llm_providers[n]
            for n in chain_names
            if n in self._llm_providers
        ]
        if not providers:
            raise ProviderNotFoundError(
                f"No LLM providers found for chain '{chain_key}'. "
                f"Chain config: {chain_names}"
            )
        return FallbackChain(providers, purpose=purpose)

    def get_ocr_chain(self, purpose: str = "default") -> FallbackChain[OCRProvider]:
        """Get the OCR fallback chain."""
        chain_key = f"ocr.{purpose}"
        chain_names = self._fallback_chains.get(
            chain_key, self._fallback_chains.get("ocr.default", [self._default_ocr])
        )
        providers = [
            self._ocr_providers[n]
            for n in chain_names
            if n in self._ocr_providers
        ]
        if not providers:
            raise ProviderNotFoundError(
                f"No OCR providers found for chain '{chain_key}'."
            )
        return FallbackChain(providers, purpose=purpose)

    def get_vision_chain(self, purpose: str = "default") -> FallbackChain[VisionProvider]:
        """Get the Vision fallback chain."""
        chain_key = f"vision.{purpose}"
        chain_names = self._fallback_chains.get(
            chain_key, self._fallback_chains.get("vision.default", [self._default_vision])
        )
        providers = [
            self._vision_providers[n]
            for n in chain_names
            if n in self._vision_providers
        ]
        if not providers:
            raise ProviderNotFoundError(
                f"No Vision providers found for chain '{chain_key}'."
            )
        return FallbackChain(providers, purpose=purpose)

    # ─── Factory: Build from Config ──────────────────────────────────────

    @classmethod
    def from_config(cls, config: dict) -> "ProviderRegistry":
        """
        Build a fully initialized registry from the platform config dict.

        Config format:
            providers:
              llm:
                mistral:
                  type: mistral
                  params: {api_key: ..., model: ...}
                openai:
                  type: openai
                  params: {api_key: ..., model: ...}
              ocr:
                mistral:
                  type: mistral_ocr
                  params: {api_key: ...}
            fallback_chains:
              llm.default: [mistral, openai]
              llm.classifier: [mistral, openai]
              ocr.default: [mistral]
        """
        _register_builtin_providers()

        registry = cls()
        providers_config = config.get("providers", {})

        # Register LLM providers
        for name, conf in providers_config.get("llm", {}).items():
            provider_type = conf.get("type", name)
            params = conf.get("params", {})
            if provider_type in PROVIDER_CLASSES["llm"]:
                try:
                    provider = PROVIDER_CLASSES["llm"][provider_type](**params)
                    registry.register_llm(name, provider)
                except Exception as e:
                    logger.warning(f"[Registry] Failed to init LLM '{name}': {e}")
            else:
                logger.warning(
                    f"[Registry] Unknown LLM type '{provider_type}'. "
                    f"Available: {list(PROVIDER_CLASSES['llm'].keys())}"
                )

        # Register OCR providers
        for name, conf in providers_config.get("ocr", {}).items():
            provider_type = conf.get("type", name)
            params = conf.get("params", {})
            if provider_type in PROVIDER_CLASSES["ocr"]:
                try:
                    provider = PROVIDER_CLASSES["ocr"][provider_type](**params)
                    registry.register_ocr(name, provider)
                except Exception as e:
                    logger.warning(f"[Registry] Failed to init OCR '{name}': {e}")

        # Register Storage providers
        for name, conf in providers_config.get("storage", {}).items():
            provider_type = conf.get("type", name)
            params = conf.get("params", {})
            if provider_type in PROVIDER_CLASSES["storage"]:
                try:
                    provider = PROVIDER_CLASSES["storage"][provider_type](**params)
                    registry.register_storage(name, provider)
                except Exception as e:
                    logger.warning(f"[Registry] Failed to init Storage '{name}': {e}")

        # Register Embedding providers
        for name, conf in providers_config.get("embedding", {}).items():
            provider_type = conf.get("type", name)
            params = conf.get("params", {})
            if provider_type in PROVIDER_CLASSES["embedding"]:
                try:
                    provider = PROVIDER_CLASSES["embedding"][provider_type](**params)
                    registry.register_embedding(name, provider)
                except Exception as e:
                    logger.warning(f"[Registry] Failed to init Embedding '{name}': {e}")

        # Register Vision providers
        for name, conf in providers_config.get("vision", {}).items():
            provider_type = conf.get("type", name)
            params = conf.get("params", {})
            if provider_type in PROVIDER_CLASSES["vision"]:
                try:
                    provider = PROVIDER_CLASSES["vision"][provider_type](**params)
                    registry.register_vision(name, provider)
                except Exception as e:
                    logger.warning(f"[Registry] Failed to init Vision '{name}': {e}")

        # Load fallback chains
        chains = config.get("fallback_chains", {})
        registry.set_fallback_chains(chains)

        # Set as singleton
        cls._instance = registry

        logger.info(
            f"[Registry] Initialized with "
            f"{len(registry._llm_providers)} LLM, "
            f"{len(registry._ocr_providers)} OCR, "
            f"{len(registry._storage_providers)} Storage, "
            f"{len(registry._embedding_providers)} Embedding, "
            f"{len(registry._vision_providers)} Vision providers"
        )

        return registry

    # ─── Health & Diagnostics ────────────────────────────────────────────

    async def health_check_all(self) -> dict:
        """Run health checks on all registered providers."""
        results = {}
        all_providers = [
            *((n, p) for n, p in self._llm_providers.items()),
            *((n, p) for n, p in self._ocr_providers.items()),
            *((n, p) for n, p in self._storage_providers.items()),
            *((n, p) for n, p in self._embedding_providers.items()),
            *((n, p) for n, p in self._vision_providers.items()),
        ]
        for name, provider in all_providers:
            try:
                status = await provider.health_check()
                results[name] = status.value
            except Exception as e:
                results[name] = f"error: {e}"
        return results

    def summary(self) -> dict:
        """Return a summary of registered providers for diagnostics."""
        return {
            "llm": list(self._llm_providers.keys()),
            "ocr": list(self._ocr_providers.keys()),
            "storage": list(self._storage_providers.keys()),
            "embedding": list(self._embedding_providers.keys()),
            "vision": list(self._vision_providers.keys()),
            "fallback_chains": self._fallback_chains,
        }
