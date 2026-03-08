"""
Rainbow Chemstation Reader
===========================

Concrete implementation of IDataReader using the rainbow-api library
for reading Agilent Chemstation .ch files (e.g., RID detector data).

This reader delegates parsing to rainbow.agilent.chemstation.parse_ch,
which handles the binary format internally, and wraps the result in
a ChromatogramData domain object.
"""

import numpy as np
from pathlib import Path
from typing import Dict, Any

from ...interfaces import IDataReader
from ...domain import ChromatogramData


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

    # ------------------------------------------------------------------
    # IDataReader interface
    # ------------------------------------------------------------------

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

        Returns True for existing files with a .ch extension.  Does not
        attempt to parse the file to keep the check lightweight.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            return False
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

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
