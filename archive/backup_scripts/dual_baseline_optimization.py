"""
Baseline Optimization for Multiple HPLC Datasets
Compares different baseline correction methods on two CSV files
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import signal, sparse
from scipy.sparse.linalg import spsolve
from scipy.ndimage import grey_opening, grey_closing
from scipy.integrate import trapezoid
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')


class BaselineOptimizer:
    """Optimize baseline correction for HPLC data"""

    def __init__(self, time: np.ndarray, intensity: np.ndarray):
        self.time = time
        self.intensity = intensity
        self.baselines = {}

    def als_baseline(self, lam: float = 1e6, p: float = 0.001, niter: int = 20) -> np.ndarray:
        """Asymmetric Least Squares baseline"""
        L = len(self.intensity)
        D = sparse.diags([1, -2, 1], [0, -1, -2], shape=(L, L-2))
        D = lam * D.dot(D.transpose())
        w = np.ones(L)
        W = sparse.spdiags(w, 0, L, L)

        for i in range(niter):
            W.setdiag(w)
            Z = W + D
            z = spsolve(Z, w * self.intensity)
            w = p * (self.intensity > z) + (1 - p) * (self.intensity < z)

        return z

    def arpls_baseline(self, lam: float = 1e5, ratio: float = 0.001, niter: int = 100) -> np.ndarray:
        """Adaptive iteratively Reweighted Penalized Least Squares"""
        L = len(self.intensity)
        D = sparse.diags([1, -2, 1], [0, -1, -2], shape=(L, L-2))
        H = lam * D.dot(D.transpose())
        w = np.ones(L)

        for i in range(niter):
            W = sparse.spdiags(w, 0, L, L)
            Z = W + H
            z = spsolve(Z, w * self.intensity)
            d = self.intensity - z
            dn = d[d < 0]

            if len(dn) == 0:
                break

            m = np.mean(dn)
            s = np.std(dn)
            w_new = 1 / (1 + np.exp(2 * (d - (2*s - m)) / s))

            if np.linalg.norm(w_new - w) / np.linalg.norm(w) < ratio:
                break

            w = w_new

        return z

    def morphological_baseline(self, window_size: int = None, iterations: int = 2) -> np.ndarray:
        """Morphological baseline"""
        if window_size is None:
            window_size = max(10, len(self.intensity) // 20)

        baseline = self.intensity.copy()

        for _ in range(iterations):
            baseline = grey_opening(baseline, size=window_size)
            baseline = grey_closing(baseline, size=window_size)

        # Smooth
        window = min(len(baseline) - 1, window_size // 2 * 2 + 1)
        if window >= 5:
            baseline = signal.savgol_filter(baseline, window, 3)

        return baseline

    def adaptive_baseline(self, window_size: int = None, percentile: float = 10) -> np.ndarray:
        """Adaptive iterative baseline"""
        if window_size is None:
            window_size = max(50, len(self.intensity) // 20)

        baseline = self.intensity.copy()

        for iteration in range(5):
            baseline_points = []
            indices = []

            for i in range(0, len(baseline), window_size // 2):
                end = min(i + window_size, len(baseline))
                window = baseline[i:end]
                if len(window) > 0:
                    threshold = np.percentile(window, percentile)
                    mask = window <= threshold
                    if np.any(mask):
                        local_indices = np.where(mask)[0] + i
                        baseline_points.extend(baseline[local_indices])
                        indices.extend(local_indices)

            if len(indices) > 3:
                from scipy.interpolate import UnivariateSpline
                indices = np.array(indices)
                baseline_points = np.array(baseline_points)

                sort_idx = np.argsort(indices)
                indices = indices[sort_idx]
                baseline_points = baseline_points[sort_idx]

                # Remove duplicates
                unique_idx = np.unique(indices, return_index=True)[1]
                indices = indices[unique_idx]
                baseline_points = baseline_points[unique_idx]

                if len(indices) > 3:
                    spl = UnivariateSpline(indices, baseline_points, s=len(indices) * 0.1, k=min(3, len(indices)-1))
                    new_baseline = spl(np.arange(len(self.intensity)))

                    if np.max(np.abs(new_baseline - baseline)) < 0.01 * np.ptp(self.intensity):
                        break

                    baseline = new_baseline

        return baseline

    def polynomial_baseline(self, degree: int = 4) -> np.ndarray:
        """Polynomial baseline fitting"""
        # Find minima points for fitting
        window = min(51, len(self.intensity) // 10)
        if window % 2 == 0:
            window += 1

        if len(self.intensity) > window:
            smoothed = signal.savgol_filter(self.intensity, window, 3)
        else:
            smoothed = self.intensity

        # Find local minima
        minima_idx = signal.argrelmin(smoothed, order=window//2)[0]

        if len(minima_idx) < degree + 1:
            # Use percentile points
            percentile_points = []
            for i in range(0, len(self.intensity), len(self.intensity) // 10):
                end = min(i + len(self.intensity) // 10, len(self.intensity))
                if end > i:
                    p10 = np.percentile(self.intensity[i:end], 10)
                    idx = i + np.argmin(np.abs(self.intensity[i:end] - p10))
                    percentile_points.append(idx)
            minima_idx = np.array(percentile_points)

        # Fit polynomial through minima
        if len(minima_idx) > degree:
            coeffs = np.polyfit(self.time[minima_idx], self.intensity[minima_idx], degree)
        else:
            coeffs = np.polyfit(self.time, self.intensity, degree)

        baseline = np.polyval(coeffs, self.time)

        # Ensure baseline doesn't go above signal
        baseline = np.minimum(baseline, self.intensity)

        return baseline

    def optimize_all_methods(self) -> Dict:
        """Run all baseline methods and return results"""
        results = {}

        # Test different methods with various parameters
        methods_params = [
            ('als_1e5', lambda: self.als_baseline(lam=1e5, p=0.001)),
            ('als_1e6', lambda: self.als_baseline(lam=1e6, p=0.001)),
            ('als_1e7', lambda: self.als_baseline(lam=1e7, p=0.001)),
            ('arpls_1e4', lambda: self.arpls_baseline(lam=1e4)),
            ('arpls_1e5', lambda: self.arpls_baseline(lam=1e5)),
            ('arpls_1e6', lambda: self.arpls_baseline(lam=1e6)),
            ('morphological', lambda: self.morphological_baseline()),
            ('adaptive', lambda: self.adaptive_baseline()),
            ('polynomial_3', lambda: self.polynomial_baseline(degree=3)),
            ('polynomial_4', lambda: self.polynomial_baseline(degree=4)),
        ]

        for name, method in methods_params:
            try:
                baseline = method()
                corrected = self.intensity - baseline

                # Calculate quality metrics
                # 1. Smoothness of baseline (lower is smoother)
                smoothness = np.mean(np.abs(np.diff(baseline, 2)))

                # 2. Percentage of negative values after correction (should be minimal)
                neg_percentage = np.sum(corrected < 0) / len(corrected) * 100

                # 3. Baseline follows the bottom of peaks
                percentile_10 = np.percentile(self.intensity, 10)
                baseline_fit = np.mean(np.abs(baseline[self.intensity < percentile_10] -
                                             self.intensity[self.intensity < percentile_10]))

                # 4. Peak preservation (peaks should remain after correction)
                original_peaks = signal.find_peaks(self.intensity, prominence=np.ptp(self.intensity)*0.05)[0]
                if len(original_peaks) > 0:
                    corrected_peaks = signal.find_peaks(corrected, prominence=np.ptp(corrected)*0.05)[0]
                    peak_preservation = len(corrected_peaks) / len(original_peaks) * 100
                else:
                    peak_preservation = 100

                results[name] = {
                    'baseline': baseline,
                    'corrected': corrected,
                    'smoothness': smoothness,
                    'neg_percentage': neg_percentage,
                    'baseline_fit': baseline_fit,
                    'peak_preservation': peak_preservation,
                    'score': 100 - neg_percentage - smoothness/10 - baseline_fit/10 + peak_preservation/2
                }

            except Exception as e:
                print(f"Error with method {name}: {e}")

        return results


def analyze_dual_datasets():
    """Analyze both CSV files and optimize baselines"""

    # Load first dataset (EXPORT.CSV)
    print("Loading EXPORT.CSV...")
    df1 = pd.read_csv('peakpicker/examples/EXPORT.CSV',
                      header=None, sep='\t', encoding='utf-16-le')
    time1 = df1[0].values
    intensity1 = df1[1].values

    # Shift to positive if needed
    if np.min(intensity1) < 0:
        intensity1 = intensity1 - np.min(intensity1)

    print(f"EXPORT.CSV: {len(time1)} points, range {intensity1.min():.2f} to {intensity1.max():.2f}")

    # Load second dataset (sample_chromatogram.csv)
    print("\nLoading sample_chromatogram.csv...")
    df2 = pd.read_csv('peakpicker/examples/sample_chromatogram.csv')
    time2 = df2['Time'].values
    intensity2 = df2['Intensity'].values

    print(f"sample_chromatogram: {len(time2)} points, range {intensity2.min():.2f} to {intensity2.max():.2f}")

    # Optimize baselines for both datasets
    print("\n" + "="*60)
    print("OPTIMIZING BASELINES")
    print("="*60)

    optimizer1 = BaselineOptimizer(time1, intensity1)
    results1 = optimizer1.optimize_all_methods()

    optimizer2 = BaselineOptimizer(time2, intensity2)
    results2 = optimizer2.optimize_all_methods()

    # Find best methods for each dataset
    best1 = max(results1.items(), key=lambda x: x[1]['score'])
    best2 = max(results2.items(), key=lambda x: x[1]['score'])

    print(f"\nBest method for EXPORT.CSV: {best1[0]}")
    print(f"  Score: {best1[1]['score']:.2f}")
    print(f"  Smoothness: {best1[1]['smoothness']:.4f}")
    print(f"  Negative %: {best1[1]['neg_percentage']:.2f}%")
    print(f"  Peak preservation: {best1[1]['peak_preservation']:.1f}%")

    print(f"\nBest method for sample_chromatogram: {best2[0]}")
    print(f"  Score: {best2[1]['score']:.2f}")
    print(f"  Smoothness: {best2[1]['smoothness']:.4f}")
    print(f"  Negative %: {best2[1]['neg_percentage']:.2f}%")
    print(f"  Peak preservation: {best2[1]['peak_preservation']:.1f}%")

    # Visualize results
    fig, axes = plt.subplots(2, 4, figsize=(16, 8))

    # Dataset 1 - EXPORT.CSV
    axes[0, 0].plot(time1, intensity1, 'b-', alpha=0.7, label='Original')
    axes[0, 0].plot(time1, best1[1]['baseline'], 'r--', label=f'Best: {best1[0]}')
    axes[0, 0].set_title('EXPORT.CSV - Best Baseline')
    axes[0, 0].set_xlabel('Time (min)')
    axes[0, 0].set_ylabel('Intensity')
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)

    axes[0, 1].plot(time1, best1[1]['corrected'], 'g-', alpha=0.7)
    axes[0, 1].set_title('EXPORT.CSV - Corrected')
    axes[0, 1].set_xlabel('Time (min)')
    axes[0, 1].set_ylabel('Intensity')
    axes[0, 1].grid(True, alpha=0.3)

    # Compare top 3 methods for dataset 1
    top3_1 = sorted(results1.items(), key=lambda x: x[1]['score'], reverse=True)[:3]
    for i, (name, res) in enumerate(top3_1):
        axes[0, 2].plot(time1, res['baseline'], alpha=0.7, label=f'{name} ({res["score"]:.1f})')
    axes[0, 2].set_title('EXPORT.CSV - Top 3 Methods')
    axes[0, 2].set_xlabel('Time (min)')
    axes[0, 2].set_ylabel('Intensity')
    axes[0, 2].legend(fontsize=8)
    axes[0, 2].grid(True, alpha=0.3)

    # Score comparison for dataset 1
    methods = list(results1.keys())
    scores = [results1[m]['score'] for m in methods]
    axes[0, 3].barh(range(len(methods)), scores)
    axes[0, 3].set_yticks(range(len(methods)))
    axes[0, 3].set_yticklabels(methods, fontsize=8)
    axes[0, 3].set_xlabel('Score')
    axes[0, 3].set_title('EXPORT.CSV - Method Scores')
    axes[0, 3].grid(True, alpha=0.3)

    # Dataset 2 - sample_chromatogram
    axes[1, 0].plot(time2, intensity2, 'b-', alpha=0.7, label='Original')
    axes[1, 0].plot(time2, best2[1]['baseline'], 'r--', label=f'Best: {best2[0]}')
    axes[1, 0].set_title('Sample Chromatogram - Best Baseline')
    axes[1, 0].set_xlabel('Time (min)')
    axes[1, 0].set_ylabel('Intensity')
    axes[1, 0].legend()
    axes[1, 0].grid(True, alpha=0.3)

    axes[1, 1].plot(time2, best2[1]['corrected'], 'g-', alpha=0.7)
    axes[1, 1].set_title('Sample Chromatogram - Corrected')
    axes[1, 1].set_xlabel('Time (min)')
    axes[1, 1].set_ylabel('Intensity')
    axes[1, 1].grid(True, alpha=0.3)

    # Compare top 3 methods for dataset 2
    top3_2 = sorted(results2.items(), key=lambda x: x[1]['score'], reverse=True)[:3]
    for i, (name, res) in enumerate(top3_2):
        axes[1, 2].plot(time2, res['baseline'], alpha=0.7, label=f'{name} ({res["score"]:.1f})')
    axes[1, 2].set_title('Sample Chromatogram - Top 3 Methods')
    axes[1, 2].set_xlabel('Time (min)')
    axes[1, 2].set_ylabel('Intensity')
    axes[1, 2].legend(fontsize=8)
    axes[1, 2].grid(True, alpha=0.3)

    # Score comparison for dataset 2
    methods = list(results2.keys())
    scores = [results2[m]['score'] for m in methods]
    axes[1, 3].barh(range(len(methods)), scores)
    axes[1, 3].set_yticks(range(len(methods)))
    axes[1, 3].set_yticklabels(methods, fontsize=8)
    axes[1, 3].set_xlabel('Score')
    axes[1, 3].set_title('Sample Chromatogram - Method Scores')
    axes[1, 3].grid(True, alpha=0.3)

    plt.suptitle('Baseline Optimization Comparison', fontsize=14, y=1.02)
    plt.tight_layout()
    plt.savefig('baseline_optimization_comparison.png', dpi=100, bbox_inches='tight')
    plt.show()

    # Peak detection comparison
    print("\n" + "="*60)
    print("PEAK DETECTION AFTER BASELINE CORRECTION")
    print("="*60)

    # Detect peaks with best baseline for each dataset
    corrected1 = best1[1]['corrected']
    corrected2 = best2[1]['corrected']

    # Dataset 1 peaks
    peaks1, properties1 = signal.find_peaks(
        corrected1,
        prominence=np.ptp(corrected1) * 0.01,
        height=np.std(corrected1) * 3,
        width=3
    )

    print(f"\nEXPORT.CSV: {len(peaks1)} peaks detected")
    if len(peaks1) > 0:
        print(f"  Peak RTs: {[f'{time1[p]:.2f}' for p in peaks1[:10]]}")  # Show first 10

    # Dataset 2 peaks
    peaks2, properties2 = signal.find_peaks(
        corrected2,
        prominence=np.ptp(corrected2) * 0.01,
        height=np.std(corrected2) * 3,
        width=3
    )

    print(f"\nSample Chromatogram: {len(peaks2)} peaks detected")
    if len(peaks2) > 0:
        print(f"  Peak RTs: {[f'{time2[p]:.2f}' for p in peaks2]}")

    return results1, results2, best1, best2


if __name__ == "__main__":
    results = analyze_dual_datasets()

    print("\n" + "="*60)
    print("OPTIMIZATION COMPLETE")
    print("="*60)
    print("\nResults saved to:")
    print("  - baseline_optimization_comparison.png")
    print("\nKey findings:")
    print("  - Different datasets may require different baseline methods")
    print("  - Adaptive and ALS methods generally perform well")
    print("  - Parameter tuning is crucial for optimal results")