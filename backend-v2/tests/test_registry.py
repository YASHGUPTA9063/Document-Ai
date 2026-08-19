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

    def test_get_raises_before_init(self):
        """ProviderRegistry.get() raises if not initialized."""
        from platform_core.registry import ProviderRegistry

        ProviderRegistry._instance = None

        with pytest.raises(Exception):
            ProviderRegistry.get()

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
