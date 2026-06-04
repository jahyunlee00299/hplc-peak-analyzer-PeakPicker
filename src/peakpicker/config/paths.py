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
3. The platform default (``C:\\Chem32\\1\\DATA`` on Windows)

Usage
-----
    from peakpicker.config.paths import resolve_data_dir, add_data_dir_argument

    # In a script with argparse:
    parser = argparse.ArgumentParser()
    add_data_dir_argument(parser)
    args = parser.parse_args()
    data_dir = resolve_data_dir(args.data_dir, experiment="260216_cofactor_m2_main_new")
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

#: Environment variable name for the CHEM32 data root.
CHEM32_DATA_ENV = "CHEM32_DATA"

#: Platform default for the CHEM32 data root.
DEFAULT_CHEM32_DATA_ROOT = Path(r"C:\Chem32\1\DATA")


def get_data_root(explicit: Optional[os.PathLike | str] = None) -> Path:
    """Return the CHEM32 data root directory.

    Precedence: ``explicit`` > ``$CHEM32_DATA`` > :data:`DEFAULT_CHEM32_DATA_ROOT`.
    """
    if explicit:
        return Path(explicit)
    env = os.environ.get(CHEM32_DATA_ENV)
    if env:
        return Path(env)
    return DEFAULT_CHEM32_DATA_ROOT


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
        Experiment subfolder name (e.g. ``"260216_cofactor_m2_main_new"``).
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
            f"Overrides ${CHEM32_DATA_ENV} and the platform default. {help_suffix}"
        ).strip(),
    )
