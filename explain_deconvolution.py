"""
피크 디컨볼루션(Peak Deconvolution) 설명 및 시각화
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False


def gaussian(x, amp, center, width):
    """가우시안 함수"""
    return amp * np.exp(-(x - center)**2 / (2 * width**2))


def create_overlapping_peaks():
    """겹친 피크 시뮬레이션"""
    x = np.linspace(0, 20, 1000)

    # 3개의 겹친 가우시안 피크 생성
    peak1 = gaussian(x, 100, 7, 0.5)   # 왼쪽 숄더
    peak2 = gaussian(x, 200, 9, 0.8)   # 메인 피크
    peak3 = gaussian(x, 80, 10.5, 0.6) # 오른쪽 숄더

    # 전체 신호 = 각 피크의 합
    signal = peak1 + peak2 + peak3

    # 약간의 노이즈 추가
    noise = np.random.normal(0, 2, len(x))
    signal_with_noise = signal + noise

    return x, signal_with_noise, [peak1, peak2, peak3], [(7, 100), (9, 200), (10.5, 80)]


def explain_deconvolution():
    """디컨볼루션 개념 설명"""

    # 겹친 피크 생성
    x, signal, individual_peaks, peak_info = create_overlapping_peaks()

    # 그림 생성
    fig = plt.figure(figsize=(18, 12))

    # ========== 1. 문제 상황: 겹친 피크 ==========
    ax1 = plt.subplot(3, 2, 1)
    ax1.plot(x, signal, 'b-', linewidth=2, label='측정된 크로마토그램')
    ax1.fill_between(x, 0, signal, alpha=0.2, color='blue')

    # 피크 최대값 표시
    peak_idx = np.argmax(signal)
    ax1.plot(x[peak_idx], signal[peak_idx], 'ro', markersize=10, label='검출된 피크')

    ax1.set_title('❓ 문제: 여러 화합물이 겹쳐서 하나의 피크처럼 보임',
                  fontsize=12, fontweight='bold', pad=10)
    ax1.set_xlabel('Retention Time (min)')
    ax1.set_ylabel('Intensity')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # 비대칭 표시
    ax1.annotate('비대칭 모양!\n숄더가 있음',
                xy=(10.5, signal[np.argmin(np.abs(x-10.5))]),
                xytext=(12, 150),
                arrowprops=dict(arrowstyle='->', color='red', lw=2),
                fontsize=10, color='red', fontweight='bold',
                bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.7))

    # ========== 2. 비대칭도 검사 ==========
    ax2 = plt.subplot(3, 2, 2)
    ax2.plot(x, signal, 'b-', linewidth=2)

    # 반높이에서 폭 계산
    peak_height = signal[peak_idx]
    half_height = peak_height / 2

    # 왼쪽과 오른쪽 반폭
    left_idx = peak_idx
    while left_idx > 0 and signal[left_idx] > half_height:
        left_idx -= 1

    right_idx = peak_idx
    while right_idx < len(signal) - 1 and signal[right_idx] > half_height:
        right_idx += 1

    # 비대칭도 계산
    left_width = x[peak_idx] - x[left_idx]
    right_width = x[right_idx] - x[peak_idx]
    asymmetry = right_width / left_width if left_width > 0 else 1.0

    # 시각화
    ax2.axhline(y=half_height, color='gray', linestyle='--', alpha=0.5)
    ax2.plot([x[left_idx], x[peak_idx]], [half_height, half_height],
            'g-', linewidth=3, label=f'왼쪽 폭: {left_width:.2f}')
    ax2.plot([x[peak_idx], x[right_idx]], [half_height, half_height],
            'r-', linewidth=3, label=f'오른쪽 폭: {right_width:.2f}')

    ax2.set_title(f'1️⃣ 비대칭도 검사: {asymmetry:.2f} > 1.2 ➜ 디컨볼루션 필요!',
                  fontsize=12, fontweight='bold', pad=10)
    ax2.set_xlabel('Retention Time (min)')
    ax2.set_ylabel('Intensity')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    # ========== 3. 2차 미분으로 숄더 검출 ==========
    ax3 = plt.subplot(3, 2, 3)

    # 2차 미분 계산
    second_deriv = np.gradient(np.gradient(signal))

    ax3_top = ax3
    ax3_bottom = ax3.twinx()

    ax3_top.plot(x, signal, 'b-', linewidth=2, label='원본 신호', alpha=0.7)
    ax3_bottom.plot(x, -second_deriv, 'r-', linewidth=1.5, label='2차 미분 (음수)', alpha=0.7)
    ax3_bottom.axhline(y=0, color='gray', linestyle='--', alpha=0.3)

    # 2차 미분의 피크 찾기 (숄더 위치)
    shoulder_peaks, _ = find_peaks(-second_deriv, prominence=np.max(-second_deriv)*0.1, distance=50)

    for sp in shoulder_peaks:
        ax3_top.axvline(x=x[sp], color='orange', linestyle=':', alpha=0.7)
        ax3_top.text(x[sp], signal[sp], '숄더', ha='center',
                    bbox=dict(boxstyle='round', facecolor='orange', alpha=0.7))

    ax3_top.set_title('2️⃣ 2차 미분으로 숄더 피크 자동 검출',
                      fontsize=12, fontweight='bold', pad=10)
    ax3_top.set_xlabel('Retention Time (min)')
    ax3_top.set_ylabel('Intensity', color='b')
    ax3_bottom.set_ylabel('2차 미분', color='r')
    ax3_top.legend(loc='upper left')
    ax3_bottom.legend(loc='upper right')
    ax3_top.grid(True, alpha=0.3)

    # ========== 4. 초기 피크 중심 추정 ==========
    ax4 = plt.subplot(3, 2, 4)
    ax4.plot(x, signal, 'b-', linewidth=2, alpha=0.5, label='원본 신호')

    # 로컬 최대값 찾기
    local_peaks, props = find_peaks(signal, prominence=np.max(signal)*0.05, distance=50)

    for i, lp in enumerate(local_peaks):
        ax4.plot(x[lp], signal[lp], 'ro', markersize=10)
        ax4.axvline(x=x[lp], color='red', linestyle='--', alpha=0.5)
        ax4.text(x[lp], signal[lp]+20, f'피크 {i+1}\n추정',
                ha='center', fontweight='bold',
                bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.7))

    ax4.set_title('3️⃣ 개별 피크 중심 위치 자동 추정',
                  fontsize=12, fontweight='bold', pad=10)
    ax4.set_xlabel('Retention Time (min)')
    ax4.set_ylabel('Intensity')
    ax4.legend()
    ax4.grid(True, alpha=0.3)

    # ========== 5. 가우시안 피팅 ==========
    ax5 = plt.subplot(3, 2, 5)
    ax5.plot(x, signal, 'b-', linewidth=2, alpha=0.5, label='원본 신호')

    # 개별 피크 표시
    colors = ['green', 'orange', 'purple']
    for i, (peak, (center, amp)) in enumerate(zip(individual_peaks, peak_info)):
        ax5.plot(x, peak, '--', color=colors[i], linewidth=2,
                label=f'피크 {i+1} (RT={center}, H={amp})')
        ax5.fill_between(x, 0, peak, alpha=0.2, color=colors[i])

    ax5.set_title('4️⃣ 다중 가우시안 피팅 (최적화)',
                  fontsize=12, fontweight='bold', pad=10)
    ax5.set_xlabel('Retention Time (min)')
    ax5.set_ylabel('Intensity')
    ax5.legend()
    ax5.grid(True, alpha=0.3)

    # ========== 6. 최종 결과 ==========
    ax6 = plt.subplot(3, 2, 6)

    # 원본
    ax6.plot(x, signal, 'gray', linewidth=2, alpha=0.5, label='원본 (겹친 피크)')

    # 디컨볼루션된 개별 피크
    for i, (peak, (center, amp)) in enumerate(zip(individual_peaks, peak_info)):
        ax6.plot(x, peak, linewidth=2.5, color=colors[i],
                label=f'분리된 피크 {i+1}')

        # 피크 면적 계산
        area = np.trapz(peak, x)
        ax6.fill_between(x, 0, peak, alpha=0.3, color=colors[i])

        # 면적 표시
        ax6.text(center, amp/2, f'면적\n{area:.0f}',
                ha='center', fontweight='bold',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    ax6.set_title('✅ 결과: 3개의 개별 피크로 분리 → 정확한 정량 가능!',
                  fontsize=12, fontweight='bold', pad=10, color='green')
    ax6.set_xlabel('Retention Time (min)')
    ax6.set_ylabel('Intensity')
    ax6.legend()
    ax6.grid(True, alpha=0.3)

    # 전체 제목
    fig.suptitle('피크 디컨볼루션(Peak Deconvolution) 작동 원리',
                fontsize=16, fontweight='bold', y=0.98)

    plt.tight_layout(rect=[0, 0.03, 1, 0.96])

    # 저장
    output_file = 'deconvolution_explanation.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\n설명 그림 저장: {output_file}")

    plt.show()


def print_explanation():
    """텍스트 설명 출력"""
    print("\n" + "="*80)
    print("피크 디컨볼루션(Peak Deconvolution)이란?")
    print("="*80)

    print("\n[개념]")
    print("   - 겹쳐진 여러 피크를 개별 피크로 분리하는 기술")
    print("   - 비슷한 RT를 가진 화합물들이 하나의 피크처럼 보일 때 사용")

    print("\n[작동 단계]")
    print("   STEP 1. 비대칭도 검사")
    print("      -> 비대칭도 > 1.2이면 겹친 피크일 가능성")
    print("      -> 비대칭도 = 오른쪽 폭 / 왼쪽 폭 (반높이 기준)")

    print("\n   STEP 2. 숄더(shoulder) 피크 검출")
    print("      -> 2차 미분 분석으로 숨어있는 피크 찾기")
    print("      -> 2차 미분의 양수 영역 = 오목한 부분 = 숄더")

    print("\n   STEP 3. 개별 피크 중심 추정")
    print("      -> 로컬 최대값 찾기")
    print("      -> prominence(돌출도) 기반으로 유의미한 피크만 선택")

    print("\n   STEP 4. 다중 가우시안 피팅")
    print("      -> N개의 가우시안 함수 동시 피팅")
    print("      -> 최소제곱법(curve_fit)으로 최적 파라미터 찾기")
    print("      -> R-squared > 0.85이면 성공으로 판정")

    print("\n   STEP 5. 개별 피크 정보 추출")
    print("      -> 각 피크의 RT, 높이, 면적, 면적% 계산")
    print("      -> 정확한 정량 분석 가능")

    print("\n[장점]")
    print("   * 겹친 피크도 정확하게 정량 가능")
    print("   * 숄더 피크 자동 검출")
    print("   * 미량 성분 분석 가능")

    print("\n[주요 파라미터]")
    print("   - min_asymmetry: 1.2 (비대칭도 임계값)")
    print("   - min_shoulder_ratio: 0.1 (숄더 높이 최소 10%)")
    print("   - max_components: 4 (최대 4개 피크까지 분리)")
    print("   - fit_tolerance: 0.85 (R² 최소값)")

    print("\n" + "="*80)


if __name__ == "__main__":
    print_explanation()
    explain_deconvolution()