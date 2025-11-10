"""
음수 피크 검출 테스트
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from hybrid_baseline import HybridBaselineCorrector
from iterative_peak_recovery import IterativePeakRecovery

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False


def create_test_signal_with_negative_peaks():
    """음수 피크가 포함된 테스트 신호 생성"""
    time = np.linspace(0, 20, 1000)

    # 베이스라인 (완만한 곡선)
    baseline = 100 + 20 * np.sin(time * 0.3)

    # 양수 피크 추가
    signal = baseline.copy()

    # 피크 1 (양수, RT=3)
    signal += 80 * np.exp(-((time - 3) ** 2) / 0.5)

    # 피크 2 (음수, RT=7)
    signal -= 60 * np.exp(-((time - 7) ** 2) / 0.3)

    # 피크 3 (양수, RT=11)
    signal += 100 * np.exp(-((time - 11) ** 2) / 0.6)

    # 피크 4 (음수, RT=15)
    signal -= 40 * np.exp(-((time - 15) ** 2) / 0.4)

    # 노이즈 추가
    noise = np.random.normal(0, 2, len(time))
    signal += noise

    return time, signal


def test_with_synthetic_data():
    """합성 데이터로 테스트"""
    print("="*60)
    print("합성 데이터로 음수 피크 검출 테스트")
    print("="*60)

    time, intensity = create_test_signal_with_negative_peaks()

    print(f"\n신호 범위: {np.min(intensity):.2f} ~ {np.max(intensity):.2f}")
    print(f"음수 값 포함: {np.any(intensity < 0)}")

    # 베이스라인 보정
    corrector = HybridBaselineCorrector(time, intensity)
    baseline, params = corrector.optimize_baseline_with_linear_peaks()
    corrected = intensity - baseline

    print(f"\n베이스라인 보정 후:")
    print(f"  보정 신호 범위: {np.min(corrected):.2f} ~ {np.max(corrected):.2f}")
    print(f"  음수 값 포함: {np.any(corrected < 0)}")

    # 피크 검출
    recovery = IterativePeakRecovery(time, intensity)
    peaks, peak_info = recovery.detect_peaks(corrected)

    print(f"\n피크 검출 결과:")
    print(f"  총 {len(peaks)}개 피크 검출")

    positive_peaks = [p for p in peak_info if p['polarity'] == 'positive']
    negative_peaks = [p for p in peak_info if p['polarity'] == 'negative']

    print(f"  - 양수 피크: {len(positive_peaks)}개")
    print(f"  - 음수 피크: {len(negative_peaks)}개")

    print(f"\n피크 상세:")
    for i, p in enumerate(peak_info, 1):
        polarity_str = "양수" if p['polarity'] == 'positive' else "음수"
        print(f"  {i}. RT={p['rt']:.2f}, 높이={p['height']:.2f}, "
              f"면적={p['area']:.2f}, {polarity_str} 피크")

    # 시각화
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # Panel 1: 원본 신호
    ax1 = axes[0, 0]
    ax1.plot(time, intensity, 'b-', linewidth=1.5, label='원본 신호')
    ax1.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    ax1.set_xlabel('시간 (min)')
    ax1.set_ylabel('강도')
    ax1.set_title('원본 신호 (음수 영역 포함)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Panel 2: 베이스라인 비교
    ax2 = axes[0, 1]
    ax2.plot(time, intensity, 'b-', linewidth=1.5, alpha=0.7, label='원본 신호')
    ax2.plot(time, baseline, 'k--', linewidth=2, label='베이스라인')
    ax2.axhline(y=0, color='gray', linestyle='--', alpha=0.5)

    # 베이스라인이 신호 위로 가는 영역 강조
    above_signal = baseline > intensity
    if np.any(above_signal):
        ax2.fill_between(time, intensity, baseline, where=above_signal,
                        color='red', alpha=0.3, label='베이스라인이 신호 위')

    ax2.set_xlabel('시간 (min)')
    ax2.set_ylabel('강도')
    ax2.set_title('베이스라인 (신호 위로 갈 수 있음)')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    # Panel 3: 보정된 신호
    ax3 = axes[1, 0]
    ax3.plot(time, corrected, 'g-', linewidth=1.5, label='보정된 신호')
    ax3.axhline(y=0, color='gray', linestyle='--', alpha=0.5)

    # 양수/음수 영역 구분
    ax3.fill_between(time, 0, corrected, where=corrected >= 0,
                    color='green', alpha=0.3, label='양수 영역')
    ax3.fill_between(time, 0, corrected, where=corrected < 0,
                    color='red', alpha=0.3, label='음수 영역')

    ax3.set_xlabel('시간 (min)')
    ax3.set_ylabel('강도')
    ax3.set_title('베이스라인 보정 후 (양수/음수 모두 포함)')
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    # Panel 4: 검출된 피크
    ax4 = axes[1, 1]
    ax4.plot(time, corrected, 'gray', linewidth=1, alpha=0.5, label='보정된 신호')
    ax4.axhline(y=0, color='gray', linestyle='--', alpha=0.5)

    # 양수 피크
    for p in positive_peaks:
        ax4.plot(p['rt'], p['height'], 'go', markersize=12,
                markeredgecolor='darkgreen', markeredgewidth=2,
                label='양수 피크' if p == positive_peaks[0] else '')
        ax4.annotate(f"RT:{p['rt']:.1f}\nA:{p['area']:.0f}",
                   xy=(p['rt'], p['height']),
                   xytext=(0, 15), textcoords='offset points',
                   ha='center', fontsize=8,
                   bbox=dict(boxstyle='round,pad=0.3', facecolor='lightgreen', alpha=0.8),
                   arrowprops=dict(arrowstyle='->', lw=1))

    # 음수 피크
    for p in negative_peaks:
        ax4.plot(p['rt'], p['height'], 'r^', markersize=12,
                markeredgecolor='darkred', markeredgewidth=2,
                label='음수 피크' if p == negative_peaks[0] else '')
        ax4.annotate(f"RT:{p['rt']:.1f}\nA:{p['area']:.0f}",
                   xy=(p['rt'], p['height']),
                   xytext=(0, -20), textcoords='offset points',
                   ha='center', fontsize=8,
                   bbox=dict(boxstyle='round,pad=0.3', facecolor='lightcoral', alpha=0.8),
                   arrowprops=dict(arrowstyle='->', lw=1))

    ax4.set_xlabel('시간 (min)')
    ax4.set_ylabel('강도')
    ax4.set_title(f'검출된 피크 (양수: {len(positive_peaks)}개, 음수: {len(negative_peaks)}개)')
    ax4.legend()
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('result/negative_peak_test_synthetic.png', dpi=150, bbox_inches='tight')
    print(f"\n시각화 저장: result/negative_peak_test_synthetic.png")
    plt.show()


def test_with_real_data():
    """실제 데이터로 테스트 (첫 번째 샘플)"""
    print("\n" + "="*60)
    print("실제 데이터로 음수 피크 검출 테스트")
    print("="*60)

    csv_dir = Path('exported_signals')
    csv_files = sorted(csv_dir.glob('*.csv'))

    if len(csv_files) == 0:
        print("실제 데이터 파일이 없습니다.")
        return

    # 첫 번째 파일 사용
    csv_file = csv_files[0]
    print(f"\n파일: {csv_file.name}")

    df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
    time = df[0].values
    intensity = df[1].values

    print(f"신호 범위: {np.min(intensity):.2f} ~ {np.max(intensity):.2f}")
    print(f"음수 값 포함: {np.any(intensity < 0)}")

    # 베이스라인 보정
    corrector = HybridBaselineCorrector(time, intensity)
    baseline, params = corrector.optimize_baseline_with_linear_peaks()
    corrected = intensity - baseline

    print(f"\n베이스라인 보정 후:")
    print(f"  보정 신호 범위: {np.min(corrected):.2f} ~ {np.max(corrected):.2f}")
    print(f"  음수 값 포함: {np.any(corrected < 0)}")

    # 피크 검출
    recovery = IterativePeakRecovery(time, intensity)
    peaks, peak_info = recovery.detect_peaks(corrected)

    print(f"\n피크 검출 결과:")
    print(f"  총 {len(peaks)}개 피크 검출")

    positive_peaks = [p for p in peak_info if p['polarity'] == 'positive']
    negative_peaks = [p for p in peak_info if p['polarity'] == 'negative']

    print(f"  - 양수 피크: {len(positive_peaks)}개")
    print(f"  - 음수 피크: {len(negative_peaks)}개")

    if negative_peaks:
        print(f"\n음수 피크 상세:")
        for i, p in enumerate(negative_peaks, 1):
            print(f"  {i}. RT={p['rt']:.2f}, 높이={p['height']:.2f}, 면적={p['area']:.2f}")

    # 시각화 (실제 데이터)
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # Panel 1: 원본 신호
    ax1 = axes[0, 0]
    ax1.plot(time, intensity, 'b-', linewidth=1, label='원본 신호')
    ax1.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    ax1.set_xlabel('시간 (min)')
    ax1.set_ylabel('강도')
    ax1.set_title(f'원본 신호 - {csv_file.stem}')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Panel 2: 베이스라인 비교
    ax2 = axes[0, 1]
    ax2.plot(time, intensity, 'b-', linewidth=1, alpha=0.7, label='원본 신호')
    ax2.plot(time, baseline, 'k--', linewidth=2, label='베이스라인')
    ax2.axhline(y=0, color='gray', linestyle='--', alpha=0.5)

    # 베이스라인이 신호 위로 가는 영역
    above_signal = baseline > intensity
    if np.any(above_signal):
        ax2.fill_between(time, intensity, baseline, where=above_signal,
                        color='red', alpha=0.3, label=f'베이스라인이 신호 위 ({np.sum(above_signal)}점)')

    ax2.set_xlabel('시간 (min)')
    ax2.set_ylabel('강도')
    ax2.set_title('베이스라인')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    # Panel 3: 보정된 신호
    ax3 = axes[1, 0]
    ax3.plot(time, corrected, 'g-', linewidth=1, label='보정된 신호')
    ax3.axhline(y=0, color='gray', linestyle='--', alpha=0.5)

    # 양수/음수 영역
    if np.any(corrected >= 0):
        ax3.fill_between(time, 0, corrected, where=corrected >= 0,
                        color='green', alpha=0.3, label='양수 영역')
    if np.any(corrected < 0):
        ax3.fill_between(time, 0, corrected, where=corrected < 0,
                        color='red', alpha=0.3, label='음수 영역')

    ax3.set_xlabel('시간 (min)')
    ax3.set_ylabel('강도')
    ax3.set_title('베이스라인 보정 후')
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    # Panel 4: 검출된 피크
    ax4 = axes[1, 1]
    ax4.plot(time, corrected, 'gray', linewidth=0.5, alpha=0.5, label='보정된 신호')
    ax4.axhline(y=0, color='gray', linestyle='--', alpha=0.5)

    # 양수 피크
    if positive_peaks:
        for p in positive_peaks[:10]:  # 처음 10개만
            ax4.plot(p['rt'], p['height'], 'go', markersize=8,
                    markeredgecolor='darkgreen', markeredgewidth=1.5,
                    label='양수 피크' if p == positive_peaks[0] else '')

    # 음수 피크
    if negative_peaks:
        for p in negative_peaks[:10]:  # 처음 10개만
            ax4.plot(p['rt'], p['height'], 'r^', markersize=10,
                    markeredgecolor='darkred', markeredgewidth=1.5,
                    label='음수 피크' if p == negative_peaks[0] else '')
            # 음수 피크에 RT 라벨
            ax4.annotate(f"{p['rt']:.1f}",
                       xy=(p['rt'], p['height']),
                       xytext=(0, -15), textcoords='offset points',
                       ha='center', fontsize=7,
                       bbox=dict(boxstyle='round,pad=0.2', facecolor='yellow', alpha=0.7))

    ax4.set_xlabel('시간 (min)')
    ax4.set_ylabel('강도')
    ax4.set_title(f'검출된 피크 (양수: {len(positive_peaks)}, 음수: {len(negative_peaks)})')
    ax4.legend()
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()
    output_file = f'result/negative_peak_test_{csv_file.stem}.png'
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\n시각화 저장: {output_file}")
    plt.show()


if __name__ == '__main__':
    # 출력 디렉토리 생성
    Path('result').mkdir(exist_ok=True)

    # 1. 합성 데이터 테스트
    test_with_synthetic_data()

    # 2. 실제 데이터 테스트
    test_with_real_data()
