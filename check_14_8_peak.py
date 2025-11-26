"""
Check if peak around 14.8 min is being quantified
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import sys

# Add src directory
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from hybrid_baseline import HybridBaselineCorrector
from scipy import signal

# Load the data
csv_file = Path("result/Revision 재실험/250908_FLOXU_D_GA_2NDACP_3_5H.csv")

print(f"Analyzing: {csv_file.name}\n")

# Read data
df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
time = df[0].values
intensity = df[1].values

# Shift to positive
if np.min(intensity) < 0:
    intensity = intensity - np.min(intensity)

print(f"Time range: {time.min():.2f} - {time.max():.2f} min")
print(f"Intensity range: {intensity.min():.2f} - {intensity.max():.2f}\n")

# Check data around 14.8 min
mask_14_8 = (time >= 14.5) & (time <= 15.1)
time_region = time[mask_14_8]
intensity_region = intensity[mask_14_8]

print("=" * 70)
print("REGION AROUND 14.8 MIN:")
print("=" * 70)
print(f"Time range: {time_region.min():.3f} - {time_region.max():.3f} min")
print(f"Intensity range: {intensity_region.min():.2f} - {intensity_region.max():.2f}")
print(f"Max intensity at: {time_region[np.argmax(intensity_region)]:.3f} min")
print(f"Peak height: {intensity_region.max():.2f}")
print()

# Apply baseline correction
print("=" * 70)
print("APPLYING BASELINE CORRECTION:")
print("=" * 70)
corrector = HybridBaselineCorrector(time, intensity)
baseline, params = corrector.optimize_baseline_with_linear_peaks()
corrected = intensity - baseline
corrected = np.maximum(corrected, 0)

print(f"Baseline method: {params.get('method', 'unknown')}")
print(f"Peaks detected for flat baseline: {params.get('num_peaks', 0)}")
print()

# After baseline correction, check the region again
corrected_region = corrected[mask_14_8]
baseline_region = baseline[mask_14_8]

print("After baseline correction:")
print(f"Corrected intensity range: {corrected_region.min():.2f} - {corrected_region.max():.2f}")
print(f"Max corrected at: {time_region[np.argmax(corrected_region)]:.3f} min")
print(f"Corrected peak height: {corrected_region.max():.2f}")
print()

# Peak detection
print("=" * 70)
print("PEAK DETECTION:")
print("=" * 70)

noise_level = np.std(corrected[corrected < np.percentile(corrected, 25)])
signal_range = np.ptp(corrected)
min_prominence = max(signal_range * 0.005, noise_level * 3)
min_height = noise_level * 3

print(f"Noise level: {noise_level:.2f}")
print(f"Signal range: {signal_range:.2f}")
print(f"Min prominence: {min_prominence:.2f}")
print(f"Min height: {min_height:.2f}")
print()

peaks, properties = signal.find_peaks(
    corrected,
    prominence=min_prominence,
    height=min_height,
    width=3,
    distance=20
)

peak_times = time[peaks]
peak_heights = corrected[peaks]

print(f"Total peaks detected: {len(peaks)}")
print()

# Check if any peak is around 14.8 min
peaks_around_14_8 = []
for i, (pt, ph) in enumerate(zip(peak_times, peak_heights)):
    if 14.5 <= pt <= 15.1:
        peaks_around_14_8.append((i, pt, ph))

print("=" * 70)
print("PEAKS IN 14.5-15.1 MIN RANGE:")
print("=" * 70)
if peaks_around_14_8:
    for idx, pt, ph in peaks_around_14_8:
        print(f"Peak #{idx+1}: RT={pt:.3f} min, Height={ph:.2f}")
        # Get peak boundaries
        if 'left_bases' in properties and 'right_bases' in properties:
            left = int(properties['left_bases'][idx])
            right = int(properties['right_bases'][idx])
        else:
            width_samples = properties['widths'][idx] if 'widths' in properties else 20
            half_width = int(width_samples * 1.5)
            peak_idx = peaks[idx]
            left = max(0, peak_idx - half_width)
            right = min(len(corrected) - 1, peak_idx + half_width)

        # Calculate area
        from scipy.integrate import trapezoid
        peak_time = time[left:right+1] * 60  # Convert to seconds
        peak_intensity = corrected[left:right+1]
        area = trapezoid(peak_intensity, peak_time)

        print(f"  Start: {time[left]:.3f} min, End: {time[right]:.3f} min")
        print(f"  Area: {area:.2f}")
        print(f"  Prominence: {properties['prominences'][idx]:.2f}")
        print()
else:
    print("X NO PEAKS DETECTED in this region!")
    print()
    print("Checking if there's a peak-like feature:")
    # Check if there's a local maximum
    local_max_idx = np.argmax(corrected_region)
    local_max_time = time_region[local_max_idx]
    local_max_height = corrected_region[local_max_idx]

    print(f"Local maximum at: {local_max_time:.3f} min")
    print(f"Height: {local_max_height:.2f}")

    # Calculate relative prominence
    left_min = corrected_region[:local_max_idx].min() if local_max_idx > 0 else local_max_height
    right_min = corrected_region[local_max_idx:].min() if local_max_idx < len(corrected_region)-1 else local_max_height
    relative_prominence = local_max_height - max(left_min, right_min)

    print(f"Relative prominence: {relative_prominence:.2f}")
    print(f"Required prominence: {min_prominence:.2f}")

    if relative_prominence < min_prominence:
        print(f"\n! Peak is TOO SMALL to be detected (prominence {relative_prominence:.2f} < {min_prominence:.2f})")
    else:
        print(f"\n! Peak should be detected but isn't - possible width or distance issue")

# Create visualization
fig, axes = plt.subplots(3, 1, figsize=(14, 10))

# Full chromatogram
ax = axes[0]
ax.plot(time, intensity, 'b-', linewidth=1, label='Original', alpha=0.7)
ax.plot(time, baseline, 'r--', linewidth=1.5, label='Baseline')
ax.axvline(14.8, color='green', linestyle=':', linewidth=2, label='14.8 min', alpha=0.7)
ax.set_xlabel('Time (min)')
ax.set_ylabel('Intensity')
ax.set_title(f'{csv_file.name} - Full Chromatogram')
ax.legend()
ax.grid(True, alpha=0.3)

# Baseline corrected
ax = axes[1]
ax.plot(time, corrected, 'b-', linewidth=1, label='Baseline Corrected')
ax.plot(time[peaks], corrected[peaks], 'ro', markersize=8, label='Detected Peaks')
ax.axvline(14.8, color='green', linestyle=':', linewidth=2, label='14.8 min', alpha=0.7)
ax.axhline(min_height, color='orange', linestyle='--', linewidth=1, label=f'Min Height={min_height:.1f}', alpha=0.7)
ax.set_xlabel('Time (min)')
ax.set_ylabel('Intensity')
ax.set_title('Baseline Corrected with Detected Peaks')
ax.legend()
ax.grid(True, alpha=0.3)

# Zoomed region around 14.8 min
ax = axes[2]
ax.plot(time_region, intensity_region, 'gray', linewidth=1, label='Original', alpha=0.5)
ax.plot(time_region, baseline_region, 'r--', linewidth=1.5, label='Baseline')
ax.plot(time_region, corrected_region, 'b-', linewidth=2, label='Corrected')

# Mark detected peaks in this region
for idx, pt, ph in peaks_around_14_8:
    region_mask = (time_region >= pt - 0.1) & (time_region <= pt + 0.1)
    if np.any(region_mask):
        ax.plot(pt, ph, 'ro', markersize=10, label='Detected' if idx == peaks_around_14_8[0][0] else '')

ax.axvline(14.8, color='green', linestyle=':', linewidth=2, label='Target: 14.8 min', alpha=0.7)
ax.axhline(min_height, color='orange', linestyle='--', linewidth=1, label=f'Min Height={min_height:.1f}', alpha=0.7)
ax.set_xlabel('Time (min)')
ax.set_ylabel('Intensity')
ax.set_title('Zoomed View: 14.5-15.1 min Region')
ax.legend()
ax.grid(True, alpha=0.3)

plt.tight_layout()
output_file = Path('check_14_8_peak_analysis.png')
plt.savefig(output_file, dpi=150, bbox_inches='tight')
print(f"\n[PLOT] Plot saved: {output_file}")
print("\n" + "=" * 70)

# Final summary
print("SUMMARY:")
print("=" * 70)
if peaks_around_14_8:
    print(f"[OK] {len(peaks_around_14_8)} peak(s) detected around 14.8 min")
    print("[OK] This region IS being quantified")
else:
    print("[X] NO peaks detected around 14.8 min")
    print("[X] This region is NOT being quantified")

    # Provide recommendation
    if corrected_region.max() > min_height:
        print("\n[!] RECOMMENDATION:")
        print("   The peak exists but may not meet detection criteria.")
        print("   Consider:")
        print("   1. Lowering the prominence threshold")
        print("   2. Adjusting the width parameter")
        print("   3. Manual integration for this specific region")
print("=" * 70)
