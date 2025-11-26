"""
Debug: Check if 1-3 min constraint is being applied
"""
import pandas as pd
import numpy as np
from pathlib import Path
import sys

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

print("=== 1-3 Min Constraint Debug ===\n")

corrector = HybridBaselineCorrector(time, intensity)

# Check 1-3 min region calculation
reference_start_time = 1.0
reference_end_time = 3.0

time_per_point = (time[-1] - time[0]) / len(time)
ref_start_idx = int(reference_start_time / time_per_point)
ref_end_idx = int(reference_end_time / time_per_point)

print(f"Time array:")
print(f"  Min time: {time.min():.2f}")
print(f"  Max time: {time.max():.2f}")
print(f"  Len time: {len(time)}")
print(f"  Time per point: {time_per_point:.4f}")

print(f"\n1-3 min region:")
print(f"  ref_start_idx: {ref_start_idx}")
print(f"  ref_end_idx: {ref_end_idx}")
print(f"  len(intensity): {len(intensity)}")

print(f"\nCondition check:")
print(f"  ref_start_idx < ref_end_idx: {ref_start_idx < ref_end_idx}")
print(f"  ref_end_idx < len(intensity): {ref_end_idx < len(intensity)}")
print(f"  OVERALL: {ref_start_idx < ref_end_idx < len(intensity)}")

if ref_start_idx < ref_end_idx < len(intensity):
    reference_region = intensity[ref_start_idx:ref_end_idx]
    reference_baseline = np.percentile(reference_region, 10)
    reference_range = np.ptp(reference_region)

    allowed_deviation = max(reference_range * 3.0, 1000)
    lower_bound = reference_baseline - allowed_deviation
    upper_bound = reference_baseline + allowed_deviation * 2.0

    print(f"\nConstraint values:")
    print(f"  reference_baseline: {reference_baseline:.1f}")
    print(f"  reference_range: {reference_range:.1f}")
    print(f"  allowed_deviation: {allowed_deviation:.1f}")
    print(f"  lower_bound: {lower_bound:.1f}")
    print(f"  upper_bound: {upper_bound:.1f}")

    print(f"\n>>> CONSTRAINT SHOULD BE APPLIED <<<")
else:
    print(f"\n>>> CONSTRAINT IS NOT APPLIED <<<")
