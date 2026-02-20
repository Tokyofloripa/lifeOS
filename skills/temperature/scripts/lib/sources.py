"""Source registry — auto-discovers, selects, and runs source modules in parallel.

Source modules in lib/ implement the protocol:
  Constants: SOURCE_NAME, DISPLAY_NAME, SOURCE_TIER, SOURCE_DIMENSION
  Functions: is_available(config), should_search(topic), search(topic, window_days, config)

Discovery is automatic at import time. Adding a source = creating one .py file.
"""

import importlib
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import env
from .schema import SourceError, TrendSignal
from .http import HTTPError


def _log(msg: str):
    """Log source registry messages to stderr."""
    sys.stderr.write(f"[temperature:sources] {msg}\n")
    sys.stderr.flush()


# --- Registry ---

# Non-source modules in lib/ that must be skipped during discovery
_SKIP_FILES = {
    "__init__", "sources", "schema", "env", "http", "dates",
    "sparkline", "score", "render", "normalize",
}

# Protocol requirements for a source module
_REQUIRED_ATTRS = ["SOURCE_NAME", "DISPLAY_NAME", "SOURCE_TIER", "SOURCE_DIMENSION"]
_REQUIRED_FUNCS = ["is_available", "should_search", "search"]

# Global registry: SOURCE_NAME -> module
ALL_SOURCES: Dict[str, Any] = {}


def _discover_sources():
    """Scan lib/ for conforming source modules and register them."""
    lib_dir = Path(__file__).parent
    for path in sorted(lib_dir.glob("*.py")):
        name = path.stem
        if name in _SKIP_FILES or name.startswith("_"):
            continue

        try:
            module = importlib.import_module(f".{name}", package="lib")
        except Exception as e:
            _log(f"Skip {name}.py: import error — {e}")
            continue

        # Validate protocol
        missing_attrs = [a for a in _REQUIRED_ATTRS if not hasattr(module, a)]
        missing_funcs = [f for f in _REQUIRED_FUNCS if not hasattr(module, f) or not callable(getattr(module, f))]

        if missing_attrs or missing_funcs:
            parts = []
            if missing_attrs:
                parts.append(f"missing attrs: {missing_attrs}")
            if missing_funcs:
                parts.append(f"missing funcs: {missing_funcs}")
            _log(f"Skip {name}.py: non-conforming — {', '.join(parts)}")
            continue

        ALL_SOURCES[module.SOURCE_NAME] = module

    if ALL_SOURCES:
        _log(f"Discovered {len(ALL_SOURCES)} sources: {sorted(ALL_SOURCES.keys())}")


# Run discovery at import time
_discover_sources()


# --- Selection ---

def select_sources(
    topic: str,
    config: Dict[str, Any],
    quick: bool = False,
    premium: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Select which sources to run based on tier, keys, and topic relevance.

    Args:
        topic: The search topic
        config: Configuration dict from env.get_config()
        quick: If True, restrict to Tier 1 only
        premium: If True, also enable Tier 3 sources

    Returns:
        (selected, skipped) — selected is name->module, skipped is name->reason
    """
    available_tiers = env.get_available_tiers(config)

    # Compute allowed tiers based on flags
    allowed_tiers = {1}
    if not quick:
        allowed_tiers.add(2)
    if premium:
        allowed_tiers.add(3)

    selected: Dict[str, Any] = {}
    skipped: Dict[str, str] = {}

    for name, module in ALL_SOURCES.items():
        tier = module.SOURCE_TIER

        # Tier check
        if tier not in allowed_tiers:
            skipped[name] = f"tier {tier} not enabled"
            continue

        # Key check (Tier 2/3 only — Tier 1 is always available)
        if tier >= 2:
            tier_key = f"tier{tier}"
            available_in_tier = available_tiers.get(tier_key, [])
            if name not in available_in_tier:
                skipped[name] = "API key not configured"
                continue

        # Availability check
        if not module.is_available(config):
            skipped[name] = "not available"
            continue

        # Relevance check
        if not module.should_search(topic):
            skipped[name] = "not relevant for topic"
            continue

        selected[name] = module

    return selected, skipped


# --- Execution ---

@dataclass
class SourceResult:
    """Result from a single source execution."""
    name: str
    signal: Optional[TrendSignal] = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    http_status: Optional[int] = None
    elapsed_ms: int = 0


def _classify_error(e: Exception) -> str:
    """Classify an exception into an error type string.

    Returns one of: source, rate_limit, auth, http, timeout, parse, unknown.
    """
    if isinstance(e, SourceError):
        return "source"
    if isinstance(e, HTTPError):
        code = e.status_code
        if code == 429:
            return "rate_limit"
        if code in (401, 403):
            return "auth"
        return "http"
    if isinstance(e, (TimeoutError, OSError)):
        return "timeout"
    if isinstance(e, (json.JSONDecodeError, KeyError, ValueError)):
        return "parse"
    return "unknown"


def run_sources(
    selected: Dict[str, Any],
    topic: str,
    window_days: int,
    config: Dict[str, Any],
    per_source_timeout: int = 12,
    global_budget: float = 45.0,
) -> Tuple[Dict[str, TrendSignal], Dict[str, SourceResult]]:
    """Execute selected sources in parallel with dual timeout.

    Args:
        selected: name->module dict from select_sources()
        topic: The search topic
        window_days: Lookback window in days
        config: Configuration dict
        per_source_timeout: Per-source HTTP timeout in seconds
        global_budget: Global budget in seconds via as_completed()

    Returns:
        (results, all_results) — results has name->TrendSignal for successful sources,
        all_results has name->SourceResult for every source (success, None, or error)
    """
    if not selected:
        return {}, {}

    def _run_one(name: str, module) -> SourceResult:
        """Execute a single source with error handling."""
        start = time.monotonic()
        cfg = dict(config)
        cfg["per_source_timeout"] = per_source_timeout

        try:
            signal = module.search(topic, window_days, cfg)
            elapsed = int((time.monotonic() - start) * 1000)
            if signal is not None:
                return SourceResult(name=name, signal=signal, elapsed_ms=elapsed)
            return SourceResult(name=name, elapsed_ms=elapsed)
        except SourceError as e:
            elapsed = int((time.monotonic() - start) * 1000)
            return SourceResult(
                name=name,
                error=e.message,
                error_type="source",
                elapsed_ms=elapsed,
            )
        except Exception as e:
            elapsed = int((time.monotonic() - start) * 1000)
            http_status = getattr(e, "status_code", None)
            return SourceResult(
                name=name,
                error=str(e),
                error_type=_classify_error(e),
                http_status=http_status,
                elapsed_ms=elapsed,
            )

    results: Dict[str, TrendSignal] = {}
    all_results: Dict[str, SourceResult] = {}

    max_workers = min(len(selected), 10)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_run_one, name, module): name
            for name, module in selected.items()
        }

        def _store_result(result: SourceResult):
            """Store a result, handling list-return (multi-signal) sources."""
            if result.signal is not None and isinstance(result.signal, list):
                # Multi-signal source (e.g. GDELT returns [volume, sentiment])
                for s in result.signal:
                    composite_key = f"{result.name}_{s.metric_name}"
                    results[composite_key] = s
                    all_results[composite_key] = SourceResult(
                        name=composite_key,
                        signal=s,
                        elapsed_ms=result.elapsed_ms,
                    )
            elif result.signal is not None:
                all_results[result.name] = result
                results[result.name] = result.signal
            else:
                all_results[result.name] = result

        try:
            for future in as_completed(futures, timeout=global_budget):
                result = future.result()
                _store_result(result)
        except TimeoutError:
            # Global budget exceeded — collect completed, mark remaining as timed out
            for future, name in futures.items():
                if name in all_results or any(
                    k.startswith(name + "_") for k in all_results
                ):
                    continue  # Already collected (single or multi-signal)
                if future.done():
                    result = future.result()
                    _store_result(result)
                else:
                    all_results[name] = SourceResult(
                        name=name,
                        error="global timeout exceeded",
                        error_type="timeout",
                    )

    return results, all_results


# --- Status ---

def get_source_status(
    selected: Dict[str, Any],
    skipped: Dict[str, str],
    all_results: Dict[str, "SourceResult"],
) -> Dict[str, Any]:
    """Produce a status dict for rendering.

    Args:
        selected: name->module dict of sources that were selected
        skipped: name->reason dict of sources that were skipped
        all_results: name->SourceResult dict from run_sources()

    Returns:
        Dict with active_count, total_discovered, active, skipped, failed, timed_out lists.
    """
    active = []
    failed = []
    timed_out = []

    for name, result in all_results.items():
        module = selected.get(name)
        display_name = getattr(module, "DISPLAY_NAME", name) if module else name

        if result.signal is not None:
            active.append({
                "name": name,
                "display_name": display_name,
                "elapsed_ms": result.elapsed_ms,
            })
        elif result.error_type == "timeout":
            timed_out.append({
                "name": name,
                "display_name": display_name,
                "error": result.error,
                "error_type": result.error_type,
                "elapsed_ms": result.elapsed_ms,
            })
        elif result.error is not None:
            failed.append({
                "name": name,
                "display_name": display_name,
                "error": result.error,
                "error_type": result.error_type,
                "elapsed_ms": result.elapsed_ms,
            })

    skipped_list = [{"name": name, "reason": reason} for name, reason in skipped.items()]

    return {
        "active_count": len(active),
        "total_discovered": len(ALL_SOURCES),
        "active": active,
        "skipped": skipped_list,
        "failed": failed,
        "timed_out": timed_out,
    }
