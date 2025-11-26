"""
Check the actual data to understand the issue with negative values
"""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def check_data():
    """Check the raw data for issues"""

    csv_file = Path("result/Riba pH temp pre/250829_RIBA_PH_SP6_18H.csv")

    if not csv_file.exists():
        print(f"File not found: {csv_file}")
        return

    print(f"Checking data from: {csv_file.name}")

    # Load data
    df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
    print(f"\nDataFrame shape: {df.shape}")
    print(f"DataFrame columns: {df.columns.tolist()}")

    # Check first few rows
    print("\nFirst 5 rows:")
    print(df.head())

    time = df[0].values
    intensity = df[1].values

    print(f"\nData statistics:")
    print(f"  Time range: {time.min():.2f} to {time.max():.2f} minutes")
    print(f"  Intensity range: {intensity.min():.2f} to {intensity.max():.2f}")
    print(f"  Mean intensity: {intensity.mean():.2f}")
    print(f"  Median intensity: {np.median(intensity):.2f}")

    # Check for negative values
    neg_count = np.sum(intensity < 0)
    print(f"\nNegative values: {neg_count} out of {len(intensity)} ({neg_count/len(intensity)*100:.1f}%)")

    if neg_count > 0:
        print("\nNegative value statistics:")
        neg_values = intensity[intensity < 0]
        print(f"  Min negative: {neg_values.min():.2f}")
        print(f"  Max negative: {neg_values.max():.2f}")
        print(f"  Mean negative: {neg_values.mean():.2f}")

    # Plot the raw data
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # Plot 1: Full signal
    ax1 = axes[0, 0]
    ax1.plot(time, intensity, 'b-', linewidth=1)
    ax1.axhline(y=0, color='r', linestyle='--', alpha=0.5)
    ax1.set_title('Raw Signal (Full View)')
    ax1.set_xlabel('Time (min)')
    ax1.set_ylabel('Intensity')
    ax1.grid(True, alpha=0.3)

    # Plot 2: Histogram
    ax2 = axes[0, 1]
    ax2.hist(intensity, bins=100, alpha=0.7, color='blue', edgecolor='black')
    ax2.axvline(x=0, color='r', linestyle='--', alpha=0.5)
    ax2.set_title('Intensity Distribution')
    ax2.set_xlabel('Intensity')
    ax2.set_ylabel('Count')
    ax2.grid(True, alpha=0.3)

    # Plot 3: First 3 minutes (baseline region)
    ax3 = axes[1, 0]
    mask = time <= 3
    ax3.plot(time[mask], intensity[mask], 'b-', linewidth=1, marker='o', markersize=2)
    ax3.axhline(y=0, color='r', linestyle='--', alpha=0.5)
    ax3.set_title('First 3 Minutes (Baseline Region)')
    ax3.set_xlabel('Time (min)')
    ax3.set_ylabel('Intensity')
    ax3.grid(True, alpha=0.3)

    # Plot 4: Signal with baseline estimate
    ax4 = axes[1, 1]
    ax4.plot(time, intensity, 'b-', linewidth=1, alpha=0.8, label='Signal')

    # Simple baseline estimate - use lowest 5% of values
    baseline_estimate = np.percentile(intensity, 5)
    ax4.axhline(y=baseline_estimate, color='r', linestyle='--', alpha=0.5,
                label=f'5th percentile: {baseline_estimate:.0f}')

    # Show where intensity is below the 5th percentile
    below_baseline = intensity < baseline_estimate
    if np.any(below_baseline):
        ax4.scatter(time[below_baseline], intensity[below_baseline],
                   c='red', s=1, alpha=0.5, label='Below 5th percentile')

    ax4.set_title('Signal with Baseline Estimate')
    ax4.set_xlabel('Time (min)')
    ax4.set_ylabel('Intensity')
    ax4.legend()
    ax4.grid(True, alpha=0.3)

    plt.suptitle('Raw Data Analysis', fontsize=14, fontweight='bold')
    plt.tight_layout()

    # Save figure
    output_file = Path("data_analysis.png")
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\nPlot saved to: {output_file}")

    plt.show()


if __name__ == "__main__":
    check_data()