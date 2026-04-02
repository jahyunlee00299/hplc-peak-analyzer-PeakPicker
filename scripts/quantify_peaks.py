"""
피크 면적 정량 분석
통합 피크 검출 시스템을 사용하여 폴더 내 모든 샘플 정량
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import sys
import re

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from hybrid_baseline import HybridBaselineCorrector

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False


class PeakQuantifier:
    """피크 면적 정량 분석"""

    def __init__(self, half_peak_mode: str = 'none'):
        self.results = []
        self.half_peak_mode = half_peak_mode

    def quantify_sample(self, csv_file, baseline_method='robust_fit'):
        """단일 샘플 정량"""
        # 데이터 로드
        df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
        time = df[0].values
        intensity = df[1].values

        # 베이스라인 보정
        corrector = HybridBaselineCorrector(time, intensity)
        corrector.find_baseline_anchor_points(valley_prominence=0.01, percentile=10)
        baseline = corrector.generate_hybrid_baseline(
            method=baseline_method,
            enhanced_smoothing=True
        )

        # 보정 및 후처리
        corrected_raw = intensity - baseline
        corrected = corrector.post_process_corrected_signal(
            corrected_raw,
            clip_negative=True,
            negative_threshold=-50.0
        )

        # 피크 검출
        peaks_info = self._detect_peaks(time, corrected)

        return {
            'time': time,
            'intensity': intensity,
            'baseline': baseline,
            'corrected': corrected,
            'peaks': peaks_info
        }

    def _estimate_noise_level(self, corrected):
        """
        Robust noise level estimation using MAD (Median Absolute Deviation).

        Better than percentile-based estimation for signals with many peaks.
        """
        # Use derivative for noise estimation (less affected by peaks)
        derivative = np.diff(corrected)

        # MAD is more robust than standard deviation for non-Gaussian noise
        mad = np.median(np.abs(derivative - np.median(derivative)))

        # Convert MAD to standard deviation equivalent
        # For Gaussian: std ≈ 1.4826 * MAD
        noise_std = mad * 1.4826

        return noise_std

    def _estimate_snr(self, corrected, noise_level):
        """
        Estimate Signal-to-Noise Ratio for the chromatogram.

        Returns
        -------
        float
            Estimated SNR (signal peak / noise level)
        """
        signal_max = np.max(corrected)
        if noise_level > 0:
            return signal_max / noise_level
        return 100.0  # Default high SNR if noise is zero

    def _get_adaptive_parameters(self, corrected):
        """
        Calculate adaptive peak detection parameters based on SNR.

        Low SNR: More conservative (higher thresholds)
        High SNR: More sensitive (lower thresholds)
        """
        noise_level = self._estimate_noise_level(corrected)
        snr = self._estimate_snr(corrected, noise_level)
        signal_range = np.ptp(corrected)

        # Adaptive prominence based on SNR
        if snr > 100:
            # High SNR: Very sensitive detection
            prominence_factor = 0.0005
            height_factor = 0.3
            min_width = 1
        elif snr > 50:
            # Medium-high SNR: Sensitive detection
            prominence_factor = 0.001
            height_factor = 0.5
            min_width = 1
        elif snr > 20:
            # Medium SNR: Standard detection
            prominence_factor = 0.002
            height_factor = 1.0
            min_width = 2
        elif snr > 10:
            # Low SNR: Conservative detection
            prominence_factor = 0.005
            height_factor = 2.0
            min_width = 3
        else:
            # Very low SNR: Very conservative
            prominence_factor = 0.01
            height_factor = 3.0
            min_width = 5

        min_prominence = max(signal_range * prominence_factor, noise_level * height_factor)
        min_height = noise_level * height_factor

        return {
            'noise_level': noise_level,
            'snr': snr,
            'min_prominence': min_prominence,
            'min_height': min_height,
            'min_width': min_width
        }

    def _detect_peaks(self, time, corrected):
        """피크 검출 및 면적 계산 (SNR 기반 적응형 파라미터)"""
        from scipy import signal
        from scipy.integrate import trapezoid

        # Get adaptive parameters based on SNR
        params = self._get_adaptive_parameters(corrected)
        noise_level = params['noise_level']
        min_prominence = params['min_prominence']
        min_height = params['min_height']
        min_width = params['min_width']

        # 양수 피크만 검출
        peaks, props = signal.find_peaks(
            corrected,
            prominence=min_prominence,
            height=min_height,
            width=min_width,
            distance=15
        )

        peaks_info = []
        for i, peak_idx in enumerate(peaks):
            peak_height = corrected[peak_idx]

            # 피크 높이 기반 경계 임계값 (피크 높이의 1%)
            # 이 방식은 작은 피크와 큰 피크 모두에서 일관된 경계 검출을 보장
            boundary_threshold = max(peak_height * 0.01, noise_level * 0.5)

            # 베이스라인 복귀 지점 찾기
            left_idx = peak_idx
            while left_idx > 0 and corrected[left_idx] > boundary_threshold:
                left_idx -= 1

            right_idx = peak_idx
            while right_idx < len(corrected) - 1 and corrected[right_idx] > boundary_threshold:
                right_idx += 1

            # 면적 계산 (초 단위로 변환)
            peak_region_time = time[left_idx:right_idx+1] * 60  # 분 → 초
            peak_region_signal = np.maximum(corrected[left_idx:right_idx+1], 0)

            # Half-peak quantification
            apex_rel = peak_idx - left_idx  # apex index relative to peak region

            if self.half_peak_mode in ('left', 'right', 'auto') and apex_rel > 0 and apex_rel < len(peak_region_signal) - 1:
                left_area = trapezoid(peak_region_signal[:apex_rel+1], peak_region_time[:apex_rel+1])
                right_area = trapezoid(peak_region_signal[apex_rel:], peak_region_time[apex_rel:])
                asymmetry_ratio = left_area / right_area if right_area > 0 else float('inf')

                if self.half_peak_mode == 'left':
                    half_area = left_area
                    area = half_area * 2
                    used_half = 'left'
                elif self.half_peak_mode == 'right':
                    half_area = right_area
                    area = half_area * 2
                    used_half = 'right'
                else:  # auto
                    if left_area <= right_area:
                        half_area = left_area
                        used_half = 'left'
                    else:
                        half_area = right_area
                        used_half = 'right'
                    area = half_area * 2

                asymmetry_warning = asymmetry_ratio > 1.5 or asymmetry_ratio < 0.67
            else:
                area = trapezoid(peak_region_signal, peak_region_time)
                left_area = trapezoid(peak_region_signal[:max(1, apex_rel+1)], peak_region_time[:max(1, apex_rel+1)]) if apex_rel > 0 else area / 2
                right_area = area - left_area
                asymmetry_ratio = left_area / right_area if right_area > 0 else 1.0
                asymmetry_warning = False
                used_half = 'none'
                half_area = area / 2

            peaks_info.append({
                'index': peak_idx,
                'rt': time[peak_idx],
                'height': peak_height,
                'area': area,
                'prominence': props['prominences'][i],
                'width': time[right_idx] - time[left_idx],
                'left_idx': left_idx,
                'right_idx': right_idx,
                'half_peak_mode': used_half,
                'half_area': half_area,
                'full_area': left_area + right_area,
                'asymmetry_ratio': round(asymmetry_ratio, 3),
                'asymmetry_warning': asymmetry_warning,
            })

        # 면적 순 정렬
        peaks_info.sort(key=lambda p: p['area'], reverse=True)

        return peaks_info

    def analyze_folder(self, folder_path, create_individual_plots=True):
        """폴더 내 모든 샘플 분석"""
        folder = Path(folder_path)
        csv_files = sorted(folder.glob('*.csv'))

        print(f"\n{'='*80}")
        print(f"폴더: {folder.name}")
        print(f"{'='*80}")
        print(f"총 {len(csv_files)}개 샘플 발견\n")

        all_results = []
        sample_details = []  # 개별 샘플 상세 정보 저장

        for csv_file in csv_files:
            sample_name = csv_file.stem
            print(f"분석 중: {sample_name}")

            try:
                result = self.quantify_sample(csv_file)

                # 샘플명에서 정보 추출
                sample_info = self._parse_sample_name(sample_name)

                # 피크 정보
                peaks = result['peaks']

                # 결과 저장
                for i, peak in enumerate(peaks[:5], 1):  # 상위 5개 피크만
                    all_results.append({
                        'sample': sample_name,
                        'concentration': sample_info.get('concentration', 'unknown'),
                        'conc_numeric': sample_info.get('conc_numeric', 0),
                        'replicate': sample_info.get('replicate', 'unknown'),
                        'peak_rank': i,
                        'rt': peak['rt'],
                        'height': peak['height'],
                        'area': peak['area'],
                        'width': peak['width'],
                        'prominence': peak['prominence']
                    })

                print(f"  검출된 피크: {len(peaks)}개")
                if len(peaks) > 0:
                    print(f"  주 피크 RT: {peaks[0]['rt']:.2f} min, 면적: {peaks[0]['area']:.1f}")

                # 샘플 상세 정보 저장
                sample_details.append({
                    'name': sample_name,
                    'time': result['time'],
                    'intensity': result['intensity'],
                    'baseline': result['baseline'],
                    'corrected': result['corrected'],
                    'peaks': peaks
                })

            except Exception as e:
                print(f"  [오류] {e}")

        # 개별 크로마토그램 저장
        if create_individual_plots and len(sample_details) > 0:
            self.sample_details = sample_details

        return pd.DataFrame(all_results)

    def _parse_sample_name(self, sample_name):
        """샘플명에서 농도 및 반복 정보 추출"""
        info = {}

        # SP0810 같은 샘플 ID 뒤의 농도만 추출
        # 예: SP0810_0_625MM_1 -> 0.625mM
        #     SP0810_10MM_1 -> 10mM

        # SP나 다른 ID 이후의 농도 패턴만 찾기
        conc_patterns = [
            # SP0810_0_625MM 형태
            (r'SP\d+_(\d+_\d+)MM', lambda m: f"{m.group(1).replace('_', '.')}"),
            # SP0810_10MM 형태
            (r'SP\d+_(\d+)MM', lambda m: f"{m.group(1)}"),
            # 일반적인 패턴 (SP 없는 경우)
            (r'_(\d+_\d+)MM', lambda m: f"{m.group(1).replace('_', '.')}"),
            (r'_(\d+)MM', lambda m: f"{m.group(1)}"),
        ]

        for pattern, formatter in conc_patterns:
            match = re.search(pattern, sample_name)
            if match:
                conc_value = formatter(match)
                info['concentration'] = conc_value
                info['conc_numeric'] = float(conc_value)
                break

        # 반복 번호 찾기 (마지막 _숫자)
        rep_match = re.search(r'_(\d+)$', sample_name)
        if rep_match:
            info['replicate'] = int(rep_match.group(1))

        return info

    def create_summary_report(self, df, output_dir, reference_y0=None, reference_a=None):
        """요약 리포트 생성 및 참조값 비교"""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # STD 샘플 여부 확인 (샘플명에 'STD' 포함)
        is_std_samples = df['sample'].str.contains('STD', case=False, na=False).any()

        # 농도별 그룹화 (STD 샘플만)
        if is_std_samples and 'concentration' in df.columns and df['concentration'].nunique() > 1:
            # 주 피크 (rank 1)만 필터
            main_peaks = df[df['peak_rank'] == 1].copy()

            # 숫자 농도로 정렬
            main_peaks['conc_value'] = main_peaks['conc_numeric']
            main_peaks = main_peaks[main_peaks['conc_value'] > 0]  # unknown 제외
            main_peaks = main_peaks.sort_values('conc_value')

            # 농도별 통계
            summary = main_peaks.groupby('concentration').agg({
                'area': ['mean', 'std', 'count'],
                'rt': 'mean',
                'height': 'mean'
            }).round(2)

            print(f"\n{'='*80}")
            print("농도별 주 피크 면적 요약")
            print(f"{'='*80}")
            print(summary)
        else:
            # 일반 샘플: 피크 정보 시각화
            print(f"\n{'='*80}")
            print("일반 샘플 분석 결과")
            print(f"{'='*80}")
            self._plot_peak_information(df, output_dir)

        # 전체 결과 CSV
        full_file = output_dir / 'all_peaks_detailed.csv'
        df.to_csv(full_file, index=False, encoding='utf-8-sig')
        print(f"전체 결과 저장: {full_file}")

        # 개별 크로마토그램 생성
        chromatogram_files = self.create_individual_chromatograms(output_dir)

        # 오버레이 크로마토그램 생성
        overlay_files = self.create_overlay_chromatograms(output_dir)

        return df


    def _plot_peak_information(self, df, output_dir):
        """일반 샘플 피크 정보 시각화"""
        # 샘플별 주 피크 (rank 1) 정보
        main_peaks = df[df['peak_rank'] == 1].copy()

        if len(main_peaks) == 0:
            print("표시할 주 피크가 없습니다.")
            return

        # 샘플별 통계
        print(f"\n샘플별 주 피크 정보:")
        print(f"{'샘플':<40} {'RT':>8} {'높이':>12} {'면적':>15} {'폭':>8}")
        print("-" * 90)

        for _, row in main_peaks.iterrows():
            print(f"{row['sample']:<40} {row['rt']:>8.2f} {row['height']:>12.1f} {row['area']:>15.1f} {row['width']:>8.4f}")

        # 시각화
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))

        # Panel 1: RT 분포
        ax1 = axes[0, 0]
        ax1.bar(range(len(main_peaks)), main_peaks['rt'].values, color='steelblue', alpha=0.7)
        ax1.set_xlabel('샘플 번호', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Retention Time (min)', fontsize=12, fontweight='bold')
        ax1.set_title('주 피크 RT 분포', fontsize=13, fontweight='bold')
        ax1.grid(True, alpha=0.3, axis='y')

        # RT 평균선
        rt_mean = main_peaks['rt'].mean()
        ax1.axhline(rt_mean, color='red', linestyle='--', linewidth=2,
                   label=f'평균: {rt_mean:.2f} min')
        ax1.legend(fontsize=10)

        # Panel 2: 면적 분포
        ax2 = axes[0, 1]
        ax2.bar(range(len(main_peaks)), main_peaks['area'].values, color='forestgreen', alpha=0.7)
        ax2.set_xlabel('샘플 번호', fontsize=12, fontweight='bold')
        ax2.set_ylabel('피크 면적', fontsize=12, fontweight='bold')
        ax2.set_title('주 피크 면적 분포', fontsize=13, fontweight='bold')
        ax2.grid(True, alpha=0.3, axis='y')

        # 면적 평균 및 표준편차
        area_mean = main_peaks['area'].mean()
        area_std = main_peaks['area'].std()
        ax2.axhline(area_mean, color='red', linestyle='--', linewidth=2,
                   label=f'평균: {area_mean:.1f}')
        ax2.axhline(area_mean + area_std, color='orange', linestyle=':', linewidth=1.5,
                   label=f'±1 SD: {area_std:.1f}')
        ax2.axhline(area_mean - area_std, color='orange', linestyle=':', linewidth=1.5)
        ax2.legend(fontsize=10)

        # Panel 3: 높이 vs 면적 산점도
        ax3 = axes[1, 0]
        scatter = ax3.scatter(main_peaks['height'].values, main_peaks['area'].values,
                            s=100, c=main_peaks['rt'].values, cmap='viridis',
                            alpha=0.7, edgecolors='black', linewidth=1)
        ax3.set_xlabel('피크 높이 (mAU)', fontsize=12, fontweight='bold')
        ax3.set_ylabel('피크 면적', fontsize=12, fontweight='bold')
        ax3.set_title('높이 vs 면적 상관관계', fontsize=13, fontweight='bold')
        ax3.grid(True, alpha=0.3)

        # 컬러바 (RT)
        cbar = plt.colorbar(scatter, ax=ax3)
        cbar.set_label('RT (min)', fontsize=10)

        # Panel 4: 통계 요약 테이블
        ax4 = axes[1, 1]
        ax4.axis('off')

        # 통계 계산
        stats = {
            '항목': ['샘플 수', 'RT 평균', 'RT 표준편차', 'RT 범위',
                    '면적 평균', '면적 표준편차', '면적 CV%', '면적 범위',
                    '높이 평균', '높이 표준편차'],
            '값': [
                f"{len(main_peaks)}",
                f"{main_peaks['rt'].mean():.2f} min",
                f"{main_peaks['rt'].std():.4f} min",
                f"{main_peaks['rt'].min():.2f} ~ {main_peaks['rt'].max():.2f} min",
                f"{main_peaks['area'].mean():.1f}",
                f"{main_peaks['area'].std():.1f}",
                f"{main_peaks['area'].std() / main_peaks['area'].mean() * 100:.1f}%",
                f"{main_peaks['area'].min():.1f} ~ {main_peaks['area'].max():.1f}",
                f"{main_peaks['height'].mean():.1f}",
                f"{main_peaks['height'].std():.1f}"
            ]
        }

        table_data = [[stats['항목'][i], stats['값'][i]] for i in range(len(stats['항목']))]

        table = ax4.table(cellText=table_data, colLabels=['항목', '값'],
                         cellLoc='left', loc='center',
                         colWidths=[0.4, 0.6])
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1, 2.5)

        # 헤더 스타일
        for i in range(2):
            table[(0, i)].set_facecolor('#4CAF50')
            table[(0, i)].set_text_props(weight='bold', color='white')

        # 행 색상 교대
        for i in range(1, len(table_data) + 1):
            for j in range(2):
                if i % 2 == 0:
                    table[(i, j)].set_facecolor('#f0f0f0')

        ax4.set_title('통계 요약', fontsize=13, fontweight='bold', pad=20)

        plt.tight_layout()
        plot_file = output_dir / 'peak_information_summary.png'
        plt.savefig(plot_file, dpi=150, bbox_inches='tight')
        print(f"피크 정보 그래프 저장: {plot_file}")
        plt.close()

    def create_individual_chromatograms(self, output_dir):
        """각 샘플별 크로마토그램 시각화"""
        if not hasattr(self, 'sample_details') or len(self.sample_details) == 0:
            print("생성할 크로마토그램이 없습니다.")
            return []

        output_dir = Path(output_dir) / 'chromatograms'
        output_dir.mkdir(parents=True, exist_ok=True)

        saved_files = []

        print(f"\n{'='*80}")
        print("개별 크로마토그램 생성 중...")
        print(f"{'='*80}")

        for sample in self.sample_details:
            sample_name = sample['name']
            time = sample['time']
            intensity = sample['intensity']
            baseline = sample['baseline']
            corrected = sample['corrected']
            peaks = sample['peaks']

            # 피크가 있는 영역 감지 (x축 범위 설정용)
            xlim_min, xlim_max = None, None
            if len(peaks) > 0:
                # 모든 피크의 경계 찾기
                all_left_times = [time[p['left_idx']] for p in peaks]
                all_right_times = [time[p['right_idx']] for p in peaks]

                # 여유 공간 추가 (피크 전후 10%)
                time_span = time[-1] - time[0]
                margin = time_span * 0.05
                xlim_min = max(time[0], min(all_left_times) - margin)
                xlim_max = min(time[-1], max(all_right_times) + margin)

            # 6패널 레이아웃 (로그 스케일 추가)
            fig = plt.figure(figsize=(18, 14))
            gs = fig.add_gridspec(4, 2, hspace=0.35, wspace=0.3,
                                 left=0.06, right=0.97, top=0.95, bottom=0.04)

            # Panel 1: 원본 신호 + 베이스라인 (선형)
            ax1 = fig.add_subplot(gs[0, :])
            ax1.plot(time, intensity, 'b-', linewidth=1, alpha=0.7, label='원본 신호')
            ax1.plot(time, baseline, 'r--', linewidth=2, label='베이스라인')

            # 피크 위치 표시
            for i, peak in enumerate(peaks[:5], 1):  # 상위 5개만
                peak_idx = peak['index']
                ax1.axvline(time[peak_idx], color='green', linestyle=':', alpha=0.5)
                ax1.text(time[peak_idx], intensity[peak_idx], f'P{i}',
                        fontsize=9, ha='center', va='bottom', color='green', fontweight='bold')

            ax1.set_xlabel('시간 (min)', fontsize=11, fontweight='bold')
            ax1.set_ylabel('강도 (mAU)', fontsize=11, fontweight='bold')
            ax1.set_title(f'원본 크로마토그램: {sample_name}', fontsize=12, fontweight='bold')
            ax1.legend(fontsize=10, loc='upper right')
            ax1.grid(True, alpha=0.3)
            if xlim_min is not None:
                ax1.set_xlim(xlim_min, xlim_max)

            # Panel 2: 원본 신호 + 베이스라인 (로그 스케일)
            ax1_log = fig.add_subplot(gs[1, :])
            # 로그 스케일을 위해 양수 값으로 변환
            intensity_shifted = intensity - np.min(intensity) + 1
            baseline_shifted = baseline - np.min(intensity) + 1

            ax1_log.plot(time, intensity_shifted, 'b-', linewidth=1, alpha=0.7, label='원본 신호')
            ax1_log.plot(time, baseline_shifted, 'r--', linewidth=2, label='베이스라인')
            ax1_log.set_yscale('log')

            # 피크 위치 표시
            for i, peak in enumerate(peaks[:5], 1):
                peak_idx = peak['index']
                ax1_log.axvline(time[peak_idx], color='green', linestyle=':', alpha=0.5)

            ax1_log.set_xlabel('시간 (min)', fontsize=11, fontweight='bold')
            ax1_log.set_ylabel('강도 (mAU, log scale)', fontsize=11, fontweight='bold')
            ax1_log.set_title(f'원본 크로마토그램 (로그 스케일)', fontsize=12, fontweight='bold')
            ax1_log.legend(fontsize=10, loc='upper right')
            ax1_log.grid(True, alpha=0.3, which='both')
            if xlim_min is not None:
                ax1_log.set_xlim(xlim_min, xlim_max)

            # Panel 3: 보정된 신호 (선형)
            ax2 = fig.add_subplot(gs[2, :])
            ax2.plot(time, corrected, 'g-', linewidth=1.5, label='보정 신호')
            ax2.axhline(0, color='black', linestyle='-', linewidth=0.5, alpha=0.5)

            # 피크 영역 채우기
            for i, peak in enumerate(peaks[:5], 1):
                left_idx = peak['left_idx']
                right_idx = peak['right_idx']
                ax2.fill_between(time[left_idx:right_idx+1], 0, corrected[left_idx:right_idx+1],
                                alpha=0.3, label=f'P{i}' if i <= 3 else None)

                # 피크 정보 표시
                peak_idx = peak['index']
                ax2.plot(time[peak_idx], corrected[peak_idx], 'ro', markersize=8)
                ax2.text(time[peak_idx], corrected[peak_idx] * 1.05,
                        f"P{i}\nRT={peak['rt']:.2f}",
                        fontsize=8, ha='center', va='bottom',
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7))

            ax2.set_xlabel('시간 (min)', fontsize=11, fontweight='bold')
            ax2.set_ylabel('강도 (mAU)', fontsize=11, fontweight='bold')
            ax2.set_title('베이스라인 보정 후', fontsize=12, fontweight='bold')
            if len(peaks) <= 3:
                ax2.legend(fontsize=9, loc='upper right')
            ax2.grid(True, alpha=0.3)
            if xlim_min is not None:
                ax2.set_xlim(xlim_min, xlim_max)

            # Panel 4: 피크 정보 테이블
            ax3 = fig.add_subplot(gs[3, 0])
            ax3.axis('off')

            if len(peaks) > 0:
                table_data = []
                for i, peak in enumerate(peaks[:10], 1):  # 상위 10개
                    table_data.append([
                        f'P{i}',
                        f"{peak['rt']:.2f}",
                        f"{peak['height']:.1f}",
                        f"{peak['area']:.1f}",
                        f"{peak['width']:.4f}",
                        f"{peak['prominence']:.1f}"
                    ])

                table = ax3.table(
                    cellText=table_data,
                    colLabels=['#', 'RT\n(min)', '높이\n(mAU)', '면적', '폭\n(min)', '두드러짐'],
                    cellLoc='center',
                    loc='center',
                    colWidths=[0.08, 0.15, 0.18, 0.22, 0.15, 0.22]
                )
                table.auto_set_font_size(False)
                table.set_fontsize(9)
                table.scale(1, 2.2)

                # 헤더 스타일
                for i in range(6):
                    table[(0, i)].set_facecolor('#2196F3')
                    table[(0, i)].set_text_props(weight='bold', color='white')

                # 행 색상 교대
                for i in range(1, len(table_data) + 1):
                    for j in range(6):
                        if i % 2 == 0:
                            table[(i, j)].set_facecolor('#f0f0f0')

                ax3.set_title(f'검출된 피크 정보 (상위 {min(len(peaks), 10)}개)',
                            fontsize=11, fontweight='bold', pad=10)

            # Panel 5: 통계 요약
            ax4 = fig.add_subplot(gs[3, 1])
            ax4.axis('off')

            stats_data = [
                ['총 피크 수', f"{len(peaks)}개"],
                ['데이터 포인트', f"{len(time)}개"],
                ['시간 범위', f"{time[0]:.2f} ~ {time[-1]:.2f} min"],
                ['강도 범위 (원본)', f"{np.min(intensity):.1f} ~ {np.max(intensity):.1f}"],
                ['강도 범위 (보정)', f"{np.min(corrected):.1f} ~ {np.max(corrected):.1f}"],
            ]

            if len(peaks) > 0:
                main_peak = peaks[0]
                stats_data.extend([
                    ['', ''],
                    ['[주 피크]', ''],
                    ['RT', f"{main_peak['rt']:.2f} min"],
                    ['높이', f"{main_peak['height']:.1f} mAU"],
                    ['면적', f"{main_peak['area']:.1f}"],
                    ['폭', f"{main_peak['width']:.4f} min"],
                ])

            stats_table = ax4.table(
                cellText=stats_data,
                cellLoc='left',
                loc='center',
                colWidths=[0.45, 0.55]
            )
            stats_table.auto_set_font_size(False)
            stats_table.set_fontsize(9)
            stats_table.scale(1, 1.8)

            # 주 피크 섹션 강조
            if len(peaks) > 0:
                stats_table[(6, 0)].set_facecolor('#4CAF50')
                stats_table[(6, 1)].set_facecolor('#4CAF50')
                stats_table[(6, 0)].set_text_props(weight='bold', color='white')

            ax4.set_title('샘플 통계', fontsize=11, fontweight='bold', pad=10)

            plt.suptitle(f'크로마토그램 분석: {sample_name}',
                        fontsize=14, fontweight='bold', y=0.995)

            # 저장
            output_file = output_dir / f'{sample_name}_chromatogram.png'
            plt.savefig(output_file, dpi=150, bbox_inches='tight')
            plt.close()

            saved_files.append(output_file)
            print(f"  저장: {sample_name}_chromatogram.png")

        print(f"\n총 {len(saved_files)}개 크로마토그램 생성 완료")
        print(f"저장 위치: {output_dir}/")

        return saved_files

    def create_overlay_chromatograms(self, output_dir):
        """유사한 샘플들의 크로마토그램 오버레이"""
        if not hasattr(self, 'sample_details') or len(self.sample_details) == 0:
            print("생성할 오버레이가 없습니다.")
            return []

        output_dir = Path(output_dir) / 'overlays'
        output_dir.mkdir(parents=True, exist_ok=True)

        # 유사한 샘플 스마트 그룹화
        import re
        groups = {}

        for sample in self.sample_details:
            sample_name = sample['name']

            # 다양한 패턴으로 그룹화 시도
            base_name = None

            # 패턴 1: 마지막 _숫자_ 또는 _숫자 제거 (예: _1_, _2_, _3_)
            match = re.search(r'(.+?)_\d+_?$', sample_name)
            if match:
                base_name = match.group(1)
            # 패턴 2: 마지막 숫자만 제거 (예: sample1, sample2)
            elif re.search(r'\d+$', sample_name):
                base_name = re.sub(r'\d+$', '', sample_name).rstrip('_')
            # 패턴 3: 그대로 사용 (그룹화 불가)
            else:
                base_name = sample_name

            if base_name not in groups:
                groups[base_name] = []
            groups[base_name].append(sample)

        # 2개 이상의 샘플이 있는 그룹만 오버레이
        saved_files = []

        print(f"\n{'='*80}")
        print("오버레이 크로마토그램 생성 중...")
        print(f"{'='*80}")

        for base_name, samples in groups.items():
            if len(samples) < 2:
                continue

            print(f"  그룹: {base_name} ({len(samples)}개 샘플)")

            # 피크가 있는 영역 감지 (모든 샘플의 피크 고려)
            xlim_min, xlim_max = None, None
            all_peak_times = []
            for sample in samples:
                if len(sample['peaks']) > 0:
                    for peak in sample['peaks']:
                        all_peak_times.append(sample['time'][peak['left_idx']])
                        all_peak_times.append(sample['time'][peak['right_idx']])

            if len(all_peak_times) > 0:
                time_span = samples[0]['time'][-1] - samples[0]['time'][0]
                margin = time_span * 0.05
                xlim_min = max(samples[0]['time'][0], min(all_peak_times) - margin)
                xlim_max = min(samples[0]['time'][-1], max(all_peak_times) + margin)

            # 4패널 레이아웃 (로그 스케일 추가)
            fig = plt.figure(figsize=(18, 12))
            gs = fig.add_gridspec(3, 2, hspace=0.35, wspace=0.3,
                                 left=0.06, right=0.97, top=0.93, bottom=0.05)

            # Panel 1: 원본 신호 오버레이 (선형) + Area 데이터 포인트
            ax1 = fig.add_subplot(gs[0, :])
            colors = plt.cm.tab10(np.linspace(0, 1, len(samples)))

            for i, (sample, color) in enumerate(zip(samples, colors), 1):
                time = sample['time']
                intensity = sample['intensity']
                peaks = sample['peaks']
                label = sample['name'].replace(base_name, '').strip('_') or f'#{i}'
                ax1.plot(time, intensity, linewidth=1.5, alpha=0.7,
                        color=color, label=label)

                # 모든 피크 위치에 area 값을 데이터 포인트로 표시
                for peak in peaks:
                    peak_idx = peak['index']
                    peak_rt = time[peak_idx]
                    peak_intensity = intensity[peak_idx]
                    area = peak['area']

                    # 데이터 포인트 표시
                    ax1.scatter(peak_rt, peak_intensity, s=80, color=color,
                              edgecolors='black', linewidths=1.5, zorder=10, alpha=0.9)

                    # Area 값 텍스트 표시 (작은 폰트)
                    ax1.annotate(f'{area:.0f}',
                               xy=(peak_rt, peak_intensity),
                               xytext=(0, 8), textcoords='offset points',
                               fontsize=7, color=color, fontweight='bold',
                               ha='center',
                               bbox=dict(boxstyle='round,pad=0.2', facecolor='white',
                                       edgecolor=color, alpha=0.7))

            ax1.set_xlabel('시간 (min)', fontsize=12, fontweight='bold')
            ax1.set_ylabel('강도 (mAU)', fontsize=12, fontweight='bold')
            ax1.set_title(f'원본 크로마토그램 오버레이 (시간대별 Area 표시): {base_name}',
                         fontsize=13, fontweight='bold')
            ax1.legend(fontsize=10, ncol=min(len(samples), 5), loc='upper left')
            ax1.grid(True, alpha=0.3)
            if xlim_min is not None:
                ax1.set_xlim(xlim_min, xlim_max)

            # Panel 2: 원본 신호 오버레이 (로그 스케일)
            ax1_log = fig.add_subplot(gs[1, :])

            for i, (sample, color) in enumerate(zip(samples, colors), 1):
                time = sample['time']
                intensity = sample['intensity']
                # 로그 스케일을 위해 양수 값으로 변환
                intensity_shifted = intensity - np.min(intensity) + 1
                label = sample['name'].replace(base_name, '').strip('_') or f'#{i}'
                ax1_log.plot(time, intensity_shifted, linewidth=1.5, alpha=0.7,
                           color=color, label=label)

            ax1_log.set_yscale('log')
            ax1_log.set_xlabel('시간 (min)', fontsize=12, fontweight='bold')
            ax1_log.set_ylabel('강도 (mAU, log scale)', fontsize=12, fontweight='bold')
            ax1_log.set_title(f'원본 크로마토그램 오버레이 (로그 스케일): {base_name}',
                            fontsize=13, fontweight='bold')
            ax1_log.legend(fontsize=10, ncol=min(len(samples), 5))
            ax1_log.grid(True, alpha=0.3, which='both')
            if xlim_min is not None:
                ax1_log.set_xlim(xlim_min, xlim_max)

            # Panel 3: 베이스라인 보정 후 오버레이
            ax2 = fig.add_subplot(gs[2, 0])

            for i, (sample, color) in enumerate(zip(samples, colors), 1):
                time = sample['time']
                corrected = sample['corrected']
                label = sample['name'].replace(base_name, '').strip('_') or f'#{i}'
                ax2.plot(time, corrected, linewidth=1.5, alpha=0.7,
                        color=color, label=label)

            ax2.axhline(0, color='black', linestyle='-', linewidth=0.5, alpha=0.5)
            ax2.set_xlabel('시간 (min)', fontsize=11, fontweight='bold')
            ax2.set_ylabel('강도 (mAU)', fontsize=11, fontweight='bold')
            ax2.set_title('보정 후 오버레이', fontsize=12, fontweight='bold')
            ax2.legend(fontsize=9, ncol=min(len(samples), 3))
            ax2.grid(True, alpha=0.3)
            if xlim_min is not None:
                ax2.set_xlim(xlim_min, xlim_max)

            # Panel 4: 주 피크 비교 테이블
            ax3 = fig.add_subplot(gs[2, 1])
            ax3.axis('off')

            table_data = []
            for i, sample in enumerate(samples, 1):
                peaks = sample['peaks']
                if len(peaks) > 0:
                    main_peak = peaks[0]
                    label = sample['name'].replace(base_name, '').strip('_') or f'#{i}'
                    table_data.append([
                        label,
                        f"{main_peak['rt']:.2f}",
                        f"{main_peak['height']:.1f}",
                        f"{main_peak['area']:.1f}",
                        f"{len(peaks)}"
                    ])

            if len(table_data) > 0:
                table = ax3.table(
                    cellText=table_data,
                    colLabels=['샘플', 'RT\n(min)', '높이\n(mAU)', '면적', '총\n피크수'],
                    cellLoc='center',
                    loc='center',
                    colWidths=[0.15, 0.15, 0.25, 0.25, 0.15]
                )
                table.auto_set_font_size(False)
                table.set_fontsize(10)
                table.scale(1, 2.5)

                # 헤더 스타일
                for i in range(5):
                    table[(0, i)].set_facecolor('#FF9800')
                    table[(0, i)].set_text_props(weight='bold', color='white')

                # 행 색상 교대
                for i in range(1, len(table_data) + 1):
                    for j in range(5):
                        if i % 2 == 0:
                            table[(i, j)].set_facecolor('#f0f0f0')

                ax3.set_title('주 피크 비교', fontsize=12, fontweight='bold', pad=10)

            plt.suptitle(f'반복 측정 비교: {base_name}',
                        fontsize=14, fontweight='bold')

            # 저장
            output_file = output_dir / f'{base_name}_overlay.png'
            plt.savefig(output_file, dpi=150, bbox_inches='tight')
            plt.close()

            saved_files.append(output_file)
            print(f"    저장: {base_name}_overlay.png")

        print(f"\n총 {len(saved_files)}개 오버레이 생성 완료")
        print(f"저장 위치: {output_dir}/")

        return saved_files


def main():
    """메인 함수"""
    import sys

    if len(sys.argv) > 1:
        folder_path = sys.argv[1]
    else:
        folder_path = str(Path(__file__).parent.parent / "results" / "DEF_LC 2025-05-19 17-57-25")

    print("\n" + "="*80)
    print("피크 면적 정량 분석")
    print("="*80)

    quantifier = PeakQuantifier()

    # 폴더 분석
    df = quantifier.analyze_folder(folder_path)

    if len(df) > 0:
        # 리포트 생성 (참조값 전달)
        output_dir = Path(folder_path) / 'quantification'
        reference_y0 = 2173.0209  # tag y0
        reference_a = 52004.0462   # tag a
        quantifier.create_summary_report(df, output_dir, reference_y0, reference_a)

        print(f"\n{'='*80}")
        print("분석 완료!")
        print(f"{'='*80}")
        print(f"결과 저장 위치: {output_dir}/")
    else:
        print("\n분석된 데이터가 없습니다.")


if __name__ == '__main__':
    main()
