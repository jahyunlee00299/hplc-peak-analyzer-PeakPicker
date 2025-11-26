"""
Analyze all peaks in 250908 files to understand the large peak + small peaks pattern
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from hybrid_baseline import HybridBaselineCorrector
from scipy import signal

# Get all 250908 files
data_dir = Path("result/Revision 재실험")
files = sorted(data_dir.glob("250908*.csv"))

print(f"Found {len(files)} files to analyze\n")
print("=" * 80)

for csv_file in files[:3]:  # Analyze first 3 files
    print(f"\nFile: {csv_file.name}")
    print("-" * 80)

    # Read data
    df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
    time = df[0].values
    intensity = df[1].values

    if np.min(intensity) < 0:
        intensity = intensity - np.min(intensity)

    # Apply baseline correction
    corrector = HybridBaselineCorrector(time, intensity)
    baseline, params = corrector.optimize_baseline_with_linear_peaks()
    corrected = intensity - baseline
    corrected = np.maximum(corrected, 0)

    # Current detection parameters
    noise_level = np.std(corrected[corrected < np.percentile(corrected, 25)])
    signal_range = np.ptp(corrected)
    min_prominence = max(signal_range * 0.005, noise_level * 3)
    min_height = noise_level * 3

    print(f"Signal range: {signal_range:.2f}")
    print(f"Noise level: {noise_level:.2f}")
    print(f"Min prominence (current): {min_prominence:.2f}")
    print(f"Min height: {min_height:.2f}")

    # Current detection
    peaks_current, props_current = signal.find_peaks(
        corrected,
        prominence=min_prominence,
        height=min_height,
        width=3,
        distance=20
    )

    print(f"\nCurrent method detects: {len(peaks_current)} peaks")
    for i, pk in enumerate(peaks_current):
        print(f"  Peak {i+1}: RT={time[pk]:.3f} min, Height={corrected[pk]:.2f}, Prom={props_current['prominences'][i]:.2f}")

    # Find ALL local maxima to see what we're missing
    peaks_all, props_all = signal.find_peaks(
        corrected,
        prominence=noise_level * 5,  # Much lower threshold
        height=min_height,
        width=3,
        distance=10
    )

    print(f"\nLower threshold detects: {len(peaks_all)} peaks")
    for i, pk in enumerate(peaks_all):
        detected = pk in peaks_current
        marker = "[DETECTED]" if detected else "[MISSED]  "
        print(f"  {marker} Peak {i+1}: RT={time[pk]:.3f} min, Height={corrected[pk]:.2f}, Prom={props_all['prominences'][i]:.2f}")

    # Categorize peaks by height
    if len(peaks_all) > 0:
        peak_heights = corrected[peaks_all]
        max_height = peak_heights.max()

        major_peaks = peaks_all[peak_heights > max_height * 0.1]  # > 10% of max
        minor_peaks = peaks_all[(peak_heights <= max_height * 0.1) & (peak_heights > max_height * 0.001)]

        print(f"\nPeak categories:")
        print(f"  Major peaks (>10% of max): {len(major_peaks)}")
        print(f"  Minor peaks (0.1-10% of max): {len(minor_peaks)}")
        print(f"  Max height: {max_height:.2f}")
        print(f"  10% threshold: {max_height * 0.1:.2f}")

print("\n" + "=" * 80)
print("\nANALYSIS COMPLETE")
