"""
Rainbow File Readers
====================

Two concrete IDataReader implementations using the rainbow-api library:

- RainbowReader: reads Agilent .D folders (multi-detector, auto-selects signal)
- RainbowChemstationReader: reads individual .ch files directly
"""

import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

import numpy as np

from ...interfaces import IDataReader
from ...domain import ChromatogramData

logger = logging.getLogger(__name__)


class RainbowReader(IDataReader):
    """
    Reader for Agilent .D folders using the rainbow library.

    Supports both .D folder paths and direct .ch file paths.
    """

    DETECTOR_PRIORITY = ['RID', 'VWD', 'DAD', 'MWD', 'FLD']

    def __init__(self, preferred_detector: Optional[str] = None):
        """
        Parameters
        ----------
        preferred_detector : str, optional
            Preferred detector signal file prefix (e.g., 'RID1A', 'VWD1A').
            If None, auto-selects based on DETECTOR_PRIORITY.
        """
        self.preferred_detector = preferred_detector

    def read(self, file_path: Path) -> ChromatogramData:
        """Read chromatogram data from .D folder or .ch file."""
        import rainbow as rb

        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Path not found: {file_path}")

        # Determine the .ch file to parse
        if file_path.is_dir() and file_path.suffix.lower() == '.d':
            ch_file = self._find_best_ch_file(file_path)
        elif file_path.suffix.lower() == '.ch':
            ch_file = file_path
        else:
            raise ValueError(f"Not a .D folder or .ch file: {file_path}")

        if ch_file is None:
            raise FileNotFoundError(
                f"No suitable .ch signal file found in: {file_path}"
            )

        # Parse using rainbow
        data = rb.agilent.chemstation.parse_ch(str(ch_file))

        time = data.xlabels.copy()

        # Handle 2D data array (Nx1) or 1D
        if data.data.ndim == 2:
            intensity = data.data[:, 0].copy()
        else:
            intensity = data.data.copy()

        if len(time) == 0 or len(intensity) == 0:
            raise ValueError(f"Empty data in: {ch_file}")

        if len(time) != len(intensity):
            raise ValueError(
                f"Time/intensity length mismatch: "
                f"{len(time)} vs {len(intensity)}"
            )

        # Extract metadata
        rb_meta = data.metadata if data.metadata else {}
        sample_name = self._extract_sample_name(file_path, rb_meta)
        detector_type = self._detect_detector_type(ch_file, rb_meta)

        metadata = {
            'file_path': str(file_path),
            'ch_file': str(ch_file),
            'source': 'rainbow',
            'notebook': rb_meta.get('notebook', ''),
            'date': rb_meta.get('date', ''),
            'method': rb_meta.get('method', ''),
            'instrument': rb_meta.get('instrument', ''),
            'unit': rb_meta.get('unit', ''),
            'signal': rb_meta.get('signal', ''),
        }

        return ChromatogramData(
            time=time,
            intensity=intensity,
            sample_name=sample_name,
            detector_type=detector_type,
            metadata=metadata,
        )

    def can_read(self, file_path: Path) -> bool:
        """Check if this reader can handle the file/folder."""
        file_path = Path(file_path)

        if not file_path.exists():
            return False

        if file_path.is_dir() and file_path.suffix.lower() == '.d':
            return self._has_ch_files(file_path)

        if file_path.is_file() and file_path.suffix.lower() == '.ch':
            return True

        return False

    def _has_ch_files(self, d_folder: Path) -> bool:
        """Check if .D folder contains any .ch files."""
        for item in d_folder.iterdir():
            if item.suffix.lower() == '.ch':
                return True
        return False

    def _find_best_ch_file(self, d_folder: Path) -> Optional[Path]:
        """Find the best .ch signal file in a .D folder."""
        ch_files = [
            f for f in d_folder.iterdir()
            if f.suffix.lower() == '.ch'
        ]

        if not ch_files:
            return None

        # If preferred detector is specified, look for it first
        if self.preferred_detector:
            pref = self.preferred_detector.upper()
            for ch in ch_files:
                if ch.stem.upper().startswith(pref):
                    return ch

        # Auto-select based on detector priority
        for detector_prefix in self.DETECTOR_PRIORITY:
            for ch in ch_files:
                if ch.stem.upper().startswith(detector_prefix):
                    return ch

        # Fallback: return first .ch file
        return ch_files[0]

    def _extract_sample_name(self, file_path: Path, metadata: dict) -> str:
        """Extract sample name from metadata or path."""
        notebook = metadata.get('notebook', '').strip()
        if notebook:
            return notebook

        if file_path.is_dir() and file_path.suffix.lower() == '.d':
            return file_path.stem

        parent = file_path.parent
        if parent.suffix.lower() == '.d':
            return parent.stem

        return file_path.stem

    def _detect_detector_type(self, ch_file: Path, metadata: dict) -> str:
        """Detect detector type from filename or metadata."""
        name = ch_file.stem.upper()
        if name.startswith('RID'):
            return 'RID'
        elif name.startswith('VWD') or name.startswith('UV'):
            return 'UV-Vis'
        elif name.startswith('DAD'):
            return 'DAD'
        elif name.startswith('FLD'):
            return 'FLD'
        elif name.startswith('MWD'):
            return 'MWD'

        # Try from signal metadata
        signal = metadata.get('signal', '')
        if 'Refractive Index' in signal:
            return 'RID'
        elif 'UV' in signal or 'Absorbance' in signal:
            return 'UV-Vis'

        return 'Signal'


class RainbowChemstationReader(IDataReader):
    """
    Reader for Agilent Chemstation .ch files using the rainbow-api library.

    Single Responsibility: Only handles reading Chemstation files via the
    rainbow third-party library.  For a pure-Python reader that does its
    own binary parsing, see ChemstationReader.

    Parameters
    ----------
    detector_type : str, optional
        Detector type label to attach to the resulting ChromatogramData.
        Defaults to "RID".
    """

    SUPPORTED_EXTENSIONS = {'.ch'}

    def __init__(self, detector_type: str = "RID"):
        self._detector_type = detector_type

    def read(self, file_path: Path) -> ChromatogramData:
        """
        Read chromatogram data from a Chemstation .ch file using rainbow-api.

        Parameters
        ----------
        file_path : Path
            Path to the .ch data file.

        Returns
        -------
        ChromatogramData
            Loaded chromatogram with time (minutes) and intensity arrays.

        Raises
        ------
        FileNotFoundError
            If the file does not exist.
        ImportError
            If the rainbow-api package is not installed.
        ValueError
            If the file cannot be parsed.
        """
        from rainbow.agilent.chemstation import parse_ch

        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            result = parse_ch(str(file_path))
        except Exception as exc:
            raise ValueError(
                f"Failed to parse Chemstation file with rainbow-api: {file_path}"
            ) from exc

        # rainbow returns time in minutes via xlabels and raw signal in data
        time = np.asarray(result.xlabels, dtype=float)
        intensity = np.asarray(result.data, dtype=float).flatten()

        # Ensure arrays are the same length (defensive)
        min_len = min(len(time), len(intensity))
        time = time[:min_len]
        intensity = intensity[:min_len]

        sample_name = self._extract_sample_name(file_path)

        metadata: Dict[str, Any] = {
            'file_path': str(file_path),
            'reader': 'RainbowChemstationReader',
            'num_points': min_len,
        }

        # Merge any metadata exposed by rainbow
        if hasattr(result, 'metadata') and isinstance(result.metadata, dict):
            metadata.update(result.metadata)

        return ChromatogramData(
            time=time,
            intensity=intensity,
            sample_name=sample_name,
            detector_type=self._detector_type,
            metadata=metadata,
        )

    def can_read(self, file_path: Path) -> bool:
        """
        Check if this reader can handle the given file.

        Returns True for existing files with a .ch extension.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            return False
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    @staticmethod
    def _extract_sample_name(file_path: Path) -> str:
        """
        Extract a human-readable sample name from the file path.

        Agilent data is typically stored inside a ``*.D`` folder, so the
        folder name (without the .D suffix) is used as the sample name.
        """
        d_folder = file_path.parent
        if d_folder.suffix.lower() == '.d':
            return d_folder.stem
        return file_path.stem
