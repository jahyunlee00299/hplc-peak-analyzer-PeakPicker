"""
Test y-axis setting
"""
import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
import matplotlib.ticker as ticker

# Load sample data
csv_file = Path("result/Revision 재실험/250909_MAIN_FLOXU_GLYACP_12MM_NC_3_6H.csv")
df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
time = df[0].values
intensity = df[1].values

if np.min(intensity) < 0:
    intensity = intensity - np.min(intensity)

# Find break points
peaks, properties = find_peaks(intensity, height=intensity.max() * 0.01, prominence=intensity.max() * 0.005)
if len(peaks) > 0:
    peak_heights = intensity[peaks]
    max_peak = peak_heights.max()
    break_start = max_peak * 0.10
    break_end = max_peak * 0.70
else:
    max_signal = intensity.max()
    break_start = max_signal * 0.10
    break_end = max_signal * 0.70

print(f"Intensity min: {intensity.min():.2f}")
print(f"Intensity max: {intensity.max():.2f}")
print(f"Break start: {break_start:.2f}")
print(f"Break end: {break_end:.2f}")

# Calculate y_min
if intensity.min() < -500:
    y_min_original = intensity.min() * 1.1
else:
    y_min_original = -500

print(f"Calculated y_min_original: {y_min_original:.2f}")

# Test plot
fig = plt.figure(figsize=(10, 8))
height_ratios = [2, 0.25, 0, 6]
gs = fig.add_gridspec(4, 1, height_ratios=height_ratios, hspace=0.25)

ax_top = fig.add_subplot(gs[0, 0])
ax_bottom = fig.add_subplot(gs[3, 0])

# Plot on both
for ax in [ax_top, ax_bottom]:
    ax.plot(time, intensity, 'b-', linewidth=1.5, alpha=0.7)
    ax.grid(True, alpha=0.3)

# Set limits
ax_top.set_ylim(break_end, intensity.max() * 1.01)
print(f"Setting ax_bottom.set_ylim({y_min_original:.2f}, {break_start:.2f})")
ax_bottom.set_ylim(y_min_original, break_start)

# Check actual limits
actual_ylim = ax_bottom.get_ylim()
print(f"Actual ylim after setting: {actual_ylim}")

ax_top.spines['bottom'].set_visible(False)
ax_bottom.spines['top'].set_visible(False)
ax_top.xaxis.set_visible(False)

ax_top.set_title('Top panel')
ax_bottom.set_title(f'Bottom panel (should start at {y_min_original:.0f})')
ax_bottom.set_xlabel('Time (min)')

plt.tight_layout()
plt.savefig('test_y_axis.png', dpi=150)
print(f"\nSaved test_y_axis.png")
