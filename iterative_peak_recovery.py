"""
반복적 피크 복구 알고리즘
제거된 베이스라인에서 발견된 피크를 원본 신호에서 재확인하고 추가
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from scipy import signal
from scipy.integrate import trapezoid
import sys

sys.path.insert(0, str(Path(__file__).parent / 'src'))
from hybrid_baseline import HybridBaselineCorrector

# 한글 폰트 설정
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False


class IterativePeakRecovery:
    """반복적으로 누락된 피크를 복구하는 클래스"""

    def __init__(self, time, intensity):
        self.time = time
        self.original_intensity = intensity.copy()
        self.current_intensity = intensity.copy()

        # 음수 값 보존: 음수 피크 검출을 위해 자동 변환 제거
        # if np.min(self.current_intensity) < 0:
        #     self.current_intensity = self.current_intensity - np.min(self.current_intensity)
        #     self.original_intensity = self.current_intensity.copy()

        self.iterations = []

    def estimate_noise(self, intensity):
        """노이즈 수준 추정"""
        noise_region = np.percentile(intensity, 25)
        quiet_mask = intensity < noise_region * 1.5
        if np.any(quiet_mask):
            noise_std = np.std(intensity[quiet_mask])
        else:
            noise_std = np.std(intensity) * 0.1
        return max(noise_std, np.ptp(intensity) * 0.001)

    def detect_peaks(self, intensity, prominence_factor=0.005, height_factor=3):
        """
        양방향 피크 검출: 양수 피크와 음수 피크를 모두 검출
        """
        noise_level = self.estimate_noise(intensity)
        signal_range = np.ptp(intensity)

        min_prominence = max(signal_range * prominence_factor, noise_level * 3)
        min_height = noise_level * height_factor

        peak_info = []

        # 1. 양수 피크 검출 (기존 방식)
        positive_peaks, pos_properties = signal.find_peaks(
            intensity,
            prominence=min_prominence,
            height=min_height,
            width=3,
            distance=20
        )

        for i, peak_idx in enumerate(positive_peaks):
            # 피크 경계 찾기
            if 'left_bases' in pos_properties:
                left = pos_properties['left_bases'][i]
                right = pos_properties['right_bases'][i]
            else:
                left = max(0, peak_idx - 10)
                right = min(len(intensity) - 1, peak_idx + 10)

            # 면적 계산
            peak_time = self.time[left:right+1]
            peak_intensity = intensity[left:right+1]
            area = trapezoid(peak_intensity, peak_time)

            peak_info.append({
                'index': peak_idx,
                'rt': self.time[peak_idx],
                'height': intensity[peak_idx],
                'area': area,
                'prominence': pos_properties['prominences'][i] if 'prominences' in pos_properties else 0,
                'left': left,
                'right': right,
                'polarity': 'positive'  # 양수 피크 표시
            })

        # 2. 음수 피크 검출 (신호 반전)
        inverted_intensity = -intensity
        negative_peaks, neg_properties = signal.find_peaks(
            inverted_intensity,
            prominence=min_prominence,
            height=min_height,
            width=3,
            distance=20
        )

        for i, peak_idx in enumerate(negative_peaks):
            # 피크 경계 찾기
            if 'left_bases' in neg_properties:
                left = neg_properties['left_bases'][i]
                right = neg_properties['right_bases'][i]
            else:
                left = max(0, peak_idx - 10)
                right = min(len(intensity) - 1, peak_idx + 10)

            # 면적 계산 (음수이므로 절대값)
            peak_time = self.time[left:right+1]
            peak_intensity = intensity[left:right+1]
            area = abs(trapezoid(peak_intensity, peak_time))

            peak_info.append({
                'index': peak_idx,
                'rt': self.time[peak_idx],
                'height': intensity[peak_idx],  # 실제 음수 값
                'area': area,  # 절대값
                'prominence': neg_properties['prominences'][i] if 'prominences' in neg_properties else 0,
                'left': left,
                'right': right,
                'polarity': 'negative'  # 음수 피크 표시
            })

        # RT 순으로 정렬
        peak_info.sort(key=lambda p: p['rt'])
        all_peaks = np.array([p['index'] for p in peak_info])

        return all_peaks, peak_info

    def validate_candidate_peak(self, rt, original_intensity, corrected_intensity,
                               existing_peaks_rt, tolerance=0.15, debug=False):
        """후보 피크가 유효한지 원본 신호에서 검증"""

        # 이미 검출된 피크와 너무 가까우면 제외
        for existing_rt in existing_peaks_rt:
            if abs(rt - existing_rt) <= tolerance:
                if debug:
                    print(f"      [X] RT={rt:.2f}: 기존 피크({existing_rt:.2f})와 중복")
                return False, "기존 피크와 중복"

        # 원본 신호에서 해당 위치의 값 확인
        idx = np.argmin(np.abs(self.time - rt))
        window = slice(max(0, idx-15), min(len(self.time), idx+15))

        local_original = original_intensity[window]
        local_corrected = corrected_intensity[window]
        local_time = self.time[window]

        # 원본 신호에서 피크가 존재하는지 확인
        local_max_idx = np.argmax(local_original)
        local_max_rt = local_time[local_max_idx]
        local_max_height = local_original[local_max_idx]

        # RT가 근접하고, 원본에서 충분한 높이가 있는지 확인
        if abs(local_max_rt - rt) > 0.3:  # RT가 너무 다르면 거부 (0.2 -> 0.3 완화)
            if debug:
                print(f"      [X] RT={rt:.2f}: RT 불일치 (원본 최대={local_max_rt:.2f})")
            return False, "RT 불일치"

        # 노이즈 대비 충분한 신호인지 확인
        noise_level = self.estimate_noise(original_intensity)
        snr = local_max_height / noise_level if noise_level > 0 else float('inf')
        if snr < 3:  # SNR < 3 (5 -> 3 완화)
            if debug:
                print(f"      [X] RT={rt:.2f}: 신호가 약함 (SNR={snr:.1f})")
            return False, "신호가 약함"

        # 보정된 신호에서 억제된 정도 확인
        suppression_ratio = local_corrected[local_max_idx] / local_max_height if local_max_height > 0 else 0
        if suppression_ratio > 0.3:  # 30% 이상 남아있으면 이미 검출되었을 것 (0.5 -> 0.3 강화)
            if debug:
                print(f"      [X] RT={rt:.2f}: 이미 충분히 검출됨 (억제율={suppression_ratio:.1%})")
            return False, "이미 충분히 검출됨"

        # 원본 신호에서 실제 피크 모양을 확인 (양옆보다 높은지)
        if local_max_idx > 0 and local_max_idx < len(local_original) - 1:
            left_val = local_original[local_max_idx - 1]
            right_val = local_original[local_max_idx + 1]
            if local_max_height <= left_val or local_max_height <= right_val:
                if debug:
                    print(f"      [X] RT={rt:.2f}: 피크 모양이 아님")
                return False, "피크 모양이 아님"

        if debug:
            print(f"      [OK] RT={rt:.2f}: 유효 (H={local_max_height:.1f}, SNR={snr:.1f}, 억제={suppression_ratio:.1%})")

        return True, {
            'rt': local_max_rt,
            'index': idx,
            'height': local_max_height,
            'suppression_ratio': suppression_ratio,
            'snr': snr,
            'peak_idx': np.argmin(np.abs(self.time - local_max_rt))  # 정확한 인덱스 저장
        }

    def calculate_peak_area_from_original(self, peak_rt, baseline):
        """
        원본 신호에서 복구된 피크의 면적을 계산
        피크 영역에서는 직선 베이스라인을 사용 (양 끝 앵커포인트 연결)
        """
        # 피크 중심 찾기
        peak_idx = np.argmin(np.abs(self.time - peak_rt))

        # 피크 경계 찾기 (반치폭 기준)
        peak_height = self.original_intensity[peak_idx]
        baseline_at_peak = baseline[peak_idx]
        corrected_height = peak_height - baseline_at_peak
        half_height = baseline_at_peak + corrected_height / 2

        # 왼쪽 경계 찾기
        left_idx = peak_idx
        while left_idx > 0:
            if self.original_intensity[left_idx] < half_height:
                break
            left_idx -= 1

        # 오른쪽 경계 찾기
        right_idx = peak_idx
        while right_idx < len(self.original_intensity) - 1:
            if self.original_intensity[right_idx] < half_height:
                break
            right_idx += 1

        # 경계 확장 (피크 전체를 포함하도록)
        window_size = max(20, (right_idx - left_idx) // 2)
        left_idx = max(0, peak_idx - window_size)
        right_idx = min(len(self.original_intensity) - 1, peak_idx + window_size)

        # 피크 영역에서 직선 베이스라인 생성 (양 끝 앵커포인트 연결)
        baseline_left = baseline[left_idx]
        baseline_right = baseline[right_idx]

        # 직선 베이스라인 (음수 방지)
        baseline_left = max(0, baseline_left)
        baseline_right = max(0, baseline_right)

        linear_baseline = np.linspace(baseline_left, baseline_right, right_idx - left_idx + 1)

        # 원본 신호에서 면적 계산 (직선 베이스라인 위)
        peak_region_time = self.time[left_idx:right_idx+1]
        peak_region_signal = self.original_intensity[left_idx:right_idx+1]

        # 직선 베이스라인 위의 면적
        corrected_signal = peak_region_signal - linear_baseline
        corrected_signal = np.maximum(corrected_signal, 0)

        area = trapezoid(corrected_signal, peak_region_time)

        return {
            'area': area,
            'left_idx': left_idx,
            'right_idx': right_idx,
            'start_time': self.time[left_idx],
            'end_time': self.time[right_idx],
            'width': self.time[right_idx] - self.time[left_idx],
            'linear_baseline': linear_baseline  # 시각화용
        }

    def check_integration_overlap(self, recovered_peak, initial_main_peaks):
        """
        복구된 피크의 integration 영역이 기존 피크들의 integration 영역과 겹치는지 확인

        목적: 이미 integration된 영역에서는 복구하지 않음
              피크 검출은 잘 되고 있으므로, 정확한 면적 계산만 개선
        """
        rp_start = recovered_peak['start_time']
        rp_end = recovered_peak['end_time']

        for main_peak in initial_main_peaks:
            mp_start = main_peak.get('start_time', main_peak.get('rt_start', main_peak['rt'] - 0.1))
            mp_end = main_peak.get('end_time', main_peak.get('rt_end', main_peak['rt'] + 0.1))

            # Integration 영역 중첩 확인
            overlap = not (rp_end < mp_start or rp_start > mp_end)

            if overlap:
                # Integration 영역이 겹침 - 이미 적분된 영역
                overlap_start = max(rp_start, mp_start)
                overlap_end = min(rp_end, mp_end)
                overlap_ratio = (overlap_end - overlap_start) / (rp_end - rp_start)

                # 50% 이상 겹치면 거부
                if overlap_ratio > 0.5:
                    return True, main_peak, overlap_ratio

        return False, None, 0

    def merge_or_add_recovered_peak(self, recovered_peak, initial_main_peaks):
        """
        복구된 피크를 원래 메인 피크와 비교하여 병합 또는 추가 결정

        중요: Integration 영역이 겹치지 않는 경우에만 처리
               이미 다른 피크가 integration되고 있는 영역은 복구하지 않음
        """
        # 먼저 integration 영역 중첩 확인
        has_overlap, overlapped_peak, overlap_ratio = self.check_integration_overlap(
            recovered_peak, initial_main_peaks
        )

        if has_overlap:
            # Integration 영역이 겹침 - 이미 다른 피크가 적분 중
            return 'ignore', overlapped_peak, 0, f"Integration 영역 {overlap_ratio:.1%} 겹침"

        rp_rt = recovered_peak['rt']
        rp_area = recovered_peak['area']
        rp_start = recovered_peak['start_time']
        rp_end = recovered_peak['end_time']

        # RT만 확인 (integration 영역은 이미 확인했으므로)
        for main_peak in initial_main_peaks:
            mp_rt = main_peak['rt']
            mp_area = main_peak['area']

            # RT가 가까운지만 확인 (±0.2 min)
            if abs(rp_rt - mp_rt) <= 0.2:
                # 같은 피크로 간주 - 면적 비교
                if rp_area > mp_area:
                    # 복구된 피크의 면적이 더 크면 병합 (곡선 베이스라인 보정)
                    additional_area = rp_area - mp_area
                    return 'merge', main_peak, additional_area, "면적 증가"
                else:
                    # 복구된 피크의 면적이 작거나 같으면 무시
                    return 'ignore', main_peak, 0, "원래 피크가 더 큼"

        # 겹치지 않고 RT도 다르면 새로운 피크로 추가
        return 'add', None, rp_area, "새로운 피크"

    def recover_peaks_iterative(self, max_iterations=3):
        """반복적으로 피크 복구"""

        print(f"\n{'='*60}")
        print("반복적 피크 복구 시작")
        print(f"{'='*60}")

        # 첫 번째 반복에서 검출된 메인 피크 저장 (기준)
        initial_main_peaks = None
        all_recovered = []
        merged_peaks = []

        for iteration in range(max_iterations):
            print(f"\n[반복 {iteration + 1}/{max_iterations}]")

            # 현재 신호에 대해 베이스라인 보정
            # 피크 영역에 직선 베이스라인 적용 + robust vs weighted 비교
            corrector = HybridBaselineCorrector(self.time, self.current_intensity)
            baseline, best_params = corrector.optimize_baseline_with_linear_peaks()
            corrected = self.current_intensity - baseline
            # 음수 피크를 위해 음수 제거 제거
            # corrected = np.maximum(corrected, 0)

            # 메인 피크 검출
            main_peaks, main_peak_info = self.detect_peaks(corrected)
            print(f"  메인 피크 검출: {len(main_peaks)}개")

            # 베이스라인 방법 선택 정보 출력
            if 'selection_info' in best_params:
                info = best_params['selection_info']
                print(f"  베이스라인 선택: robust={info['robust_selected_count']}개, weighted={info['weighted_selected_count']}개")

            # 첫 번째 반복: 메인 피크를 기준으로 저장
            if initial_main_peaks is None:
                initial_main_peaks = main_peak_info.copy()
                print(f"  [기준] 첫 검출된 메인 피크: {len(initial_main_peaks)}개 (이후 비교 기준)")

            # 제거된 베이스라인에서 후보 찾기
            removed_baseline = self.current_intensity - corrected

            # 베이스라인 범위 기준으로 검출 (corrected 범위가 아닌)
            baseline_range = np.ptp(removed_baseline)
            baseline_noise = self.estimate_noise(removed_baseline)

            print(f"  베이스라인 범위: {baseline_range:.1f}, 노이즈: {baseline_noise:.1f}")

            # 매우 민감한 임계값
            min_prominence = max(baseline_range * 0.001, baseline_noise * 0.5)
            min_height = baseline_noise * 0.5

            baseline_peaks, properties = signal.find_peaks(
                removed_baseline,
                prominence=min_prominence,
                height=min_height,
                width=2,
                distance=10
            )

            baseline_peak_info = []
            for i, peak_idx in enumerate(baseline_peaks):
                baseline_peak_info.append({
                    'index': peak_idx,
                    'rt': self.time[peak_idx],
                    'height': removed_baseline[peak_idx],
                    'prominence': properties['prominences'][i] if 'prominences' in properties else 0
                })

            print(f"  베이스라인 피크 발견: {len(baseline_peaks)}개")

            # 기존에 검출된 모든 피크의 RT (새로 추가된 피크만)
            all_existing_rt = [p['rt'] for p in all_recovered]

            # 후보 피크 검증
            recovered_this_iter = []
            print(f"  후보 피크 검증 중...")
            for bp in baseline_peak_info:
                is_valid, result = self.validate_candidate_peak(
                    bp['rt'],
                    self.original_intensity,
                    corrected,
                    all_existing_rt,
                    tolerance=0.15,
                    debug=False  # 디버그 모드 비활성화 (출력 줄이기)
                )

                if is_valid:
                    # 원본 신호에서 면적 계산
                    area_info = self.calculate_peak_area_from_original(result['rt'], baseline)
                    result.update(area_info)

                    # 첫 번째 반복 이후: 병합 또는 추가 결정
                    if iteration > 0:
                        action, matched_peak, additional_area, reason = self.merge_or_add_recovered_peak(
                            result, initial_main_peaks
                        )

                        if action == 'merge':
                            print(f"    [병합] RT={result['rt']:.2f}, 원래면적={matched_peak['area']:.1f}, "
                                  f"복구면적={result['area']:.1f}, 추가면적={additional_area:.1f}")
                            merged_peaks.append({
                                'original_peak': matched_peak,
                                'recovered_peak': result,
                                'additional_area': additional_area
                            })
                            recovered_this_iter.append(result)
                        elif action == 'add':
                            print(f"    [추가] RT={result['rt']:.2f}, H={result['height']:.1f}, "
                                  f"면적={result['area']:.1f}, SNR={result['snr']:.1f}")
                            recovered_this_iter.append(result)
                        else:  # ignore
                            if matched_peak:
                                print(f"    [무시] RT={result['rt']:.2f}, 면적={result['area']:.1f} "
                                      f"({reason}: 피크 {matched_peak['rt']:.2f})")
                            else:
                                print(f"    [무시] RT={result['rt']:.2f}, 면적={result['area']:.1f} ({reason})")
                    else:
                        # 첫 번째 반복: integration 영역만 확인
                        has_overlap, overlapped_peak, overlap_ratio = self.check_integration_overlap(
                            result, initial_main_peaks
                        )

                        if has_overlap:
                            print(f"    [무시] RT={result['rt']:.2f}, 면적={result['area']:.1f} "
                                  f"(Integration 영역 {overlap_ratio:.1%} 겹침: 피크 {overlapped_peak['rt']:.2f})")
                        else:
                            print(f"    [추가] RT={result['rt']:.2f}, H={result['height']:.1f}, "
                                  f"면적={result['area']:.1f}, SNR={result['snr']:.1f}")
                            recovered_this_iter.append(result)

            print(f"  이번 반복에서 복구/병합: {len(recovered_this_iter)}개")
            all_recovered.extend(recovered_this_iter)

            # 이번 반복 결과 저장
            iteration_data = {
                'iteration': iteration + 1,
                'baseline': baseline,
                'corrected': corrected.copy(),
                'removed_baseline': removed_baseline,
                'main_peaks': main_peak_info,
                'recovered_peaks': recovered_this_iter,
                'baseline_method': best_params.get('method', 'unknown')
            }
            self.iterations.append(iteration_data)

            # 종료 조건: 더 이상 복구할 피크가 없으면
            if len(recovered_this_iter) == 0:
                print(f"  더 이상 복구할 피크가 없음. 종료.")
                break

            # 다음 반복을 위해: 복구된 피크 위치의 베이스라인을 낮춤
            # (너무 공격적인 베이스라인 보정 완화)
            for rp in recovered_this_iter:
                idx = rp['peak_idx']
                window = slice(max(0, idx-20), min(len(self.time), idx+20))
                # 해당 영역의 베이스라인을 50% 줄임
                self.current_intensity[window] = self.current_intensity[window] - baseline[window] * 0.5

        print(f"\n{'='*60}")
        print(f"복구 완료 요약:")
        print(f"  첫 검출 메인 피크: {len(initial_main_peaks)}개")
        print(f"  새로 추가된 피크: {len([r for r in all_recovered if r not in merged_peaks])}개")
        print(f"  병합된 피크: {len(merged_peaks)}개")
        print(f"  총 복구/병합: {len(all_recovered)}개")
        print(f"{'='*60}\n")

        return {
            'initial_peaks': initial_main_peaks,
            'recovered_peaks': all_recovered,
            'merged_peaks': merged_peaks
        }

    def visualize_recovery(self, output_file):
        """복구 과정 시각화"""

        n_iterations = len(self.iterations)

        # 동적으로 행 수 결정 (최대 3개 반복까지 표시)
        n_rows = min(n_iterations, 3)

        fig = plt.figure(figsize=(18, 6 * n_rows))

        for idx, iter_data in enumerate(self.iterations[:3]):  # 최대 3개만 표시
            iteration = iter_data['iteration']

            # 각 반복마다 3개 패널
            base_idx = idx * 3

            # Panel 1: 원본 + 베이스라인 비교 (더 명확하게)
            ax1 = plt.subplot(n_rows, 3, base_idx + 1)

            # 원본 신호 (파란색)
            ax1.plot(self.time, self.original_intensity, 'b-', linewidth=1.5, alpha=0.8, label='원본 신호', zorder=1)

            # 베이스라인 (검은 점선, 더 두껍게)
            ax1.plot(self.time, iter_data['baseline'], 'k--', linewidth=2.5, alpha=0.9, label='베이스라인', zorder=3)

            # 베이스라인 아래 영역을 회색으로
            ax1.fill_between(self.time, 0, iter_data['baseline'],
                           alpha=0.2, color='gray', label='제거될 영역', zorder=0)

            # 메인 피크 표시 (초록)
            for i, peak in enumerate(iter_data['main_peaks'][:8]):  # 최대 8개만
                ax1.plot(peak['rt'], iter_data['corrected'][peak['index']], 'go',
                        markersize=8, markeredgecolor='darkgreen', markeredgewidth=1.5,
                        label='메인 피크' if i == 0 else '', zorder=4)

            ax1.set_xlabel('시간 (min)', fontsize=11, fontweight='bold')
            ax1.set_ylabel('강도', fontsize=11, fontweight='bold')
            ax1.set_title(f'반복 {iteration}: 베이스라인 설정 ({iter_data["baseline_method"]})',
                        fontsize=12, fontweight='bold')
            ax1.legend(fontsize=9, loc='upper right')
            ax1.grid(True, alpha=0.3)

            # Panel 2: 제거된 베이스라인 + 복구된 피크
            ax2 = plt.subplot(n_rows, 3, base_idx + 2)
            ax2.plot(self.time, iter_data['removed_baseline'], 'gray', linewidth=1, alpha=0.5, label='제거된 베이스라인')

            # 복구된 피크 표시
            for rp in iter_data['recovered_peaks']:
                ax2.plot(rp['rt'], iter_data['removed_baseline'][rp['index']],
                        'r^', markersize=10, label='복구된 피크' if rp == iter_data['recovered_peaks'][0] else '')
                # 복구된 피크에 라벨 추가
                ax2.annotate(f"RT:{rp['rt']:.2f}\nA:{rp['area']:.0f}",
                           xy=(rp['rt'], iter_data['removed_baseline'][rp['index']]),
                           xytext=(0, 20), textcoords='offset points',
                           ha='center', fontsize=7,
                           bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7),
                           arrowprops=dict(arrowstyle='->', lw=1))

            ax2.set_xlabel('시간 (min)', fontsize=10)
            ax2.set_ylabel('강도', fontsize=10)
            ax2.set_title(f'반복 {iteration}: 복구된 피크 ({len(iter_data["recovered_peaks"])}개)', fontsize=11, fontweight='bold')
            ax2.legend(fontsize=9)
            ax2.grid(True, alpha=0.3)

            # Panel 3: 원본 + 베이스라인 + 복구된 피크 영역 (더 명확하게)
            ax3 = plt.subplot(n_rows, 3, base_idx + 3)

            # 원본 신호
            ax3.plot(self.time, self.original_intensity, 'b-', linewidth=1.5, alpha=0.7, label='원본 신호', zorder=1)

            # 베이스라인 (더 두껍고 명확하게)
            ax3.plot(self.time, iter_data['baseline'], 'k--', linewidth=2, alpha=0.8, label='베이스라인', zorder=2)

            # 복구된 피크 영역만 강조 (먼저 그려서 뒤에 배치)
            for rp in iter_data['recovered_peaks']:
                left_idx = rp['left_idx']
                right_idx = rp['right_idx']
                peak_region_time = self.time[left_idx:right_idx+1]
                peak_region_signal = self.original_intensity[left_idx:right_idx+1]

                # 직선 베이스라인 사용 (양 끝 연결)
                if 'linear_baseline' in rp:
                    peak_region_baseline = rp['linear_baseline']
                else:
                    # 이전 버전 호환성
                    peak_region_baseline = iter_data['baseline'][left_idx:right_idx+1]

                # 직선 베이스라인을 파란 점선으로 표시
                ax3.plot(peak_region_time, peak_region_baseline, 'b--', linewidth=2, alpha=0.7,
                        label='직선 베이스라인' if rp == iter_data['recovered_peaks'][0] else '', zorder=2)

                # 베이스라인 위 면적을 진한 빨강으로
                ax3.fill_between(peak_region_time, peak_region_baseline, peak_region_signal,
                               alpha=0.5, color='red', edgecolor='darkred', linewidth=1.5,
                               label='복구된 피크 면적' if rp == iter_data['recovered_peaks'][0] else '', zorder=3)

            # 복구된 피크 정점 표시
            for rp in iter_data['recovered_peaks']:
                ax3.plot(rp['rt'], rp['height'], 'r^', markersize=14,
                        markeredgecolor='darkred', markeredgewidth=2, zorder=5)

                # 라벨 (배경 더 진하게)
                ax3.annotate(f"RT:{rp['rt']:.2f}\n면적:{rp['area']:.0f}",
                           xy=(rp['rt'], rp['height']),
                           xytext=(0, 20), textcoords='offset points',
                           ha='center', fontsize=9, fontweight='bold',
                           bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow',
                                   edgecolor='red', linewidth=2, alpha=0.9),
                           arrowprops=dict(arrowstyle='->', lw=2, color='red'),
                           zorder=6)

            # 메인 피크도 표시 (작게)
            for i, peak in enumerate(iter_data['main_peaks'][:5]):  # 처음 5개만
                idx = np.argmin(np.abs(self.time - peak['rt']))
                ax3.plot(peak['rt'], self.original_intensity[idx], 'go', markersize=6, alpha=0.5,
                        label='메인 피크' if i == 0 else '', zorder=4)

            ax3.set_xlabel('시간 (min)', fontsize=11, fontweight='bold')
            ax3.set_ylabel('강도', fontsize=11, fontweight='bold')
            ax3.set_title(f'반복 {iteration}: 원본에서 복구된 피크 영역 (빨강)', fontsize=12, fontweight='bold')
            ax3.legend(fontsize=9, loc='upper right')
            ax3.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        print(f"  시각화 저장: {output_file.name}")
        plt.close()


def analyze_with_recovery(csv_file, output_dir):
    """피크 복구를 포함한 분석"""

    # CSV 파일 읽기
    df = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
    time = df[0].values
    intensity = df[1].values

    sample_name = Path(csv_file).stem

    print(f"\n{'='*80}")
    print(f"샘플: {sample_name}")
    print(f"{'='*80}")

    # 반복적 피크 복구
    recovery = IterativePeakRecovery(time, intensity)
    result = recovery.recover_peaks_iterative(max_iterations=3)

    # 결과 추출
    initial_peaks = result['initial_peaks']
    recovered_peaks = result['recovered_peaks']
    merged_peaks = result['merged_peaks']

    # 최종 결과 계산
    num_added = len([r for r in recovered_peaks if not any(m['recovered_peak'] == r for m in merged_peaks)])
    num_merged = len(merged_peaks)
    total_peaks = len(initial_peaks) + num_added

    print(f"\n{'='*60}")
    print(f"최종 결과:")
    print(f"  첫 검출 메인 피크: {len(initial_peaks)}개")
    print(f"  새로 추가된 피크: {num_added}개")
    print(f"  병합된 피크: {num_merged}개")
    print(f"  최종 총 피크: {total_peaks}개")
    print(f"{'='*60}")

    # 병합된 피크 상세 정보
    if merged_peaks:
        print(f"\n병합된 피크 (곡선 베이스라인 보정):")
        for i, mp in enumerate(merged_peaks, 1):
            orig = mp['original_peak']
            recov = mp['recovered_peak']
            add_area = mp['additional_area']
            print(f"    {i}. RT={orig['rt']:.2f} → {recov['rt']:.2f}, "
                  f"원래면적={orig['area']:.1f}, 복구면적={recov['area']:.1f}, "
                  f"추가면적={add_area:.1f} (+{add_area/orig['area']*100:.1f}%)")

    # 새로 추가된 피크 상세 정보
    added_peaks = [r for r in recovered_peaks if not any(m['recovered_peak'] == r for m in merged_peaks)]
    if added_peaks:
        print(f"\n새로 추가된 피크:")
        for i, rp in enumerate(added_peaks, 1):
            print(f"    {i}. RT={rp['rt']:.2f} min, 높이={rp['height']:.1f}, "
                  f"면적={rp['area']:.1f}, 폭={rp['width']:.3f} min")

    # 시각화
    output_file = output_dir / f'{sample_name}_peak_recovery.png'
    recovery.visualize_recovery(output_file)

    return {
        'sample': sample_name,
        'initial_peaks': len(initial_peaks),
        'added_peaks': num_added,
        'merged_peaks': num_merged,
        'total_peaks': total_peaks
    }


if __name__ == '__main__':
    # 출력 디렉토리
    output_dir = Path('result/peak_recovery')
    output_dir.mkdir(parents=True, exist_ok=True)

    # 분석할 샘플 선택
    csv_dir = Path('exported_signals')
    csv_files = sorted(csv_dir.glob('*.csv'))

    # 처음 10개 샘플로 테스트
    selected_files = list(csv_files[:10])

    print("\n" + "="*80)
    print("반복적 피크 복구 분석")
    print("="*80)
    print(f"총 {len(selected_files)}개 샘플 분석\n")

    results = []
    for csv_file in selected_files:
        result = analyze_with_recovery(csv_file, output_dir)
        results.append(result)

    # 전체 요약
    print("\n" + "="*80)
    print("전체 분석 요약")
    print("="*80)
    for r in results:
        print(f"\n{r['sample']}")
        print(f"  첫 검출: {r['initial_peaks']}개")
        print(f"  추가: {r['added_peaks']}개")
        print(f"  병합: {r['merged_peaks']}개")
        print(f"  최종: {r['total_peaks']}개")
        improvement = (r['added_peaks'] / r['initial_peaks'] * 100) if r['initial_peaks'] > 0 else 0
        print(f"  개선율: +{improvement:.1f}%")

    print(f"\n모든 이미지 저장: {output_dir}/")
