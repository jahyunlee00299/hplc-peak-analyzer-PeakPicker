r"""
Half-Peak Quantification verification test
==========================================================
Part 1: synthetic data (symmetric/asymmetric Gaussian)
"""

import sys
import os
import numpy as np
from scipy.integrate import trapezoid
from scipy import signal
from scipy.ndimage import minimum_filter1d, uniform_filter1d

# matplotlib Agg backend (no GUI)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Korean font (kept for CJK-capable rendering environments)
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

# PeakPicker src module path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# ============================================================
#  Part 1: synthetic data test
# ============================================================
def test_synthetic():
    print("=" * 70)
    print("  Part 1: synthetic data test (Gaussian peak)")
    print("=" * 70)

    dt = 0.001  # time resolution (min)
    time = np.arange(0, 10, dt)
    rt = 5.0
    sigma = 0.3
    amplitude = 100000

    # --- 1-a. Symmetric Gaussian peak ---
    symmetric = amplitude * np.exp(-0.5 * ((time - rt) / sigma) ** 2)

    apex_idx = np.argmin(np.abs(time - rt))
    time_sec = time * 60  # seconds

    full_area = trapezoid(symmetric, time_sec)
    left_area = trapezoid(symmetric[:apex_idx + 1], time_sec[:apex_idx + 1])
    right_area = trapezoid(symmetric[apex_idx:], time_sec[apex_idx:])

    left_x2 = left_area * 2
    right_x2 = right_area * 2

    err_left = abs(left_x2 - full_area) / full_area * 100
    err_right = abs(right_x2 - full_area) / full_area * 100

    print(f"\n[1-a] Symmetric Gaussian (RT={rt}, sigma={sigma}, amp={amplitude})")
    print(f"  Full area          : {full_area:>15.1f}")
    print(f"  Left half x2        : {left_x2:>15.1f}  (error {err_left:.4f}%)")
    print(f"  Right half x2       : {right_x2:>15.1f}  (error {err_right:.4f}%)")
    print(f"  Asymmetry (L/R)     : {left_area / right_area:.6f}")

    sym_pass = err_left < 1.0 and err_right < 1.0
    print(f"  --> Result: {'PASS' if sym_pass else 'FAIL'}  (criterion: error < 1%)")

    # --- 1-b. Asymmetric peak (right shoulder) ---
    shoulder = 30000 * np.exp(-0.5 * ((time - (rt + 0.4)) / 0.2) ** 2)
    asymmetric = symmetric + shoulder

    asym_apex_idx = np.argmax(asymmetric)
    asym_full = trapezoid(asymmetric, time_sec)
    asym_left = trapezoid(asymmetric[:asym_apex_idx + 1], time_sec[:asym_apex_idx + 1])
    asym_right = trapezoid(asymmetric[asym_apex_idx:], time_sec[asym_apex_idx:])

    # True pure peak area (no shoulder)
    true_area = full_area

    err_full = abs(asym_full - true_area) / true_area * 100
    err_left_asym = abs(asym_left * 2 - true_area) / true_area * 100
    err_right_asym = abs(asym_right * 2 - true_area) / true_area * 100

    print("\n[1-b] Asymmetric peak (right shoulder added, 30% size)")
    print(f"  Pure peak area (true value) : {true_area:>15.1f}")
    print(f"  Full area                    : {asym_full:>15.1f}  (error {err_full:.2f}%)")
    print(f"  Left half x2                 : {asym_left * 2:>15.1f}  (error {err_left_asym:.2f}%)")
    print(f"  Right half x2                : {asym_right * 2:>15.1f}  (error {err_right_asym:.2f}%)")
    print(f"  Asymmetry (L/R)              : {asym_left / asym_right:.4f}")
    print(f"  --> Left half is more accurate: {err_left_asym < err_full}")

    return {
        'time': time,
        'symmetric': symmetric,
        'asymmetric': asymmetric,
        'apex_idx': apex_idx,
        'asym_apex_idx': asym_apex_idx,
        'sym_pass': sym_pass,
    }


def _rolling_min_baseline(intensity, window_frac=0.2):
    """Simple rolling-minimum baseline estimate (suitable for RID data)"""
    win = max(int(len(intensity) * window_frac), 50)
    base = minimum_filter1d(intensity, size=win)
    base = uniform_filter1d(base, size=win)
    return base
