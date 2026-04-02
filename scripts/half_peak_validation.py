"""
Half-peak quantification validation using real CSV chromatogram data.
Bypasses .ch parser and loads Chemstation-exported CSVs directly.
"""
import sys
import os as _os
from pathlib import Path
sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'src'))

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from scipy import signal
from scipy.integrate import trapezoid
from hybrid_baseline import HybridBaselineCorrector

# Font setup for Korean
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

# ===== 1. Load CSV data =====
def load_chemstation_csv(filepath):
    """Chemstation exported tab-separated UTF-16-LE CSV loader."""
    df = pd.read_csv(filepath, header=None, sep='\t', encoding='utf-16-le')
    time = df[0].values.astype(float)
    intensity = df[1].values.astype(float)
    return time, intensity


def detect_peaks_from_corrected(time, corrected):
    """Detect peaks from baseline-corrected signal."""
    noise_level = np.percentile(np.abs(corrected), 25) * 1.5
    ptp = np.ptp(corrected)
    peaks, props = signal.find_peaks(
        corrected,
        prominence=max(ptp * 0.01, noise_level * 3),
        height=noise_level * 3,
        width=3,
        distance=10
    )
    return peaks, props


def find_peak_boundaries(corrected, peak_idx, baseline_threshold_ratio=0.01):
    """
    Find left and right boundaries of a peak where signal drops to ~baseline.
    Uses the point where corrected signal falls below baseline_threshold_ratio * peak_height.
    """
    peak_height = corrected[peak_idx]
    threshold = peak_height * baseline_threshold_ratio

    # Left boundary
    left = peak_idx
    while left > 0 and corrected[left] > threshold:
        left -= 1

    # Right boundary
    right = peak_idx
    while right < len(corrected) - 1 and corrected[right] > threshold:
        right += 1

    return left, right


def calculate_half_peak_areas(time, corrected, peak_idx, left_bound, right_bound):
    """
    Calculate full area, left half * 2, right half * 2 for a peak.

    Returns dict with:
        full_area: trapezoid integration over [left_bound, right_bound]
        left_half_area: trapezoid integration over [left_bound, peak_idx] * 2
        right_half_area: trapezoid integration over [peak_idx, right_bound] * 2
        asymmetry_ratio: |left_x2 - right_x2| / full_area
    """
    t = time[left_bound:right_bound + 1]
    y = np.maximum(corrected[left_bound:right_bound + 1], 0)

    # Full area
    full_area = trapezoid(y, t)

    # Left half: [left_bound, peak_idx]
    t_left = time[left_bound:peak_idx + 1]
    y_left = np.maximum(corrected[left_bound:peak_idx + 1], 0)
    left_half = trapezoid(y_left, t_left)

    # Right half: [peak_idx, right_bound]
    t_right = time[peak_idx:right_bound + 1]
    y_right = np.maximum(corrected[peak_idx:right_bound + 1], 0)
    right_half = trapezoid(y_right, t_right)

    left_x2 = left_half * 2
    right_x2 = right_half * 2

    if full_area > 0:
        asymmetry_ratio = abs(left_x2 - right_x2) / full_area
    else:
        asymmetry_ratio = float('inf')

    return {
        'full_area': full_area,
        'left_half': left_half,
        'right_half': right_half,
        'left_x2': left_x2,
        'right_x2': right_x2,
        'asymmetry_ratio': asymmetry_ratio,
        'left_bound': left_bound,
        'right_bound': right_bound,
    }


# ===== Main processing =====
csv_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', 'exported_signals') + _os.sep
# Pick a representative file with clear peaks
csv_file = csv_dir + '251014_RIBA_PH_MAIN_GN10_1_6H.csv'

print("=" * 70)
print("Half-Peak Quantification Validation")
print("=" * 70)
print(f"\nCSV: {csv_file}")

time_arr, intensity_arr = load_chemstation_csv(csv_file)
print(f"Data points: {len(time_arr)}")
print(f"Time range: {time_arr[0]:.2f} - {time_arr[-1]:.2f} min")
print(f"Intensity range: {intensity_arr.min():.1f} - {intensity_arr.max():.1f}")

# Baseline correction
corrector = HybridBaselineCorrector(time_arr, intensity_arr)
corrector.find_baseline_anchor_points(valley_prominence=0.01, percentile=10)
baseline = corrector.generate_hybrid_baseline(method='weighted_spline')
corrected = intensity_arr - baseline
corrected_clipped = np.maximum(corrected, 0)

# Peak detection
peaks, props = detect_peaks_from_corrected(time_arr, corrected_clipped)
print(f"\nDetected peaks: {len(peaks)}")

# Calculate half-peak areas for each peak
results = []
for i, pidx in enumerate(peaks):
    left_b, right_b = find_peak_boundaries(corrected_clipped, pidx)
    areas = calculate_half_peak_areas(time_arr, corrected_clipped, pidx, left_b, right_b)
    areas['peak_idx'] = pidx
    areas['rt'] = time_arr[pidx]
    areas['height'] = corrected_clipped[pidx]
    results.append(areas)

# Sort by full area (descending)
results.sort(key=lambda x: x['full_area'], reverse=True)

# Print summary table
print(f"\n{'='*90}")
print(f"{'RT(min)':>8} {'Height':>10} {'Full Area':>12} {'Left x2':>12} {'Right x2':>12} {'Asym. Ratio':>12} {'Status':>10}")
print(f"{'-'*90}")
for r in results:
    status = "OK" if r['asymmetry_ratio'] < 0.10 else ("Warn" if r['asymmetry_ratio'] < 0.20 else "Asym!")
    print(f"{r['rt']:8.2f} {r['height']:10.1f} {r['full_area']:12.1f} {r['left_x2']:12.1f} {r['right_x2']:12.1f} {r['asymmetry_ratio']:12.4f} {status:>10}")

# ===== Identify best symmetric and most asymmetric peaks =====
valid_results = [r for r in results if r['full_area'] > 0 and r['height'] > 50]

if len(valid_results) == 0:
    print("\nNo valid peaks found. Trying with lower threshold...")
    valid_results = results

best_symmetric = min(valid_results, key=lambda x: x['asymmetry_ratio'])
most_asymmetric = max(valid_results, key=lambda x: x['asymmetry_ratio'])

print(f"\nBest symmetric peak: RT={best_symmetric['rt']:.2f} min, Asym={best_symmetric['asymmetry_ratio']:.4f}")
print(f"Most asymmetric peak: RT={most_asymmetric['rt']:.2f} min, Asym={most_asymmetric['asymmetry_ratio']:.4f}")

# ===== Publication-quality plot =====
fig = plt.figure(figsize=(16, 12))
gs = GridSpec(2, 2, figure=fig, hspace=0.35, wspace=0.3)

# --- Panel 1: Full chromatogram with peaks labeled ---
ax1 = fig.add_subplot(gs[0, 0])
ax1.plot(time_arr, corrected_clipped, 'b-', linewidth=0.8, label='Corrected signal')
ax1.plot(time_arr, baseline - baseline.min(), 'r--', linewidth=0.6, alpha=0.5, label='Baseline (shifted)')

for r in valid_results[:10]:  # Top 10 peaks
    pidx = r['peak_idx']
    ax1.annotate(
        f"{r['rt']:.1f}",
        xy=(time_arr[pidx], corrected_clipped[pidx]),
        xytext=(0, 8),
        textcoords='offset points',
        fontsize=7,
        ha='center',
        arrowprops=dict(arrowstyle='-', color='gray', lw=0.5)
    )
    # Mark peak
    ax1.plot(time_arr[pidx], corrected_clipped[pidx], 'rv', markersize=5)

ax1.set_xlabel('Time (min)')
ax1.set_ylabel('Intensity (mAU)')
ax1.set_title('(A) Full chromatogram - peak detection', fontweight='bold')
ax1.legend(fontsize=8, loc='upper right')
ax1.grid(True, alpha=0.2)
ax1.set_xlim(time_arr[0], time_arr[-1])

# --- Panel 2: Zoom on best symmetric peak with L/R coloring ---
ax2 = fig.add_subplot(gs[0, 1])
r = best_symmetric
pidx = r['peak_idx']
lb, rb = r['left_bound'], r['right_bound']
margin = max(20, (rb - lb) // 2)
zoom_left = max(0, lb - margin)
zoom_right = min(len(time_arr) - 1, rb + margin)

t_zoom = time_arr[zoom_left:zoom_right + 1]
y_zoom = corrected_clipped[zoom_left:zoom_right + 1]
ax2.plot(t_zoom, y_zoom, 'k-', linewidth=1.0)

# Left half fill (blue)
t_left = time_arr[lb:pidx + 1]
y_left = corrected_clipped[lb:pidx + 1]
ax2.fill_between(t_left, 0, y_left, alpha=0.4, color='#2196F3', label=f'Left x2 = {r["left_x2"]:.1f}')

# Right half fill (orange)
t_right = time_arr[pidx:rb + 1]
y_right = corrected_clipped[pidx:rb + 1]
ax2.fill_between(t_right, 0, y_right, alpha=0.4, color='#FF9800', label=f'Right x2 = {r["right_x2"]:.1f}')

# Vertical line at apex
ax2.axvline(time_arr[pidx], color='gray', linestyle=':', linewidth=0.8)
ax2.set_xlabel('Time (min)')
ax2.set_ylabel('Intensity (mAU)')
ax2.set_title(f'(B) Best symmetric peak (RT={r["rt"]:.2f} min)\nAsymmetry ratio = {r["asymmetry_ratio"]:.4f}, Full area = {r["full_area"]:.1f}',
              fontweight='bold', fontsize=9)
ax2.legend(fontsize=8)
ax2.grid(True, alpha=0.2)

# --- Panel 3: Zoom on most asymmetric peak (warning case) ---
ax3 = fig.add_subplot(gs[1, 0])
r = most_asymmetric
pidx = r['peak_idx']
lb, rb = r['left_bound'], r['right_bound']
margin = max(20, (rb - lb) // 2)
zoom_left = max(0, lb - margin)
zoom_right = min(len(time_arr) - 1, rb + margin)

t_zoom = time_arr[zoom_left:zoom_right + 1]
y_zoom = corrected_clipped[zoom_left:zoom_right + 1]
ax3.plot(t_zoom, y_zoom, 'k-', linewidth=1.0)

# Left half fill
t_left = time_arr[lb:pidx + 1]
y_left = corrected_clipped[lb:pidx + 1]
ax3.fill_between(t_left, 0, y_left, alpha=0.4, color='#2196F3', label=f'Left x2 = {r["left_x2"]:.1f}')

# Right half fill
t_right = time_arr[pidx:rb + 1]
y_right = corrected_clipped[pidx:rb + 1]
ax3.fill_between(t_right, 0, y_right, alpha=0.4, color='#FF9800', label=f'Right x2 = {r["right_x2"]:.1f}')

ax3.axvline(time_arr[pidx], color='gray', linestyle=':', linewidth=0.8)
ax3.set_xlabel('Time (min)')
ax3.set_ylabel('Intensity (mAU)')
ax3.set_title(f'(C) Most asymmetric peak (RT={r["rt"]:.2f} min)\nAsymmetry ratio = {r["asymmetry_ratio"]:.4f}, Full area = {r["full_area"]:.1f}',
              fontweight='bold', fontsize=9)
ax3.legend(fontsize=8)
ax3.grid(True, alpha=0.2)

# --- Panel 4: Bar chart comparing full vs left*2 vs right*2 ---
ax4 = fig.add_subplot(gs[1, 1])

# Top N peaks by area for bar chart
top_n = min(8, len(valid_results))
top_peaks = valid_results[:top_n]

x_labels = [f"RT {r['rt']:.1f}" for r in top_peaks]
full_areas = [r['full_area'] for r in top_peaks]
left_x2s = [r['left_x2'] for r in top_peaks]
right_x2s = [r['right_x2'] for r in top_peaks]

x = np.arange(top_n)
bar_width = 0.25

bars1 = ax4.bar(x - bar_width, full_areas, bar_width, label='Full area', color='#4CAF50', edgecolor='black', linewidth=0.5)
bars2 = ax4.bar(x, left_x2s, bar_width, label='Left x2', color='#2196F3', edgecolor='black', linewidth=0.5)
bars3 = ax4.bar(x + bar_width, right_x2s, bar_width, label='Right x2', color='#FF9800', edgecolor='black', linewidth=0.5)

# Asymmetry annotations on top
for i, r in enumerate(top_peaks):
    max_val = max(r['full_area'], r['left_x2'], r['right_x2'])
    color = 'green' if r['asymmetry_ratio'] < 0.10 else ('orange' if r['asymmetry_ratio'] < 0.20 else 'red')
    ax4.text(i, max_val * 1.02, f"{r['asymmetry_ratio']:.2f}",
             ha='center', va='bottom', fontsize=7, color=color, fontweight='bold')

ax4.set_xticks(x)
ax4.set_xticklabels(x_labels, rotation=45, ha='right', fontsize=7)
ax4.set_ylabel('Area (mAU*min)')
ax4.set_title('(D) Full area vs Half-peak x2 comparison\n(numbers = asymmetry ratio)', fontweight='bold', fontsize=9)
ax4.legend(fontsize=8)
ax4.grid(True, alpha=0.2, axis='y')

fig.suptitle('Half-Peak Quantification Validation\n(Real HPLC data: 251014_RIBA_PH_MAIN_GN10_1_6H)',
             fontsize=13, fontweight='bold', y=1.01)

plt.savefig(Path(__file__).parent.parent / 'results' / 'half_peak_validation.png',
            dpi=200, bbox_inches='tight', facecolor='white')
print(f"\nPlot saved: results/half_peak_validation.png")

# ===== Additional statistics =====
print(f"\n{'='*70}")
print("Half-Peak Quantification Summary")
print(f"{'='*70}")
sym_count = sum(1 for r in valid_results if r['asymmetry_ratio'] < 0.10)
warn_count = sum(1 for r in valid_results if 0.10 <= r['asymmetry_ratio'] < 0.20)
asym_count = sum(1 for r in valid_results if r['asymmetry_ratio'] >= 0.20)
print(f"Total valid peaks: {len(valid_results)}")
print(f"  Symmetric (ratio < 0.10): {sym_count} ({100*sym_count/max(1,len(valid_results)):.0f}%) - half-peak quantification reliable")
print(f"  Warning   (0.10-0.20):    {warn_count} ({100*warn_count/max(1,len(valid_results)):.0f}%) - half-peak quantification usable with caution")
print(f"  Asymmetric (ratio >= 0.20): {asym_count} ({100*asym_count/max(1,len(valid_results)):.0f}%) - half-peak quantification NOT recommended")

# Mean error for symmetric peaks
sym_peaks = [r for r in valid_results if r['asymmetry_ratio'] < 0.10]
if sym_peaks:
    left_errors = [abs(r['left_x2'] - r['full_area']) / r['full_area'] * 100 for r in sym_peaks if r['full_area'] > 0]
    right_errors = [abs(r['right_x2'] - r['full_area']) / r['full_area'] * 100 for r in sym_peaks if r['full_area'] > 0]
    print(f"\nFor symmetric peaks (ratio < 0.10):")
    print(f"  Left x2 vs Full area error:  {np.mean(left_errors):.2f}% (mean), {np.max(left_errors):.2f}% (max)")
    print(f"  Right x2 vs Full area error: {np.mean(right_errors):.2f}% (mean), {np.max(right_errors):.2f}% (max)")

print("\nDone.")
