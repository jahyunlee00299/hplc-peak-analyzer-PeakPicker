r"""
반쪽 피크 정량(Half-Peak Quantification) 기능 검증 테스트
==========================================================
Part 1: 합성 데이터 (대칭/비대칭 Gaussian)
"""

import sys
import os
import numpy as np
from scipy.integrate import trapezoid
from scipy import signal
from scipy.ndimage import minimum_filter1d, uniform_filter1d

# matplotlib Agg 백엔드 (GUI 없이)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# 한글 폰트
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

# PeakPicker src 모듈 경로
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


# ============================================================
#  Part 1: 합성 데이터 테스트
# ============================================================
def test_synthetic():
    print("=" * 70)
    print("  Part 1: 합성 데이터 테스트 (Gaussian 피크)")
    print("=" * 70)

    dt = 0.001  # 시간 해상도 (분)
    time = np.arange(0, 10, dt)
    rt = 5.0
    sigma = 0.3
    amplitude = 100000

    # --- 1-a. 대칭 Gaussian 피크 ---
    symmetric = amplitude * np.exp(-0.5 * ((time - rt) / sigma) ** 2)

    apex_idx = np.argmin(np.abs(time - rt))
    time_sec = time * 60  # 초 단위

    full_area = trapezoid(symmetric, time_sec)
    left_area = trapezoid(symmetric[:apex_idx + 1], time_sec[:apex_idx + 1])
    right_area = trapezoid(symmetric[apex_idx:], time_sec[apex_idx:])

    left_x2 = left_area * 2
    right_x2 = right_area * 2

    err_left = abs(left_x2 - full_area) / full_area * 100
    err_right = abs(right_x2 - full_area) / full_area * 100

    print(f"\n[1-a] 대칭 Gaussian (RT={rt}, sigma={sigma}, amp={amplitude})")
    print(f"  전체 면적       : {full_area:>15.1f}")
    print(f"  왼쪽 반쪽 x2    : {left_x2:>15.1f}  (오차 {err_left:.4f}%)")
    print(f"  오른쪽 반쪽 x2  : {right_x2:>15.1f}  (오차 {err_right:.4f}%)")
    print(f"  비대칭도 (L/R)  : {left_area / right_area:.6f}")

    sym_pass = err_left < 1.0 and err_right < 1.0
    print(f"  --> 결과: {'통과' if sym_pass else '실패'}  (오차 < 1% 기준)")

    # --- 1-b. 비대칭 피크 (오른쪽 어깨) ---
    shoulder = 30000 * np.exp(-0.5 * ((time - (rt + 0.4)) / 0.2) ** 2)
    asymmetric = symmetric + shoulder

    asym_apex_idx = np.argmax(asymmetric)
    asym_full = trapezoid(asymmetric, time_sec)
    asym_left = trapezoid(asymmetric[:asym_apex_idx + 1], time_sec[:asym_apex_idx + 1])
    asym_right = trapezoid(asymmetric[asym_apex_idx:], time_sec[asym_apex_idx:])

    # 실제 순수 피크 면적 (어깨 없음)
    true_area = full_area

    err_full = abs(asym_full - true_area) / true_area * 100
    err_left_asym = abs(asym_left * 2 - true_area) / true_area * 100
    err_right_asym = abs(asym_right * 2 - true_area) / true_area * 100

    print("\n[1-b] 비대칭 피크 (오른쪽 어깨 추가, 30% 크기)")
    print(f"  순수 피크 면적 (참값) : {true_area:>15.1f}")
    print(f"  전체 면적             : {asym_full:>15.1f}  (오차 {err_full:.2f}%)")
    print(f"  왼쪽 반쪽 x2          : {asym_left * 2:>15.1f}  (오차 {err_left_asym:.2f}%)")
    print(f"  오른쪽 반쪽 x2        : {asym_right * 2:>15.1f}  (오차 {err_right_asym:.2f}%)")
    print(f"  비대칭도 (L/R)        : {asym_left / asym_right:.4f}")
    print(f"  --> 왼쪽 반쪽이 더 정확: {err_left_asym < err_full}")

    return {
        'time': time,
        'symmetric': symmetric,
        'asymmetric': asymmetric,
        'apex_idx': apex_idx,
        'asym_apex_idx': asym_apex_idx,
        'sym_pass': sym_pass,
    }


def _rolling_min_baseline(intensity, window_frac=0.2):
    """Rolling-minimum 기반 간단한 베이스라인 추정 (RID 데이터에 적합)"""
    win = max(int(len(intensity) * window_frac), 50)
    base = minimum_filter1d(intensity, size=win)
    base = uniform_filter1d(base, size=win)
    return base
