"""
Test the new detection on all 250908 files
"""
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from hplc_analyzer_enhanced import EnhancedHPLCAnalyzer

# Get all 250908 files
data_dir = Path("result/Revision 재실험")
files = sorted(data_dir.glob("250908*.csv"))

print("=" * 80)
print("TESTING NEW DETECTION ON ALL 250908 FILES")
print("=" * 80)
print(f"\nFound {len(files)} files\n")

# Create analyzer
analyzer = EnhancedHPLCAnalyzer(
    data_directory=str(data_dir),
    use_hybrid_baseline=True,
    enable_deconvolution=False
)

results_summary = []

for csv_file in files:
    print("-" * 80)
    print(f"\nFile: {csv_file.name}")

    # Analyze
    result = analyzer.analyze_csv_file(csv_file)

    if 'error' in result:
        print(f"  ERROR: {result['error']}")
        continue

    peak_data = result['peak_data']
    print(f"  Total peaks detected: {len(peak_data)}")

    # Categorize peaks
    if peak_data:
        heights = [p['height'] for p in peak_data]
        max_height = max(heights)

        major_peaks = [p for p in peak_data if p['height'] > max_height * 0.1]
        minor_peaks = [p for p in peak_data if p['height'] <= max_height * 0.1]

        print(f"  Major peaks (>10% of max): {len(major_peaks)}")
        print(f"  Minor peaks (<=10% of max): {len(minor_peaks)}")

        if minor_peaks:
            print(f"  Minor peak details:")
            for p in minor_peaks:
                print(f"    RT={p['retention_time']:.3f} min, Height={p['height']:.2f}, Area={p['area']:.2f}")

        # Check for 14-15 min region specifically
        peaks_14_15 = [p for p in peak_data if 14.0 <= p['retention_time'] <= 15.0]
        if peaks_14_15:
            print(f"  [FOUND] Peaks in 14-15 min region: {len(peaks_14_15)}")

        results_summary.append({
            'file': csv_file.name,
            'total_peaks': len(peak_data),
            'major_peaks': len(major_peaks),
            'minor_peaks': len(minor_peaks),
            'has_14_15_peak': len(peaks_14_15) > 0
        })

print("\n" + "=" * 80)
print("SUMMARY OF ALL FILES:")
print("=" * 80)

total_files = len(results_summary)
files_with_minor = sum(1 for r in results_summary if r['minor_peaks'] > 0)
files_with_14_15 = sum(1 for r in results_summary if r['has_14_15_peak'])

print(f"\nTotal files analyzed: {total_files}")
print(f"Files with minor peaks detected: {files_with_minor}")
print(f"Files with peaks in 14-15 min region: {files_with_14_15}")

print("\nDetailed breakdown:")
for r in results_summary:
    status = "[OK]" if r['minor_peaks'] > 0 else "    "
    region_14 = "[14-15]" if r['has_14_15_peak'] else "      "
    print(f"  {status} {region_14} {r['file']}: {r['total_peaks']} peaks "
          f"({r['major_peaks']} major, {r['minor_peaks']} minor)")

print("\n" + "=" * 80)
print("CONCLUSION:")
print("=" * 80)
if files_with_minor > 0:
    print(f"[SUCCESS] New detection method finds minor peaks in {files_with_minor}/{total_files} files")
else:
    print("[INFO] No files with minor peaks detected (might be normal for these samples)")

print()
