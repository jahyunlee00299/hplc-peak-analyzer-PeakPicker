r"""
260212 (ATP 0.5 mM pretest) vs 260225 (ACP inhibition) 비교
=============================================================
- 260212: ACP 100/150/250/300 mM + ATP 0.5 mM, 시간: 15min/30min/1h/1.5h/3h
- 260225: ACP 100/150/200/300 mM,               시간: 90min/180min
- 공통 비교: ACP 100/150/300 mM, 시간 90min(=1.5h) & 180min(=3h)

캘리브레이션 (Chemstation 기준, 230221):
  Xyl: slope=22786.19, intercept=207.54 (mg/mL basis, MW=150.13)
  Xul: slope=23465.27, intercept=-59.45 (mg/mL basis, MW=150.13)

파서 스케일 주의사항:
  - 반응 샘플(90/180 min): 우리 면적 ≈ Chemstation (0.95×, ~5% 오차) → STD slope 그대로 사용 가능
  - NC 샘플: 우리 면적이 Chemstation의 2.196× → AcP broad background로 인한 baseline 처리 차이
    AcP 100mM NC에는 AcP가 그대로 있어 RT 10-12 min에 broad hump 존재
    Chemstation은 이를 Xyl의 elevated baseline으로 처리 (height 13364 nRIU 기준 17679 baseline)
    우리 rolling_min은 raw 최솟값(~12 nRIU)을 baseline으로 사용 → NC 절대값 신뢰 불가
  - PARSER_SCALE 보정 불필요: 반응 샘플에서는 거의 일치하므로 원래 slope 사용
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

import re
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.integrate import trapezoid
from scipy.signal import find_peaks
from scipy.ndimage import minimum_filter1d, uniform_filter1d
import warnings
warnings.filterwarnings('ignore')

from chemstation_parser import ChemstationParser
from sample_metadata import read_d_folder_metadata

# ── 경로 ─────────────────────────────────────────────────────────────────────
DATA_ROOT = Path(r'C:\Chem32\1\DATA\2. D-Xyl cascade HPLC\Xul 5P production\Pretest')
DIR_212   = DATA_ROOT / '260212_ACP_ATP_0_5'
DIR_225   = DATA_ROOT / '260225_ACP'
OUT_DIR   = Path(__file__).parent / 'result' / '260212_vs_260225'
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── 캘리브레이션 ──────────────────────────────────────────────────────────────
# STD calibration: 230221 기준, Chemstation 면적(nRIU·s)으로 만들어진 slope
# 반응 샘플(90/180 min)에서 우리 파서 면적 ≈ Chemstation 면적 (비율 ~0.95)
# → PARSER_SCALE 보정 없이 원래 slope 사용 (약 5% 오차 허용)
# NC는 AcP broad background 때문에 절대값 신뢰 불가 (별도 주석 처리)
STD = {
    'Xyl': {'slope': 22786.1903, 'intercept': 207.5383,
            'unit': 'mg/mL', 'MW': 150.13},
    'Xul': {'slope': 23465.2695, 'intercept': -59.4471,
            'unit': 'mg/mL', 'MW': 150.13},
    'AcO': {'slope': 8708,       'intercept': -901.6,
            'unit': 'mM'},
}
XYL_RT_RANGE = (10.9, 11.5)
XUL_RT_RANGE = (11.5, 12.1)
ACO_RT_RANGE = (16.8, 17.8)
INITIAL_XYL  = 250.0   # mM

plt.rcParams.update({
    'font.family': 'Malgun Gothic',
    'axes.unicode_minus': False,
    'figure.dpi': 150,
    'axes.spines.top': False,
    'axes.spines.right': False,
})


# ── 분석 함수 ──────────────────────────────────────────────────────────────────
def rolling_min_baseline(intensity, window_frac=0.10):
    win = max(int(len(intensity) * window_frac), 50)
    clipped = np.maximum(intensity, 0.0)
    base = minimum_filter1d(clipped, size=win)
    base = uniform_filter1d(base, size=win)
    return base


def find_peak_in_range(time, corrected, rt_start, rt_end, min_height=30):
    mask = (time >= rt_start) & (time <= rt_end)
    if mask.sum() < 5:
        return None
    indices = np.where(mask)[0]
    region  = corrected[indices]
    peaks, props = find_peaks(region, height=min_height, distance=5)
    if len(peaks) == 0:
        max_idx = np.argmax(region)
        return indices[max_idx] if region[max_idx] > min_height else None
    return indices[peaks[np.argmax(props['peak_heights'])]]


def half_peak_area(time, raw_intensity, apex_idx, side='left', max_width_min=2.0):
    """Valley baseline 방식 half-peak 적분.

    apex에서 좌/우로 탐색하며 신호가 다시 증가하는 지점(valley)을 찾고,
    그 valley signal을 수평 baseline으로 사용.

    NC: Xyl 왼쪽 AcP broad peak 끝 valley를 잡아 Chemstation과 유사.
    반응 샘플: broad peak 없으므로 valley ≈ 실제 baseline → 전체 면적 포함.
    """
    dt = float(np.median(np.diff(time)))
    max_pts = int(max_width_min / dt)

    if side == 'left':
        limit = max(0, apex_idx - max_pts)
        # apex에서 왼쪽으로 탐색: 신호 3% 이상 증가 감지 → 그 다음 점이 valley
        valley_idx = limit
        running_min = raw_intensity[apex_idx]
        for i in range(apex_idx - 1, limit - 1, -1):
            curr = raw_intensity[i]
            if curr > running_min * 1.03:
                valley_idx = i + 1
                break
            if curr < running_min:
                running_min = curr
        baseline_val = raw_intensity[valley_idx]
        sig = np.maximum(raw_intensity[valley_idx:apex_idx + 1] - baseline_val, 0)
        t_sec = time[valley_idx:apex_idx + 1] * 60
        area = trapezoid(sig, t_sec)
        return area, area, (valley_idx, apex_idx)
    else:
        limit = min(len(raw_intensity) - 1, apex_idx + max_pts)
        valley_idx = limit
        running_min = raw_intensity[apex_idx]
        for i in range(apex_idx + 1, limit + 1):
            curr = raw_intensity[i]
            if curr > running_min * 1.03:
                valley_idx = i - 1
                break
            if curr < running_min:
                running_min = curr
        baseline_val = raw_intensity[valley_idx]
        sig = np.maximum(raw_intensity[apex_idx:valley_idx + 1] - baseline_val, 0)
        t_sec = time[apex_idx:valley_idx + 1] * 60
        area = trapezoid(sig, t_sec)
        return area, area, (apex_idx, valley_idx)


def area_to_conc(area, compound, dilution_factor):
    s = STD[compound]
    conc_raw = (area - s['intercept']) / s['slope']
    if s['unit'] == 'mg/mL':
        conc_mM = (conc_raw / s['MW']) * 1000
    else:
        conc_mM = conc_raw
    return max(conc_mM * dilution_factor, 0.0)


def analyze_d_folder(d_folder_path):
    """단일 .D 폴더 분석 → dict 반환"""
    d_folder = Path(d_folder_path)
    ch_path  = d_folder / 'RID1A.ch'
    if not ch_path.exists():
        chs = list(d_folder.glob('*.ch'))
        if not chs:
            return None
        ch_path = chs[0]

    meta   = read_d_folder_metadata(d_folder)
    df_val = meta.get('dilution', 20.0)

    parser    = ChemstationParser(str(ch_path))
    time, intensity = parser.read()
    baseline  = rolling_min_baseline(intensity)
    corrected = np.maximum(intensity - baseline, 0)

    result = {'dilution': df_val, 'time': time, 'corrected': corrected, 'raw': intensity}

    # Xyl (LEFT half) — apex는 corrected로 찾고, 면적은 raw valley baseline으로 계산
    xyl_idx = find_peak_in_range(time, corrected, *XYL_RT_RANGE)
    if xyl_idx is not None:
        xyl_area, _, _ = half_peak_area(time, intensity, xyl_idx, 'left')
        result.update({
            'Xyl_RT': time[xyl_idx], 'Xyl_area': xyl_area,
            'Xyl_height': corrected[xyl_idx],
            'Xyl_mM': area_to_conc(xyl_area, 'Xyl', df_val),
        })
    else:
        result.update({'Xyl_RT': np.nan, 'Xyl_area': 0, 'Xyl_height': 0, 'Xyl_mM': 0})

    # Xul (RIGHT half) — 동일하게 raw valley baseline
    xul_idx = find_peak_in_range(time, corrected, *XUL_RT_RANGE)
    if xul_idx is not None:
        xul_area, _, _ = half_peak_area(time, intensity, xul_idx, 'right')
        result.update({
            'Xul_RT': time[xul_idx], 'Xul_area': xul_area,
            'Xul_height': corrected[xul_idx],
            'Xul_mM': area_to_conc(xul_area, 'Xul', df_val),
        })
    else:
        result.update({'Xul_RT': np.nan, 'Xul_area': 0, 'Xul_height': 0, 'Xul_mM': 0})

    # AcO (full peak) — rolling_min corrected 유지 (AcO 구간에 broad background 없음)
    aco_idx = find_peak_in_range(time, corrected, *ACO_RT_RANGE, min_height=10)
    if aco_idx is not None:
        apex_h = corrected[aco_idx]; thr = apex_h * 0.02
        l = aco_idx
        while l > 0 and corrected[l] > thr: l -= 1
        r = aco_idx
        while r < len(corrected)-1 and corrected[r] > thr: r += 1
        t_sec = time[l:r+1] * 60
        aco_area = trapezoid(corrected[l:r+1], t_sec)
        result.update({
            'AcO_RT': time[aco_idx], 'AcO_area': aco_area,
            'AcO_height': corrected[aco_idx],
            'AcO_mM': area_to_conc(aco_area, 'AcO', df_val),
        })
    else:
        result.update({'AcO_RT': np.nan, 'AcO_area': 0, 'AcO_height': 0, 'AcO_mM': 0})

    return result


# ── 샘플명 파싱 ──────────────────────────────────────────────────────────────
def parse_212(name):
    """260212_ACP_100_ATP_0_5_1_5H → acp=100, time_min=90, is_nc=False"""
    parts = name.upper()
    is_nc = 'NC' in parts
    acp = None
    for v in [300, 250, 150, 100]:
        if f'ACP_{v}' in parts or f'_{v}_' in parts:
            acp = v; break
    time_min = None
    time_map = {'3H': 180, '1_5H': 90, '1H': 60, '30MIN': 30, '15MIN': 15}
    for k, v in time_map.items():
        if k in parts:
            time_min = v; break
    return acp, time_min, is_nc


def parse_225(name):
    """260225_ACP_100_90MIN / 260225_ACP_100_NC_90MIN"""
    parts = name.upper()
    is_nc = 'NC' in parts
    acp = None
    for v in [300, 200, 150, 100]:
        if f'ACP_{v}' in parts or f'_{v}_' in parts:
            acp = v; break
    time_min = None
    for p in parts.split('_'):
        if p.endswith('MIN'):
            try: time_min = int(p.replace('MIN', '')); break
            except ValueError: pass
    return acp, time_min, is_nc


# ── 실험 전체 분석 ─────────────────────────────────────────────────────────────
def run_experiment(data_dir, parse_fn, label):
    rows = []
    d_dirs = sorted(data_dir.glob('*.D'))
    print(f"\n{'='*70}")
    print(f"  {label}  ({len(d_dirs)} .D folders)")
    print(f"{'='*70}")
    print(f"  {'샘플':<45} {'ACP':>5} {'t(min)':>7} {'NC':>4} "
          f"{'Xyl(mM)':>9} {'Xul(mM)':>9} {'AcO(mM)':>9}")
    print("  " + "-" * 93)

    for d_folder in d_dirs:
        name = d_folder.stem
        acp, time_min, is_nc = parse_fn(name)
        try:
            res = analyze_d_folder(d_folder)
            if res is None:
                continue
            nc_tag = 'Y' if is_nc else ''
            print(f"  {name:<45} {str(acp or '?'):>5} {str(time_min or '?'):>7} {nc_tag:>4} "
                  f"{res['Xyl_mM']:>9.1f} {res['Xul_mM']:>9.1f} {res['AcO_mM']:>9.1f}")
            rows.append({
                'experiment': label, 'sample': name,
                'acp': acp, 'time_min': time_min, 'is_nc': is_nc,
                'dilution': res['dilution'],
                'Xyl_mM': res['Xyl_mM'], 'Xul_mM': res['Xul_mM'], 'AcO_mM': res['AcO_mM'],
                'Xyl_RT': res['Xyl_RT'], 'Xul_RT': res['Xul_RT'],
                'Xyl_height': res['Xyl_height'], 'Xul_height': res['Xul_height'],
                'Xyl_area': res['Xyl_area'], 'Xul_area': res['Xul_area'],
                'time': res['time'], 'corrected': res['corrected'],
            })
        except Exception as e:
            print(f"  [ERR] {name}: {e}")

    return pd.DataFrame(rows)


# ── 비교 플롯 ──────────────────────────────────────────────────────────────────
COLORS_212 = {100: '#1f77b4', 150: '#ff7f0e', 250: '#2ca02c', 300: '#d62728'}
COLORS_225 = {100: '#aec7e8', 150: '#ffbb78', 200: '#98df8a', 300: '#ff9896'}
LS_212 = '-'
LS_225 = '--'


def make_comparison_plot(df212, df225):
    """ACP별 Xyl/Xul/Xul5P 시간 경과 비교"""
    fig, axes = plt.subplots(2, 3, figsize=(15, 9))
    acp_vals = [100, 150, 300]
    compounds = [
        ('Xyl_mM', 'D-Xylose (mM)', 0),
        ('Xul_mM', 'D-Xylulose (mM)', 1),
    ]

    # Xul5P mass balance 계산
    for df in [df212, df225]:
        df['Xul5P_mM'] = 0.0
        rxn_mask = ~df['is_nc']
        total = df.loc[rxn_mask, 'Xyl_mM'] + df.loc[rxn_mask, 'Xul_mM']
        df.loc[rxn_mask, 'Xul5P_mM'] = (INITIAL_XYL - total).clip(lower=0)

    compounds.append(('Xul5P_mM', 'D-Xul5P est. (mM)', 2))

    for row_idx, (col, ylabel, ax_col) in enumerate(compounds):
        for acp_idx, acp in enumerate(acp_vals):
            ax = axes[0 if acp_idx < 3 else 1, acp_idx % 3]
            # 각 compound에 대해 별도 axes 사용
        # 실제 플롯: axes[0,:] = ACP 100/150/300, axes[1,:] = 각 compound별 비교
        pass

    # 레이아웃: 3행(ACP) × 2열(Xyl, Xul) + 1열(Xul5P)
    fig.clear()
    n_acps_212 = sorted(df212['acp'].dropna().unique().astype(int))
    n_acps_225 = sorted(df225['acp'].dropna().unique().astype(int))
    common_acps = sorted(set(n_acps_212) & set(n_acps_225))

    n_rows = len(common_acps)
    n_cols = 3  # Xyl, Xul, Xul5P
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(14, 4 * n_rows))
    if n_rows == 1:
        axes = axes[np.newaxis, :]

    for df in [df212, df225]:
        df['Xul5P_mM'] = 0.0
        rxn = ~df['is_nc']
        total = df.loc[rxn, 'Xyl_mM'] + df.loc[rxn, 'Xul_mM']
        df.loc[rxn, 'Xul5P_mM'] = (INITIAL_XYL - total).clip(lower=0)

    col_configs = [
        ('Xyl_mM',  'D-Xylose (mM)'),
        ('Xul_mM',  'D-Xylulose (mM)'),
        ('Xul5P_mM','D-Xul5P est. (mM)'),
    ]

    for row_i, acp in enumerate(common_acps):
        for col_i, (col, ylabel) in enumerate(col_configs):
            ax = axes[row_i, col_i]

            # 260212 (ATP 0.5 mM)
            sub212 = df212[(df212['acp'] == acp) & (~df212['is_nc'])].dropna(subset=['time_min'])
            sub212 = sub212.sort_values('time_min')
            if len(sub212) > 0:
                ax.plot(sub212['time_min'], sub212[col], 'o-',
                        color='#1f77b4', linewidth=2, markersize=7,
                        label='260212 (ATP 0.5 mM)', zorder=3)

            # 260225
            sub225 = df225[(df225['acp'] == acp) & (~df225['is_nc'])].dropna(subset=['time_min'])
            sub225 = sub225.sort_values('time_min')
            if len(sub225) > 0:
                ax.plot(sub225['time_min'], sub225[col], 's--',
                        color='#d62728', linewidth=2, markersize=7,
                        label='260225 (ATP 0.5 mM, fresh enz)', zorder=3)

            ax.set_xlabel('Time (min)', fontsize=10)
            ax.set_ylabel(ylabel, fontsize=10)
            ax.set_title(f'AcP {acp} mM – {ylabel.split("(")[0].strip()}', fontsize=11)
            ax.grid(True, alpha=0.3)
            if col_i == 0:
                ax.set_ylim(bottom=0)
            if row_i == 0 and col_i == 2:
                ax.legend(fontsize=8, loc='upper left')

    plt.suptitle('260212 (ATP 0.5 mM) vs 260225 – D-Xyl Cascade',
                 fontsize=14, fontweight='bold', y=1.01)
    plt.tight_layout()
    out_path = OUT_DIR / 'comparison_timecourse.png'
    plt.savefig(str(out_path), dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\n비교 플롯 저장: {out_path}")
    return out_path


def make_bar_comparison(df212, df225):
    """90min & 180min 시점에서 bar chart 비교"""
    for df in [df212, df225]:
        df['Xul5P_mM'] = 0.0
        rxn = ~df['is_nc']
        total = df.loc[rxn, 'Xyl_mM'] + df.loc[rxn, 'Xul_mM']
        df.loc[rxn, 'Xul5P_mM'] = (INITIAL_XYL - total).clip(lower=0)

    timepoints = [90, 180]
    common_acps = sorted(set(df212['acp'].dropna().astype(int)) &
                         set(df225['acp'].dropna().astype(int)))
    cols = ['Xyl_mM', 'Xul_mM', 'Xul5P_mM']
    col_labels = ['D-Xylose', 'D-Xylulose', 'D-Xul5P (est.)']

    for t in timepoints:
        fig, axes = plt.subplots(1, 3, figsize=(14, 5))
        for ci, (col, clabel) in enumerate(zip(cols, col_labels)):
            ax = axes[ci]
            x = np.arange(len(common_acps))
            width = 0.35

            vals_212, vals_225 = [], []
            for acp in common_acps:
                r212 = df212[(df212['acp'] == acp) & (~df212['is_nc']) &
                             (df212['time_min'] == t)]
                r225 = df225[(df225['acp'] == acp) & (~df225['is_nc']) &
                             (df225['time_min'] == t)]
                vals_212.append(r212[col].values[0] if len(r212) else 0)
                vals_225.append(r225[col].values[0] if len(r225) else 0)

            bars1 = ax.bar(x - width/2, vals_212, width,
                           label='260212 (ATP 0.5 mM)', color='#1f77b4', alpha=0.85)
            bars2 = ax.bar(x + width/2, vals_225, width,
                           label='260225 (ATP 0.5 mM, fresh enz)', color='#d62728', alpha=0.85)

            # 값 표시
            for bar in bars1:
                h = bar.get_height()
                if h > 0:
                    ax.text(bar.get_x() + bar.get_width()/2, h + 1,
                            f'{h:.0f}', ha='center', va='bottom', fontsize=8)
            for bar in bars2:
                h = bar.get_height()
                if h > 0:
                    ax.text(bar.get_x() + bar.get_width()/2, h + 1,
                            f'{h:.0f}', ha='center', va='bottom', fontsize=8)

            ax.set_xticks(x)
            ax.set_xticklabels([f'AcP {a} mM' for a in common_acps])
            ax.set_ylabel(f'{clabel} (mM)', fontsize=10)
            ax.set_title(f'{clabel} @ {t} min', fontsize=11, fontweight='bold')
            ax.legend(fontsize=8)
            ax.grid(True, alpha=0.3, axis='y')
            ax.set_ylim(bottom=0)

        plt.suptitle(f'260212 vs 260225 비교 – {t} min 시점', fontsize=13, fontweight='bold')
        plt.tight_layout()
        out_path = OUT_DIR / f'bar_comparison_{t}min.png'
        plt.savefig(str(out_path), dpi=150, bbox_inches='tight')
        plt.close()
        print(f"bar 플롯 저장: {out_path}")


def make_summary_table(df212, df225):
    """요약 테이블 출력 및 CSV 저장"""
    for df, label in [(df212, '260212_ATP0.5mM'), (df225, '260225_freshEnz')]:
        df['Xul5P_mM'] = 0.0
        rxn = ~df['is_nc']
        total = df.loc[rxn, 'Xyl_mM'] + df.loc[rxn, 'Xul_mM']
        df.loc[rxn, 'Xul5P_mM'] = (INITIAL_XYL - total).clip(lower=0)
        df['experiment'] = label

    combined = pd.concat([df212, df225], ignore_index=True)
    cols_save = ['experiment', 'sample', 'acp', 'time_min', 'is_nc',
                 'dilution', 'Xyl_mM', 'Xul_mM', 'AcO_mM', 'Xul5P_mM',
                 'Xyl_RT', 'Xul_RT', 'Xyl_height', 'Xul_height']
    save_df = combined[[c for c in cols_save if c in combined.columns]]
    csv_path = OUT_DIR / 'quantification_260212_vs_260225.csv'
    save_df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f"\n요약 CSV: {csv_path}")

    # 터미널 출력
    print("\n" + "=" * 100)
    print(f"  {'Exp':<22} {'ACP':>5} {'t(min)':>7} {'NC':>4} "
          f"{'Xyl(mM)':>9} {'Xul(mM)':>9} {'Xul5P(mM)':>10} {'AcO(mM)':>9}")
    print("  " + "-" * 98)
    for _, row in save_df.sort_values(['experiment', 'acp', 'is_nc', 'time_min']).iterrows():
        nc = 'Y' if row['is_nc'] else ''
        xul5p = f"{row['Xul5P_mM']:.1f}" if not row['is_nc'] else 'NC'
        print(f"  {row['experiment']:<22} {str(row['acp'] or '?'):>5} "
              f"{str(int(row['time_min']) if pd.notna(row['time_min']) else '?'):>7} {nc:>4} "
              f"{row['Xyl_mM']:>9.1f} {row['Xul_mM']:>9.1f} {xul5p:>10} "
              f"{row.get('AcO_mM', 0):>9.1f}")

    return save_df


# ── 메인 ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("=" * 70)
    print("  260212 (ATP 0.5 mM) vs 260225 비교 분석")
    print("=" * 70)

    # 1. 정량
    df212 = run_experiment(DIR_212, parse_212, '260212_ACP_ATP_0_5')
    df225 = run_experiment(DIR_225, parse_225, '260225_ACP')

    # time 및 corrected 컬럼 제거 (plot 외 저장 불필요)
    df212_plot = df212.copy()
    df225_plot = df225.copy()

    for df in [df212, df225]:
        for c in ['time', 'corrected']:
            if c in df.columns:
                df.drop(columns=[c], inplace=True)

    # 2. 요약 테이블
    summary = make_summary_table(df212, df225)

    # 3. 시계열 비교 플롯
    p1 = make_comparison_plot(df212_plot, df225_plot)

    # 4. 시점별 bar 비교
    make_bar_comparison(df212, df225)

    print("\n완료! 결과 위치:", OUT_DIR)
