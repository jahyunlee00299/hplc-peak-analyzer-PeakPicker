"""
chromatogram_io.py — Signal file resolution and chromatogram loading.

SRP: File path resolution (SignalFileResolver) and raw data loading
     (ChromatogramParser) are separate responsibilities.
"""
import sys
from pathlib import Path
from typing import Tuple

import numpy as np


class SignalFileResolver:
    """Resolves the .ch signal file path inside a .D folder."""

    _SIGNAL_CANDIDATES = ["RID1A.ch", "vwd1A.ch", "DAD1A.ch", "FID1A.ch"]

    def __init__(self, preferred_signal_file: str = "RID1A.ch"):
        self._preferred = preferred_signal_file

    def resolve(self, folder: Path) -> Path:
        """
        Return the .ch file to use for *folder*.

        Priority:
        1. YAML-declared signal_file
        2. Known candidates in order
        3. Any .ch file in folder
        4. Original (may not exist — caller handles error)
        """
        explicit = folder / self._preferred
        if explicit.exists():
            return explicit

        for candidate in self._SIGNAL_CANDIDATES:
            p = folder / candidate
            if p.exists():
                return p

        ch_files = sorted(folder.glob("*.ch"))
        if ch_files:
            return ch_files[0]

        return explicit  # not found — let caller raise


class ChromatogramParser:
    """Loads .ch files using rainbow or the bundled ChemstationParser."""

    @staticmethod
    def load(ch_path: Path) -> Tuple[np.ndarray, np.ndarray]:
        """Return (time_min, signal) arrays."""
        try:
            from rainbow.agilent.chemstation import parse_ch
            result = parse_ch(str(ch_path))
            time = np.asarray(result.xlabels, dtype=float)
            sig  = np.asarray(result.data, dtype=float).flatten()
        except Exception:
            src_dir = Path(__file__).parent.parent  # src/
            if str(src_dir) not in sys.path:
                sys.path.insert(0, str(src_dir))
            from chemstation_parser import ChemstationParser  # type: ignore
            parser = ChemstationParser(str(ch_path))
            time, sig = parser.read()

        n = min(len(time), len(sig))
        return time[:n], sig[:n]


# Backward-compat alias used by existing code
ChromatogramLoader = type("ChromatogramLoader", (), {
    "resolve_ch_path": staticmethod(
        lambda folder, signal_file: SignalFileResolver(signal_file).resolve(folder)
    ),
    "load": staticmethod(ChromatogramParser.load),
    "_SIGNAL_CANDIDATES": SignalFileResolver._SIGNAL_CANDIDATES,
})
