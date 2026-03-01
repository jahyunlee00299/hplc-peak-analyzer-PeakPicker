r"""
Xul 5P Pretest 재정량 — Half-peak 적분 + 올바른 RT
===================================================
이전 정량의 문제점:
1. RT bin이 완전히 틀림 (Xyl: 9.3-10.5 → 실제 11.07-11.31)
2. Half-peak 적분 미적용 (Xyl/Xul co-elution ΔRT ~0.6 min)

올바른 방법 (Asana "HPX-87H Retention Time" 태스크 기준):
- Xyl RT: ~11.2 min → LEFT half-peak × 2
- Xul RT: ~11.8 min → RIGHT half-peak × 2
- AcO/AcP RT: ~17.3 min
- Standard curves (230221, full peak, pure compound):
  Xyl: a=22786.19, y0=207.54 (mg/mL basis)
  Xul: a=23465.27, y0=-59.45 (mg/mL basis)
  AcO: a=8708, y0=-901.6 (mM basis)
- Dilution factor: 15x
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import numpy as np
import pandas as pd
from pathlib import Path
from scipy.integrate import trapezoid
from scipy.signal import find_peaks
from scipy.ndimage import minimum_filter1d, uniform_filter1d
import warnings
warnings.filterwarnings('ignore')

from chemstation_parser import ChemstationParser

# ============================================================
#  설정
# ============================================================
DATA_ROOT = Path(r'C:\Chem32\1\DATA\2. D-Xyl cascade HPLC\Xul 5P production\Pretest')
OUTPUT_DIR = Path(__file__).parent / 'result' / 'pretest_analysis'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Standard curves (230221_HPx-87H_Xyl_Xul_Rib.xlsx)
# 개별 pure compound 주입, full peak area 기반
STD = {
    'Xyl': {'slope': 22786.1903, 'intercept': 207.5383, 'unit': 'mg/mL',
            'MW': 150.13},  # D-Xylose
    'Xul': {'slope': 23465.2695, 'intercept': -59.4471, 'unit': 'mg/mL',
            'MW': 150.13},  # D-Xylulose
    'AcO': {'slope': 8708, 'intercept': -901.6, 'unit': 'mM'},  # Acetate
}

DILUTION_FACTOR = 15

# RT ranges (Asana "HPX-87H Retention Time" + peak_identification.json)
# early batch (260106~260115): Xyl 11.28-11.31, Xul 11.91-11.96
# late batch  (260212~260225): Xyl 11.07-11.10, Xul 11.64-11.67
# → 전체 범위로 peak search
XYL_RT_RANGE = (10.9, 11.5)   # Xylose 피크 탐색 범위
XUL_RT_RANGE = (11.5, 12.1)   # Xylulose 피크 탐색 범위
ACO_RT_RANGE = (16.8, 17.8)   # Acetate 피크 탐색 범위


def rolling_min_baseline(intensity, window_frac=0.15):
    """Rolling-minimum 기반 베이스라인 추정"""
    win = max(int(len(intensity) * window_frac), 50)
    base = minimum_filter1d(intensity, size=win)
    base = uniform_filter1d(base, size=win * 2)
    return base


def find_peak_in_range(time, corrected, rt_start, rt_end, min_height=30):
    """주어진 RT 범위에서 가장 큰 피크의 인덱스 반환"""
    mask = (time >= rt_start) & (time <= rt_end)
    if mask.sum() < 5:
        return None

    indices = np.where(mask)[0]
    region = corrected[indices]

    peaks, props = find_peaks(region, height=min_height, distance=5)
    if len(peaks) == 0:
        # no peak found — check if there's any significant signal
        max_idx = np.argmax(region)
        if region[max_idx] > min_height:
            return indices[max_idx]
        return None

    # 가장 높은 피크 선택
    best = peaks[np.argmax(props['peak_heights'])]
    return indices[best]


def half_peak_area(time, corrected, apex_idx, side='left'):
    """
    Half-peak 적분: apex에서 수직으로 자르고 한쪽만 적분 후 ×2

    Parameters
    ----------
    side : 'left' or 'right'
        'left': apex 기준 왼쪽 절반 적분 (Xyl용 — 오른쪽은 Xul과 겹침)
        'right': apex 기준 오른쪽 절반 적분 (Xul용 — 왼쪽은 Xyl과 겹침)

    Returns
    -------
    area : float
        half_area × 2 (full peak area 근사값, Chemstation area 단위와 동일)
    half_area : float
        실제 half peak area
    boundary : tuple (start_idx, end_idx)
    """
    apex_h = corrected[apex_idx]
    thr = apex_h * 0.02  # 2% threshold for peak boundary

    if side == 'left':
        # 왼쪽으로 경계 탐색
        left = apex_idx
        while left > 0 and corrected[left] > thr:
            left -= 1

        # 적분 구간: left ~ apex (포함)
        t_sec = time[left:apex_idx + 1] * 60  # min → sec (Chemstation area 단위)
        sig = corrected[left:apex_idx + 1]
        half_area = trapezoid(sig, t_sec)
        return half_area * 2, half_area, (left, apex_idx)

    else:  # right
        # 오른쪽으로 경계 탐색
        right = apex_idx
        while right < len(corrected) - 1 and corrected[right] > thr:
            right += 1

        # 적분 구간: apex ~ right (포함)
        t_sec = time[apex_idx:right + 1] * 60
        sig = corrected[apex_idx:right + 1]
        half_area = trapezoid(sig, t_sec)
        return half_area * 2, half_area, (apex_idx, right)


def full_peak_area(time, corrected, apex_idx):
    """전체 피크 적분 (co-elution 없는 피크용, e.g., AcO)"""
    apex_h = corrected[apex_idx]
    thr = apex_h * 0.02

    left = apex_idx
    while left > 0 and corrected[left] > thr:
        left -= 1
    right = apex_idx
    while right < len(corrected) - 1 and corrected[right] > thr:
        right += 1

    if right <= left + 1:
        return 0.0, (left, right)

    t_sec = time[left:right + 1] * 60
    sig = corrected[left:right + 1]
    area = trapezoid(sig, t_sec)
    return area, (left, right)


def area_to_conc(area, compound):
    """Area → 농도 변환 (dilution factor 적용)"""
    s = STD[compound]
    conc_raw = (area - s['intercept']) / s['slope']  # mg/mL or mM
    if s['unit'] == 'mg/mL':
        # mg/mL → mM
        conc_mM = (conc_raw / s['MW']) * 1000
    else:
        conc_mM = conc_raw
    return conc_mM * DILUTION_FACTOR


def analyze_one_file(ch_path):
    """하나의 .ch 파일 분석"""
    parser = ChemstationParser(str(ch_path))
    time, intensity = parser.read()

    # 베이스라인 보정
    baseline = rolling_min_baseline(intensity)
    corrected = np.maximum(intensity - baseline, 0)

    result = {
        'time_arr': time,
        'corrected_arr': corrected,
    }

    # --- Xylose: LEFT half-peak ---
    xyl_apex = find_peak_in_range(time, corrected, *XYL_RT_RANGE)
    if xyl_apex is not None:
        xyl_area, xyl_half, xyl_bounds = half_peak_area(time, corrected, xyl_apex, side='left')
        result['Xyl_RT'] = time[xyl_apex]
        result['Xyl_area'] = xyl_area  # half × 2
        result['Xyl_half_area'] = xyl_half
        result['Xyl_height'] = corrected[xyl_apex]
        result['Xyl_conc_mM'] = max(area_to_conc(xyl_area, 'Xyl'), 0)
    else:
        result['Xyl_RT'] = np.nan
        result['Xyl_area'] = 0
        result['Xyl_half_area'] = 0
        result['Xyl_height'] = 0
        result['Xyl_conc_mM'] = 0

    # --- Xylulose: RIGHT half-peak ---
    xul_apex = find_peak_in_range(time, corrected, *XUL_RT_RANGE)
    if xul_apex is not None:
        xul_area, xul_half, xul_bounds = half_peak_area(time, corrected, xul_apex, side='right')
        result['Xul_RT'] = time[xul_apex]
        result['Xul_area'] = xul_area  # half × 2
        result['Xul_half_area'] = xul_half
        result['Xul_height'] = corrected[xul_apex]
        result['Xul_conc_mM'] = max(area_to_conc(xul_area, 'Xul'), 0)
    else:
        result['Xul_RT'] = np.nan
        result['Xul_area'] = 0
        result['Xul_half_area'] = 0
        result['Xul_height'] = 0
        result['Xul_conc_mM'] = 0

    # --- Acetate: full peak ---
    aco_apex = find_peak_in_range(time, corrected, *ACO_RT_RANGE, min_height=10)
    if aco_apex is not None:
        aco_area, aco_bounds = full_peak_area(time, corrected, aco_apex)
        result['AcO_RT'] = time[aco_apex]
        result['AcO_area'] = aco_area
        result['AcO_height'] = corrected[aco_apex]
        result['AcO_conc_mM'] = max(area_to_conc(aco_area, 'AcO'), 0)
    else:
        result['AcO_RT'] = np.nan
        result['AcO_area'] = 0
        result['AcO_height'] = 0
        result['AcO_conc_mM'] = 0

    # Asymmetry ratio (Xyl/Xul peak quality 확인)
    if xyl_apex is not None:
        xyl_left_a, _, _ = half_peak_area(time, corrected, xyl_apex, 'left')
        xyl_right_a, _, _ = half_peak_area(time, corrected, xyl_apex, 'right')
        result['Xyl_asymmetry'] = (xyl_left_a / xyl_right_a) if xyl_right_a > 0 else np.nan
    else:
        result['Xyl_asymmetry'] = np.nan

    if xul_apex is not None:
        xul_left_a, _, _ = half_peak_area(time, corrected, xul_apex, 'left')
        xul_right_a, _, _ = half_peak_area(time, corrected, xul_apex, 'right')
        result['Xul_asymmetry'] = (xul_left_a / xul_right_a) if xul_right_a > 0 else np.nan
    else:
        result['Xul_asymmetry'] = np.nan

    return result


def parse_sample_info(sample_name, exp_name):
    """샘플명에서 NC 여부, 시간점 등 추출"""
    name_upper = sample_name.upper()
    is_nc = 'NC' in name_upper or 'CONTROL' in name_upper or 'CTL' in name_upper

    # 시간점 추출
    timepoint = ''
    for pat in ['24H', '12H', '6H', '3H', '2_5H', '2.5H', '1_5H', '1.5H', '1H', '0_5H', '0.5H',
                '90MIN', '60MIN', '30MIN', '0H', '0MIN']:
        if pat in name_upper:
            timepoint = pat.replace('_', '.')
            break

    return is_nc, timepoint


# ============================================================
#  메인
# ============================================================
if __name__ == '__main__':
    print("=" * 80)
    print("  Xul 5P Pretest Requantification - Half-peak")
    print("  Xyl: LEFT half × 2  |  Xul: RIGHT half × 2  |  AcO: full peak")
    print("=" * 80)

    all_rows = []

    exp_dirs = sorted([d for d in DATA_ROOT.iterdir() if d.is_dir()])
    for exp_dir in exp_dirs:
        exp_name = exp_dir.name
        ch_files = sorted(exp_dir.rglob('RID1A.ch'))
        if not ch_files:
            ch_files = sorted(exp_dir.rglob('*.ch'))

        print(f"\n--- {exp_name} ({len(ch_files)} files) ---")

        for ch_file in ch_files:
            sample_name = ch_file.parent.name.replace('.D', '').strip()
            is_nc, timepoint = parse_sample_info(sample_name, exp_name)

            try:
                result = analyze_one_file(ch_file)
                row = {
                    'experiment': exp_name,
                    'sample': sample_name,
                    'is_NC': is_nc,
                    'timepoint': timepoint,
                    'Xyl_RT': result['Xyl_RT'],
                    'Xyl_area_halfx2': result['Xyl_area'],
                    'Xyl_half_area': result['Xyl_half_area'],
                    'Xyl_height': result['Xyl_height'],
                    'Xyl_conc_mM': result['Xyl_conc_mM'],
                    'Xyl_asymmetry': result['Xyl_asymmetry'],
                    'Xul_RT': result['Xul_RT'],
                    'Xul_area_halfx2': result['Xul_area'],
                    'Xul_half_area': result['Xul_half_area'],
                    'Xul_height': result['Xul_height'],
                    'Xul_conc_mM': result['Xul_conc_mM'],
                    'Xul_asymmetry': result['Xul_asymmetry'],
                    'AcO_RT': result['AcO_RT'],
                    'AcO_area': result['AcO_area'],
                    'AcO_height': result['AcO_height'],
                    'AcO_conc_mM': result['AcO_conc_mM'],
                }
                all_rows.append(row)

                flag = ''
                if result['Xyl_asymmetry'] is not np.nan and not np.isnan(result.get('Xyl_asymmetry', np.nan)):
                    asym = result['Xyl_asymmetry']
                    if asym > 1.5 or asym < 0.67:
                        flag += ' [Xyl비대칭!]'
                if result['Xul_asymmetry'] is not np.nan and not np.isnan(result.get('Xul_asymmetry', np.nan)):
                    asym = result['Xul_asymmetry']
                    if asym > 1.5 or asym < 0.67:
                        flag += ' [Xul비대칭!]'

                nc_tag = '(NC)' if is_nc else '    '
                print(f"  {nc_tag} {sample_name[:45]:<45s}  "
                      f"Xyl={result['Xyl_conc_mM']:6.1f}mM  "
                      f"Xul={result['Xul_conc_mM']:6.1f}mM  "
                      f"AcO={result['AcO_conc_mM']:6.1f}mM"
                      f"{flag}")

            except Exception as e:
                print(f"  [ERR] {sample_name}: {e}")
                all_rows.append({
                    'experiment': exp_name,
                    'sample': sample_name,
                    'is_NC': is_nc,
                    'timepoint': timepoint,
                    'error': str(e),
                })

    # CSV 저장
    df = pd.DataFrame(all_rows)
    csv_path = OUTPUT_DIR / 'quantification_halfpeak.csv'
    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f"\n결과 저장: {csv_path}")
    print(f"총 {len(df)}개 샘플 분석 완료")

    # 요약 통계
    print("\n" + "=" * 80)
    print("  실험별 요약 (mean ± std)")
    print("=" * 80)
    for exp in df['experiment'].unique():
        sub = df[df['experiment'] == exp]
        nc = sub[sub['is_NC'] == True]
        rxn = sub[sub['is_NC'] == False]

        print(f"\n  {exp}")
        if len(nc) > 0:
            print(f"    NC  (n={len(nc):2d}):  Xyl={nc['Xyl_conc_mM'].mean():6.1f}±{nc['Xyl_conc_mM'].std():5.1f}  "
                  f"Xul={nc['Xul_conc_mM'].mean():6.1f}±{nc['Xul_conc_mM'].std():5.1f}  "
                  f"AcO={nc['AcO_conc_mM'].mean():6.1f}±{nc['AcO_conc_mM'].std():5.1f}")
        if len(rxn) > 0:
            print(f"    Rxn (n={len(rxn):2d}):  Xyl={rxn['Xyl_conc_mM'].mean():6.1f}±{rxn['Xyl_conc_mM'].std():5.1f}  "
                  f"Xul={rxn['Xul_conc_mM'].mean():6.1f}±{rxn['Xul_conc_mM'].std():5.1f}  "
                  f"AcO={rxn['AcO_conc_mM'].mean():6.1f}±{rxn['AcO_conc_mM'].std():5.1f}")
