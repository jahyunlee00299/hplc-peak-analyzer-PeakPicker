"""
Debug why flat baseline is not applied properly in WOACP_1H file
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from hybrid_baseline import HybridBaselineCorrector

# Load data
csv_file = Path("result/Revision 재실험/250908_FLOXU_D_GA_WOACP_1H.csv")

print("=" * 80)
print(f"DEBUGGING BASELINE FOR: {csv_file.name}")
print("=" * 80)

df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
time = df[0].values
intensity = df[1].values

if np.min(intensity) < 0:
    intensity = intensity - np.min(intensity)

print(f"\nData range: {time.min():.2f} - {time.max():.2f} min")
print(f"Intensity range: {intensity.min():.2f} - {intensity.max():.2f}")

# Apply baseline correction
corrector = HybridBaselineCorrector(time, intensity)
baseline, params = corrector.optimize_baseline_with_linear_peaks()

print(f"\nBaseline method: {params.get('method', 'unknown')}")
print(f"Peaks detected for flat baseline: {params.get('num_peaks', 0)}")

if 'detected_peaks' in params:
    peaks = params['detected_peaks']
    print(f"\nDetected peak positions:")
    for i, pk_idx in enumerate(peaks):
        print(f"  Peak {i+1}: {time[pk_idx]:.3f} min, Height={intensity[pk_idx]:.2f}")

if 'peak_regions' in params:
    regions = params['peak_regions']
    print(f"\nFlat baseline regions:")
    for i, (start, end) in enumerate(regions):
        print(f"  Region {i+1}: {time[start]:.3f} - {time[end]:.3f} min")

# Check the main peak region (around 7 min)
mask_7min = (time >= 6.5) & (time <= 8.0)
time_7 = time[mask_7min]
intensity_7 = intensity[mask_7min]
baseline_7 = baseline[mask_7min]

print("\n" + "=" * 80)
print("MAIN PEAK REGION (6.5-8.0 min):")
print("=" * 80)
print(f"Max intensity: {intensity_7.max():.2f} at {time_7[np.argmax(intensity_7)]:.3f} min")
print(f"Baseline range in this region: {baseline_7.min():.2f} - {baseline_7.max():.2f}")
print(f"Baseline variation: {baseline_7.max() - baseline_7.min():.2f}")

# Check if baseline is flat in peak region
baseline_std = np.std(baseline_7)
print(f"Baseline std dev in peak region: {baseline_std:.2f}")

if baseline_std > 10:
    print("\n[PROBLEM] Baseline is NOT flat in peak region!")
    print("  Expected: Horizontal flat baseline")
    print(f"  Actual: Baseline varies by {baseline_7.max() - baseline_7.min():.2f}")
else:
    print("\n[OK] Baseline is flat in peak region")

# Visualize
fig, axes = plt.subplots(2, 1, figsize=(14, 10))

# Full chromatogram
ax = axes[0]
ax.plot(time, intensity, 'b-', linewidth=1.5, label='Original', alpha=0.7)
ax.plot(time, baseline, 'r--', linewidth=2, label='Baseline')

# Mark peak regions if available
if 'peak_regions' in params:
    for start, end in params['peak_regions']:
        ax.axvspan(time[start], time[end], alpha=0.2, color='yellow', label='Peak Region')
        # Draw horizontal line at baseline level in peak region
        baseline_level = baseline[start:end].mean()
        ax.plot([time[start], time[end]], [baseline_level, baseline_level],
                'g-', linewidth=3, alpha=0.8, label='Expected Flat')

ax.set_xlabel('Time (min)')
ax.set_ylabel('Intensity')
ax.set_title(f'{csv_file.stem} - Full Chromatogram')
ax.legend()
ax.grid(True, alpha=0.3)

# Zoomed to main peak
ax = axes[1]
ax.plot(time_7, intensity_7, 'b-', linewidth=2, label='Original', alpha=0.7)
ax.plot(time_7, baseline_7, 'r--', linewidth=3, label='Baseline')

# If there's a peak region here, mark it
if 'peak_regions' in params:
    for start, end in params['peak_regions']:
        if time[start] >= 6.5 and time[end] <= 8.0:
            region_mask = (time_7 >= time[start]) & (time_7 <= time[end])
            baseline_level = baseline[start:end].mean()
            ax.plot([time[start], time[end]], [baseline_level, baseline_level],
                    'g-', linewidth=4, alpha=0.8, label='Expected Flat')
            ax.axvspan(time[start], time[end], alpha=0.2, color='yellow')

ax.set_xlabel('Time (min)')
ax.set_ylabel('Intensity')
ax.set_title('Zoomed: Main Peak Region (6.5-8.0 min)')
ax.legend()
ax.grid(True, alpha=0.3)

plt.tight_layout()
output_file = Path('debug_woacp_baseline.png')
plt.savefig(output_file, dpi=150, bbox_inches='tight')
print(f"\n[PLOT] Saved: {output_file}")
print("=" * 80)
