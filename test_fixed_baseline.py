"""
Test fixed baseline
"""
import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
import sys

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from hybrid_baseline import HybridBaselineCorrector

# Test with the same file that had the issue
csv_file = Path("result/Revision 재실험/250908_4MM_ACH.csv")
sample_name = csv_file.stem

print(f"Testing: {sample_name}")

# Load data
df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
time = df[0].values
intensity = df[1].values

if np.min(intensity) < 0:
    intensity = intensity - np.min(intensity)

# Apply baseline correction
corrector = HybridBaselineCorrector(time, intensity)
baseline, params = corrector.optimize_baseline_with_linear_peaks()

# Calculate metrics
from scipy.signal import find_peaks

peaks, _ = find_peaks(intensity, height=intensity.max() * 0.01, prominence=intensity.max() * 0.005)

# Create mask for non-peak regions
non_peak_mask = np.ones(len(intensity), dtype=bool)
for peak in peaks:
    start = max(0, peak - 100)
    end = min(len(intensity), peak + 100)
    non_peak_mask[start:end] = False

if np.sum(non_peak_mask) > 0:
    non_peak_intensity = intensity[non_peak_mask]
    non_peak_baseline = baseline[non_peak_mask]
    diff = non_peak_intensity - non_peak_baseline

    print(f"\nNon-peak regions (AFTER FIX):")
    print(f"  Signal range: {non_peak_intensity.min():.1f} - {non_peak_intensity.max():.1f}")
    print(f"  Baseline range: {non_peak_baseline.min():.1f} - {non_peak_baseline.max():.1f}")
    print(f"  Difference (signal - baseline):")
    print(f"    Mean: {diff.mean():.1f}")
    print(f"    Min: {diff.min():.1f}")
    print(f"    Max: {diff.max():.1f}")

# Create diagnostic plot
fig, axes = plt.subplots(2, 1, figsize=(16, 10))

# Full view
ax = axes[0]
ax.plot(time, intensity, 'b-', linewidth=1.5, label='Original Signal', alpha=0.7)
ax.plot(time, baseline, 'r-', linewidth=1.5, label='Baseline (FIXED)', alpha=0.8)
ax.plot(time[peaks], intensity[peaks], 'go', markersize=8, label='Detected Peaks')
ax.set_xlabel('Time (min)')
ax.set_ylabel('Intensity')
ax.set_title(f'{sample_name} - Full View (AFTER FIX)')
ax.legend()
ax.grid(True, alpha=0.3)

# Zoomed to bottom
ax = axes[1]
ax.plot(time, intensity, 'b-', linewidth=1.5, label='Original Signal', alpha=0.7)
ax.plot(time, baseline, 'r-', linewidth=1.5, label='Baseline (FIXED)', alpha=0.8)
ax.fill_between(time, baseline, intensity, where=(baseline < intensity),
               alpha=0.3, color='yellow', label='Area to Remove')
ax.set_xlabel('Time (min)')
ax.set_ylabel('Intensity')
ax.set_title(f'{sample_name} - Bottom View (AFTER FIX)')
ax.set_ylim(-500, 500)
ax.legend()
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('test_fixed_baseline.png', dpi=150)
print(f"\nSaved: test_fixed_baseline.png")
plt.close()
