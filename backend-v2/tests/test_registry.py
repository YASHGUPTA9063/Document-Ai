"""
Registry Unit Tests
====================
Tests for the ProviderRegistry singleton and provider lookup.
"""

import pytest
from unittest.mock import MagicMock, patch


class TestProviderRegistry:
    """Tests for the ProviderRegistry class."""

    def test_singleton_pattern(self):
        """ProviderRegistry.get() returns the same instance after initialization."""
        from platform_core.registry import ProviderRegistry

        # Reset singleton for test isolation
        ProviderRegistry._instance = None

        with patch("platform_core.registry.ProviderRegistry.from_config") as mock_from:
            mock_registry = MagicMock()
            mock_from.return_value = mock_registry
            ProviderRegistry._instance = mock_registry

            r1 = ProviderRegistry.get()
            r2 = ProviderRegistry.get()
            assert r1 is r2

    def test_get_returns_an_empty_registry_before_init(self):
        """
        get() lazily creates an EMPTY registry rather than raising.

        This is the mechanism behind the quietest failure mode in the system:
        activities/extractor.py resolves the vLLM fallback through
        ProviderRegistry.get(), and if nothing called from_config() first, the
        lookup fails against an empty registry and the caller's except-clause
        swallows it. Nothing is logged, and second-pass extraction simply never
        runs.

        The test pins the behaviour so it cannot change silently, and
        bootstrap.init_platform() is what guarantees every process populates
        the registry before serving traffic.
        """
        from platform_core.registry import ProviderRegistry

        ProviderRegistry._instance = None
        registry = ProviderRegistry.get()

        assert registry.summary()["llm"] == []
        with pytest.raises(Exception):
            registry.get_llm("vllm_fallback")

    def test_from_config_installs_the_singleton(self):
        """
        bootstrap.init_platform() relies on from_config() setting the singleton
        — that is the single line keeping the vLLM fallback alive in the
        workflow-worker process.
        """
        from platform_core.registry import ProviderRegistry

        ProviderRegistry._instance = None
        built = ProviderRegistry.from_config({"providers": {}, "fallback_chains": {}})

        assert ProviderRegistry.get() is built

    def test_get_llm_returns_provider(self):
        """Registry.get_llm() returns a registered LLM provider."""
        from platform_core.registry import ProviderRegistry

        mock_llm = MagicMock()
        mock_llm.name = "mistral"

        registry = MagicMock(spec=ProviderRegistry)
        registry.get_llm.return_value = mock_llm

        result = registry.get_llm()
        assert result.name == "mistral"

    def test_get_vision_returns_provider(self):
        """Registry.get_vision() returns a registered Vision provider."""
        from platform_core.registry import ProviderRegistry

        mock_vision = MagicMock()
        mock_vision.name = "mistral_vision"

        registry = MagicMock(spec=ProviderRegistry)
        registry.get_vision.return_value = mock_vision

        result = registry.get_vision()
        assert result.name == "mistral_vision"
