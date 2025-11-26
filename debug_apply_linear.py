"""
Debug: Check baseline before and after apply_linear_baseline_to_peaks
"""
import pandas as pd
import numpy as np
from pathlib import Path
import sys
from scipy import signal

if 'hybrid_baseline' in sys.modules:
    del sys.modules['hybrid_baseline']

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from hybrid_baseline import HybridBaselineCorrector

# Load data
csv_file = Path("result/Revision 재실험/250908_4MM_ACH.csv")
df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
time = df[0].values
intensity = df[1].values

if np.min(intensity) < 0:
    intensity = intensity - np.min(intensity)

print("=== Baseline Generation Debug ===\n")

corrector = HybridBaselineCorrector(time, intensity)

# Step 1: Find anchor points
corrector.find_baseline_anchor_points(valley_prominence=0.01, percentile=10)
print(f"Step 1: Found {len(corrector.baseline_points)} anchor points")

# Step 2: Generate baseline with robust_fit
baseline_robust = corrector.generate_hybrid_baseline(method='robust_fit')
print(f"\nStep 2: Generated baseline with robust_fit")
print(f"  Baseline range: {baseline_robust.min():.1f} - {baseline_robust.max():.1f}")
print(f"  Baseline median: {np.median(baseline_robust):.1f}")

# Step 3: Detect peaks
corrected = np.maximum(intensity - baseline_robust, 0)
noise_level = np.percentile(corrected, 25) * 1.5
peaks, _ = signal.find_peaks(
    corrected,
    prominence=np.ptp(corrected) * 0.005,
    height=noise_level * 3,
    width=0
)
print(f"\nStep 3: Detected {len(peaks)} peaks")

# Step 4: Apply linear baseline to peaks
if len(peaks) > 0:
    hybrid_baseline = corrector.apply_linear_baseline_to_peaks(baseline_robust, peaks)
    print(f"\nStep 4: Applied linear baseline to peaks")
    print(f"  Hybrid baseline range: {hybrid_baseline.min():.1f} - {hybrid_baseline.max():.1f}")
    print(f"  Hybrid baseline median: {np.median(hybrid_baseline):.1f}")

    # Check difference
    diff = hybrid_baseline - baseline_robust
    print(f"\n  Difference (hybrid - robust):")
    print(f"    Min: {diff.min():.1f}")
    print(f"    Max: {diff.max():.1f}")
    print(f"    Mean: {diff.mean():.1f}")

    # Count zero values
    zero_count_robust = np.sum(baseline_robust == 0)
    zero_count_hybrid = np.sum(hybrid_baseline == 0)
    print(f"\n  Zero value count:")
    print(f"    Robust: {zero_count_robust} / {len(baseline_robust)} ({100*zero_count_robust/len(baseline_robust):.1f}%)")
    print(f"    Hybrid: {zero_count_hybrid} / {len(hybrid_baseline)} ({100*zero_count_hybrid/len(hybrid_baseline):.1f}%)")
else:
    hybrid_baseline = baseline_robust
    print(f"\nStep 4: No peaks detected, using robust baseline as is")

print(f"\n{'='*60}")
print(f"RESULT:")
print(f"  Expected median: ~14,670")
print(f"  Robust median: {np.median(baseline_robust):.1f}")
print(f"  Hybrid median: {np.median(hybrid_baseline):.1f}")
