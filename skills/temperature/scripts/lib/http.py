"""HTTP utilities for temperature skill (stdlib only)."""

import base64
import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

DEFAULT_TIMEOUT = 15
DEBUG = os.environ.get("TEMPERATURE_DEBUG", "").lower() in ("1", "true", "yes")


def log(msg: str):
    """Log debug message to stderr."""
    if DEBUG:
        sys.stderr.write(f"[DEBUG] {msg}\n")
        sys.stderr.flush()


MAX_RETRIES = 1
RETRY_DELAY = 1.0
USER_AGENT = "temperature-skill/1.0 (Claude Code Skill)"


class HTTPError(Exception):
    """HTTP request error with status code."""
    def __init__(self, message: str, status_code: Optional[int] = None, body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


def basic_auth_header(login: str, password: str) -> str:
    """Produce a Basic Auth header value for DataForSEO-style APIs.

    Args:
        login: The username/login string
        password: The password string

    Returns:
        "Basic <base64-encoded credentials>" string
    """
    encoded = base64.b64encode(f"{login}:{password}".encode()).decode()
    return f"Basic {encoded}"


def request(
    method: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    json_data: Optional[Dict[str, Any]] = None,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = MAX_RETRIES,
) -> Dict[str, Any]:
    """Make an HTTP request and return JSON response.

    Args:
        method: HTTP method (GET, POST, etc.)
        url: Request URL
        headers: Optional headers dict
        json_data: Optional JSON body (for POST)
        timeout: Request timeout in seconds
        retries: Number of retries on failure

    Returns:
        Parsed JSON response

    Raises:
        HTTPError: On request failure
    """
    headers = headers or {}
    headers.setdefault("User-Agent", USER_AGENT)
    headers.setdefault("Accept-Encoding", "gzip")

    data = None
    if json_data is not None:
        data = json.dumps(json_data).encode('utf-8')
        headers.setdefault("Content-Type", "application/json")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    log(f"{method} {url}")
    if json_data:
        log(f"Payload keys: {list(json_data.keys())}")

    last_error = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw_body = response.read()
                encoding = response.getheader('Content-Encoding', '')
                if encoding == 'gzip':
                    raw_body = gzip.decompress(raw_body)
                body = raw_body.decode('utf-8')
                log(f"Response: {response.status} ({len(body)} bytes)")
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as e:
            body = None
            try:
                body = e.read().decode('utf-8')
            except Exception:
                pass
            log(f"HTTP Error {e.code}: {e.reason}")
            if body:
                log(f"Error body: {body[:500]}")
            last_error = HTTPError(f"HTTP {e.code}: {e.reason}", e.code, body)

            # Don't retry client errors (4xx) except rate limits
            if 400 <= e.code < 500 and e.code != 429:
                raise last_error

            if attempt < retries - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
        except urllib.error.URLError as e:
            log(f"URL Error: {e.reason}")
            last_error = HTTPError(f"URL Error: {e.reason}")
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
        except json.JSONDecodeError as e:
            log(f"JSON decode error: {e}")
            last_error = HTTPError(f"Invalid JSON response: {e}")
            raise last_error
        except (OSError, TimeoutError, ConnectionResetError) as e:
            # Handle socket-level errors (connection reset, timeout, etc.)
            log(f"Connection error: {type(e).__name__}: {e}")
            last_error = HTTPError(f"Connection error: {type(e).__name__}: {e}")
            if attempt < retries - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))

    if last_error:
        raise last_error
    raise HTTPError("Request failed with no error details")


def get(url: str, headers: Optional[Dict[str, str]] = None, **kwargs) -> Dict[str, Any]:
    """Make a GET request."""
    return request("GET", url, headers=headers, **kwargs)


def post(url: str, json_data: Dict[str, Any], headers: Optional[Dict[str, str]] = None, **kwargs) -> Dict[str, Any]:
    """Make a POST request with JSON body."""
    return request("POST", url, headers=headers, json_data=json_data, **kwargs)
