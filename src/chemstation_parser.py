"""
Improved Agilent Chemstation .ch File Parser
Based on reverse engineering and community knowledge
"""

import struct
import numpy as np
from pathlib import Path
from typing import Tuple, Dict
import re
from datetime import datetime


class ChemstationParser:
    """Improved parser for Agilent Chemstation .ch files (format 130/131)"""

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        self.metadata = {}
        self.time = None
        self.data = None

    def _read_runlog_time(self) -> Tuple[float, float]:
        """
        Read actual run time from RUN.LOG file in parent .D directory
        Returns (start_time, end_time) in minutes, or (None, None) if not found
        """
        # RUN.LOG is in the parent .D directory
        d_folder = self.file_path.parent
        runlog_path = d_folder / "RUN.LOG"

        if not runlog_path.exists():
            return None, None

        try:
            with open(runlog_path, 'rb') as f:
                content = f.read()

            # Decode with error handling for binary content
            text = content.decode('utf-16-le', errors='ignore')

            # Look for Method started and Method completed/Instrument run complete lines
            # Example: "Method started: line # 33 at 58 inj # 1                   06:06:55 10/15/25"
            # Example: "Instrument run completed                                               06:32:48 10/15/25"

            start_pattern = r'Method\s+started.*?(\d{2}):(\d{2}):(\d{2})'
            end_pattern = r'(?:Instrument\s+run\s+complete|Method\s+complete).*?(\d{2}):(\d{2}):(\d{2})'

            start_match = re.search(start_pattern, text, re.IGNORECASE)
            end_match = re.search(end_pattern, text, re.IGNORECASE)

            if start_match and end_match:
                # Extract times
                start_h, start_m, start_s = map(int, start_match.groups())
                end_h, end_m, end_s = map(int, end_match.groups())

                # Convert to minutes from start
                start_time = 0.0  # Always start from 0
                end_time = (end_h - start_h) * 60 + (end_m - start_m) + (end_s - start_s) / 60.0

                # Handle case where end time is next day (rare)
                if end_time < 0:
                    end_time += 24 * 60

                return start_time, end_time

        except Exception:
            pass

        return None, None

    def read(self) -> Tuple[np.ndarray, np.ndarray]:
        """Read chromatogram data from .ch file"""
        # Try to read actual run time from RUN.LOG first
        runlog_start, runlog_end = self._read_runlog_time()

        with open(self.file_path, 'rb') as f:
            # Read header to determine version
            magic = f.read(4)

            if magic[:2] not in [b'\x03\x31', b'\x02\x33']:
                raise ValueError(f"Not a recognized Chemstation file format: {magic.hex()}")

            # Read key metadata from known offsets
            # These offsets are for Chemstation 130/131 format

            # Data offset location (usually 0x1800 or 0x2000)
            f.seek(0x10C)
            data_start = struct.unpack('>I', f.read(4))[0]

            if data_start == 0 or data_start > 0x10000:
                # Try default offset
                data_start = 0x1800

            # Read time range
            f.seek(0x282)
            start_time_ms = struct.unpack('>I', f.read(4))[0]
            f.seek(0x286)
            end_time_ms = struct.unpack('>I', f.read(4))[0]

            # Convert to minutes
            start_time = start_time_ms / 60000.0 if start_time_ms > 0 else 0.0
            end_time = end_time_ms / 60000.0 if end_time_ms > 0 else 0.0

            # Read Y-axis scaling
            f.seek(0x127A)
            y_scale = struct.unpack('>d', f.read(8))[0]
            if y_scale == 0 or abs(y_scale) > 1e10 or abs(y_scale) < 1e-10:
                y_scale = 1.0

            f.seek(0x1282)
            y_offset = struct.unpack('>d', f.read(8))[0]
            if abs(y_offset) > 1e10:
                y_offset = 0.0

            # Read data section
            f.seek(data_start)
            data_bytes = f.read()

            # Decompress data
            intensities = self._decompress_delta(data_bytes, y_offset, y_scale)

            # Create time array
            num_points = len(intensities)

            # Use RUN.LOG time if available, otherwise use file header or estimate
            if runlog_start is not None and runlog_end is not None:
                start_time = runlog_start
                end_time = runlog_end
            elif end_time <= start_time:
                # Estimate from data points (typical HPLC runs)
                end_time = num_points / 100.0  # Assume ~100 points per minute

            time = np.linspace(start_time, end_time, num_points)

            # Store for later access
            self.time = time
            self.data = intensities
            self.metadata = {
                'start_time': start_time,
                'end_time': end_time,
                'num_points': num_points,
                'y_scale': y_scale,
                'y_offset': y_offset,
                'data_start': data_start,
                'file_path': str(self.file_path),
                'time_source': 'RUN.LOG' if runlog_start is not None else 'estimated'
            }

            return time, intensities

    def get_metadata(self) -> Dict:
        """Get metadata from the chromatogram"""
        if not self.metadata:
            self.read()
        return self.metadata

    def _decompress_delta(self, data_bytes: bytes, offset: float = 0, scale: float = 1) -> np.ndarray:
        """
        Decompress Agilent delta-compressed data

        Format uses variable-length encoding:
        - If byte & 0x80: two-byte value
        - Otherwise: one-byte value
        """
        values = []
        current = 0
        i = 0

        while i < len(data_bytes):
            byte = data_bytes[i]

            if byte & 0x80:  # Two-byte value
                if i + 1 >= len(data_bytes):
                    break

                next_byte = data_bytes[i + 1]
                # Combine bytes
                value = ((byte & 0x7F) << 8) | next_byte
                # Check sign bit and convert
                if value & 0x4000:
                    value = -(0x8000 - value)
                else:
                    value = value

                i += 2
            else:  # One-byte value
                value = byte
                # Check sign bit
                if value & 0x40:
                    value = -(0x80 - value)

                i += 1

            current += value
            values.append(current)

        # Convert to numpy array and apply scaling
        intensities = np.array(values, dtype=float)
        intensities = offset + scale * intensities

        return intensities


def read_chemstation_file(file_path: str) -> Tuple[np.ndarray, np.ndarray]:
    """Convenience function to read a Chemstation file"""
    parser = ChemstationParser(file_path)
    return parser.read()


if __name__ == "__main__":
    import sys
    import matplotlib.pyplot as plt

    if len(sys.argv) > 1:
        test_file = sys.argv[1]
    else:
        test_file = r"C:\Chem32\1\DATA\1. DeoxyNucleoside HPLC raw data\C18\0_2MMDECITA_STD_1MEHO_1DW.D\vwd1A.ch"

    print(f"Testing parser on: {test_file}")
    time, intensity = read_chemstation_file(test_file)

    print(f"Data points: {len(time)}")
    print(f"Time range: {time[0]:.3f} - {time[-1]:.3f} min")
    print(f"Intensity range: {intensity.min():.2f} - {intensity.max():.2f}")
    print(f"Intensity stats: mean={intensity.mean():.2f}, std={intensity.std():.2f}")

    # Quick plot
    plt.figure(figsize=(12, 4))
    plt.plot(time, intensity, 'b-', linewidth=0.5)
    plt.xlabel('Time (min)')
    plt.ylabel('Intensity')
    plt.title('Chromatogram')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig('test_chromatogram.png', dpi=150)
    print("Plot saved to: test_chromatogram.png")
