"""
Batch LC Quantification for Cofactor M2 Main Experiment
========================================================
260216_cofactor_m2_main_new 폴더의 모든 .D 폴더에서 RID1A.ch 파일을 읽고
피크를 검출하여 정량 분석 결과를 출력합니다.

실험 조건:
- Column: Aminex HPX-87H
- Detector: RID (Refractive Index), unit: nRIU
- Eluent: 5 mM H2SO4
- Flow rate: 0.5 mL/min
- Run time: ~17 min
- Injection volume: 20 µL

샘플 명명 규칙:
260212_M1_0_1_M2_COFACTOR_{D1-D5}_{RO|RS}_GO_{1-3}_{6H|12H|24H}
- D1-D5: cofactor 조건
- RO/RS: 두 가지 효소/균주 조건
- GO: galactitol oxidase
- 1-3: triplicate
- 6H/12H/24H: 반응 시간
- NC_GO: negative control
"""

import sys
import re
import numpy as np
import pandas as pd
from pathlib import Path
from scipy import signal
from scipy.integrate import trapezoid
from rainbow.agilent.chemstation import parse_ch


def read_rid_data(ch_path):
    """rainbow 라이브러리로 RID .ch 파일 읽기"""
    result = parse_ch(str(ch_path))
    if result is None:
        raise ValueError(f"Cannot parse: {ch_path}")
    time = result.xlabels  # minutes
    intensity = result.data.flatten()  # nRIU
    metadata = result.metadata
    return time, intensity, metadata


def estimate_noise(intensity):
    """MAD 기반 noise 추정 (derivative 이용)"""
    derivative = np.diff(intensity)
    mad = np.median(np.abs(derivative - np.median(derivative)))
    noise_std = mad * 1.4826
    return max(noise_std, 0.1)


def detect_peaks(time, intensity):
    """적응형 피크 검출 및 면적 계산"""
    noise_level = estimate_noise(intensity)
    signal_range = np.ptp(intensity)

    # Major peaks: 신호 범위 기반
    major_prominence = max(signal_range * 0.005, noise_level * 5)
    major_peaks, major_props = signal.find_peaks(
        intensity,
        prominence=major_prominence,
        height=noise_level * 5,
        width=3,
        distance=20
    )

    # Minor peaks: noise 기반
    minor_prominence = max(noise_level * 3, signal_range * 0.001)
    minor_peaks, minor_props = signal.find_peaks(
        intensity,
        prominence=minor_prominence,
        height=noise_level * 3,
        width=2,
        distance=10
    )

    # Merge & deduplicate
    all_peaks = list(major_peaks)
    all_prominences = list(major_props['prominences'])
    min_dist = 10

    for i, mp in enumerate(minor_peaks):
        if not any(abs(mp - majp) < min_dist for majp in major_peaks):
            all_peaks.append(mp)
            all_prominences.append(minor_props['prominences'][i])

    if not all_peaks:
        return []

    sort_idx = np.argsort(all_peaks)
    peaks = np.array(all_peaks)[sort_idx]
    prominences = np.array(all_prominences)[sort_idx]

    # 피크별 면적 계산
    peak_data = []
    for i, peak_idx in enumerate(peaks):
        peak_height = intensity[peak_idx]

        # 경계: 피크 높이의 1% 또는 noise의 50% 중 큰 값
        threshold = max(peak_height * 0.01, noise_level * 0.5)

        # 왼쪽 경계
        left = peak_idx
        while left > 0 and intensity[left] > threshold:
            left -= 1

        # 오른쪽 경계
        right = peak_idx
        while right < len(intensity) - 1 and intensity[right] > threshold:
            right += 1

        # Valley detection: 인접 피크 간 최소점
        if i < len(peaks) - 1:
            region = intensity[peak_idx:peaks[i+1]]
            if len(region) > 0:
                right = min(right, peak_idx + np.argmin(region))

        if i > 0:
            region = intensity[peaks[i-1]:peak_idx]
            if len(region) > 0:
                left = max(left, peaks[i-1] + np.argmin(region))

        # 최대 폭 2분
        dt = np.mean(np.diff(time))
        max_w = int(2.0 / dt) if dt > 0 else 1000
        if right - left > max_w:
            half = max_w // 2
            left = max(0, peak_idx - half)
            right = min(len(intensity) - 1, peak_idx + half)

        left = max(0, left)
        right = min(len(intensity) - 1, right)

        # 면적 (nRIU·s)
        peak_time_sec = time[left:right+1] * 60
        peak_signal = intensity[left:right+1]
        area = trapezoid(np.maximum(peak_signal, 0), peak_time_sec)

        peak_data.append({
            'peak_number': i + 1,
            'rt_min': round(time[peak_idx], 3),
            'height_nRIU': round(peak_height, 1),
            'area_nRIUs': round(area, 1),
            'width_min': round(time[right] - time[left], 4),
            'prominence': round(prominences[i], 1),
            'snr': round(peak_height / noise_level, 1) if noise_level > 0 else 0,
            'start_min': round(time[left], 3),
            'end_min': round(time[right], 3),
        })

    # RT순 정렬
    peak_data.sort(key=lambda p: p['rt_min'])

    return peak_data


def parse_sample_name(folder_name):
    """샘플 폴더명에서 실험 조건 추출"""
    info = {
        'folder': folder_name,
        'cofactor_dose': '',
        'enzyme': '',
        'replicate': '',
        'time_h': '',
        'is_nc': False,
    }

    # NC (negative control)
    if 'NC_GO' in folder_name:
        info['is_nc'] = True
        info['cofactor_dose'] = 'NC'
        info['enzyme'] = 'NC'
        return info

    # D1-D5
    d_match = re.search(r'_(D\d+)_', folder_name)
    if d_match:
        info['cofactor_dose'] = d_match.group(1)

    # RO or RS
    enz_match = re.search(r'_(RO|RS)_', folder_name)
    if enz_match:
        info['enzyme'] = enz_match.group(1)

    # Replicate (GO_1, GO_2, GO_3)
    rep_match = re.search(r'GO_(\d+)_', folder_name)
    if rep_match:
        info['replicate'] = rep_match.group(1)

    # Time point
    time_match = re.search(r'_(\d+H)\.D$', folder_name, re.IGNORECASE)
    if time_match:
        info['time_h'] = time_match.group(1)

    return info


def main():
    data_dir = Path(r"C:\Chem32\1\DATA\260216_cofactor_m2_main_new")
    output_dir = data_dir / "quantification_results"
    output_dir.mkdir(parents=True, exist_ok=True)

    d_folders = sorted([d for d in data_dir.iterdir() if d.is_dir() and d.suffix.upper() == '.D'])
    print(f"총 {len(d_folders)}개 .D 폴더 발견\n")

    all_results = []
    errors = []

    for idx, d_folder in enumerate(d_folders, 1):
        ch_file = d_folder / "RID1A.ch"
        if not ch_file.exists():
            errors.append(f"[SKIP] {d_folder.name}: RID1A.ch 없음")
            continue

        sample_info = parse_sample_name(d_folder.name)
        label = f"[{idx}/{len(d_folders)}]"

        try:
            time, intensity, metadata = read_rid_data(ch_file)

            # 피크 검출
            peaks = detect_peaks(time, intensity)

            n_peaks = len(peaks)
            print(f"{label} {d_folder.name}: {n_peaks}개 피크", end='')
            if n_peaks > 0:
                main_pk = max(peaks, key=lambda p: p['area_nRIUs'])
                print(f" | 주 피크 RT={main_pk['rt_min']:.2f}min, H={main_pk['height_nRIU']:.0f}nRIU, A={main_pk['area_nRIUs']:.0f}")
            else:
                print()

            # 결과 저장
            for pk in peaks:
                row = {
                    'sample': d_folder.name.replace('.D', ''),
                    'cofactor_dose': sample_info['cofactor_dose'],
                    'enzyme': sample_info['enzyme'],
                    'replicate': sample_info['replicate'],
                    'time_h': sample_info['time_h'],
                    'is_nc': sample_info['is_nc'],
                }
                row.update(pk)
                all_results.append(row)

        except Exception as e:
            err_msg = f"{label} {d_folder.name}: {e}"
            print(f"  [ERROR] {err_msg}")
            errors.append(err_msg)

    if not all_results:
        print("\n분석된 결과가 없습니다.")
        return

    df = pd.DataFrame(all_results)

    # ========================
    # 1. 전체 피크 상세 결과
    # ========================
    detail_file = output_dir / "all_peaks_detailed.csv"
    df.to_csv(detail_file, index=False, encoding='utf-8-sig')
    print(f"\n전체 피크 상세 결과: {detail_file}")

    # ========================
    # 2. 샘플별 주 피크 요약 (면적 최대 피크)
    # ========================
    main_peaks = df.loc[df.groupby('sample')['area_nRIUs'].idxmax()].copy()
    main_peaks = main_peaks.sort_values(['cofactor_dose', 'enzyme', 'time_h', 'replicate'])
    summary_file = output_dir / "main_peak_summary.csv"
    main_peaks.to_csv(summary_file, index=False, encoding='utf-8-sig')
    print(f"주 피크 요약: {summary_file}")

    # ========================
    # 3. RT별 피크 그룹 식별
    # ========================
    df_sorted = df.sort_values('rt_min')
    rt_groups = []
    current_group = []
    current_rt = None

    for _, row in df_sorted.iterrows():
        if current_rt is None or abs(row['rt_min'] - current_rt) <= 0.3:
            current_group.append(row.to_dict())
            current_rt = np.mean([r['rt_min'] for r in current_group])
        else:
            rt_groups.append(current_group)
            current_group = [row.to_dict()]
            current_rt = row['rt_min']
    if current_group:
        rt_groups.append(current_group)

    print(f"\nRT 기준 피크 그룹: {len(rt_groups)}개")
    print(f"{'그룹':>4} {'RT범위':>20} {'평균RT':>8} {'#샘플':>6} {'평균H':>12} {'평균Area':>14}")
    print("-" * 70)
    for i, group in enumerate(rt_groups, 1):
        rts = [r['rt_min'] for r in group]
        heights = [r['height_nRIU'] for r in group]
        areas = [r['area_nRIUs'] for r in group]
        print(f"{i:>4} {min(rts):>7.2f}-{max(rts):.2f}min {np.mean(rts):>8.2f} {len(group):>6} {np.mean(heights):>12.1f} {np.mean(areas):>14.1f}")

    # ========================
    # 4. Excel 종합 결과
    # ========================
    excel_file = output_dir / "cofactor_m2_quantification.xlsx"
    with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='All_Peaks', index=False)
        main_peaks.to_excel(writer, sheet_name='Main_Peaks', index=False)

        # 조건별 pivot (NC 제외)
        non_nc = main_peaks[~main_peaks['is_nc']].copy()
        if len(non_nc) > 0:
            # Area pivot
            pivot_area = non_nc.pivot_table(
                values='area_nRIUs',
                index=['cofactor_dose', 'enzyme'],
                columns='time_h',
                aggfunc=['mean', 'std', 'count']
            )
            pivot_area.to_excel(writer, sheet_name='Pivot_Area')

            # Height pivot
            pivot_height = non_nc.pivot_table(
                values='height_nRIU',
                index=['cofactor_dose', 'enzyme'],
                columns='time_h',
                aggfunc=['mean', 'std']
            )
            pivot_height.to_excel(writer, sheet_name='Pivot_Height')

            # RT pivot
            pivot_rt = non_nc.pivot_table(
                values='rt_min',
                index=['cofactor_dose', 'enzyme'],
                columns='time_h',
                aggfunc='mean'
            )
            pivot_rt.to_excel(writer, sheet_name='Pivot_RT')

        # RT groups
        group_rows = []
        for i, group in enumerate(rt_groups, 1):
            rts = [r['rt_min'] for r in group]
            areas = [r['area_nRIUs'] for r in group]
            heights = [r['height_nRIU'] for r in group]
            group_rows.append({
                'group': i,
                'rt_mean': round(np.mean(rts), 3),
                'rt_min': round(min(rts), 3),
                'rt_max': round(max(rts), 3),
                'n_detections': len(group),
                'height_mean': round(np.mean(heights), 1),
                'area_mean': round(np.mean(areas), 1),
                'area_std': round(np.std(areas), 1) if len(areas) > 1 else 0,
            })
        pd.DataFrame(group_rows).to_excel(writer, sheet_name='RT_Groups', index=False)

        if errors:
            pd.DataFrame({'error': errors}).to_excel(writer, sheet_name='Errors', index=False)

    print(f"\nExcel: {excel_file}")

    # ========================
    # 5. 콘솔 요약
    # ========================
    print(f"\n{'='*70}")
    print("분석 완료 요약")
    print(f"{'='*70}")
    print(f"총 샘플: {len(d_folders)}")
    print(f"성공: {df['sample'].nunique()}")
    print(f"에러: {len(errors)}")
    print(f"전체 피크: {len(df)}")
    print(f"샘플당 평균 피크: {len(df) / df['sample'].nunique():.1f}")
    print(f"\n결과 위치: {output_dir}")

    if errors:
        print(f"\n에러:")
        for e in errors:
            print(f"  {e}")


if __name__ == '__main__':
    main()
