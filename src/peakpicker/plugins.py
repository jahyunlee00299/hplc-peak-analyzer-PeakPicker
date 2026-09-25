"""
plugins.py — Loader for private, experiment-specific plugin modules.

The public source tree (src/peakpicker) contains only generic mechanisms and
registries. Experiment-specific code (sample-name parsers, quantification
presets, method-selection rules for a particular lab's compounds) lives in a
PRIVATE plugin directory that is not part of this repository. This module
loads that directory (if present) so the public registries can be populated
at runtime without src/ ever importing anything experiment-specific.

Resolution of the plugin directory list:
    1. ``PEAKPICKER_PLUGIN_PATH`` environment variable — os.pathsep-separated
       list of directories.
    2. Otherwise, ``<repo_root>/plugins`` if that directory exists.

A missing directory is a no-op (not an error) — the public code must work
standalone. An import error in one plugin file is reported via
``warnings.warn`` (never swallowed silently) and does not stop the loading
of the remaining plugin files.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import warnings
from pathlib import Path
from typing import List

_loaded = False


def _default_plugin_dir() -> Path:
    # repo_root = .../src/peakpicker/plugins.py -> parents[2] = repo_root
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "plugins"


def _plugin_dirs() -> List[Path]:
    env = os.environ.get("PEAKPICKER_PLUGIN_PATH")
    if env:
        return [Path(p) for p in env.split(os.pathsep) if p]
    default = _default_plugin_dir()
    return [default] if default.is_dir() else []


def _import_file(path: Path) -> None:
    module_name = f"peakpicker_plugin_{path.stem}_{abs(hash(str(path)))}"
    try:
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"could not create import spec for {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - report, never swallow
        warnings.warn(f"peakpicker plugin failed to load: {path} ({exc!r})")


def load_plugins(force: bool = False) -> None:
    """Import every plugin module once.

    Idempotent: subsequent calls are no-ops unless ``force=True``. Registries
    (sample_parser.get_parser, quantification_config.get_preset, the
    method_selector match-rule loader) call this lazily before doing a
    lookup, so callers never need to invoke it directly.
    """
    global _loaded
    if _loaded and not force:
        return
    _loaded = True

    for plugin_dir in _plugin_dirs():
        if not plugin_dir.is_dir():
            continue
        for path in sorted(plugin_dir.glob("*.py")):
            if path.name.startswith("_"):
                continue
            _import_file(path)


def reset_for_testing() -> None:
    """Reset the idempotency guard. For test isolation only."""
    global _loaded
    _loaded = False
