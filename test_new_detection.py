"""
Test the new two-pass peak detection on 250908 files
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from hplc_analyzer_enhanced import EnhancedHPLCAnalyzer

# Test on the specific file with 14.8 min peak
csv_file = Path("result/Revision 재실험/250908_FLOXU_D_GA_2NDACP_3_5H.csv")

print("=" * 80)
print("TESTING NEW TWO-PASS ADAPTIVE PEAK DETECTION")
print("=" * 80)
print(f"\nFile: {csv_file.name}\n")

# Create analyzer with new detection
analyzer = EnhancedHPLCAnalyzer(
    data_directory=str(csv_file.parent),
    use_hybrid_baseline=True,
    enable_deconvolution=False  # Disable for now to focus on detection
)

# Analyze the file
result = analyzer.analyze_csv_file(csv_file)

if 'error' in result:
    print(f"ERROR: {result['error']}")
    sys.exit(1)

# Check results
time = result['time']
intensity = result['intensity']
corrected = result['corrected']
peaks = result['peaks']
peak_data = result['peak_data']

print("\n" + "=" * 80)
print("DETECTION RESULTS:")
print("=" * 80)
print(f"Total peaks detected: {len(peaks)}\n")

# Show all peaks
for p in peak_data:
    print(f"Peak #{p['peak_number']}: RT={p['retention_time']:.3f} min, "
          f"Height={p['height']:.2f}, Area={p['area']:.2f}, "
          f"Prom={p['prominence']:.2f}, SNR={p['snr']:.1f}")

# Check for 14.8 min peak specifically
print("\n" + "=" * 80)
print("CHECKING FOR 14.8 MIN PEAK:")
print("=" * 80)

peaks_around_14_8 = [p for p in peak_data if 14.5 <= p['retention_time'] <= 15.1]

if peaks_around_14_8:
    print(f"\n[SUCCESS] Found {len(peaks_around_14_8)} peak(s) in 14.5-15.1 min range:")
    for p in peaks_around_14_8:
        print(f"  Peak #{p['peak_number']}: RT={p['retention_time']:.3f} min")
        print(f"    Height: {p['height']:.2f}")
        print(f"    Area: {p['area']:.2f}")
        print(f"    Prominence: {p['prominence']:.2f}")
        print(f"    SNR: {p['snr']:.1f}")
else:
    print("\n[FAILED] No peaks found in 14.5-15.1 min range")

# Check for other expected small peaks
print("\n" + "=" * 80)
print("OTHER SMALL PEAKS:")
print("=" * 80)

peaks_15_to_20 = [p for p in peak_data if 15.0 <= p['retention_time'] <= 20.0]
if peaks_15_to_20:
    print(f"\nFound {len(peaks_15_to_20)} peak(s) in 15-20 min range:")
    for p in peaks_15_to_20:
        print(f"  Peak #{p['peak_number']}: RT={p['retention_time']:.3f} min, "
              f"Height={p['height']:.2f}, Area={p['area']:.2f}")
else:
    print("\nNo peaks found in 15-20 min range")

# Create visualization
fig, axes = plt.subplots(2, 1, figsize=(14, 8))

# Full chromatogram with all detected peaks
ax = axes[0]
ax.plot(time, corrected, 'b-', linewidth=1, label='Baseline Corrected')
peak_times = [p['retention_time'] for p in peak_data]
peak_heights = [p['height'] for p in peak_data]
ax.plot(peak_times, peak_heights, 'ro', markersize=8, label='Detected Peaks')
ax.axvline(14.8, color='green', linestyle=':', linewidth=2, label='Target: 14.8 min', alpha=0.7)
ax.set_xlabel('Time (min)')
ax.set_ylabel('Intensity')
ax.set_title(f'{csv_file.name} - All Detected Peaks (Two-Pass Method)')
ax.legend()
ax.grid(True, alpha=0.3)

# Zoomed view around 14.8 min
ax = axes[1]
mask = (time >= 14.0) & (time <= 18.0)
ax.plot(time[mask], corrected[mask], 'b-', linewidth=2, label='Baseline Corrected')

# Mark detected peaks in this region
peaks_in_region = [p for p in peak_data if 14.0 <= p['retention_time'] <= 18.0]
for p in peaks_in_region:
    ax.plot(p['retention_time'], p['height'], 'ro', markersize=10)
    ax.text(p['retention_time'], p['height'] * 1.1, f"{p['retention_time']:.2f}",
            ha='center', va='bottom', fontsize=9)

ax.axvline(14.8, color='green', linestyle=':', linewidth=2, label='Target: 14.8 min', alpha=0.7)
ax.set_xlabel('Time (min)')
ax.set_ylabel('Intensity')
ax.set_title('Zoomed View: 14-18 min Region')
ax.legend()
ax.grid(True, alpha=0.3)

plt.tight_layout()
output_file = Path('test_new_detection.png')
plt.savefig(output_file, dpi=150, bbox_inches='tight')
print(f"\n[PLOT] Visualization saved: {output_file}")

print("\n" + "=" * 80)
print("SUMMARY:")
print("=" * 80)

if peaks_around_14_8:
    print("[OK] Two-pass detection successfully detects the 14.8 min peak!")
else:
    print("[FAILED] Two-pass detection still misses the 14.8 min peak")

print("\n")
