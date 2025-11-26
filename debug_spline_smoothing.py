"""
Debug: Check spline smoothing factor
"""
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from hybrid_baseline import HybridBaselineCorrector

# Load data
csv_file = Path("result/Revision 재실험/250908_4MM_ACH.csv")
df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
time = df[0].values
intensity = df[1].values

if np.min(intensity) < 0:
    intensity = intensity - np.min(intensity)

print("=== Spline Smoothing Debug ===\n")

corrector = HybridBaselineCorrector(time, intensity)

# Find anchor points
anchor_points = corrector.find_baseline_anchor_points()
print(f"Total anchor points: {len(anchor_points)}")

# Simulate robust_fit method
indices = np.array([p.index for p in anchor_points])
values = np.array([p.value for p in anchor_points])
confidences = np.array([p.confidence for p in anchor_points])

print(f"\nAnchor values:")
print(f"  Min: {values.min():.1f}")
print(f"  Max: {values.max():.1f}")
print(f"  Median: {np.median(values):.1f}")
print(f"  Mean: {values.mean():.1f}")

# MAD calculation
median = np.median(values)
mad = np.median(np.abs(values - median))
threshold = median + 3 * mad

print(f"\nRobust fit MAD filtering:")
print(f"  Median: {median:.1f}")
print(f"  MAD: {mad:.1f}")
print(f"  Threshold (median + 3*MAD): {threshold:.1f}")

# Apply mask
mask = values < threshold
robust_indices = indices[mask]
robust_values = values[mask]
robust_weights = confidences[mask]

print(f"\nAfter MAD filtering:")
print(f"  Remaining points: {len(robust_indices)} / {len(indices)}")
print(f"  Removed points: {len(indices) - len(robust_indices)}")
print(f"  Robust values range: {robust_values.min():.1f} - {robust_values.max():.1f}")

# Smoothing factor
smooth_factor = 0.5
enhanced_smoothing = True

if enhanced_smoothing:
    s = len(robust_indices) * smooth_factor * 5.0
else:
    s = len(robust_indices) * smooth_factor

print(f"\nSpline smoothing:")
print(f"  Number of points: {len(robust_indices)}")
print(f"  smooth_factor: {smooth_factor}")
print(f"  enhanced_smoothing: {enhanced_smoothing}")
print(f"  Final s value: {s:.1f}")
print(f"  s / n_points ratio: {s / len(robust_indices):.2f}")

print(f"\n⚠️ High s/n ratio (> 1.0) means spline will smooth heavily")
print(f"   and may deviate significantly from anchor points!")
