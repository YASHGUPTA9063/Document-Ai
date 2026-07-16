"""
Prompt Manager
==============
Loads and caches system prompts from local markdown files.

Replaces Mistral Agent IDs (pre-configured on Mistral Studio) with
locally-managed system prompt files. This makes the system provider-agnostic
— the same prompt works with any LLM provider.

Prompt files are stored in platform/prompts/*.md and loaded on demand.
"""

import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class PromptManager:
    """
    Loads system prompts from the prompts/ directory.

    Usage:
        prompts = PromptManager()
        system_prompt = prompts.get("classifier")
        # Returns the content of platform/prompts/classifier.md
    """

    def __init__(self, prompts_dir: str | None = None):
        if prompts_dir is None:
            # Default: platform/prompts/ relative to this file
            prompts_dir = str(Path(__file__).parent)
        self._dir = prompts_dir
        self._cache: dict[str, str] = {}
        logger.info(f"[PromptManager] Prompts directory: {self._dir}")

    def get(self, agent_name: str) -> str:
        """
        Load the system prompt for a given agent by name.

        Args:
            agent_name: Name of the agent (e.g., "classifier", "extractor").
                        Maps to a file: platform/prompts/{agent_name}.md

        Returns:
            The system prompt string.

        Raises:
            FileNotFoundError: If the prompt file does not exist.
        """
        if agent_name not in self._cache:
            path = os.path.join(self._dir, f"{agent_name}.md")
            if not os.path.exists(path):
                raise FileNotFoundError(
                    f"Prompt file not found: {path}. "
                    f"Create a file at platform/prompts/{agent_name}.md "
                    f"with the system prompt for the '{agent_name}' agent."
                )
            with open(path, encoding="utf-8") as f:
                self._cache[agent_name] = f.read()
            logger.info(f"[PromptManager] Loaded prompt: {agent_name} ({len(self._cache[agent_name])} chars)")
        return self._cache[agent_name]

    def get_or_default(self, agent_name: str, default: str = "") -> str:
        """Load a prompt, returning `default` if the file doesn't exist."""
        try:
            return self.get(agent_name)
        except FileNotFoundError:
            logger.warning(
                f"[PromptManager] No prompt file for '{agent_name}', using default"
            )
            return default

    def reload(self):
        """Clear the cache — useful after editing prompts in production."""
        self._cache.clear()
        logger.info("[PromptManager] Cache cleared, prompts will reload on next access")

    def list_available(self) -> list[str]:
        """List all available prompt names (without .md extension)."""
        prompts = []
        for f in os.listdir(self._dir):
            if f.endswith(".md") and not f.startswith("_"):
                prompts.append(f[:-3])
        return sorted(prompts)
