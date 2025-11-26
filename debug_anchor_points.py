"""
Debug: Visualize baseline anchor points
"""
import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
import sys

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from hybrid_baseline import HybridBaselineCorrector

# Test with the same file
csv_file = Path("result/Revision 재실험/250908_4MM_ACH.csv")
sample_name = csv_file.stem

print(f"Testing: {sample_name}\n")

# Load data
df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
time = df[0].values
intensity = df[1].values

if np.min(intensity) < 0:
    intensity = intensity - np.min(intensity)

# Apply baseline correction - but inspect anchor points
corrector = HybridBaselineCorrector(time, intensity)
anchor_points = corrector.find_baseline_anchor_points()

print(f"Found {len(anchor_points)} anchor points:\n")
print(f"{'Index':>6} {'Time':>8} {'Value':>12} {'Type':>12} {'Confidence':>12}")
print("-" * 60)
for pt in anchor_points:  # Show ALL
    print(f"{pt.index:6d} {time[pt.index]:8.2f} {pt.value:12.1f} {pt.type:>12} {pt.confidence:12.3f}")

# Statistics
values = [pt.value for pt in anchor_points]
print(f"\nAnchor point statistics:")
print(f"  Min value: {min(values):.1f}")
print(f"  Max value: {max(values):.1f}")
print(f"  Mean value: {np.mean(values):.1f}")
print(f"  Median value: {np.median(values):.1f}")

print(f"\nSignal statistics:")
print(f"  Min: {intensity.min():.1f}")
print(f"  Max: {intensity.max():.1f}")
print(f"  Mean: {intensity.mean():.1f}")
print(f"  Median: {np.median(intensity):.1f}")
print(f"  10th percentile: {np.percentile(intensity, 10):.1f}")
print(f"  25th percentile: {np.percentile(intensity, 25):.1f}")

# Generate baseline
baseline = corrector.generate_hybrid_baseline(method='robust_fit')

# Plot
fig, axes = plt.subplots(2, 1, figsize=(16, 10))

# Full view with anchor points
ax = axes[0]
ax.plot(time, intensity, 'b-', linewidth=1.5, label='Original Signal', alpha=0.7)
ax.plot(time, baseline, 'r-', linewidth=1.5, label='Baseline', alpha=0.8)

# Mark anchor points
anchor_times = [time[pt.index] for pt in anchor_points]
anchor_values = [pt.value for pt in anchor_points]
ax.scatter(anchor_times, anchor_values, c='green', s=50, zorder=5,
          label=f'{len(anchor_points)} Anchor Points', marker='o', edgecolors='black')

ax.set_xlabel('Time (min)')
ax.set_ylabel('Intensity')
ax.set_title(f'{sample_name} - Anchor Points')
ax.legend()
ax.grid(True, alpha=0.3)

# Bottom view
ax = axes[1]
ax.plot(time, intensity, 'b-', linewidth=1.5, label='Original Signal', alpha=0.7)
ax.plot(time, baseline, 'r-', linewidth=1.5, label='Baseline', alpha=0.8)
ax.scatter(anchor_times, anchor_values, c='green', s=50, zorder=5,
          label='Anchor Points', marker='o', edgecolors='black')
ax.set_xlabel('Time (min)')
ax.set_ylabel('Intensity')
ax.set_title(f'{sample_name} - Bottom View')
ax.set_ylim(-500, 1000)
ax.legend()
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('debug_anchor_points.png', dpi=150)
print(f"\nSaved: debug_anchor_points.png")
plt.close()
