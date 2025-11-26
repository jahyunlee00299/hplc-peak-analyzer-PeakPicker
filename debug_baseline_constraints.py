"""
Debug: Check all baseline constraints
"""
import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Load data
csv_file = Path("result/Revision 재실험/250908_4MM_ACH.csv")
df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
time = df[0].values
intensity = df[1].values

if np.min(intensity) < 0:
    intensity = intensity - np.min(intensity)

print("=== Baseline Constraint Debug ===\n")

# Check 1-3 min reference region
reference_start_time = 1.0
reference_end_time = 3.0

time_per_point = (time[-1] - time[0]) / len(time)
ref_start_idx = int(reference_start_time / time_per_point)
ref_end_idx = int(reference_end_time / time_per_point)

print(f"Reference region (1-3 min):")
print(f"  Start idx: {ref_start_idx}, End idx: {ref_end_idx}")

if ref_start_idx < ref_end_idx < len(intensity):
    reference_region = intensity[ref_start_idx:ref_end_idx]
    reference_baseline = np.percentile(reference_region, 10)
    reference_range = np.ptp(reference_region)

    allowed_deviation = max(reference_range * 3.0, 1000)
    lower_bound = reference_baseline - allowed_deviation
    upper_bound = reference_baseline + allowed_deviation * 2.0

    print(f"  Region intensity range: {reference_region.min():.1f} - {reference_region.max():.1f}")
    print(f"  Reference baseline (10th percentile): {reference_baseline:.1f}")
    print(f"  Reference range (ptp): {reference_range:.1f}")
    print(f"  Allowed deviation: {allowed_deviation:.1f}")
    print(f"  Lower bound: {lower_bound:.1f}")
    print(f"  Upper bound: {upper_bound:.1f}")

    print(f"\nProblem analysis:")
    print(f"  If baseline should be ~14,670:")
    print(f"    Is it within bounds? {lower_bound:.1f} <= 14670 <= {upper_bound:.1f}")
    print(f"    Result: {lower_bound <= 14670 <= upper_bound}")
