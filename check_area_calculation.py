"""
면적 계산 방법 검증
다양한 적분 방법으로 피크 면적 계산 비교
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from scipy import signal
from scipy.integrate import trapezoid, simpson
import sys

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from hybrid_baseline import HybridBaselineCorrector

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False


def check_area_calculation_methods(csv_file):
    """다양한 방법으로 면적 계산 비교"""

    # 데이터 로드
    df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
    time = df[0].values
    intensity = df[1].values

    sample_name = csv_file.stem

    print(f"\n{'='*80}")
    print(f"샘플: {sample_name}")
    print(f"{'='*80}")

    # 데이터 정보
    print(f"\n[데이터 정보]")
    print(f"  데이터 포인트: {len(time)}개")
    print(f"  시간 범위: {time[0]:.4f} ~ {time[-1]:.4f} min")
    print(f"  시간 간격 (평균): {np.mean(np.diff(time)):.6f} min ({np.mean(np.diff(time))*60:.4f} sec)")
    print(f"  강도 범위: {np.min(intensity):.2f} ~ {np.max(intensity):.2f}")

    # 베이스라인 보정
    corrector = HybridBaselineCorrector(time, intensity)
    corrector.find_baseline_anchor_points(valley_prominence=0.01, percentile=10)
    baseline = corrector.generate_hybrid_baseline(method='robust_fit', enhanced_smoothing=True)
    corrected_raw = intensity - baseline
    corrected = corrector.post_process_corrected_signal(corrected_raw, clip_negative=True, negative_threshold=-50.0)

    # 주 피크 찾기
    signal_range = np.ptp(corrected)
    noise_level = np.percentile(np.abs(corrected), 25) * 1.5
    min_prominence = max(signal_range * 0.005, noise_level * 2)
    min_height = noise_level * 2

    peaks, props = signal.find_peaks(corrected, prominence=min_prominence, height=min_height, width=3, distance=20)

    if len(peaks) == 0:
        print("\n피크를 찾을 수 없습니다.")
        return

    # 가장 큰 피크
    main_peak_idx = peaks[np.argmax(corrected[peaks])]

    print(f"\n[주 피크 정보]")
    print(f"  RT: {time[main_peak_idx]:.2f} min")
    print(f"  높이 (보정 후): {corrected[main_peak_idx]:.2f}")
    print(f"  높이 (원본): {intensity[main_peak_idx]:.2f}")

    # 피크 경계 찾기 (여러 방법)
    peak_height = corrected[main_peak_idx]

    # 방법 1: 반치폭 (FWHM)
    half_height = peak_height / 2
    left_fwhm = main_peak_idx
    while left_fwhm > 0 and corrected[left_fwhm] > half_height:
        left_fwhm -= 1
    right_fwhm = main_peak_idx
    while right_fwhm < len(corrected) - 1 and corrected[right_fwhm] > half_height:
        right_fwhm += 1

    # 방법 2: 10% 높이
    tenth_height = peak_height * 0.1
    left_10pct = main_peak_idx
    while left_10pct > 0 and corrected[left_10pct] > tenth_height:
        left_10pct -= 1
    right_10pct = main_peak_idx
    while right_10pct < len(corrected) - 1 and corrected[right_10pct] > tenth_height:
        right_10pct += 1

    # 방법 3: 베이스라인으로 돌아가는 지점
    baseline_threshold = noise_level * 2
    left_baseline = main_peak_idx
    while left_baseline > 0 and corrected[left_baseline] > baseline_threshold:
        left_baseline -= 1
    right_baseline = main_peak_idx
    while right_baseline < len(corrected) - 1 and corrected[right_baseline] > baseline_threshold:
        right_baseline += 1

    # 각 방법으로 면적 계산
    print(f"\n{'='*80}")
    print("면적 계산 방법 비교")
    print(f"{'='*80}")

    results = []

    # 방법 1: FWHM + trapezoid (분 단위)
    time_fwhm = time[left_fwhm:right_fwhm+1]
    signal_fwhm = corrected[left_fwhm:right_fwhm+1]
    area_fwhm_min = trapezoid(np.maximum(signal_fwhm, 0), time_fwhm)

    print(f"\n[1] FWHM 경계 + trapezoid (분 단위)")
    print(f"  경계: {time[left_fwhm]:.2f} ~ {time[right_fwhm]:.2f} min")
    print(f"  폭: {time[right_fwhm] - time[left_fwhm]:.4f} min")
    print(f"  포인트 수: {right_fwhm - left_fwhm + 1}")
    print(f"  면적: {area_fwhm_min:.2f} (mAU*min)")
    results.append(('FWHM + trapezoid (min)', area_fwhm_min, left_fwhm, right_fwhm))

    # 방법 2: FWHM + trapezoid (초 단위)
    time_fwhm_sec = time_fwhm * 60  # 분을 초로 변환
    area_fwhm_sec = trapezoid(np.maximum(signal_fwhm, 0), time_fwhm_sec)

    print(f"\n[2] FWHM 경계 + trapezoid (초 단위)")
    print(f"  경계: {time[left_fwhm]*60:.2f} ~ {time[right_fwhm]*60:.2f} sec")
    print(f"  폭: {(time[right_fwhm] - time[left_fwhm])*60:.4f} sec")
    print(f"  면적: {area_fwhm_sec:.2f} (mAU*sec)")
    results.append(('FWHM + trapezoid (sec)', area_fwhm_sec, left_fwhm, right_fwhm))

    # 방법 3: FWHM + simpson
    if len(signal_fwhm) > 2:
        area_fwhm_simps = simpson(np.maximum(signal_fwhm, 0), x=time_fwhm_sec)
        print(f"\n[3] FWHM 경계 + simpson (초 단위)")
        print(f"  면적: {area_fwhm_simps:.2f} (mAU*sec)")
        results.append(('FWHM + simpson (sec)', area_fwhm_simps, left_fwhm, right_fwhm))

    # 방법 4: 10% 높이 + trapezoid (초 단위)
    time_10pct = time[left_10pct:right_10pct+1]
    signal_10pct = corrected[left_10pct:right_10pct+1]
    time_10pct_sec = time_10pct * 60
    area_10pct_sec = trapezoid(np.maximum(signal_10pct, 0), time_10pct_sec)

    print(f"\n[4] 10% 높이 경계 + trapezoid (초 단위)")
    print(f"  경계: {time[left_10pct]:.2f} ~ {time[right_10pct]:.2f} min")
    print(f"  폭: {time[right_10pct] - time[left_10pct]:.4f} min")
    print(f"  포인트 수: {right_10pct - left_10pct + 1}")
    print(f"  면적: {area_10pct_sec:.2f} (mAU*sec)")
    results.append(('10% height + trapezoid (sec)', area_10pct_sec, left_10pct, right_10pct))

    # 방법 5: 베이스라인 복귀 + trapezoid (초 단위)
    time_baseline = time[left_baseline:right_baseline+1]
    signal_baseline = corrected[left_baseline:right_baseline+1]
    time_baseline_sec = time_baseline * 60
    area_baseline_sec = trapezoid(np.maximum(signal_baseline, 0), time_baseline_sec)

    print(f"\n[5] 베이스라인 복귀 + trapezoid (초 단위)")
    print(f"  경계: {time[left_baseline]:.2f} ~ {time[right_baseline]:.2f} min")
    print(f"  폭: {time[right_baseline] - time[left_baseline]:.4f} min")
    print(f"  포인트 수: {right_baseline - left_baseline + 1}")
    print(f"  면적: {area_baseline_sec:.2f} (mAU*sec)")
    results.append(('Baseline return + trapezoid (sec)', area_baseline_sec, left_baseline, right_baseline))

    # 방법 6: 원본 신호 직접 적분 (베이스라인 빼지 않고)
    time_orig = time[left_10pct:right_10pct+1]
    signal_orig = intensity[left_10pct:right_10pct+1]
    baseline_orig = baseline[left_10pct:right_10pct+1]
    time_orig_sec = time_orig * 60

    # 베이스라인 위의 면적
    area_orig_above_baseline = trapezoid(np.maximum(signal_orig - baseline_orig, 0), time_orig_sec)

    print(f"\n[6] 원본 신호 - 베이스라인 (초 단위)")
    print(f"  면적: {area_orig_above_baseline:.2f} (mAU*sec)")
    results.append(('Original - baseline (sec)', area_orig_above_baseline, left_10pct, right_10pct))

    # 시각화
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))

    # Panel 1: 원본 + 베이스라인
    ax1 = axes[0, 0]
    ax1.plot(time, intensity, 'b-', linewidth=1.5, alpha=0.7, label='원본 신호')
    ax1.plot(time, baseline, 'r--', linewidth=2, label='베이스라인')
    ax1.axvline(time[main_peak_idx], color='green', linestyle=':', alpha=0.5, label='피크 위치')
    ax1.set_xlabel('시간 (min)', fontsize=11)
    ax1.set_ylabel('강도 (mAU)', fontsize=11)
    ax1.set_title('원본 신호 + 베이스라인', fontsize=12, fontweight='bold')
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3)

    # Panel 2: 보정 신호 + 경계선
    ax2 = axes[0, 1]
    ax2.plot(time, corrected, 'g-', linewidth=1.5, label='보정 신호')
    ax2.axhline(half_height, color='orange', linestyle='--', alpha=0.5, label=f'50% 높이 ({half_height:.1f})')
    ax2.axhline(tenth_height, color='purple', linestyle='--', alpha=0.5, label=f'10% 높이 ({tenth_height:.1f})')
    ax2.axhline(baseline_threshold, color='brown', linestyle='--', alpha=0.5, label=f'베이스라인 ({baseline_threshold:.1f})')

    ax2.axvline(time[left_fwhm], color='orange', linestyle=':', alpha=0.7)
    ax2.axvline(time[right_fwhm], color='orange', linestyle=':', alpha=0.7)
    ax2.axvline(time[left_10pct], color='purple', linestyle=':', alpha=0.7)
    ax2.axvline(time[right_10pct], color='purple', linestyle=':', alpha=0.7)

    ax2.set_xlabel('시간 (min)', fontsize=11)
    ax2.set_ylabel('강도 (mAU)', fontsize=11)
    ax2.set_title('보정 신호 + 적분 경계', fontsize=12, fontweight='bold')
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.3)

    # Panel 3: 적분 영역 비교
    ax3 = axes[1, 0]
    ax3.plot(time, corrected, 'gray', linewidth=1, alpha=0.5)

    colors = ['orange', 'purple', 'brown']
    labels = ['FWHM', '10% 높이', '베이스라인']
    boundaries = [(left_fwhm, right_fwhm), (left_10pct, right_10pct), (left_baseline, right_baseline)]

    for i, ((left, right), color, label) in enumerate(zip(boundaries, colors, labels)):
        ax3.fill_between(time[left:right+1], 0, corrected[left:right+1],
                        alpha=0.3, color=color, label=f'{label} 영역')

    ax3.set_xlabel('시간 (min)', fontsize=11)
    ax3.set_ylabel('강도 (mAU)', fontsize=11)
    ax3.set_title('적분 영역 비교', fontsize=12, fontweight='bold')
    ax3.legend(fontsize=9)
    ax3.grid(True, alpha=0.3)

    # Panel 4: 면적 비교 바 차트
    ax4 = axes[1, 1]
    method_names = [r[0] for r in results]
    areas = [r[1] for r in results]

    bars = ax4.barh(range(len(results)), areas, color=['orange', 'blue', 'cyan', 'purple', 'brown', 'green'])
    ax4.set_yticks(range(len(results)))
    ax4.set_yticklabels([f"{i+1}. {name}" for i, name in enumerate(method_names)], fontsize=9)
    ax4.set_xlabel('면적', fontsize=11, fontweight='bold')
    ax4.set_title('면적 계산 방법 비교', fontsize=12, fontweight='bold')

    # 값 표시
    for i, (bar, area) in enumerate(zip(bars, areas)):
        ax4.text(area, i, f' {area:.1f}', va='center', fontsize=9, fontweight='bold')

    ax4.grid(True, alpha=0.3, axis='x')

    plt.suptitle(f'면적 계산 검증: {sample_name}', fontsize=14, fontweight='bold', y=0.995)
    plt.tight_layout()

    output_file = f'result/area_calculation_check_{sample_name}.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\n시각화 저장: {output_file}")
    plt.close()

    return results


def main():
    # 5mM 샘플 중 하나 테스트
    csv_file = Path(r"C:\Users\Jahyun\PycharmProjects\PeakPicker\result\DEF_LC 2025-05-19 17-57-25\250519_TAGATOSE_STD_SP0810_5MM_1.csv")

    print("\n" + "="*80)
    print("면적 계산 방법 검증")
    print("="*80)
    print(f"예상 면적: ~280,000")

    results = check_area_calculation_methods(csv_file)

    print(f"\n{'='*80}")
    print("결과 요약")
    print(f"{'='*80}")

    for i, (method, area, left, right) in enumerate(results, 1):
        ratio_to_expected = area / 280000 * 100
        print(f"{i}. {method:40s}: {area:12.2f} (예상 대비 {ratio_to_expected:5.1f}%)")

    print(f"\n예상 면적 280,000과 가장 가까운 방법:")
    closest = min(results, key=lambda x: abs(x[1] - 280000))
    print(f"  → {closest[0]}: {closest[1]:.2f}")


if __name__ == '__main__':
    main()
