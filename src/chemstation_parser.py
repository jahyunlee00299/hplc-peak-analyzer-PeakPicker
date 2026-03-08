"""
Improved Agilent Chemstation .ch File Parser
Based on reverse engineering and community knowledge
"""

import struct
import numpy as np
from pathlib import Path
from typing import Tuple, Dict


class ChemstationParser:
    """Improved parser for Agilent Chemstation .ch files (format 130/131)"""

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        self.metadata = {}
        self.time = None
        self.data = None

    def read(self) -> Tuple[np.ndarray, np.ndarray]:
        """Read chromatogram data from .ch file (format 130)"""
        with open(self.file_path, 'rb') as f:
            raw = f.read()

        # Validate version (Pascal string at offset 0: length byte + "130")
        ver_len = raw[0]
        if ver_len > 0 and ver_len < 20:
            version = raw[1:1 + ver_len].decode('ascii', errors='ignore')
        else:
            version = ''
        if version not in ('130', '131'):
            raise ValueError(
                f"Unsupported Chemstation version '{version}' "
                f"(first bytes: {raw[:4].hex()})"
            )

        # Time range at 0x11A (start) and 0x11E (end), unsigned int32 ms
        start_time_ms = struct.unpack('>I', raw[0x11A:0x11E])[0]
        end_time_ms = struct.unpack('>I', raw[0x11E:0x122])[0]
        start_time = start_time_ms / 60000.0
        end_time = end_time_ms / 60000.0

        # Scaling factor at 0x127C (big-endian double)
        y_scale = struct.unpack('>d', raw[0x127C:0x1284])[0]
        if y_scale == 0:
            y_scale = 1.0

        # Data body starts at fixed offset 0x1800 for version 130
        data_start = 0x1800
        intensities = self._decompress_segments(raw, data_start)

        # Apply scaling
        intensities = intensities * y_scale

        # Create time array
        num_points = len(intensities)
        if end_time <= start_time:
            end_time = num_points / 100.0

        time = np.linspace(start_time, end_time, num_points)

        self.time = time
        self.data = intensities
        self.metadata = {
            'start_time': start_time,
            'end_time': end_time,
            'num_points': num_points,
            'y_scale': y_scale,
            'data_start': data_start,
            'file_path': str(self.file_path),
            'version': version,
        }

        return time, intensities

    def get_metadata(self) -> Dict:
        """Get metadata from the chromatogram"""
        if not self.metadata:
            self.read()
        return self.metadata

    @staticmethod
    def _decompress_segments(raw: bytes, data_start: int) -> np.ndarray:
        """
        Decompress Agilent version-130 segment-based delta data.

        The data body is a sequence of segments. Each segment has a 2-byte
        header (label, count) followed by *count* values.

        Each value is a big-endian signed int16:
          - If the int16 equals -32768 (0x8000), the next 4 bytes are a
            big-endian signed int32 that replaces the accumulator (absolute).
          - Otherwise, the int16 is a delta added to the accumulator.

        The segment list ends when both label and count are 0.
        """
        values = []
        current = 0
        pos = data_start

        while pos + 1 < len(raw):
            label = raw[pos]
            count = raw[pos + 1]
            pos += 2

            if label == 0 and count == 0:
                break

            for _ in range(count):
                if pos + 2 > len(raw):
                    break
                v16 = struct.unpack('>h', raw[pos:pos + 2])[0]
                pos += 2

                if v16 == -32768:
                    if pos + 4 > len(raw):
                        break
                    current = struct.unpack('>i', raw[pos:pos + 4])[0]
                    pos += 4
                else:
                    current += v16

                values.append(current)

        return np.array(values, dtype=float)


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
