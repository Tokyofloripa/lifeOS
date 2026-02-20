"""Environment and API key management for temperature skill."""

import os
from pathlib import Path
from typing import Dict, Any, List

# Allow override via environment variable for testing
# Set TEMPERATURE_CONFIG_DIR="" for clean/no-config mode
# Set TEMPERATURE_CONFIG_DIR="/path/to/dir" for custom config location
_config_override = os.environ.get('TEMPERATURE_CONFIG_DIR')
if _config_override == "":
    # Empty string = no config file (clean mode)
    CONFIG_DIR = None
    CONFIG_FILE = None
elif _config_override:
    CONFIG_DIR = Path(_config_override)
    CONFIG_FILE = CONFIG_DIR / ".env"
else:
    CONFIG_DIR = Path.home() / ".config" / "temperature"
    CONFIG_FILE = CONFIG_DIR / ".env"


def load_env_file(path: Path) -> Dict[str, str]:
    """Load environment variables from a file."""
    env = {}
    if not path.exists():
        return env

    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, _, value = line.partition('=')
                key = key.strip()
                value = value.strip()
                # Remove quotes if present
                if value and value[0] in ('"', "'") and value[-1] == value[0]:
                    value = value[1:-1]
                if key and value:
                    env[key] = value
    return env


def get_config() -> Dict[str, Any]:
    """Load configuration from ~/.config/temperature/.env and environment.

    Environment variables take precedence over file values.
    Returns all keys as None when no config exists (graceful for Tier 1 zero-key operation).
    """
    # Load from config file first (if configured)
    file_env = load_env_file(CONFIG_FILE) if CONFIG_FILE else {}

    # Environment variables override file
    config = {
        'ALPHA_VANTAGE_KEY': os.environ.get('ALPHA_VANTAGE_KEY') or file_env.get('ALPHA_VANTAGE_KEY'),
        'COINGECKO_DEMO_KEY': os.environ.get('COINGECKO_DEMO_KEY') or file_env.get('COINGECKO_DEMO_KEY'),
        'CLOUDFLARE_API_TOKEN': os.environ.get('CLOUDFLARE_API_TOKEN') or file_env.get('CLOUDFLARE_API_TOKEN'),
        'SEMANTIC_SCHOLAR_KEY': os.environ.get('SEMANTIC_SCHOLAR_KEY') or file_env.get('SEMANTIC_SCHOLAR_KEY'),
        'SERPAPI_KEY': os.environ.get('SERPAPI_KEY') or file_env.get('SERPAPI_KEY'),
        'DATAFORSEO_LOGIN': os.environ.get('DATAFORSEO_LOGIN') or file_env.get('DATAFORSEO_LOGIN'),
        'DATAFORSEO_PASSWORD': os.environ.get('DATAFORSEO_PASSWORD') or file_env.get('DATAFORSEO_PASSWORD'),
        'GLIMPSE_API_KEY': os.environ.get('GLIMPSE_API_KEY') or file_env.get('GLIMPSE_API_KEY'),
        'GITHUB_TOKEN': os.environ.get('GITHUB_TOKEN') or file_env.get('GITHUB_TOKEN'),
    }

    return config


# Tier definitions: which sources belong to each tier and what keys they need
_TIER1_SOURCES = ["wikipedia", "gdelt", "npm", "pypi", "semantic_scholar"]

_TIER2_KEY_MAP = {
    "alpha_vantage": "ALPHA_VANTAGE_KEY",
    "coingecko": "COINGECKO_DEMO_KEY",
    "cloudflare_radar": "CLOUDFLARE_API_TOKEN",
    "semantic_scholar_keyed": "SEMANTIC_SCHOLAR_KEY",
}

_TIER3_KEY_MAP = {
    "serpapi": "SERPAPI_KEY",
    "dataforseo": "DATAFORSEO_LOGIN",  # Also needs DATAFORSEO_PASSWORD, checked below
    "glimpse": "GLIMPSE_API_KEY",
}


def get_available_tiers(config: Dict[str, Any]) -> Dict[str, List[str]]:
    """Determine which sources are available based on API keys.

    Tier 1 sources are always available (no keys needed).
    Tier 2/3 sources require specific API keys to be configured.

    Args:
        config: Configuration dict from get_config()

    Returns:
        Dict with keys "tier1", "tier2", "tier3", each containing
        a list of available source names.
    """
    tier1 = list(_TIER1_SOURCES)

    tier2 = []
    for source, key in _TIER2_KEY_MAP.items():
        if config.get(key):
            tier2.append(source)

    tier3 = []
    for source, key in _TIER3_KEY_MAP.items():
        if source == "dataforseo":
            # DataForSEO needs both login and password
            if config.get("DATAFORSEO_LOGIN") and config.get("DATAFORSEO_PASSWORD"):
                tier3.append(source)
        elif config.get(key):
            tier3.append(source)

    return {
        "tier1": tier1,
        "tier2": tier2,
        "tier3": tier3,
    }
