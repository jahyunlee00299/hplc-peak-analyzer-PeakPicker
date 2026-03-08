"""
Chemstation File Reader
=======================

Concrete implementation of IDataReader for Agilent Chemstation .ch files.
"""

import struct
import numpy as np
from pathlib import Path
from typing import Tuple, Dict
import re

from ...interfaces import IDataReader
from ...domain import ChromatogramData


class ChemstationReader(IDataReader):
    """
    Reader for Agilent Chemstation .ch files (format 130/131).

    Single Responsibility: Only handles reading Chemstation files.
    """

    SUPPORTED_EXTENSIONS = {'.ch'}
    SUPPORTED_MAGIC = {b'\x03\x31', b'\x02\x33'}

    def read(self, file_path: Path) -> ChromatogramData:
        """Read chromatogram data from Chemstation .ch file."""
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Try to read actual run time from RUN.LOG first
        runlog_start, runlog_end = self._read_runlog_time(file_path)

        with open(file_path, 'rb') as f:
            # Read header
            magic = f.read(4)

            if magic[:2] not in self.SUPPORTED_MAGIC:
                raise ValueError(f"Not a recognized Chemstation file format: {magic.hex()}")

            # Data offset
            f.seek(0x10C)
            data_start = struct.unpack('>I', f.read(4))[0]

            if data_start == 0 or data_start > 0x10000:
                data_start = 0x1800

            # Time range
            f.seek(0x282)
            start_time_ms = struct.unpack('>I', f.read(4))[0]
            f.seek(0x286)
            end_time_ms = struct.unpack('>I', f.read(4))[0]

            start_time = start_time_ms / 60000.0 if start_time_ms > 0 else 0.0
            end_time = end_time_ms / 60000.0 if end_time_ms > 0 else 0.0

            # Y-axis scaling
            f.seek(0x127A)
            y_scale = struct.unpack('>d', f.read(8))[0]
            if y_scale == 0 or abs(y_scale) > 1e10 or abs(y_scale) < 1e-10:
                y_scale = 1.0

            f.seek(0x1282)
            y_offset = struct.unpack('>d', f.read(8))[0]
            if abs(y_offset) > 1e10:
                y_offset = 0.0

            # Read and decompress data
            f.seek(data_start)
            data_bytes = f.read()

            intensities = self._decompress_delta(data_bytes, y_offset, y_scale)
            num_points = len(intensities)

            # Determine time range
            if runlog_start is not None and runlog_end is not None:
                start_time = runlog_start
                end_time = runlog_end
            elif end_time <= start_time:
                end_time = num_points / 100.0

            time = np.linspace(start_time, end_time, num_points)

            # Extract sample name from path
            sample_name = self._extract_sample_name(file_path)

            metadata = {
                'start_time': start_time,
                'end_time': end_time,
                'num_points': num_points,
                'y_scale': y_scale,
                'y_offset': y_offset,
                'data_start': data_start,
                'file_path': str(file_path),
                'time_source': 'RUN.LOG' if runlog_start is not None else 'estimated'
            }

            return ChromatogramData(
                time=time,
                intensity=intensities,
                sample_name=sample_name,
                detector_type=self._detect_detector_type(file_path),
                metadata=metadata
            )

    def can_read(self, file_path: Path) -> bool:
        """Check if this reader can handle the file."""
        file_path = Path(file_path)

        if not file_path.exists():
            return False

        if file_path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            return False

        try:
            with open(file_path, 'rb') as f:
                magic = f.read(4)
                return magic[:2] in self.SUPPORTED_MAGIC
        except Exception:
            return False

    def _read_runlog_time(self, file_path: Path) -> Tuple[float, float]:
        """Read actual run time from RUN.LOG file."""
        d_folder = file_path.parent
        runlog_path = d_folder / "RUN.LOG"

        if not runlog_path.exists():
            return None, None

        try:
            with open(runlog_path, 'rb') as f:
                content = f.read()

            text = content.decode('utf-16-le', errors='ignore')

            start_pattern = r'Method\s+started.*?(\d{2}):(\d{2}):(\d{2})'
            end_pattern = r'(?:Instrument\s+run\s+complete|Method\s+complete).*?(\d{2}):(\d{2}):(\d{2})'

            start_match = re.search(start_pattern, text, re.IGNORECASE)
            end_match = re.search(end_pattern, text, re.IGNORECASE)

            if start_match and end_match:
                start_h, start_m, start_s = map(int, start_match.groups())
                end_h, end_m, end_s = map(int, end_match.groups())

                start_time = 0.0
                end_time = (end_h - start_h) * 60 + (end_m - start_m) + (end_s - start_s) / 60.0

                if end_time < 0:
                    end_time += 24 * 60

                return start_time, end_time

        except Exception:
            pass

        return None, None

    def _decompress_delta(self, data_bytes: bytes, offset: float, scale: float) -> np.ndarray:
        """Decompress Agilent delta-compressed data."""
        values = []
        current = 0
        i = 0

        while i < len(data_bytes):
            byte = data_bytes[i]

            if byte & 0x80:  # Two-byte value
                if i + 1 >= len(data_bytes):
                    break

                next_byte = data_bytes[i + 1]
                value = ((byte & 0x7F) << 8) | next_byte

                if value & 0x4000:
                    value = -(0x8000 - value)

                i += 2
            else:  # One-byte value
                value = byte
                if value & 0x40:
                    value = -(0x80 - value)

                i += 1

            current += value
            values.append(current)

        intensities = np.array(values, dtype=float)
        intensities = offset + scale * intensities

        return intensities

    def _extract_sample_name(self, file_path: Path) -> str:
        """Extract sample name from file path."""
        # Typically the .D folder name is the sample name
        d_folder = file_path.parent
        if d_folder.suffix.lower() == '.d':
            return d_folder.stem
        return file_path.stem

    def _detect_detector_type(self, file_path: Path) -> str:
        """Detect detector type from filename."""
        name = file_path.stem.lower()
        if 'vwd' in name or 'uv' in name:
            return 'UV-Vis'
        elif 'rid' in name:
            return 'RID'
        elif 'dad' in name:
            return 'DAD'
        elif 'fld' in name:
            return 'FLD'
        return 'Signal'


class CSVReader(IDataReader):
    """
    Reader for CSV chromatogram files.

    Simple CSV format with Time and Intensity columns.
    """

    SUPPORTED_EXTENSIONS = {'.csv', '.txt'}

    def read(self, file_path: Path) -> ChromatogramData:
        """Read chromatogram data from CSV file."""
        import pandas as pd

        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Try different separators and encodings
        for sep in [',', '\t', ';']:
            for encoding in ['utf-8', 'utf-16-le', 'latin-1']:
                try:
                    df = pd.read_csv(file_path, sep=sep, encoding=encoding)

                    # Find time and intensity columns
                    time_col = self._find_column(df, ['time', 'rt', 'retention', 'x', 'min'])
                    int_col = self._find_column(df, ['intensity', 'signal', 'response', 'y', 'area'])

                    if time_col and int_col:
                        return ChromatogramData(
                            time=df[time_col].values,
                            intensity=df[int_col].values,
                            sample_name=file_path.stem,
                            metadata={'file_path': str(file_path), 'format': 'csv'}
                        )
                except Exception:
                    continue

        raise ValueError(f"Could not parse CSV file: {file_path}")

    def can_read(self, file_path: Path) -> bool:
        """Check if this reader can handle the file."""
        file_path = Path(file_path)
        return file_path.exists() and file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def _find_column(self, df, candidates):
        """Find column matching one of the candidates."""
        for col in df.columns:
            col_lower = col.lower()
            for candidate in candidates:
                if candidate in col_lower:
                    return col
        # Try first/second column if no match
        if len(df.columns) >= 2:
            return None
        return None
