"""
Test baseline with fresh import
"""
import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
import sys
import importlib

# Force fresh import
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

print("Testing with FRESH import...")

# Apply baseline correction
corrector = HybridBaselineCorrector(time, intensity)
baseline, params = corrector.optimize_baseline_with_linear_peaks()

print(f"\nBaseline statistics:")
print(f"  Min: {baseline.min():.1f}")
print(f"  Max: {baseline.max():.1f}")
print(f"  Mean: {baseline.mean():.1f}")
print(f"  Median: {np.median(baseline):.1f}")

print(f"\nExpected baseline: ~14,670")
print(f"Actual baseline median: {np.median(baseline):.1f}")

if np.median(baseline) > 10000:
    print("\n SUCCESS! Baseline is correct!")
else:
    print("\n FAIL! Baseline is still too low!")

# Save plot
fig, ax = plt.subplots(figsize=(16, 6))
ax.plot(time, intensity, 'b-', linewidth=1.5, label='Original Signal', alpha=0.7)
ax.plot(time, baseline, 'r-', linewidth=1.5, label='Baseline', alpha=0.8)
ax.set_xlabel('Time (min)')
ax.set_ylabel('Intensity')
ax.set_title('Baseline Test (Fresh Import)')
ax.legend()
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig('test_baseline_fresh.png', dpi=150)
print(f"\nSaved: test_baseline_fresh.png")
plt.close()
