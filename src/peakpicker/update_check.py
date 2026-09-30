"""Tell the user when a newer hplc-peakpicker release is on PyPI.

pip never checks for updates on its own, so an installed copy silently goes
stale. ``maybe_notify_update()`` runs when a workflow is built: at most once
per process and once per day (cached), with a short network timeout, and it
never raises. Offline, CI, pytest, or ``PEAKPICKER_NO_UPDATE_CHECK=1`` -> skip.

``check_for_update()`` is the explicit, uncached form for users who want to ask.
"""
import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Optional, Tuple

PACKAGE_NAME = "hplc-peakpicker"
PYPI_URL = f"https://pypi.org/pypi/{PACKAGE_NAME}/json"
DISABLE_ENV = "PEAKPICKER_NO_UPDATE_CHECK"
CHECK_INTERVAL_SEC = 24 * 3600
TIMEOUT_SEC = 1.5
SKIP_ENVS = (DISABLE_ENV, "CI", "PYTEST_CURRENT_TEST")

_notified_this_process = False


def _parse_version(text: str) -> Optional[Tuple[int, ...]]:
    """'2.0.1' -> (2, 0, 1); pre-releases / odd strings -> None (never nag)."""
    try:
        return tuple(int(p) for p in text.strip().split("."))
    except (ValueError, AttributeError):
        return None


def _is_newer(latest: str, current: str) -> bool:
    lv, cv = _parse_version(latest), _parse_version(current)
    return lv is not None and cv is not None and lv > cv


def _cache_file() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or os.environ.get("LOCALAPPDATA")
    root = Path(base) if base else Path.home() / ".cache"
    return root / "peakpicker" / "update_check.json"


def _fetch_latest_version(timeout: float = TIMEOUT_SEC) -> Optional[str]:
    try:
        with urllib.request.urlopen(PYPI_URL, timeout=timeout) as resp:
            return json.load(resp)["info"]["version"]
    except Exception:
        return None


def _read_cache() -> Optional[dict]:
    try:
        return json.loads(_cache_file().read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_cache(latest: str) -> None:
    try:
        path = _cache_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"checked_at": time.time(), "latest": latest}), encoding="utf-8")
    except Exception:
        pass


def _disabled() -> bool:
    return any(os.environ.get(k) for k in SKIP_ENVS)


def _current_version() -> str:
    from . import __version__
    return __version__


def check_for_update() -> Optional[str]:
    """Query PyPI now; return the newer version string, or None if up to date/unreachable."""
    latest = _fetch_latest_version()
    if latest is None:
        return None
    _write_cache(latest)
    return latest if _is_newer(latest, _current_version()) else None


def maybe_notify_update() -> None:
    """Print a one-line upgrade hint to stderr if a newer release exists. Never raises."""
    global _notified_this_process
    if _notified_this_process or _disabled():
        return
    _notified_this_process = True
    try:
        cached = _read_cache()
        if cached and time.time() - cached.get("checked_at", 0) < CHECK_INTERVAL_SEC:
            latest = cached.get("latest")
        else:
            latest = _fetch_latest_version()
            if latest is None:
                return
            _write_cache(latest)
        current = _current_version()
        if latest and _is_newer(latest, current):
            print(
                f"[peakpicker] {PACKAGE_NAME} {latest} is available (installed {current}). "
                f"Upgrade: pip install -U {PACKAGE_NAME}   "
                f"(silence: set {DISABLE_ENV}=1)",
                file=sys.stderr,
            )
    except Exception:
        pass


def reset_for_testing() -> None:
    global _notified_this_process
    _notified_this_process = False
