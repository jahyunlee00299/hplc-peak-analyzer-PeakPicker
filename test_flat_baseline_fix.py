"""
Test if flat baseline fix is working
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import sys
from scipy import signal

# Force reload
import importlib
if 'hybrid_baseline' in sys.modules:
    del sys.modules['hybrid_baseline']

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from hybrid_baseline import HybridBaselineCorrector

# Load data
csv_file = Path("result/Revision 재실험/250908_FLOXU_D_GA_WOACP_1H.csv")

print("=" * 80)
print(f"TESTING FLAT BASELINE FIX: {csv_file.name}")
print("=" * 80)

df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
time = df[0].values
intensity = df[1].values

if np.min(intensity) < 0:
    intensity = intensity - np.min(intensity)

# Apply baseline correction
corrector = HybridBaselineCorrector(time, intensity)

# Step by step
print("\nStep 1: Find anchor points...")
anchor_points = corrector.find_baseline_anchor_points(
    valley_prominence=0.01,
    percentile=10
)
print(f"  Found {len(anchor_points)} anchor points")

print("\nStep 2: Generate robust baseline...")
baseline_robust = corrector.generate_hybrid_baseline(method='robust_fit')
print(f"  Robust baseline range: {baseline_robust.min():.2f} - {baseline_robust.max():.2f}")

print("\nStep 3: Detect peaks...")
corrected = np.maximum(intensity - baseline_robust, 0)
noise_level = np.percentile(corrected, 25) * 1.5
peaks, props = signal.find_peaks(
    corrected,
    prominence=np.ptp(corrected) * 0.005,
    height=noise_level * 3,
    width=0
)
print(f"  Detected {len(peaks)} peaks")
for i, pk in enumerate(peaks):
    print(f"    Peak {i+1}: {time[pk]:.3f} min, Height={intensity[pk]:.2f}")

print("\nStep 4: Apply flat baseline to peaks...")
if len(peaks) > 0:
    hybrid_baseline = corrector.apply_linear_baseline_to_peaks(baseline_robust, peaks.tolist())
else:
    hybrid_baseline = baseline_robust

# Check the main peak region (around 7 min)
mask_7min = (time >= 6.5) & (time <= 8.0)
time_7 = time[mask_7min]
baseline_7 = hybrid_baseline[mask_7min]

print(f"\n  Main peak region (6.5-8.0 min):")
print(f"    Baseline range: {baseline_7.min():.2f} - {baseline_7.max():.2f}")
print(f"    Baseline variation: {baseline_7.max() - baseline_7.min():.2f}")
print(f"    Baseline std dev: {np.std(baseline_7):.2f}")

if np.std(baseline_7) < 5:
    print(f"\n  [SUCCESS] Baseline is NOW flat in peak region!")
else:
    print(f"\n  [STILL PROBLEM] Baseline is still NOT flat")

# Visualize
fig, axes = plt.subplots(3, 1, figsize=(16, 12))

# Full chromatogram
ax = axes[0]
ax.plot(time, intensity, 'b-', linewidth=1.5, label='Original', alpha=0.7)
ax.plot(time, baseline_robust, 'orange', linestyle='--', linewidth=2, label='Robust Baseline', alpha=0.8)
ax.plot(time, hybrid_baseline, 'r--', linewidth=2, label='With Flat Peaks')
ax.scatter(time[peaks], intensity[peaks], color='green', s=100, zorder=5, label='Detected Peaks', marker='o')
ax.set_xlabel('Time (min)')
ax.set_ylabel('Intensity')
ax.set_title('Full Chromatogram - Baseline Comparison')
ax.legend()
ax.grid(True, alpha=0.3)

# Zoomed to main peak
ax = axes[1]
ax.plot(time_7, intensity[mask_7min], 'b-', linewidth=2, label='Original', alpha=0.7)
ax.plot(time_7, baseline_robust[mask_7min], 'orange', linestyle='--', linewidth=2, label='Robust Baseline')
ax.plot(time_7, baseline_7, 'r--', linewidth=3, label='With Flat Peak')

# Add horizontal reference line at baseline level
flat_level = baseline_7.mean()
ax.axhline(flat_level, color='green', linestyle=':', linewidth=2, label=f'Expected Flat Level={flat_level:.1f}')

ax.set_xlabel('Time (min)')
ax.set_ylabel('Intensity')
ax.set_title('Zoomed: Main Peak Region (6.5-8.0 min)')
ax.legend()
ax.grid(True, alpha=0.3)

# Corrected signal
ax = axes[2]
corrected_final = intensity - hybrid_baseline
corrected_final = np.maximum(corrected_final, 0)
ax.plot(time, corrected_final, 'b-', linewidth=1.5, label='Baseline Corrected', alpha=0.7)
ax.scatter(time[peaks], corrected_final[peaks], color='red', s=100, zorder=5, label='Detected Peaks')

# Set y-axis from -500
current_ylim = ax.get_ylim()
ax.set_ylim(-500, current_ylim[1])

ax.set_xlabel('Time (min)')
ax.set_ylabel('Intensity')
ax.set_title('Baseline Corrected Signal (y-axis starts at -500)')
ax.legend()
ax.grid(True, alpha=0.3)

plt.tight_layout()
output_file = Path('test_flat_baseline_fix.png')
plt.savefig(output_file, dpi=150, bbox_inches='tight')
print(f"\n[PLOT] Saved: {output_file}")
print("=" * 80)
