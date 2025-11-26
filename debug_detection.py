"""
Debug the two-pass detection to see what's happening
"""
import pandas as pd
import numpy as np
from pathlib import Path
import sys
from scipy import signal

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from hybrid_baseline import HybridBaselineCorrector

csv_file = Path("result/Revision 재실험/250908_FLOXU_D_GA_2NDACP_3_5H.csv")

print("=" * 80)
print("DEBUGGING TWO-PASS DETECTION")
print("=" * 80)
print(f"\nFile: {csv_file.name}\n")

# Load data
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

# Estimate noise
noise_region = np.percentile(corrected, 25)
quiet_mask = corrected < noise_region * 1.5
if np.any(quiet_mask):
    noise_level = np.std(corrected[quiet_mask])
else:
    noise_level = np.std(corrected) * 0.1
noise_level = max(noise_level, np.ptp(corrected) * 0.001)

signal_range = np.ptp(corrected)
min_height = noise_level * 3

print(f"Signal range: {signal_range:.2f}")
print(f"Noise level: {noise_level:.2f}")
print(f"Min height: {min_height:.2f}\n")

# PASS 1
print("=" * 80)
print("PASS 1: Major peaks (signal-range based)")
print("=" * 80)
major_prominence = max(signal_range * 0.005, noise_level * 3)
print(f"Major prominence threshold: {major_prominence:.2f}")

major_peaks, major_props = signal.find_peaks(
    corrected,
    prominence=major_prominence,
    height=min_height,
    width=3,
    distance=20
)

print(f"Major peaks found: {len(major_peaks)}")
for i, pk in enumerate(major_peaks):
    print(f"  Peak {i+1}: RT={time[pk]:.3f} min, Height={corrected[pk]:.2f}, Prom={major_props['prominences'][i]:.2f}")

# PASS 2
print("\n" + "=" * 80)
print("PASS 2: Minor peaks (noise-level based)")
print("=" * 80)
minor_prominence = noise_level * 10
print(f"Minor prominence threshold: {minor_prominence:.2f}")

minor_peaks, minor_props = signal.find_peaks(
    corrected,
    prominence=minor_prominence,
    height=min_height,
    width=3,
    distance=10
)

print(f"Minor peaks found: {len(minor_peaks)}")
for i, pk in enumerate(minor_peaks):
    print(f"  Peak {i+1}: RT={time[pk]:.3f} min, Height={corrected[pk]:.2f}, Prom={minor_props['prominences'][i]:.2f}")

# Try even more relaxed parameters for Pass 2
print("\n" + "=" * 80)
print("PASS 2 (MORE RELAXED): Very low threshold")
print("=" * 80)
very_low_prominence = noise_level * 5  # Even lower
print(f"Very low prominence threshold: {very_low_prominence:.2f}")

relaxed_peaks, relaxed_props = signal.find_peaks(
    corrected,
    prominence=very_low_prominence,
    height=min_height,
    width=2,  # Allow narrower peaks
    distance=5  # Allow closer peaks
)

print(f"Relaxed detection found: {len(relaxed_peaks)}")
for i, pk in enumerate(relaxed_peaks):
    in_major = pk in major_peaks
    marker = "[MAJOR]" if in_major else "[NEW]  "
    print(f"  {marker} Peak {i+1}: RT={time[pk]:.3f} min, Height={corrected[pk]:.2f}, Prom={relaxed_props['prominences'][i]:.2f}")

# Check 14.8 region specifically
print("\n" + "=" * 80)
print("CHECKING 14.5-15.1 MIN REGION:")
print("=" * 80)

mask = (time >= 14.5) & (time <= 15.1)
region_time = time[mask]
region_corrected = corrected[mask]

print(f"Max in region: {region_corrected.max():.2f} at {region_time[np.argmax(region_corrected)]:.3f} min")

# Try detecting with NO width/distance constraints
print("\nTrying minimal constraints:")
minimal_peaks, minimal_props = signal.find_peaks(
    corrected,
    prominence=very_low_prominence,
    height=min_height
)

peaks_in_region = []
for i, pk in enumerate(minimal_peaks):
    if 14.5 <= time[pk] <= 15.1:
        peaks_in_region.append((time[pk], corrected[pk], minimal_props['prominences'][i]))

if peaks_in_region:
    print(f"Found {len(peaks_in_region)} peaks in 14.5-15.1 region with minimal constraints:")
    for rt, h, prom in peaks_in_region:
        print(f"  RT={rt:.3f} min, Height={h:.2f}, Prom={prom:.2f}")
else:
    print("Still no peaks found in region!")

    # Manual check - is there actually a peak there?
    local_max_idx = np.argmax(region_corrected)
    print(f"\nManual check:")
    print(f"  Local maximum: {region_corrected[local_max_idx]:.2f} at {region_time[local_max_idx]:.3f} min")
    print(f"  Min height threshold: {min_height:.2f}")
    print(f"  Passes height test: {region_corrected[local_max_idx] > min_height}")

    # Check prominence manually
    left_min = region_corrected[:local_max_idx].min() if local_max_idx > 0 else region_corrected[local_max_idx]
    right_min = region_corrected[local_max_idx:].min() if local_max_idx < len(region_corrected)-1 else region_corrected[local_max_idx]
    manual_prom = region_corrected[local_max_idx] - max(left_min, right_min)
    print(f"  Manual prominence: {manual_prom:.2f}")
    print(f"  Required prominence: {very_low_prominence:.2f}")
    print(f"  Passes prominence test: {manual_prom > very_low_prominence}")

print("\n" + "=" * 80)
