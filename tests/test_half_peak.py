r"""
반쪽 피크 정량(Half-Peak Quantification) 기능 검증 테스트
==========================================================
Part 1: 합성 데이터 (대칭/비대칭 Gaussian)
Part 2: 실제 .ch 데이터 (C:\Chem32)
Part 3: 시각화 (half_peak_comparison.png)
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
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


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

    print(f"\n[1-b] 비대칭 피크 (오른쪽 어깨 추가, 30% 크기)")
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


# ============================================================
#  Part 2: 실제 데이터 테스트
# ============================================================
def test_real_data():
    print("\n" + "=" * 70)
    print("  Part 2: 실제 .ch 데이터 테스트")
    print("=" * 70)

    from chemstation_parser import ChemstationParser

    files = [
        r'C:\Chem32\1\DATA\260108_m1_cofactor\260108_M1_COFACTOR_D_1_0H.D\RID1A.ch',
        r'C:\Chem32\1\DATA\260108_m1_cofactor\260108_M1_COFACTOR_D_1_24H.D\RID1A.ch',
    ]

    real_results = []

    for fpath in files:
        fname = os.path.basename(os.path.dirname(fpath))
        print(f"\n--- 파일: {fname} ---")

        if not os.path.exists(fpath):
            print(f"  [건너뜀] 파일이 존재하지 않음: {fpath}")
            continue

        # 1) 파싱
        parser = ChemstationParser(fpath)
        time, intensity = parser.read()
        print(f"  데이터 포인트: {len(time)}, 시간 범위: {time[0]:.2f}~{time[-1]:.2f} min")

        # 2) 베이스라인 보정 (rolling-minimum, RID 데이터에 적합)
        baseline = _rolling_min_baseline(intensity)
        corrected = np.maximum(intensity - baseline, 0)

        print(f"  보정 후 신호 범위: {corrected.min():.1f} ~ {corrected.max():.1f}")

        # 3) 피크 검출
        noise_deriv = np.diff(corrected)
        noise_mad = np.median(np.abs(noise_deriv - np.median(noise_deriv)))
        noise_std = noise_mad * 1.4826
        sig_range = np.ptp(corrected)

        min_prom = max(sig_range * 0.01, noise_std * 3)
        min_ht = max(sig_range * 0.01, noise_std * 3)

        peaks, props = signal.find_peaks(
            corrected, prominence=min_prom, height=min_ht, width=3, distance=20
        )

        print(f"  검출된 피크 수: {len(peaks)}")
        if len(peaks) == 0:
            print("  피크가 검출되지 않았습니다.")
            continue

        # 4) 주요 피크 비교 테이블
        peak_areas = []
        sorted_peaks = np.sort(peaks)
        for i_pk, pk_idx in enumerate(sorted_peaks):
            pk_h = corrected[pk_idx]
            thr = pk_h * 0.01

            # 피크 경계: 1% threshold 또는 인접 피크와의 valley 중 좁은 쪽
            left = pk_idx
            while left > 0 and corrected[left] > thr:
                left -= 1
            right = pk_idx
            while right < len(corrected) - 1 and corrected[right] > thr:
                right += 1

            # 인접 피크와의 valley로 경계 제한
            if i_pk > 0:
                prev_pk = sorted_peaks[i_pk - 1]
                valley_region = corrected[prev_pk:pk_idx]
                if len(valley_region) > 0:
                    valley_idx = prev_pk + np.argmin(valley_region)
                    left = max(left, valley_idx)
            if i_pk < len(sorted_peaks) - 1:
                next_pk = sorted_peaks[i_pk + 1]
                valley_region = corrected[pk_idx:next_pk]
                if len(valley_region) > 0:
                    valley_idx = pk_idx + np.argmin(valley_region)
                    right = min(right, valley_idx)

            t_sec = time[left:right + 1] * 60
            sig = corrected[left:right + 1]
            area = trapezoid(sig, t_sec)
            peak_areas.append((pk_idx, left, right, area))

        peak_areas.sort(key=lambda x: x[3], reverse=True)
        top_peaks = peak_areas[:5]

        print(f"\n  {'피크':>4s}  {'RT(min)':>8s}  {'높이':>12s}  {'전체면적':>14s}"
              f"  {'왼쪽x2':>14s}  {'오른쪽x2':>14s}  {'비대칭도(L/R)':>14s}")
        print("  " + "-" * 90)

        for rank, (pk_idx, l, r, area) in enumerate(top_peaks, 1):
            apex_rel = pk_idx - l
            t_sec = time[l:r + 1] * 60
            sig = corrected[l:r + 1]

            if apex_rel > 0 and apex_rel < len(sig) - 1:
                la = trapezoid(sig[:apex_rel + 1], t_sec[:apex_rel + 1])
                ra = trapezoid(sig[apex_rel:], t_sec[apex_rel:])
            else:
                la = area / 2
                ra = area / 2

            asym = la / ra if ra > 0 else float('inf')

            print(f"  {rank:>4d}  {time[pk_idx]:>8.2f}  {corrected[pk_idx]:>12.1f}"
                  f"  {area:>14.1f}  {la * 2:>14.1f}  {ra * 2:>14.1f}  {asym:>14.4f}")

        # 첫 번째 피크 데이터 반환 (시각화용)
        pk_idx, l, r, area = top_peaks[0]
        real_results.append({
            'fname': fname,
            'time': time,
            'corrected': corrected,
            'peak_idx': pk_idx,
            'left': l,
            'right': r,
        })

    return real_results


# ============================================================
#  Part 3: 시각화
# ============================================================
def visualize(syn_data, real_data):
    print("\n" + "=" * 70)
    print("  Part 3: 시각화 생성")
    print("=" * 70)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # --- Subplot 1: 합성 대칭 피크 ---
    ax = axes[0]
    t = syn_data['time']
    sym = syn_data['symmetric']
    apex = syn_data['apex_idx']

    ax.plot(t, sym, 'k-', lw=1.2, label='피크')
    ax.fill_between(t[:apex + 1], sym[:apex + 1], alpha=0.35, color='royalblue', label='왼쪽 반쪽')
    ax.fill_between(t[apex:], sym[apex:], alpha=0.35, color='tomato', label='오른쪽 반쪽')
    ax.axvline(t[apex], color='gray', ls='--', lw=0.8, label=f'꼭짓점 (RT={t[apex]:.1f})')
    ax.set_xlabel('시간 (min)')
    ax.set_ylabel('신호 강도')
    ax.set_title('합성 대칭 Gaussian 피크')
    ax.legend(fontsize=8)
    ax.set_xlim(3.5, 6.5)

    # --- Subplot 2: 실제 크로마토그램 ---
    ax = axes[1]
    if real_data:
        rd = real_data[0]
        t_real = rd['time']
        corr = rd['corrected']
        pk = rd['peak_idx']
        l_idx = rd['left']
        r_idx = rd['right']

        # 전체 크로마토그램 (연한 회색)
        ax.plot(t_real, corr, color='gray', lw=0.5, alpha=0.6)

        # 선택 피크의 왼쪽/오른쪽 반쪽 표시
        ax.fill_between(
            t_real[l_idx:pk + 1], corr[l_idx:pk + 1],
            alpha=0.4, color='royalblue', label='왼쪽 반쪽'
        )
        ax.fill_between(
            t_real[pk:r_idx + 1], corr[pk:r_idx + 1],
            alpha=0.4, color='tomato', label='오른쪽 반쪽'
        )
        ax.axvline(t_real[pk], color='gray', ls='--', lw=0.8,
                    label=f'꼭짓점 (RT={t_real[pk]:.2f})')

        # 피크 주변만 표시
        margin = max((t_real[r_idx] - t_real[l_idx]) * 2, 1.0)
        ax.set_xlim(t_real[l_idx] - margin, t_real[r_idx] + margin)

        ax.set_title(f'실제 크로마토그램: {rd["fname"]}')
    else:
        ax.text(0.5, 0.5, '실제 데이터 없음', transform=ax.transAxes,
                ha='center', va='center', fontsize=14)
        ax.set_title('실제 크로마토그램 (데이터 없음)')

    ax.set_xlabel('시간 (min)')
    ax.set_ylabel('보정 신호')
    ax.legend(fontsize=8)

    plt.tight_layout()
    outpath = os.path.join(os.path.dirname(__file__), 'half_peak_comparison.png')
    fig.savefig(outpath, dpi=150)
    print(f"  저장 완료: {outpath}")
    plt.close(fig)


# ============================================================
#  메인
# ============================================================
if __name__ == '__main__':
    # Part 1
    syn_data = test_synthetic()

    # Part 2
    real_data = test_real_data()

    # Part 3
    visualize(syn_data, real_data)

    # 최종 요약
    print("\n" + "=" * 70)
    print("  최종 결과 요약")
    print("=" * 70)
    if syn_data['sym_pass']:
        print("  [통과] 대칭 Gaussian: 왼쪽x2, 오른쪽x2 모두 전체 면적과 1% 이내 일치")
    else:
        print("  [실패] 대칭 Gaussian: 반쪽 면적 오차가 1%를 초과")
    print("  완료!")
