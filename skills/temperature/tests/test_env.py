"""Tests for temperature skill environment and config management."""

import os
import sys
import tempfile
from pathlib import Path

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.env import load_env_file, get_config, get_available_tiers


class TestLoadEnvFile:
    """Tests for load_env_file()."""

    def test_load_basic_env_file(self, tmp_path):
        """Test loading a basic .env file with key=value pairs."""
        env_file = tmp_path / ".env"
        env_file.write_text("KEY1=value1\nKEY2=value2\n")
        result = load_env_file(env_file)
        assert result == {"KEY1": "value1", "KEY2": "value2"}

    def test_load_missing_file_returns_empty(self, tmp_path):
        """Test loading a nonexistent file returns empty dict."""
        result = load_env_file(tmp_path / "nonexistent.env")
        assert result == {}

    def test_handles_comments(self, tmp_path):
        """Test that comment lines are skipped."""
        env_file = tmp_path / ".env"
        env_file.write_text("# This is a comment\nKEY=value\n# Another comment\n")
        result = load_env_file(env_file)
        assert result == {"KEY": "value"}

    def test_handles_double_quoted_values(self, tmp_path):
        """Test that double-quoted values have quotes stripped."""
        env_file = tmp_path / ".env"
        env_file.write_text('KEY="quoted value"\n')
        result = load_env_file(env_file)
        assert result == {"KEY": "quoted value"}

    def test_handles_single_quoted_values(self, tmp_path):
        """Test that single-quoted values have quotes stripped."""
        env_file = tmp_path / ".env"
        env_file.write_text("KEY='single quoted'\n")
        result = load_env_file(env_file)
        assert result == {"KEY": "single quoted"}

    def test_handles_empty_lines(self, tmp_path):
        """Test that empty lines are skipped."""
        env_file = tmp_path / ".env"
        env_file.write_text("KEY1=val1\n\n\nKEY2=val2\n")
        result = load_env_file(env_file)
        assert result == {"KEY1": "val1", "KEY2": "val2"}

    def test_handles_whitespace_around_key_value(self, tmp_path):
        """Test that whitespace around key and value is stripped."""
        env_file = tmp_path / ".env"
        env_file.write_text("  KEY  =  value  \n")
        result = load_env_file(env_file)
        assert result == {"KEY": "value"}

    def test_handles_equals_in_value(self, tmp_path):
        """Test that = in value is preserved (partition on first =)."""
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=val=ue=with=equals\n")
        result = load_env_file(env_file)
        assert result == {"KEY": "val=ue=with=equals"}


class TestGetConfig:
    """Tests for get_config()."""

    def test_all_keys_none_with_no_config(self):
        """Test that all keys are None when no config exists (clean mode)."""
        # Save and clear any env vars that might interfere
        saved = {}
        config_keys = [
            'ALPHA_VANTAGE_KEY', 'COINGECKO_DEMO_KEY', 'CLOUDFLARE_API_TOKEN',
            'SEMANTIC_SCHOLAR_KEY', 'SERPAPI_KEY', 'DATAFORSEO_LOGIN',
            'DATAFORSEO_PASSWORD', 'GLIMPSE_API_KEY', 'GITHUB_TOKEN',
        ]
        for key in config_keys:
            saved[key] = os.environ.pop(key, None)

        try:
            config = get_config()
            assert all(v is None for v in config.values()), \
                f"Expected all None, got: {config}"
            # Verify all expected keys are present
            for key in config_keys:
                assert key in config, f"Missing key: {key}"
        finally:
            # Restore env vars
            for key, val in saved.items():
                if val is not None:
                    os.environ[key] = val

    def test_reads_from_env_var(self):
        """Test that env vars override file values."""
        saved = os.environ.get('ALPHA_VANTAGE_KEY')
        try:
            os.environ['ALPHA_VANTAGE_KEY'] = 'test-key-123'
            config = get_config()
            assert config['ALPHA_VANTAGE_KEY'] == 'test-key-123'
        finally:
            if saved is not None:
                os.environ['ALPHA_VANTAGE_KEY'] = saved
            else:
                os.environ.pop('ALPHA_VANTAGE_KEY', None)

    def test_returns_nine_keys(self):
        """Test that config returns exactly 9 keys."""
        config = get_config()
        assert len(config) == 9


class TestGetAvailableTiers:
    """Tests for get_available_tiers()."""

    def test_empty_config_has_5_tier1_sources(self):
        """Test that empty config returns 5 Tier 1 sources (always available)."""
        config = {k: None for k in [
            'ALPHA_VANTAGE_KEY', 'COINGECKO_DEMO_KEY', 'CLOUDFLARE_API_TOKEN',
            'SEMANTIC_SCHOLAR_KEY', 'SERPAPI_KEY', 'DATAFORSEO_LOGIN',
            'DATAFORSEO_PASSWORD', 'GLIMPSE_API_KEY', 'GITHUB_TOKEN',
        ]}
        tiers = get_available_tiers(config)
        assert len(tiers['tier1']) == 5
        assert tiers['tier2'] == []
        assert tiers['tier3'] == []

    def test_tier1_always_contains_expected_sources(self):
        """Test that Tier 1 always contains the 5 free sources."""
        config = {k: None for k in [
            'ALPHA_VANTAGE_KEY', 'COINGECKO_DEMO_KEY', 'CLOUDFLARE_API_TOKEN',
            'SEMANTIC_SCHOLAR_KEY', 'SERPAPI_KEY', 'DATAFORSEO_LOGIN',
            'DATAFORSEO_PASSWORD', 'GLIMPSE_API_KEY', 'GITHUB_TOKEN',
        ]}
        tiers = get_available_tiers(config)
        expected = {"wikipedia", "gdelt", "npm", "pypi", "semantic_scholar"}
        assert set(tiers['tier1']) == expected

    def test_alpha_vantage_key_enables_tier2(self):
        """Test that ALPHA_VANTAGE_KEY present includes alpha_vantage in tier2."""
        config = {k: None for k in [
            'ALPHA_VANTAGE_KEY', 'COINGECKO_DEMO_KEY', 'CLOUDFLARE_API_TOKEN',
            'SEMANTIC_SCHOLAR_KEY', 'SERPAPI_KEY', 'DATAFORSEO_LOGIN',
            'DATAFORSEO_PASSWORD', 'GLIMPSE_API_KEY', 'GITHUB_TOKEN',
        ]}
        config['ALPHA_VANTAGE_KEY'] = 'test-key'
        tiers = get_available_tiers(config)
        assert 'alpha_vantage' in tiers['tier2']

    def test_multiple_tier2_keys(self):
        """Test that multiple Tier 2 keys show multiple sources."""
        config = {k: None for k in [
            'ALPHA_VANTAGE_KEY', 'COINGECKO_DEMO_KEY', 'CLOUDFLARE_API_TOKEN',
            'SEMANTIC_SCHOLAR_KEY', 'SERPAPI_KEY', 'DATAFORSEO_LOGIN',
            'DATAFORSEO_PASSWORD', 'GLIMPSE_API_KEY', 'GITHUB_TOKEN',
        ]}
        config['ALPHA_VANTAGE_KEY'] = 'key1'
        config['COINGECKO_DEMO_KEY'] = 'key2'
        tiers = get_available_tiers(config)
        assert 'alpha_vantage' in tiers['tier2']
        assert 'coingecko' in tiers['tier2']
        assert len(tiers['tier2']) == 2

    def test_serpapi_key_enables_tier3(self):
        """Test that SERPAPI_KEY enables serpapi in tier3."""
        config = {k: None for k in [
            'ALPHA_VANTAGE_KEY', 'COINGECKO_DEMO_KEY', 'CLOUDFLARE_API_TOKEN',
            'SEMANTIC_SCHOLAR_KEY', 'SERPAPI_KEY', 'DATAFORSEO_LOGIN',
            'DATAFORSEO_PASSWORD', 'GLIMPSE_API_KEY', 'GITHUB_TOKEN',
        ]}
        config['SERPAPI_KEY'] = 'serpapi-key'
        tiers = get_available_tiers(config)
        assert 'serpapi' in tiers['tier3']

    def test_dataforseo_needs_both_login_and_password(self):
        """Test that DataForSEO requires both login AND password."""
        config = {k: None for k in [
            'ALPHA_VANTAGE_KEY', 'COINGECKO_DEMO_KEY', 'CLOUDFLARE_API_TOKEN',
            'SEMANTIC_SCHOLAR_KEY', 'SERPAPI_KEY', 'DATAFORSEO_LOGIN',
            'DATAFORSEO_PASSWORD', 'GLIMPSE_API_KEY', 'GITHUB_TOKEN',
        ]}
        # Only login, no password
        config['DATAFORSEO_LOGIN'] = 'user'
        tiers = get_available_tiers(config)
        assert 'dataforseo' not in tiers['tier3']

        # Both login and password
        config['DATAFORSEO_PASSWORD'] = 'pass'
        tiers = get_available_tiers(config)
        assert 'dataforseo' in tiers['tier3']

    def test_all_keys_present(self):
        """Test with all keys present: tier1=5, tier2=4, tier3=3."""
        config = {
            'ALPHA_VANTAGE_KEY': 'k1',
            'COINGECKO_DEMO_KEY': 'k2',
            'CLOUDFLARE_API_TOKEN': 'k3',
            'SEMANTIC_SCHOLAR_KEY': 'k4',
            'SERPAPI_KEY': 'k5',
            'DATAFORSEO_LOGIN': 'user',
            'DATAFORSEO_PASSWORD': 'pass',
            'GLIMPSE_API_KEY': 'k7',
            'GITHUB_TOKEN': 'k8',
        }
        tiers = get_available_tiers(config)
        assert len(tiers['tier1']) == 5
        assert len(tiers['tier2']) == 4
        assert len(tiers['tier3']) == 3
