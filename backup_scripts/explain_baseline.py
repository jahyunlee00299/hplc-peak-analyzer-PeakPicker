"""
베이스라인 선택 기준 설명 및 시각화
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy import signal
from matplotlib.patches import FancyBboxPatch
import matplotlib.patches as mpatches


def create_sample_peak():
    """샘플 피크 데이터 생성"""
    time = np.linspace(0, 10, 1000)

    # 베이스라인 드리프트 (시간에 따라 변하는 배경)
    baseline_drift = 50 + 30 * np.sin(time / 3) + 5 * time

    # 가우시안 피크
    peak = 200 * np.exp(-((time - 5) ** 2) / 0.5)

    # 노이즈
    noise = np.random.normal(0, 3, len(time))

    # 전체 신호
    intensity = baseline_drift + peak + noise

    return time, intensity, baseline_drift


def explain_scipy_baseline_detection():
    """scipy.signal.find_peaks()의 베이스라인 찾기 원리"""

    time, intensity, true_baseline = create_sample_peak()

    # scipy.signal.find_peaks로 피크 찾기
    peak_indices, properties = signal.find_peaks(
        intensity,
        prominence=50,
        width=5
    )

    if len(peak_indices) == 0:
        print("피크를 찾지 못했습니다.")
        return

    # 첫 번째 피크 분석
    peak_idx = peak_indices[0]
    left_base = int(properties['left_bases'][0])
    right_base = int(properties['right_bases'][0])

    # 베이스라인 계산 (직선)
    baseline_linear = np.linspace(
        intensity[left_base],
        intensity[right_base],
        right_base - left_base + 1
    )

    # 시각화
    fig = plt.figure(figsize=(16, 10))

    # 메인 플롯
    ax1 = plt.subplot(2, 2, (1, 2))
    ax1.plot(time, intensity, 'b-', linewidth=2, label='Chromatogram Signal', alpha=0.8)
    ax1.plot(time, true_baseline, 'gray', linewidth=2, linestyle=':',
             label='True Baseline (with drift)', alpha=0.6)

    # 피크 마커
    ax1.plot(time[peak_idx], intensity[peak_idx], 'ro', markersize=12,
             label='Peak Maximum', zorder=5)

    # 베이스라인 포인트
    ax1.plot(time[left_base], intensity[left_base], 'gs', markersize=15,
             label='Left Base', zorder=5)
    ax1.plot(time[right_base], intensity[right_base], 'gs', markersize=15,
             label='Right Base', zorder=5)

    # 선형 베이스라인
    ax1.plot(time[left_base:right_base+1], baseline_linear, 'r--',
             linewidth=3, label='Linear Baseline (used)', alpha=0.8)

    # 피크 영역 음영
    ax1.fill_between(time[left_base:right_base+1],
                     baseline_linear,
                     intensity[left_base:right_base+1],
                     alpha=0.3, color='green', label='Integration Area')

    # 베이스라인 포인트 표시
    ax1.axvline(time[left_base], color='green', linestyle=':', alpha=0.5)
    ax1.axvline(time[right_base], color='green', linestyle=':', alpha=0.5)
    ax1.axvline(time[peak_idx], color='red', linestyle=':', alpha=0.5)

    # 주석
    ax1.annotate('Peak Start\n(Left Base)',
                xy=(time[left_base], intensity[left_base]),
                xytext=(time[left_base]-1.5, intensity[left_base]+50),
                fontsize=11, fontweight='bold',
                arrowprops=dict(arrowstyle='->', lw=2, color='green'),
                bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgreen', alpha=0.8))

    ax1.annotate('Peak Maximum\n(Peak Apex)',
                xy=(time[peak_idx], intensity[peak_idx]),
                xytext=(time[peak_idx], intensity[peak_idx]+60),
                fontsize=11, fontweight='bold',
                arrowprops=dict(arrowstyle='->', lw=2, color='red'),
                bbox=dict(boxstyle='round,pad=0.5', facecolor='lightcoral', alpha=0.8))

    ax1.annotate('Peak End\n(Right Base)',
                xy=(time[right_base], intensity[right_base]),
                xytext=(time[right_base]+1.5, intensity[right_base]+50),
                fontsize=11, fontweight='bold',
                arrowprops=dict(arrowstyle='->', lw=2, color='green'),
                bbox=dict(boxstyle='round,pad=0.5', facecolor='lightgreen', alpha=0.8))

    ax1.set_xlabel('Retention Time (min)', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Intensity', fontsize=12, fontweight='bold')
    ax1.set_title('베이스라인 선택 방법 (Baseline Detection Method)',
                  fontsize=14, fontweight='bold')
    ax1.legend(loc='upper left', fontsize=10)
    ax1.grid(True, alpha=0.3)

    # 서브플롯 2: 베이스라인 찾는 과정 설명
    ax2 = plt.subplot(2, 2, 3)
    ax2.axis('off')

    explanation = """
    베이스라인 찾기 알고리즘 (scipy.signal.find_peaks)

    1단계: 피크 검출
       - prominence (돌출도) 기준으로 피크 찾기
       - prominence = 피크가 주변 배경보다 얼마나 두드러지는지

    2단계: 베이스라인 포인트 결정
       Left Base (시작점):
         • 피크 왼쪽에서 신호가 더 이상 감소하지 않는 지점
         • 또는 다음 피크의 시작 지점

       Right Base (끝점):
         • 피크 오른쪽에서 신호가 더 이상 증가하지 않는 지점
         • 또는 이전 피크의 끝 지점

    3단계: 선형 베이스라인 생성
       • Left Base와 Right Base를 직선으로 연결
       • Baseline = linear interpolation(left_y, right_y)

    4단계: 피크 면적 계산
       • Area = ∫(Signal - Baseline) dt
       • 사다리꼴 적분법 사용
    """

    ax2.text(0.05, 0.95, explanation, transform=ax2.transAxes,
            fontsize=10, verticalalignment='top', family='monospace',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

    # 서브플롯 3: 베이스라인 선택 기준
    ax3 = plt.subplot(2, 2, 4)
    ax3.axis('off')

    criteria = """
    베이스라인 선택 기준

    ✓ 장점:
      • 자동화: 수동 개입 없이 자동으로 결정
      • 일관성: 모든 피크에 동일한 기준 적용
      • 빠른 속도: 실시간 처리 가능

    ⚠ 고려사항:
      • 베이스라인 드리프트: 배경이 크게 변하면 부정확
      • 피크 중첩: 인접한 피크가 있으면 영향받음
      • 노이즈: 잡음이 많으면 시작/끝점 오류

    📊 파라미터 영향:
      • prominence ↑ → 작은 피크 무시
      • min_width ↑ → 좁은 피크 무시
      • smoothing ↑ → 노이즈 감소, 해상도 감소

    🎯 대안 방법:
      1. 다항식 베이스라인 (Polynomial baseline)
      2. 이동 최소값 (Rolling minimum)
      3. SNIP 알고리즘 (통계적 방법)
      4. 수동 베이스라인 설정
    """

    ax3.text(0.05, 0.95, criteria, transform=ax3.transAxes,
            fontsize=10, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))

    plt.tight_layout()

    # 계산 결과 출력
    print("=" * 70)
    print("베이스라인 선택 결과")
    print("=" * 70)
    print(f"피크 최대값 위치: {time[peak_idx]:.3f} min")
    print(f"Left Base 위치: {time[left_base]:.3f} min (intensity: {intensity[left_base]:.2f})")
    print(f"Right Base 위치: {time[right_base]:.3f} min (intensity: {intensity[right_base]:.2f})")
    print(f"피크 폭: {time[right_base] - time[left_base]:.3f} min")
    print(f"\n베이스라인 방법: 선형 보간 (Linear Interpolation)")
    print(f"  - 시작점 강도: {intensity[left_base]:.2f}")
    print(f"  - 끝점 강도: {intensity[right_base]:.2f}")
    print(f"  - 기울기: {(intensity[right_base] - intensity[left_base]) / (time[right_base] - time[left_base]):.3f}")

    # 면적 계산
    corrected_intensity = intensity[left_base:right_base+1] - baseline_linear
    area = np.trapz(corrected_intensity, time[left_base:right_base+1])
    print(f"\n피크 면적: {area:.2f}")
    print("=" * 70)

    return fig


def compare_baseline_methods():
    """다양한 베이스라인 방법 비교"""

    time, intensity, true_baseline = create_sample_peak()

    # scipy로 피크 찾기
    peak_indices, properties = signal.find_peaks(intensity, prominence=50, width=5)
    peak_idx = peak_indices[0]
    left_base = int(properties['left_bases'][0])
    right_base = int(properties['right_bases'][0])

    # 1. 선형 베이스라인 (현재 방법)
    baseline_linear = np.linspace(
        intensity[left_base],
        intensity[right_base],
        right_base - left_base + 1
    )

    # 2. 수평 베이스라인 (최소값 사용)
    baseline_min = np.ones(right_base - left_base + 1) * min(intensity[left_base], intensity[right_base])

    # 3. 실제 베이스라인 (참고용)
    baseline_true = true_baseline[left_base:right_base+1]

    # 시각화
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))

    peak_time = time[left_base:right_base+1]
    peak_intensity = intensity[left_base:right_base+1]

    # 1. 선형 베이스라인
    ax = axes[0, 0]
    ax.plot(peak_time, peak_intensity, 'b-', linewidth=2, label='Signal')
    ax.plot(peak_time, baseline_linear, 'r--', linewidth=2, label='Linear Baseline')
    ax.fill_between(peak_time, baseline_linear, peak_intensity, alpha=0.3, color='green')
    ax.set_title('1. Linear Baseline (Current Method)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Intensity', fontsize=11)
    ax.legend()
    ax.grid(True, alpha=0.3)
    area1 = np.trapz(peak_intensity - baseline_linear, peak_time)
    ax.text(0.5, 0.95, f'Area: {area1:.2f}', transform=ax.transAxes,
           ha='center', va='top', fontsize=11, fontweight='bold',
           bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.8))

    # 2. 수평 베이스라인
    ax = axes[0, 1]
    ax.plot(peak_time, peak_intensity, 'b-', linewidth=2, label='Signal')
    ax.plot(peak_time, baseline_min, 'orange', linestyle='--', linewidth=2, label='Horizontal Baseline')
    ax.fill_between(peak_time, baseline_min, peak_intensity, alpha=0.3, color='orange')
    ax.set_title('2. Horizontal Baseline (Minimum)', fontsize=12, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    area2 = np.trapz(peak_intensity - baseline_min, peak_time)
    ax.text(0.5, 0.95, f'Area: {area2:.2f}', transform=ax.transAxes,
           ha='center', va='top', fontsize=11, fontweight='bold',
           bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.8))

    # 3. 실제 베이스라인 (이상적)
    ax = axes[1, 0]
    ax.plot(peak_time, peak_intensity, 'b-', linewidth=2, label='Signal')
    ax.plot(peak_time, baseline_true, 'purple', linestyle='--', linewidth=2, label='True Baseline')
    ax.fill_between(peak_time, baseline_true, peak_intensity, alpha=0.3, color='purple')
    ax.set_title('3. True Baseline (Ideal)', fontsize=12, fontweight='bold')
    ax.set_xlabel('Retention Time (min)', fontsize=11)
    ax.set_ylabel('Intensity', fontsize=11)
    ax.legend()
    ax.grid(True, alpha=0.3)
    area3 = np.trapz(peak_intensity - baseline_true, peak_time)
    ax.text(0.5, 0.95, f'Area: {area3:.2f}', transform=ax.transAxes,
           ha='center', va='top', fontsize=11, fontweight='bold',
           bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.8))

    # 4. 비교표
    ax = axes[1, 1]
    ax.axis('off')

    comparison = f"""
    베이스라인 방법 비교

    Method              | Area    | vs True  | 특징
    ────────────────────|─────────|──────────|──────────────
    1. Linear           | {area1:7.2f} | {area1-area3:+7.2f} | 현재 사용
       (직선)           |         |          | 빠르고 간단
                        |         |          | 드리프트 보정

    2. Horizontal       | {area2:7.2f} | {area2-area3:+7.2f} | 단순함
       (수평선)         |         |          | 드리프트 무시
                        |         |          | 과대평가 가능

    3. True Baseline    | {area3:7.2f} |    0.00 | 이상적
       (실제)           |         |          | 실제로 불가능
                        |         |          | 참고용

    권장: Linear Baseline
    - 대부분의 경우 가장 정확
    - 배경 드리프트 보정
    - 계산 효율적
    """

    ax.text(0.05, 0.95, comparison, transform=ax.transAxes,
           fontsize=10, verticalalignment='top', family='monospace',
           bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.8))

    plt.tight_layout()
    return fig


if __name__ == "__main__":
    print("\n베이스라인 선택 기준 설명\n")

    # 1. 기본 설명
    fig1 = explain_scipy_baseline_detection()
    plt.savefig('analysis_results/baseline_explanation.png', dpi=300, bbox_inches='tight')
    print("\n그래프 저장: analysis_results/baseline_explanation.png")

    # 2. 방법 비교
    print("\n베이스라인 방법 비교 중...")
    fig2 = compare_baseline_methods()
    plt.savefig('analysis_results/baseline_comparison.png', dpi=300, bbox_inches='tight')
    print("그래프 저장: analysis_results/baseline_comparison.png")

    print("\n완료!")
    plt.show()
