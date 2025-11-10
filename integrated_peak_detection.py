"""
통합 피크 검출 시스템
베이스라인 개선사항 (스무딩 강화, 음수 후처리) 적용
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import sys
from scipy import signal
from scipy.integrate import trapezoid

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from hybrid_baseline import HybridBaselineCorrector

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False


class IntegratedPeakDetector:
    """
    통합 피크 검출 시스템
    - 베이스라인 스무딩 강화
    - 음수 영역 후처리
    - 양방향 피크 검출 (양수/음수)
    """

    def __init__(self, time, intensity):
        self.time = time
        self.intensity = intensity

    def detect_peaks_with_baseline_correction(
        self,
        baseline_method: str = 'robust_fit',
        enhanced_smoothing: bool = True,
        clip_negative: bool = True,
        negative_threshold: float = -50.0
    ):
        """
        베이스라인 보정 후 피크 검출

        Args:
            baseline_method: 베이스라인 방법 ('robust_fit', 'weighted_spline')
            enhanced_smoothing: 강화된 스무딩 사용 여부
            clip_negative: 음수 영역 클리핑 여부
            negative_threshold: 음수 클리핑 임계값

        Returns:
            결과 딕셔너리
        """
        print(f"\n{'='*80}")
        print(f"통합 피크 검출 시작")
        print(f"{'='*80}")
        print(f"  베이스라인 방법: {baseline_method}")
        print(f"  강화 스무딩: {enhanced_smoothing}")
        print(f"  음수 클리핑: {clip_negative}")

        # 1. 베이스라인 보정
        print(f"\n[1단계] 베이스라인 보정")
        corrector = HybridBaselineCorrector(self.time, self.intensity)
        corrector.find_baseline_anchor_points(
            valley_prominence=0.01,
            percentile=10
        )

        baseline = corrector.generate_hybrid_baseline(
            method=baseline_method,
            enhanced_smoothing=enhanced_smoothing
        )

        corrected_raw = self.intensity - baseline

        print(f"  앵커 포인트: {len(corrector.baseline_points)}개")
        print(f"  보정 전 범위: {np.min(self.intensity):.2f} ~ {np.max(self.intensity):.2f}")
        print(f"  보정 후 범위: {np.min(corrected_raw):.2f} ~ {np.max(corrected_raw):.2f}")
        print(f"  음수 값: {np.sum(corrected_raw < 0)}개 ({np.sum(corrected_raw < 0)/len(corrected_raw)*100:.2f}%)")

        # 2. 음수 영역 후처리
        if clip_negative:
            print(f"\n[2단계] 음수 영역 후처리")
            corrected = corrector.post_process_corrected_signal(
                corrected_raw,
                clip_negative=True,
                negative_threshold=negative_threshold
            )

            clipped_count = np.sum(corrected_raw < 0) - np.sum(corrected < 0)
            print(f"  클리핑된 음수 값: {clipped_count}개")
            print(f"  남은 음수 값: {np.sum(corrected < 0)}개 ({np.sum(corrected < 0)/len(corrected)*100:.2f}%)")
        else:
            corrected = corrected_raw
            print(f"\n[2단계] 음수 영역 후처리 스킵")

        # 3. 피크 검출 (양방향)
        print(f"\n[3단계] 양방향 피크 검출")
        peaks_info = self._detect_bidirectional_peaks(corrected)

        positive_peaks = [p for p in peaks_info if p['polarity'] == 'positive']
        negative_peaks = [p for p in peaks_info if p['polarity'] == 'negative']

        print(f"  양수 피크: {len(positive_peaks)}개")
        print(f"  음수 피크: {len(negative_peaks)}개")
        print(f"  총 피크: {len(peaks_info)}개")

        # 4. 피크 면적 계산
        print(f"\n[4단계] 피크 면적 계산")
        self._calculate_peak_areas(peaks_info, corrected, baseline)

        total_area = sum(p['area'] for p in positive_peaks)
        print(f"  총 면적 (양수 피크): {total_area:.2f}")

        if len(negative_peaks) > 0:
            neg_total_area = sum(p['area'] for p in negative_peaks)
            print(f"  총 면적 (음수 피크): {neg_total_area:.2f}")

        return {
            'baseline': baseline,
            'corrected_raw': corrected_raw,
            'corrected': corrected,
            'peaks': peaks_info,
            'positive_peaks': positive_peaks,
            'negative_peaks': negative_peaks,
            'baseline_method': baseline_method,
            'enhanced_smoothing': enhanced_smoothing,
            'clip_negative': clip_negative
        }

    def _detect_bidirectional_peaks(self, corrected):
        """양방향 피크 검출"""
        signal_range = np.ptp(corrected)
        noise_level = np.percentile(np.abs(corrected), 25) * 1.5

        min_prominence = max(signal_range * 0.005, noise_level * 2)
        min_height = noise_level * 2

        peaks_info = []

        # 양수 피크
        pos_peaks, pos_props = signal.find_peaks(
            corrected,
            prominence=min_prominence,
            height=min_height,
            width=3,
            distance=20
        )

        for i, peak_idx in enumerate(pos_peaks):
            peaks_info.append({
                'index': peak_idx,
                'rt': self.time[peak_idx],
                'height': corrected[peak_idx],
                'prominence': pos_props['prominences'][i],
                'polarity': 'positive',
                'area': 0  # 나중에 계산
            })

        # 음수 피크
        neg_peaks, neg_props = signal.find_peaks(
            -corrected,
            prominence=min_prominence,
            height=min_height,
            width=3,
            distance=20
        )

        for i, peak_idx in enumerate(neg_peaks):
            peaks_info.append({
                'index': peak_idx,
                'rt': self.time[peak_idx],
                'height': corrected[peak_idx],
                'prominence': neg_props['prominences'][i],
                'polarity': 'negative',
                'area': 0  # 나중에 계산
            })

        # RT 순 정렬
        peaks_info.sort(key=lambda p: p['rt'])

        return peaks_info

    def _calculate_peak_areas(self, peaks_info, corrected, baseline):
        """피크 면적 계산"""
        for peak in peaks_info:
            peak_idx = peak['index']

            # 반치폭 기준 경계
            if peak['polarity'] == 'positive':
                peak_height = corrected[peak_idx]
                half_height = peak_height / 2
            else:
                peak_height = abs(corrected[peak_idx])
                half_height = corrected[peak_idx] / 2

            # 왼쪽 경계
            left_idx = peak_idx
            while left_idx > 0:
                if peak['polarity'] == 'positive':
                    if corrected[left_idx] < half_height:
                        break
                else:
                    if corrected[left_idx] > half_height:
                        break
                left_idx -= 1

            # 오른쪽 경계
            right_idx = peak_idx
            while right_idx < len(corrected) - 1:
                if peak['polarity'] == 'positive':
                    if corrected[right_idx] < half_height:
                        break
                else:
                    if corrected[right_idx] > half_height:
                        break
                right_idx += 1

            # 면적 계산
            peak_region_time = self.time[left_idx:right_idx+1]
            peak_region_signal = corrected[left_idx:right_idx+1]

            if peak['polarity'] == 'positive':
                area = trapezoid(np.maximum(peak_region_signal, 0), peak_region_time)
            else:
                area = abs(trapezoid(np.minimum(peak_region_signal, 0), peak_region_time))

            peak['area'] = area
            peak['left_idx'] = left_idx
            peak['right_idx'] = right_idx
            peak['width'] = self.time[right_idx] - self.time[left_idx]

    def visualize_results(self, result, output_file):
        """결과 시각화"""
        baseline = result['baseline']
        corrected_raw = result['corrected_raw']
        corrected = result['corrected']
        peaks = result['peaks']
        positive_peaks = result['positive_peaks']
        negative_peaks = result['negative_peaks']

        fig, axes = plt.subplots(2, 2, figsize=(16, 10))

        # Panel 1: 원본 + 베이스라인
        ax1 = axes[0, 0]
        ax1.plot(self.time, self.intensity, 'b-', linewidth=1.5, alpha=0.7, label='원본 신호')
        ax1.plot(self.time, baseline, 'r--', linewidth=2, label=f"베이스라인 ({result['baseline_method']})")
        ax1.axhline(y=0, color='gray', linestyle=':', alpha=0.5)
        ax1.set_xlabel('시간 (min)', fontsize=11)
        ax1.set_ylabel('강도', fontsize=11)
        ax1.set_title('원본 신호 + 베이스라인', fontsize=12, fontweight='bold')
        ax1.legend(fontsize=9)
        ax1.grid(True, alpha=0.3)

        # Panel 2: 보정 후 (후처리 전 vs 후)
        ax2 = axes[0, 1]
        ax2.plot(self.time, corrected_raw, 'orange', linewidth=1, alpha=0.6, label='후처리 전')
        ax2.plot(self.time, corrected, 'g-', linewidth=1.5, label='후처리 후')
        ax2.axhline(y=0, color='gray', linestyle='--', alpha=0.5)

        # 음수 영역 표시
        if result['clip_negative']:
            clipped_mask = (corrected_raw < 0) & (corrected == 0)
            if np.any(clipped_mask):
                ax2.fill_between(self.time, corrected_raw, 0, where=clipped_mask,
                               color='red', alpha=0.3, label='클리핑된 영역')

        ax2.set_xlabel('시간 (min)', fontsize=11)
        ax2.set_ylabel('강도', fontsize=11)
        ax2.set_title('보정 후 신호 (후처리 비교)', fontsize=12, fontweight='bold')
        ax2.legend(fontsize=9)
        ax2.grid(True, alpha=0.3)

        # Panel 3: 검출된 피크
        ax3 = axes[1, 0]
        ax3.plot(self.time, corrected, 'gray', linewidth=1, alpha=0.5, label='보정 신호')
        ax3.axhline(y=0, color='gray', linestyle='--', alpha=0.5)

        # 양수 피크
        if len(positive_peaks) > 0:
            pos_indices = [p['index'] for p in positive_peaks]
            ax3.plot(self.time[pos_indices], corrected[pos_indices],
                    'go', markersize=10, markeredgecolor='darkgreen', markeredgewidth=2,
                    label=f'양수 피크 ({len(positive_peaks)})')

        # 음수 피크
        if len(negative_peaks) > 0:
            neg_indices = [p['index'] for p in negative_peaks]
            ax3.plot(self.time[neg_indices], corrected[neg_indices],
                    'r^', markersize=12, markeredgecolor='darkred', markeredgewidth=2,
                    label=f'음수 피크 ({len(negative_peaks)})')

        ax3.set_xlabel('시간 (min)', fontsize=11)
        ax3.set_ylabel('강도', fontsize=11)
        ax3.set_title(f'검출된 피크 (총 {len(peaks)}개)', fontsize=12, fontweight='bold')
        ax3.legend(fontsize=9)
        ax3.grid(True, alpha=0.3)

        # Panel 4: 피크 면적 표시
        ax4 = axes[1, 1]
        ax4.plot(self.time, corrected, 'gray', linewidth=0.5, alpha=0.5)
        ax4.axhline(y=0, color='gray', linestyle='--', alpha=0.5)

        # 양수 피크 면적
        for peak in positive_peaks[:10]:  # 상위 10개만
            left = peak['left_idx']
            right = peak['right_idx']
            ax4.fill_between(self.time[left:right+1],
                           0, corrected[left:right+1],
                           alpha=0.4, color='green')
            ax4.plot(self.time[peak['index']], corrected[peak['index']],
                    'go', markersize=8, markeredgecolor='darkgreen', markeredgewidth=1.5)
            # RT 및 면적 라벨
            ax4.text(peak['rt'], corrected[peak['index']] + np.max(corrected)*0.02,
                    f"{peak['rt']:.1f}\n{peak['area']:.0f}",
                    fontsize=7, ha='center',
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='lightgreen', alpha=0.7))

        # 음수 피크 면적
        for peak in negative_peaks:
            left = peak['left_idx']
            right = peak['right_idx']
            ax4.fill_between(self.time[left:right+1],
                           0, corrected[left:right+1],
                           alpha=0.4, color='red')
            ax4.plot(self.time[peak['index']], corrected[peak['index']],
                    'r^', markersize=10, markeredgecolor='darkred', markeredgewidth=1.5)
            # RT 및 면적 라벨
            ax4.text(peak['rt'], corrected[peak['index']] - np.max(corrected)*0.02,
                    f"{peak['rt']:.1f}\n{peak['area']:.0f}",
                    fontsize=7, ha='center',
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='lightcoral', alpha=0.7))

        ax4.set_xlabel('시간 (min)', fontsize=11)
        ax4.set_ylabel('강도', fontsize=11)
        ax4.set_title('피크 면적 시각화', fontsize=12, fontweight='bold')
        ax4.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        print(f"\n시각화 저장: {output_file}")
        plt.close()


def analyze_sample(csv_file, output_dir):
    """샘플 분석"""
    # 데이터 로드
    df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
    time = df[0].values
    intensity = df[1].values

    sample_name = csv_file.stem

    print(f"\n{'='*80}")
    print(f"샘플: {sample_name}")
    print(f"{'='*80}")

    # 통합 피크 검출
    detector = IntegratedPeakDetector(time, intensity)
    result = detector.detect_peaks_with_baseline_correction(
        baseline_method='robust_fit',
        enhanced_smoothing=True,
        clip_negative=True,
        negative_threshold=-50.0
    )

    # 시각화
    output_file = output_dir / f'{sample_name}_integrated_peaks.png'
    detector.visualize_results(result, output_file)

    # 피크 정보 출력
    print(f"\n{'='*80}")
    print(f"피크 상세 정보 (상위 10개)")
    print(f"{'='*80}")

    sorted_peaks = sorted(result['positive_peaks'], key=lambda p: p['area'], reverse=True)
    for i, peak in enumerate(sorted_peaks[:10], 1):
        print(f"{i:2d}. RT={peak['rt']:6.2f} min, "
              f"높이={peak['height']:8.1f}, "
              f"면적={peak['area']:10.1f}, "
              f"폭={peak['width']:5.3f} min")

    if len(result['negative_peaks']) > 0:
        print(f"\n음수 피크:")
        for i, peak in enumerate(result['negative_peaks'], 1):
            print(f"{i:2d}. RT={peak['rt']:6.2f} min, "
                  f"높이={peak['height']:8.1f}, "
                  f"면적={peak['area']:10.1f}")

    return {
        'sample': sample_name,
        'positive_peaks': len(result['positive_peaks']),
        'negative_peaks': len(result['negative_peaks']),
        'total_area': sum(p['area'] for p in result['positive_peaks'])
    }


def main():
    """메인 함수"""
    # 출력 디렉토리
    output_dir = Path('result/integrated_detection')
    output_dir.mkdir(parents=True, exist_ok=True)

    # 데이터 디렉토리
    csv_dir = Path('exported_signals')
    csv_files = sorted(csv_dir.glob('*.csv'))

    if len(csv_files) == 0:
        print("데이터 파일이 없습니다.")
        return

    # 처음 5개 샘플 분석
    selected_files = list(csv_files[:5])

    print("\n" + "="*80)
    print("통합 피크 검출 시스템")
    print("="*80)
    print(f"총 {len(selected_files)}개 샘플 분석")
    print(f"출력 디렉토리: {output_dir}/")

    results = []
    for csv_file in selected_files:
        result = analyze_sample(csv_file, output_dir)
        results.append(result)

    # 전체 요약
    print("\n" + "="*80)
    print("전체 분석 요약")
    print("="*80)

    summary_df = pd.DataFrame(results)
    print(f"\n평균 양수 피크: {summary_df['positive_peaks'].mean():.1f}개")
    print(f"평균 음수 피크: {summary_df['negative_peaks'].mean():.1f}개")
    print(f"평균 총 면적: {summary_df['total_area'].mean():.1f}")

    print(f"\n{'샘플':<45} | 양수 | 음수 | 총면적")
    print("-" * 80)
    for _, row in summary_df.iterrows():
        print(f"{row['sample']:<45} | {row['positive_peaks']:4d} | "
              f"{row['negative_peaks']:4d} | {row['total_area']:10.0f}")

    # CSV 저장
    summary_file = output_dir / 'integrated_detection_summary.csv'
    summary_df.to_csv(summary_file, index=False, encoding='utf-8-sig')
    print(f"\n요약 저장: {summary_file}")

    print(f"\n모든 이미지 저장: {output_dir}/")


if __name__ == '__main__':
    main()
