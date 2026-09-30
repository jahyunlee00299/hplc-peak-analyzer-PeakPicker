"""
Data Path Resolution
====================

Centralized resolution of Agilent ChemStation (CHEM32) data directories.

Previously, the CHEM32 data root (e.g. ``C:\\Chem32\\1\\DATA``) was hardcoded
across multiple analysis/quantification scripts, requiring every file to be
edited whenever a new experiment was analyzed. This module makes the root
configurable via, in order of precedence:

1. An explicit path passed by the caller (e.g. an argparse ``--data-dir`` value)
2. The ``CHEM32_DATA`` environment variable
3. A synced ``HPLC_DATA`` folder directly under a OneDrive root
   (``~/OneDrive*/HPLC_DATA``; on WSL also ``/mnt/c/Users/*/OneDrive*/HPLC_DATA``),
   so every machine that syncs that folder finds the same data
4. The platform default (``C:\\Chem32\\1\\DATA`` on Windows)

Usage
-----
    from peakpicker.config.paths import resolve_data_dir, add_data_dir_argument

    # In a script with argparse:
    parser = argparse.ArgumentParser()
    add_data_dir_argument(parser)
    args = parser.parse_args()
    data_dir = resolve_data_dir(args.data_dir, experiment="<experiment_folder>")
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

#: Environment variable name for the CHEM32 data root.
CHEM32_DATA_ENV = "CHEM32_DATA"

#: Platform default for the CHEM32 data root.
DEFAULT_CHEM32_DATA_ROOT = Path(r"C:\Chem32\1\DATA")

#: Folder name looked up directly under each OneDrive root.
SYNCED_DATA_DIRNAME = "HPLC_DATA"


def _onedrive_roots() -> list[Path]:
    """OneDrive roots visible from this process (Windows home, then WSL mounts)."""
    roots = sorted(Path.home().glob("OneDrive*"))
    wsl_users = Path("/mnt/c/Users")
    if wsl_users.is_dir():
        roots += sorted(wsl_users.glob("*/OneDrive*"))
    return roots


def find_synced_data_root() -> Optional[Path]:
    """Return the first ``<OneDrive root>/HPLC_DATA`` directory, or None."""
    for root in _onedrive_roots():
        cand = root / SYNCED_DATA_DIRNAME
        if cand.is_dir():
            return cand
    return None


def get_data_root(explicit: Optional[os.PathLike | str] = None) -> Path:
    """Return the CHEM32 data root directory.

    Precedence: ``explicit`` > ``$CHEM32_DATA`` > :func:`find_synced_data_root`
    > :data:`DEFAULT_CHEM32_DATA_ROOT`.
    """
    if explicit:
        return Path(explicit)
    env = os.environ.get(CHEM32_DATA_ENV)
    if env:
        return Path(env)
    return find_synced_data_root() or DEFAULT_CHEM32_DATA_ROOT


def resolve_data_dir(
    explicit: Optional[os.PathLike | str] = None,
    experiment: Optional[str] = None,
) -> Path:
    """Resolve a concrete experiment data directory.

    If ``explicit`` is an absolute path it is used as-is (treated as the full
    experiment directory). Otherwise the directory is built as
    ``get_data_root(explicit) / experiment``.

    Parameters
    ----------
    explicit:
        A caller-supplied path. May be the data root or the full experiment
        directory; if absolute and pointing at the experiment folder, it is
        returned directly.
    experiment:
        Experiment subfolder name (e.g. ``"<experiment_folder>"``).
    """
    if explicit:
        p = Path(explicit)
        # If the caller already pointed at the experiment folder, use it directly.
        if experiment is None or p.name == experiment:
            return p
        return p / experiment
    root = get_data_root()
    return root / experiment if experiment else root


def add_data_dir_argument(parser, *, help_suffix: str = "") -> None:
    """Add a standard ``--data-dir`` argument to an argparse parser."""
    parser.add_argument(
        "--data-dir",
        dest="data_dir",
        default=None,
        help=(
            "CHEM32 experiment data directory (or data root). "
            f"Overrides ${CHEM32_DATA_ENV}, a OneDrive {SYNCED_DATA_DIRNAME} folder and the platform default. {help_suffix}"
        ).strip(),
    )
