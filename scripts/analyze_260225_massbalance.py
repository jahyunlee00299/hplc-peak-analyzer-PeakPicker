"""
260225 D-Xul5P Production Analysis – Mass Balance (v2)
======================================================

데이터 구조:
  - quantification_halfpeak.csv → Xyl_height, Xul_height, AcO_height (PeakPicker 파이프라인)
  - raw .ch (RT 6.5–7.8 min) → Xul5P 후보 피크 높이

Mass balance:
  total   = Xyl_mM + Xul_mM
  Xul5P   = max(250 − total, 0)   [D-Xyl → D-Xul → D-Xul5P 몰 보존]

Height calibration (x = mM in HPLC vial, D=20):
  Xyl: H = 36.55 + 3028.73 × mM_vial   (R²=0.999994)
  Xul: H = −5.92 + 2576.69 × mM_vial   (R²=0.999924)
검증: 250 mM / D=20 = 12.5 mM_vial → H_Xyl ≈ 37,896  ✓

주의:
  - AcP ≥ 200 mM: AcP가 D-Xyl 피크 (RT~11.1) 와 co-elute → Xyl 과다 추정
    → NC 기반 아닌 설계값(250 mM) 을 기준으로 사용
  - Xul5P 표준 없음 → RT~7.24 높이는 정성적 상관관계 확인에만 사용
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.ndimage import minimum_filter1d, uniform_filter1d
from scipy.stats import pearsonr

from chemstation_parser import ChemstationParser

# ── Paths ───────────────────────────────────────────────────────────────────
CSV_PATH   = Path(__file__).parent / 'result' / 'pretest_analysis' / 'quantification_halfpeak.csv'
DATA_DIR   = Path(r'C:\Chem32\1\DATA\2. D-Xyl cascade HPLC\Xul 5P production\Pretest\260225_ACP')
OUTPUT_DIR = Path(__file__).parent / 'result' / 'pretest_analysis'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Constants ────────────────────────────────────────────────────────────────
D           = 20     # 희석배수 (260225)
INITIAL_XYL = 250    # mM (실험 설계: D-Xylose 초기 농도)

XYL_CAL = {'slope': 3028.73, 'intercept':  36.55}
XUL_CAL = {'slope': 2576.69, 'intercept':  -5.92}

RT_XUL5P = (6.50, 7.80)   # D-Xul5P 후보 피크

COLORS = {100: '#56B4E9', 150: '#009E73', 200: '#E69F00', 300: '#D55E00'}

plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.size': 8, 'axes.labelsize': 9, 'axes.titlesize': 10,
    'xtick.labelsize': 7, 'ytick.labelsize': 7, 'legend.fontsize': 7,
    'figure.dpi': 300, 'savefig.dpi': 300,
    'axes.spines.top': False, 'axes.spines.right': False,
    'axes.linewidth': 0.8,
})


# ── Helpers ──────────────────────────────────────────────────────────────────

def height_to_mM(height, cal):
    """높이 → 반응 농도(mM).  음수는 0 처리."""
    if height is None or height <= 0:
        return 0.0
    return max((height - cal['intercept']) / cal['slope'] * D, 0.0)


def parse_sample_name(name):
    """
    '260225_ACP_100_90MIN'    → acp=100, time=90,  is_nc=False
    '260225_ACP_100_NC_90MIN' → acp=100, time=90,  is_nc=True
    """
    parts = name.split('_')
    is_nc = 'NC' in parts
    acp = None
    for v in [100, 150, 200, 300]:
        if str(v) in parts:
            acp = v
            break
    time_min = None
    for p in parts:
        if p.endswith('MIN'):
            try:
                time_min = int(p.replace('MIN', ''))
            except ValueError:
                pass
    return acp, time_min, is_nc


def rolling_min_baseline(intensity, window_frac=0.15):
    win = max(int(len(intensity) * window_frac), 50)
    base = minimum_filter1d(intensity, size=win)
    base = uniform_filter1d(base, size=win * 2)
    return base


def load_xul5p_peak(d_folder):
    """Raw .ch 에서 RT 6.5–7.8 min 구간 최대 높이와 RT 반환."""
    ch_files = list(Path(d_folder).glob('*.ch'))
    if not ch_files:
        return 0.0, None
    parser = ChemstationParser(str(ch_files[0]))
    time, intensity = parser.read()
    baseline  = rolling_min_baseline(intensity)
    corrected = np.maximum(intensity - baseline, 0)
    mask = (time >= RT_XUL5P[0]) & (time <= RT_XUL5P[1])
    if not np.any(mask):
        return 0.0, None
    idx       = np.where(mask)[0]
    apex_loc  = np.argmax(corrected[idx])
    return float(corrected[idx[apex_loc]]), float(time[idx[apex_loc]])


# ── Data Loading ─────────────────────────────────────────────────────────────

def load_csv_data():
    """
    quantification_halfpeak.csv 에서 260225_ACP 데이터 읽기.
    Xyl_height, Xul_height → height calibration → Xyl_mM, Xul_mM 계산.
    """
    df = pd.read_csv(CSV_PATH)
    df = df[df['experiment'] == '260225_ACP'].copy()

    parsed = df['sample'].apply(lambda s: pd.Series(
        parse_sample_name(s), index=['acp', 'time_min', 'is_nc']
    ))
    df = pd.concat([df, parsed], axis=1)

    df['Xyl_mM']   = df['Xyl_height'].apply(lambda h: height_to_mM(h, XYL_CAL))
    df['Xul_mM']   = df['Xul_height'].apply(lambda h: height_to_mM(h, XUL_CAL))
    df['total_mM'] = df['Xyl_mM'] + df['Xul_mM']
    return df


def load_xul5p_data(df):
    """Raw .ch 에서 RT~7.24 Xul5P 피크를 읽어 df 에 컬럼 추가."""
    h5p_heights = {}
    h5p_rts     = {}
    for d_folder in DATA_DIR.glob('*.D'):
        stem = d_folder.stem
        if '260225_ACP' not in stem:
            continue
        h, rt = load_xul5p_peak(d_folder)
        h5p_heights[stem] = h
        h5p_rts[stem]     = rt

    df = df.copy()
    df['Xul5P_h']  = df['sample'].map(h5p_heights).fillna(0)
    df['Xul5P_RT'] = df['sample'].map(h5p_rts)
    return df


# ── Analysis ─────────────────────────────────────────────────────────────────

def compute_mass_balance(df):
    """
    Rxn 샘플에 대해 mass balance Xul5P_mM 계산.
    음수(AcP co-elution 오염) → 0 clamp.
    """
    df = df.copy()
    df['Xul5P_mM'] = 0.0
    rxn_mask = ~df['is_nc']
    df.loc[rxn_mask, 'Xul5P_mM'] = (
        INITIAL_XYL - df.loc[rxn_mask, 'total_mM']
    ).clip(lower=0)
    return df


def print_data_table(df):
    """스크린샷과 동일한 구조로 데이터 테이블 출력."""
    print("=" * 110)
    print("  260225 D-Xul5P Mass Balance Analysis")
    print("=" * 110)
    hdr = (f"  {'Sample':<33} {'AcP':>5} {'t(min)':>7} {'is_NC':>6} "
           f"{'Xyl_h':>7} {'Xul_h':>7} {'Xyl_mM':>8} {'Xul_mM':>8} "
           f"{'total':>7} {'Xul5P_mb':>9} {'Xul5P_h':>9} {'RT_h5p':>7}")
    print(hdr)
    print("─" * 110)
    for _, row in df.sort_values(['acp', 'is_nc', 'time_min']).iterrows():
        nc_tag  = "True" if row['is_nc'] else "False"
        rt_str  = f"{row['Xul5P_RT']:.2f}" if pd.notna(row['Xul5P_RT']) else "  N/A"
        mb_str  = f"{row['Xul5P_mM']:.1f}" if not row['is_nc'] else "  NC"
        print(f"  {row['sample']:<33} {row['acp']:>5} {str(row['time_min'])+' ':>7} {nc_tag:>6} "
              f"{row['Xyl_height']:>7.0f} {row['Xul_height']:>7.0f} "
              f"{row['Xyl_mM']:>8.1f} {row['Xul_mM']:>8.1f} "
              f"{row['total_mM']:>7.1f} {mb_str:>9} {row['Xul5P_h']:>9.0f} {rt_str:>7}")


def print_summary_table(df):
    """AcP별 요약 테이블."""
    rxn = df[~df['is_nc']]
    nc  = df[df['is_nc']].set_index('acp')

    print("\n" + "─" * 85)
    print(f"  {'AcP':>5}   {'Xul5P_90min':>13}   {'Xul5P_180min':>14}   {'h_RT7.24_90':>12}   {'h_RT7.24_180':>13}")
    print("─" * 85)
    for acp in [100, 150, 200, 300]:
        r90  = rxn[(rxn['acp'] == acp) & (rxn['time_min'] == 90)]
        r180 = rxn[(rxn['acp'] == acp) & (rxn['time_min'] == 180)]
        mb90  = f"{r90['Xul5P_mM'].values[0]:8.1f}" if len(r90)  else "       N/A"
        mb180 = f"{r180['Xul5P_mM'].values[0]:8.1f}" if len(r180) else "       N/A"
        h90   = f"{r90['Xul5P_h'].values[0]:>10.0f}" if len(r90)  else "       N/A"
        h180  = f"{r180['Xul5P_h'].values[0]:>10.0f}" if len(r180) else "       N/A"
        print(f"  {acp:>5}   {mb90} mM   {mb180} mM   {h90}   {h180}")


def print_nc_subtracted(df):
    """NC 보정 RT~7.24 신호."""
    nc_h5p = {row['acp']: row['Xul5P_h']
               for _, row in df[df['is_nc']].iterrows()}
    rxn    = df[~df['is_nc']].sort_values(['acp', 'time_min'])

    print(f"\n  NC-subtracted RT~7.24 (Rxn - NC):")
    for _, row in rxn.iterrows():
        nc_val = nc_h5p.get(row['acp'], 0)
        net    = row['Xul5P_h'] - nc_val
        print(f"    AcP {row['acp']:>3} mM, {row['time_min']:>3} min: "
              f"Xul5P_est={row['Xul5P_mM']:6.1f} mM  "
              f"h_raw={row['Xul5P_h']:>7.0f}  NC={nc_val:>7.0f}  net={net:>+7.0f}")


# ── Figures ──────────────────────────────────────────────────────────────────

def plot_production(df):
    """Figure 1: Xul5P 생산량 bar + 180/90 ratio."""
    rxn    = df[~df['is_nc']]
    acp_vals = [100, 150, 200, 300]

    def get_val(acp, t, col):
        r = rxn[(rxn['acp'] == acp) & (rxn['time_min'] == t)]
        return r[col].values[0] if len(r) else 0.0

    xul5p_90  = [get_val(a, 90,  'Xul5P_mM') for a in acp_vals]
    xul5p_180 = [get_val(a, 180, 'Xul5P_mM') for a in acp_vals]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7, 3))
    x, w = np.arange(len(acp_vals)), 0.35

    bars1 = ax1.bar(x - w/2, xul5p_90,  w, color='#56B4E9', edgecolor='white', label='90 min')
    bars2 = ax1.bar(x + w/2, xul5p_180, w, color='#D55E00', edgecolor='white', label='180 min')
    for bars in (bars1, bars2):
        for bar in bars:
            h = bar.get_height()
            if h > 0:
                ax1.text(bar.get_x() + bar.get_width()/2, h + 1,
                         f'{h:.0f}', ha='center', va='bottom', fontsize=5.5)
    ax1.set_xticks(x); ax1.set_xticklabels([str(v) for v in acp_vals])
    ax1.set_xlabel('AcP (mM)'); ax1.set_ylabel('D-Xul5P (mM)')
    ax1.set_title('D-Xylulose-5-phosphate production\n[mass balance: 250 - Xyl - Xul]')
    ax1.legend(frameon=False)
    ax1.text(-0.12, 1.08, 'A', transform=ax1.transAxes, fontsize=11, fontweight='bold', va='top')

    ratios   = [v180/v90 if v90 > 1e-6 else 0 for v90, v180 in zip(xul5p_90, xul5p_180)]
    bar_cols = ['#009E73' if r > 1 else '#CC79A7' for r in ratios]
    ax2.bar(x, ratios, 0.5, color=bar_cols, edgecolor='white')
    ax2.axhline(1.0, color='gray', ls='--', lw=0.7, alpha=0.7)
    ax2.set_xticks(x); ax2.set_xticklabels([str(v) for v in acp_vals])
    ax2.set_xlabel('AcP (mM)'); ax2.set_ylabel('Xul5P ratio (180 min / 90 min)')
    ax2.set_title('Time-dependent conversion\n[ratio > 1: continued production]')
    for i, r in enumerate(ratios):
        if r > 0:
            ax2.text(i, r + 0.02, f'{r:.2f}', ha='center', va='bottom', fontsize=7)
    ax2.text(-0.12, 1.08, 'B', transform=ax2.transAxes, fontsize=11, fontweight='bold', va='top')

    fig.tight_layout()
    out = OUTPUT_DIR / '260225_Xul5P_production.png'
    fig.savefig(out, dpi=300, bbox_inches='tight', pad_inches=0.15)
    fig.savefig(OUTPUT_DIR / '260225_Xul5P_production.pdf', bbox_inches='tight', pad_inches=0.15)
    plt.close(fig)
    print(f"\n  Saved: {out.name}")


def plot_correlation(df):
    """Figure 2: Mass balance Xul5P vs RT~7.24 (raw & NC-subtracted)."""
    rxn      = df[~df['is_nc']]
    nc_h5p   = {row['acp']: row['Xul5P_h'] for _, row in df[df['is_nc']].iterrows()}
    acp_vals = [100, 150, 200, 300]

    mb_flat      = list(rxn.sort_values(['acp', 'time_min'])['Xul5P_mM'])
    h5p_raw_flat = list(rxn.sort_values(['acp', 'time_min'])['Xul5P_h'])
    h5p_net_flat = [h - nc_h5p.get(a, 0)
                    for a, h in zip(
                        rxn.sort_values(['acp','time_min'])['acp'],
                        h5p_raw_flat)]

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(10, 4.5))

    def scatter_corr(ax, mb_vals, h5p_vals, title, ylabel):
        rxn_sorted = rxn.sort_values(['acp', 'time_min']).reset_index(drop=True)
        for i, row in rxn_sorted.iterrows():
            mk = 'o' if row['time_min'] == 90 else 's'
            ax.scatter(mb_vals[i], h5p_vals[i],
                       color=COLORS[row['acp']], marker=mk, s=70,
                       edgecolors='white', linewidths=0.6, zorder=3,
                       label=f"{row['acp']} mM, {row['time_min']} min")
        valid = [(x, y) for x, y in zip(mb_vals, h5p_vals) if x > 0]
        r_val = None
        if len(valid) >= 3:
            xs, ys = zip(*valid)
            r_val, p = pearsonr(xs, ys)
            m_fit, b_fit = np.polyfit(xs, ys, 1)
            xline = np.linspace(min(xs)*0.9, max(xs)*1.05, 50)
            ax.plot(xline, m_fit*xline + b_fit, 'k--', lw=1.0, alpha=0.5)
            pstr = f'p = {p:.3f}' if p >= 0.001 else 'p < 0.001'
            ax.text(0.05, 0.95, f'Pearson r = {r_val:.3f}\n{pstr}',
                    transform=ax.transAxes, fontsize=9, va='top',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                              edgecolor='#aaa', alpha=0.85))
        else:
            ax.text(0.05, 0.95, f'n = {len(valid)} (need >= 3)',
                    transform=ax.transAxes, fontsize=8, va='top', color='gray')
        ax.set_xlabel('D-Xul5P (mM)  [250 − Xyl − Xul]')
        ax.set_ylabel(ylabel)
        ax.set_title(title, fontsize=9)
        ax.legend(fontsize=5.5, frameon=False,
                  loc='lower right' if (r_val and r_val > 0) else 'upper right')
        ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)

    scatter_corr(axL, mb_flat, h5p_raw_flat,
                 'Mass balance Xul5P vs RT~7.24 (raw)',
                 'RT ~7.24 peak height (a.u.)')
    axL.text(-0.12, 1.08, 'A', transform=axL.transAxes, fontsize=11, fontweight='bold', va='top')

    scatter_corr(axR, mb_flat, h5p_net_flat,
                 'Mass balance Xul5P vs RT~7.24 (NC-subtracted)',
                 'RT ~7.24 height - NC (a.u.)  [net Xul5P signal]')
    axR.text(-0.12, 1.08, 'B', transform=axR.transAxes, fontsize=11, fontweight='bold', va='top')

    fig.text(0.5, -0.05,
             'Note: AcP co-elutes with D-Xylose (RT~11.1) at >150 mM AcP; '
             'mass balance capped to 0 for 200-300 mM conditions.',
             ha='center', fontsize=7, color='#666', style='italic')
    fig.tight_layout()
    out = OUTPUT_DIR / '260225_Xul5P_correlation.png'
    fig.savefig(out, dpi=300, bbox_inches='tight', pad_inches=0.2)
    fig.savefig(OUTPUT_DIR / '260225_Xul5P_correlation.pdf', bbox_inches='tight', pad_inches=0.2)
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    # 1. CSV 에서 Xyl/Xul 데이터 로드 (height → mM)
    df = load_csv_data()

    # 2. raw .ch 에서 RT~7.24 Xul5P 피크 추가
    df = load_xul5p_data(df)

    # 3. Mass balance 계산
    df = compute_mass_balance(df)

    # 4. 데이터 테이블 출력 (스크린샷 구조)
    print_data_table(df)
    print_summary_table(df)
    print_nc_subtracted(df)

    # 5. 그림 생성
    plot_production(df)
    plot_correlation(df)
    print("  Done.")


if __name__ == '__main__':
    main()
