"""
Agilent Chemstation .ch File Parser
Supports reading chromatography data from Chemstation .ch files
"""

import struct
import numpy as np
from pathlib import Path
from typing import Tuple, Dict, Optional
import warnings


class ChemstationParser:
    """Parser for Agilent Chemstation .ch files"""

    def __init__(self, file_path: str):
        """
        Initialize parser with path to .ch file

        Args:
            file_path: Path to the .ch file
        """
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        self.data = None
        self.time = None
        self.metadata = {}

    def read(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Read chromatogram data from .ch file

        Returns:
            Tuple of (time_array, intensity_array)
        """
        with open(self.file_path, 'rb') as f:
            # Read file header
            magic = f.read(4)

            # Check file format (should be "130" or similar)
            if magic[:2] == b'\x02\x33':  # Format 179
                return self._read_format_179(f)
            elif magic[:2] == b'\x03\x31':  # Format 130/131
                return self._read_format_130(f)
            else:
                raise ValueError(f"Unknown file format: {magic.hex()}")

    def _read_format_130(self, f) -> Tuple[np.ndarray, np.ndarray]:
        """Read Chemstation format 130/131"""
        # Reset to beginning
        f.seek(0)

        # Read header information
        # Offset 0x116: Intercept value
        f.seek(0x116)
        intercept = struct.unpack('>d', f.read(8))[0]  # 64-bit double

        # Offset 0x11E: Slope value
        f.seek(0x11E)
        slope = struct.unpack('>d', f.read(8))[0]  # 64-bit double

        # Offset 0x11A: Start time (in milliseconds/60000 to get minutes)
        f.seek(0x11A)
        start_time_ms = struct.unpack('>i', f.read(4))[0]
        start_time = start_time_ms / 60000.0

        # Offset 0x120: End time
        f.seek(0x120)
        end_time_ms = struct.unpack('>i', f.read(4))[0]
        end_time = end_time_ms / 60000.0

        # Data section starts at 0x1000 (typical for format 130)
        data_offset = 0x1000

        # Get file size to determine data length
        f.seek(0, 2)  # Seek to end
        file_size = f.tell()

        # Read data points
        f.seek(data_offset)
        remaining_bytes = file_size - data_offset
        data_bytes = f.read(remaining_bytes)

        # Parse data - typically stored as delta-compressed values
        try:
            intensities = self._decompress_data(data_bytes, intercept, slope)
        except Exception as e:
            warnings.warn(f"Data decompression failed, trying alternative method: {e}")
            # Fallback: try reading as raw 16-bit integers
            num_points = len(data_bytes) // 2
            raw_data = struct.unpack(f'>{num_points}h', data_bytes[:num_points*2])
            intensities = np.array(raw_data, dtype=float)

            # Apply scaling if reasonable
            if slope != 0:
                intensities = intercept + slope * intensities

        # Create time array
        num_points = len(intensities)

        # If times are unreasonable, use defaults
        if start_time <= 0 or end_time <= start_time or end_time > 1000:
            start_time = 0.0
            end_time = num_points * 0.01  # Assume 0.01 min per point
            warnings.warn("Invalid time range detected, using default")

        time = np.linspace(start_time, end_time, num_points)

        self.time = time
        self.data = intensities
        self.metadata = {
            'start_time': start_time,
            'end_time': end_time,
            'num_points': num_points,
            'file_path': str(self.file_path),
            'intercept': intercept,
            'slope': slope,
        }

        return time, intensities

    def _read_format_179(self, f) -> Tuple[np.ndarray, np.ndarray]:
        """Read Chemstation format 179 (newer format)"""
        # This is a placeholder for newer format support
        warnings.warn("Format 179 support is experimental")
        return self._read_format_130(f)

    def _decompress_data(self, data_bytes: bytes, intercept: float = 0, slope: float = 1) -> np.ndarray:
        """
        Decompress delta-compressed chromatogram data

        Agilent uses delta compression where each value is stored
        as a difference from the previous value
        """
        intensities = []
        current_value = 0
        i = 0

        while i < len(data_bytes) - 1:
            # Read delta value (can be 1 or 2 bytes)
            byte1 = data_bytes[i]

            if byte1 & 0x80:  # Two-byte delta
                if i + 1 >= len(data_bytes):
                    break
                byte2 = data_bytes[i + 1]
                delta = ((byte1 & 0x7F) << 8) | byte2
                if delta & 0x4000:  # Sign bit
                    delta = delta - 0x8000
                i += 2
            else:  # One-byte delta
                delta = byte1
                if delta & 0x40:  # Sign bit
                    delta = delta - 0x80
                i += 1

            current_value += delta
            # Apply calibration: intensity = intercept + slope * raw_value
            calibrated_value = intercept + slope * current_value
            intensities.append(calibrated_value)

        return np.array(intensities, dtype=float)

    def get_metadata(self) -> Dict:
        """Get metadata from the chromatogram"""
        if not self.metadata:
            self.read()
        return self.metadata


def read_chemstation_file(file_path: str) -> Tuple[np.ndarray, np.ndarray]:
    """
    Convenience function to read a Chemstation .ch file

    Args:
        file_path: Path to the .ch file

    Returns:
        Tuple of (time_array, intensity_array)
    """
    parser = ChemstationParser(file_path)
    return parser.read()


if __name__ == "__main__":
    # Test the parser
    import sys

    if len(sys.argv) > 1:
        test_file = sys.argv[1]
    else:
        test_file = r"C:\Chem32\1\DATA\1. DeoxyNucleoside HPLC raw data\C18\0_2MMDECITA_STD_1MEHO_1DW.D\vwd1A.ch"

    print(f"Testing parser on: {test_file}")
    time, intensity = read_chemstation_file(test_file)
    print(f"Read {len(time)} data points")
    print(f"Time range: {time[0]:.2f} - {time[-1]:.2f} minutes")
    print(f"Intensity range: {intensity.min():.2f} - {intensity.max():.2f}")
