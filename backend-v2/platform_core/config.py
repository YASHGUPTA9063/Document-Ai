"""
Config Loader
=============
Loads the platform YAML config, resolves ${ENV_VAR} references
from the .env file, and provides a typed config dict.

Usage:
    from platform_core.config import load_config
    config = load_config()                          # Auto-discovers config/platform.yaml
    config = load_config("config/platform.yaml")    # Explicit path
"""

import os
import re
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _resolve_env_vars(value: Any) -> Any:
    """
    Recursively resolve ${ENV_VAR} references in config values.

    Examples:
        "${MISTRAL_API_KEY}" → actual value from os.environ
        "postgresql://${DB_HOST}:5432" → "postgresql://localhost:5432"
    """
    if isinstance(value, str):
        pattern = re.compile(r"\$\{([^}]+)\}")
        matches = pattern.findall(value)
        for var_name in matches:
            env_val = os.environ.get(var_name, "")
            if not env_val:
                logger.warning(f"[Config] Environment variable '{var_name}' not set")
            value = value.replace(f"${{{var_name}}}", env_val)
        return value
    elif isinstance(value, dict):
        return {k: _resolve_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_resolve_env_vars(item) for item in value]
    return value


def _load_dotenv(env_path: str | None = None):
    """Load .env file into os.environ (simple parser, no external deps)."""
    if env_path is None:
        # Look for .env in the backend-v2 directory
        env_path = str(Path(__file__).parent.parent / ".env")

    if not os.path.exists(env_path):
        logger.warning(f"[Config] .env file not found at {env_path}")
        return

    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # Remove surrounding quotes
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            else:
                # Strip trailing inline comments from unquoted values, matching
                # python-dotenv: a '#' only starts a comment when preceded by
                # whitespace, so values that legitimately contain '#' (API keys,
                # URL fragments) survive intact.
                #
                # Without this, a line like
                #     ENABLE_PREPROCESSING=true   # turn on the step
                # lands in os.environ verbatim and makes pydantic's Settings
                # bool parsing fail for any module that imports `config` after
                # load_config() has run.
                comment = re.search(r"\s+#", value)
                if comment:
                    value = value[: comment.start()].rstrip()
            os.environ.setdefault(key, value)

    logger.info(f"[Config] Loaded .env from {env_path}")


def load_config(
    config_path: str | None = None,
    env_path: str | None = None,
) -> dict:
    """
    Load and return the fully resolved platform config.

    Steps:
        1. Load .env into os.environ
        2. Parse YAML config file
        3. Resolve all ${ENV_VAR} references
        4. Return the config dict

    Args:
        config_path: Path to platform.yaml. Defaults to config/platform.yaml
                     relative to backend-v2/.
        env_path: Path to .env file. Defaults to backend-v2/.env.

    Returns:
        Fully resolved config dict.
    """
    import yaml

    # Step 1: Load .env
    _load_dotenv(env_path)

    # Step 2: Find and parse YAML
    if config_path is None:
        config_path = str(Path(__file__).parent.parent / "config" / "platform.yaml")

    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Platform config not found: {config_path}. "
            f"Create config/platform.yaml from the template."
        )

    with open(config_path, encoding="utf-8") as f:
        raw_config = yaml.safe_load(f)

    logger.info(f"[Config] Loaded config from {config_path}")

    # Step 3: Resolve environment variables
    config = _resolve_env_vars(raw_config)

    return config


def load_agent_configs() -> list[dict]:
    """
    Return the Mistral Studio agent catalogue from root-level agents_config.py.

    `agents_config.py` is the source of truth for every agent's name,
    description, instructions and model, and is what create_or_update_agents.py
    provisions from. It deliberately imports nothing from config.py — it is
    loaded before the Agent IDs it defines exist in .env — so this accessor
    reaches into it rather than the other way round, keeping that one-way
    dependency intact.

    Returns an empty list if the module is unavailable, so platform config
    loading never hard-depends on it.
    """
    try:
        import agents_config

        return list(getattr(agents_config, "AGENT_CONFIGS", []))
    except Exception as e:
        logger.warning(f"[Config] Could not load agents_config.py: {e}")
        return []


def load_config_with_agents(
    config_path: str | None = None,
    env_path: str | None = None,
) -> dict:
    """
    `load_config()` plus an `agents` section built from agents_config.py.

    The merged dict gains:
        agents:
          all:       [ ...every agent definition... ]
          by_env_var: { CLASSIFIER_AGENT_ID: {...}, ... }
          claim:     [ ... ]   # CLAIM_* agents
          face:      [ ... ]   # FACE_*  agents
          signature: [ ... ]   # SIGNATURE_* agents

    An explicit `agents` block already present in platform.yaml wins, so the
    YAML stays authoritative if someone overrides it there.
    """
    config = load_config(config_path=config_path, env_path=env_path)

    if "agents" in config:
        return config

    agents = load_agent_configs()
    if not agents:
        return config

    def _group(prefix: str) -> list[dict]:
        return [a for a in agents if str(a.get("env_var", "")).startswith(prefix)]

    config["agents"] = {
        "all": agents,
        "by_env_var": {a["env_var"]: a for a in agents if a.get("env_var")},
        "claim": _group("CLAIM_"),
        "face": _group("FACE_"),
        "signature": _group("SIGNATURE_"),
    }
    logger.info(f"[Config] Merged {len(agents)} agent definitions from agents_config.py")
    return config


def get_config_value(config: dict, path: str, default: Any = None) -> Any:
    """
    Get a nested config value using dot notation.

    Example:
        get_config_value(config, "providers.llm.mistral.params.model")
        → "mistral-large-latest"
    """
    keys = path.split(".")
    current = config
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current
