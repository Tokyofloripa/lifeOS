"""Tests for temperature skill HTTP utilities."""

import base64
import io
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib.http import (
    basic_auth_header,
    request,
    get,
    post,
    HTTPError,
    USER_AGENT,
    MAX_RETRIES,
    DEFAULT_TIMEOUT,
    log,
)


class TestBasicAuthHeader:
    """Tests for basic_auth_header()."""

    def test_produces_correct_base64(self):
        """Test that basic_auth_header produces correct Base64-encoded string."""
        result = basic_auth_header("user", "pass")
        # Manually compute expected value
        expected_encoded = base64.b64encode(b"user:pass").decode()
        assert result == f"Basic {expected_encoded}"

    def test_known_value(self):
        """Test against a known Base64 encoding."""
        # "user:pass" -> base64 -> "dXNlcjpwYXNz"
        result = basic_auth_header("user", "pass")
        assert result == "Basic dXNlcjpwYXNz"

    def test_with_email_login(self):
        """Test with email-style login (common for DataForSEO)."""
        result = basic_auth_header("user@example.com", "secret123")
        expected = base64.b64encode(b"user@example.com:secret123").decode()
        assert result == f"Basic {expected}"

    def test_empty_credentials(self):
        """Test with empty strings (edge case)."""
        result = basic_auth_header("", "")
        expected = base64.b64encode(b":").decode()
        assert result == f"Basic {expected}"


class TestHTTPError:
    """Tests for HTTPError class."""

    def test_has_status_code(self):
        """Test that HTTPError has status_code attribute."""
        err = HTTPError("test error", status_code=404)
        assert err.status_code == 404

    def test_has_body(self):
        """Test that HTTPError has body attribute."""
        err = HTTPError("test error", body='{"error": "not found"}')
        assert err.body == '{"error": "not found"}'

    def test_default_none_attributes(self):
        """Test that status_code and body default to None."""
        err = HTTPError("test error")
        assert err.status_code is None
        assert err.body is None

    def test_message(self):
        """Test that HTTPError message is accessible via str()."""
        err = HTTPError("HTTP 500: Internal Server Error")
        assert str(err) == "HTTP 500: Internal Server Error"


class TestModuleConstants:
    """Tests for module-level constants."""

    def test_max_retries_is_2(self):
        """Test that MAX_RETRIES is 2 (1 retry after initial attempt; down from 3 in last60days)."""
        assert MAX_RETRIES == 2

    def test_default_timeout_is_15(self):
        """Test that DEFAULT_TIMEOUT is 15 (down from 30 in last60days)."""
        assert DEFAULT_TIMEOUT == 15

    def test_user_agent_is_temperature(self):
        """Test that User-Agent identifies as temperature skill."""
        assert USER_AGENT == "temperature-skill/1.0 (Claude Code Skill)"


class TestRequest:
    """Tests for request() with mocked urllib."""

    def _make_mock_response(self, data, status=200, encoding=''):
        """Create a mock HTTP response."""
        body = json.dumps(data).encode('utf-8')
        mock_response = MagicMock()
        mock_response.read.return_value = body
        mock_response.status = status
        mock_response.getheader.return_value = encoding
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        return mock_response

    @patch('lib.http.urllib.request.urlopen')
    def test_get_request_returns_json(self, mock_urlopen):
        """Test that request() returns parsed JSON from mocked response."""
        mock_urlopen.return_value = self._make_mock_response({"key": "value"})
        result = request("GET", "http://example.com/api")
        assert result == {"key": "value"}

    @patch('lib.http.urllib.request.urlopen')
    def test_user_agent_header_set(self, mock_urlopen):
        """Test that User-Agent header is set in requests."""
        mock_urlopen.return_value = self._make_mock_response({})
        request("GET", "http://example.com/api")
        # Check the Request object passed to urlopen
        call_args = mock_urlopen.call_args
        req_obj = call_args[0][0]  # First positional arg
        assert req_obj.get_header("User-agent") == USER_AGENT

    @patch('lib.http.urllib.request.urlopen')
    def test_post_sends_json_body(self, mock_urlopen):
        """Test that POST sends JSON data."""
        mock_urlopen.return_value = self._make_mock_response({"ok": True})
        result = post("http://example.com/api", json_data={"query": "test"})
        assert result == {"ok": True}
        # Verify data was sent
        call_args = mock_urlopen.call_args
        req_obj = call_args[0][0]
        assert req_obj.data is not None
        sent_data = json.loads(req_obj.data.decode('utf-8'))
        assert sent_data == {"query": "test"}

    @patch('lib.http.urllib.request.urlopen')
    def test_custom_headers_preserved(self, mock_urlopen):
        """Test that custom headers are passed through."""
        mock_urlopen.return_value = self._make_mock_response({})
        request("GET", "http://example.com/api",
                headers={"Authorization": "Bearer token123"})
        call_args = mock_urlopen.call_args
        req_obj = call_args[0][0]
        assert req_obj.get_header("Authorization") == "Bearer token123"

    @patch('lib.http.urllib.request.urlopen')
    def test_empty_response_returns_empty_dict(self, mock_urlopen):
        """Test that empty response body returns empty dict."""
        mock_response = MagicMock()
        mock_response.read.return_value = b''
        mock_response.status = 200
        mock_response.getheader.return_value = ''
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        result = request("GET", "http://example.com/api")
        assert result == {}


class TestLog:
    """Tests for log() function."""

    def test_log_writes_to_stderr_when_debug(self):
        """Test that log() writes to stderr when TEMPERATURE_DEBUG=1."""
        # We need to temporarily modify the DEBUG variable
        import lib.http as http_module
        original_debug = http_module.DEBUG
        try:
            http_module.DEBUG = True
            # Capture stderr
            from io import StringIO
            captured = StringIO()
            original_stderr = sys.stderr
            sys.stderr = captured
            try:
                http_module.log("test message")
            finally:
                sys.stderr = original_stderr
            output = captured.getvalue()
            assert "[DEBUG] test message" in output
        finally:
            http_module.DEBUG = original_debug

    def test_log_silent_when_not_debug(self):
        """Test that log() is silent when DEBUG is False."""
        import lib.http as http_module
        original_debug = http_module.DEBUG
        try:
            http_module.DEBUG = False
            from io import StringIO
            captured = StringIO()
            original_stderr = sys.stderr
            sys.stderr = captured
            try:
                http_module.log("test message")
            finally:
                sys.stderr = original_stderr
            assert captured.getvalue() == ""
        finally:
            http_module.DEBUG = original_debug
