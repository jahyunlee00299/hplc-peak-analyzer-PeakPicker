"""
260225 AcP Optimization - Publication-quality visualization
===========================================================
Multi-panel figure: chromatogram overlay, Xul production, AcO accumulation
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from scipy.ndimage import minimum_filter1d, uniform_filter1d
from chemstation_parser import ChemstationParser

# ── Publication style ──
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'font.size': 8,
    'axes.labelsize': 9,
    'axes.titlesize': 10,
    'xtick.labelsize': 7,
    'ytick.labelsize': 7,
    'legend.fontsize': 7,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.linewidth': 0.8,
    'xtick.major.width': 0.8,
    'ytick.major.width': 0.8,
    'lines.linewidth': 1.0,
})

# Okabe-Ito colorblind-safe palette
COLORS = {
    100: '#56B4E9',   # sky blue
    150: '#009E73',   # green
    200: '#E69F00',   # orange
    300: '#D55E00',   # vermillion
    'NC': '#999999',  # gray
}

DATA_ROOT = Path(r'C:\Chem32\1\DATA\2. D-Xyl cascade HPLC\Xul 5P production\Pretest')
EXP_DIR = DATA_ROOT / '260225_ACP'
OUTPUT_DIR = Path(__file__).parent / 'result' / 'pretest_analysis'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def rolling_min_baseline(intensity, window_frac=0.15):
    win = max(int(len(intensity) * window_frac), 50)
    base = minimum_filter1d(intensity, size=win)
    base = uniform_filter1d(base, size=win * 2)
    return base


def load_chromatogram(d_folder):
    """Load and baseline-correct a chromatogram from a .D folder."""
    ch_files = list(d_folder.glob('*.ch'))
    if not ch_files:
        return None, None
    parser = ChemstationParser(str(ch_files[0]))
    time, intensity = parser.read()
    baseline = rolling_min_baseline(intensity)
    corrected = np.maximum(intensity - baseline, 0)
    return time, corrected


def parse_sample(d_name):
    """Parse sample info from .D folder name."""
    name = d_name.replace('.D', '')
    is_nc = '_NC_' in name.upper()
    acp = None
    for val in [100, 150, 200, 300]:
        if f'_{val}_' in name:
            acp = val
            break
    timepoint = None
    if '180MIN' in name.upper():
        timepoint = 180
    elif '90MIN' in name.upper():
        timepoint = 90
    return {'name': name, 'is_nc': is_nc, 'acp': acp, 'timepoint': timepoint}


def main():
    # ── Load all chromatograms ──
    samples = []
    d_dirs = sorted([d for d in EXP_DIR.iterdir() if d.name.endswith('.D')])

    for d_dir in d_dirs:
        info = parse_sample(d_dir.name)
        time, corrected = load_chromatogram(d_dir)
        if time is None:
            continue
        info['time_arr'] = time
        info['corrected'] = corrected
        samples.append(info)

    print(f"Loaded {len(samples)} chromatograms")

    # Separate reaction vs NC
    rxn_samples = [s for s in samples if not s['is_nc']]
    nc_samples = [s for s in samples if s['is_nc']]

    # ── Load quantification data ──
    halfpeak_csv = OUTPUT_DIR / 'quantification_halfpeak.csv'
    df_h = pd.read_csv(halfpeak_csv, encoding='utf-8-sig')
    df_h = df_h[df_h['experiment'] == '260225_ACP'].copy()

    # Parse AcP and timepoint
    def extract_acp(sample_name):
        for v in [300, 200, 150, 100]:
            if f'_{v}_' in sample_name:
                return v
        return None

    def extract_minutes(sample_name):
        sample_name = str(sample_name).upper()
        if '180MIN' in sample_name:
            return 180
        elif '90MIN' in sample_name:
            return 90
        return None

    df_h['AcP_mM'] = df_h['sample'].apply(extract_acp)
    df_h['minutes'] = df_h['sample'].apply(extract_minutes)
    df_h['is_NC'] = df_h['is_NC'].astype(bool)

    # Convert area columns to numeric
    for col in ['Xyl_area_halfx2', 'Xul_area_halfx2']:
        df_h[col] = pd.to_numeric(df_h[col], errors='coerce')

    df_rxn = df_h[~df_h['is_NC']].copy()
    df_nc = df_h[df_h['is_NC']].copy()

    # ========================================
    #  Figure 1: Multi-panel comprehensive
    # ========================================
    fig = plt.figure(figsize=(7.5, 8))
    gs = fig.add_gridspec(3, 2, hspace=0.45, wspace=0.4,
                          height_ratios=[1.2, 1, 1])

    # ── Panel A: Chromatogram overlay (reaction samples, zoomed Xyl/Xul region) ──
    ax_a = fig.add_subplot(gs[0, 0])
    for s in rxn_samples:
        if s['timepoint'] == 90:
            label = f"AcP {s['acp']} mM, 90 min"
            ax_a.plot(s['time_arr'], s['corrected'],
                      color=COLORS.get(s['acp'], 'gray'),
                      linestyle='-', alpha=0.85, label=label)
    for s in rxn_samples:
        if s['timepoint'] == 180:
            label = f"AcP {s['acp']} mM, 180 min"
            ax_a.plot(s['time_arr'], s['corrected'],
                      color=COLORS.get(s['acp'], 'gray'),
                      linestyle='--', alpha=0.85, label=label)

    ax_a.set_xlim(5, 18.5)
    ax_a.set_xlabel('Retention time (min)')
    ax_a.set_ylabel('RID signal (a.u.)')
    ax_a.set_title('Reaction samples')
    ax_a.legend(fontsize=5.5, ncol=2, frameon=False, loc='upper right')

    # Add peak annotations
    ax_a.annotate('Xyl', xy=(11.1, ax_a.get_ylim()[1]*0.75),
                  fontsize=7, ha='center', color='#555555')
    ax_a.annotate('Xul', xy=(11.7, ax_a.get_ylim()[1]*0.55),
                  fontsize=7, ha='center', color='#555555')
    ax_a.annotate('AcO', xy=(17.3, ax_a.get_ylim()[1]*0.25),
                  fontsize=7, ha='center', color='#555555')

    # ── Panel B: NC chromatograms ──
    ax_b = fig.add_subplot(gs[0, 1])
    for s in nc_samples:
        label = f"NC {s['acp']} mM"
        ax_b.plot(s['time_arr'], s['corrected'],
                  color=COLORS.get(s['acp'], 'gray'),
                  linestyle=':', alpha=0.85, label=label)

    ax_b.set_xlim(5, 18.5)
    ax_b.set_xlabel('Retention time (min)')
    ax_b.set_ylabel('RID signal (a.u.)')
    ax_b.set_title('Negative controls (no enzyme)')
    ax_b.legend(fontsize=6, frameon=False, loc='upper right')
    ax_b.annotate('Xyl', xy=(11.1, ax_b.get_ylim()[1]*0.75),
                  fontsize=7, ha='center', color='#555555')

    # ── Panel C: D-Xylulose peak height (Rxn only, Xul absent in NC) ──
    ax_c = fig.add_subplot(gs[1, 0])
    acp_vals = [100, 150, 200, 300]
    xul_90 = []
    xul_180 = []
    for acp in acp_vals:
        row_90 = df_rxn[(df_rxn['AcP_mM'] == acp) & (df_rxn['minutes'] == 90)]
        row_180 = df_rxn[(df_rxn['AcP_mM'] == acp) & (df_rxn['minutes'] == 180)]
        xul_90.append(row_90['Xul_area_halfx2'].values[0] if len(row_90) > 0 else 0)
        xul_180.append(row_180['Xul_area_halfx2'].values[0] if len(row_180) > 0 else 0)

    x = np.arange(len(acp_vals))
    width = 0.35
    bars1 = ax_c.bar(x - width/2, xul_90, width, color='#56B4E9',
                     edgecolor='white', linewidth=0.5, label='90 min')
    bars2 = ax_c.bar(x + width/2, xul_180, width, color='#D55E00',
                     edgecolor='white', linewidth=0.5, label='180 min')

    ax_c.set_xticks(x)
    ax_c.set_xticklabels([str(v) for v in acp_vals])
    ax_c.set_xlabel('AcP concentration (mM)')
    ax_c.set_ylabel('D-Xylulose half-peak area (a.u.)')
    ax_c.set_title('Xylulose production')
    ax_c.legend(frameon=False)

    # Add value labels
    for bar in bars1:
        h = bar.get_height()
        if h > 0:
            ax_c.text(bar.get_x() + bar.get_width()/2, h + 100,
                      f'{h:.0f}', ha='center', va='bottom', fontsize=5.5)
    for bar in bars2:
        h = bar.get_height()
        if h > 0:
            ax_c.text(bar.get_x() + bar.get_width()/2, h + 100,
                      f'{h:.0f}', ha='center', va='bottom', fontsize=5.5)

    # ── Panel D: Xyl peak height (shows substrate consumption pattern) ──
    ax_d = fig.add_subplot(gs[1, 1])
    xyl_90_rxn = []
    xyl_180_rxn = []
    xyl_nc = []
    for acp in acp_vals:
        row_90 = df_rxn[(df_rxn['AcP_mM'] == acp) & (df_rxn['minutes'] == 90)]
        row_180 = df_rxn[(df_rxn['AcP_mM'] == acp) & (df_rxn['minutes'] == 180)]
        row_nc = df_nc[df_nc['AcP_mM'] == acp]
        xyl_90_rxn.append(row_90['Xyl_area_halfx2'].values[0] if len(row_90) > 0 else 0)
        xyl_180_rxn.append(row_180['Xyl_area_halfx2'].values[0] if len(row_180) > 0 else 0)
        xyl_nc.append(row_nc['Xyl_area_halfx2'].values[0] if len(row_nc) > 0 else 0)

    x = np.arange(len(acp_vals))
    width = 0.25
    ax_d.bar(x - width, xyl_nc, width, color='#999999',
             edgecolor='white', linewidth=0.5, label='NC')
    ax_d.bar(x, xyl_90_rxn, width, color='#56B4E9',
             edgecolor='white', linewidth=0.5, label='90 min')
    ax_d.bar(x + width, xyl_180_rxn, width, color='#D55E00',
             edgecolor='white', linewidth=0.5, label='180 min')

    ax_d.set_xticks(x)
    ax_d.set_xticklabels([str(v) for v in acp_vals])
    ax_d.set_xlabel('AcP concentration (mM)')
    ax_d.set_ylabel('D-Xylose half-peak area (a.u.)')
    ax_d.set_title('Xylose (substrate + co-eluting)')
    ax_d.legend(frameon=False, fontsize=6)

    # ── Panel E: Xul peak height line plot (AcP dose response) ──
    ax_e = fig.add_subplot(gs[2, 0])
    ax_e.plot(acp_vals, xul_90, 'o-', color='#56B4E9', markersize=6,
              label='90 min', markeredgecolor='white', markeredgewidth=0.5)
    ax_e.plot(acp_vals, xul_180, 's--', color='#D55E00', markersize=6,
              label='180 min', markeredgecolor='white', markeredgewidth=0.5)
    ax_e.set_xlabel('AcP concentration (mM)')
    ax_e.set_ylabel('D-Xylulose half-peak area (a.u.)')
    ax_e.set_title('Xul production dose-response')
    ax_e.legend(frameon=False)

    # ── Panel F: Zoomed Xyl/Xul region overlay (300 mM AcP) ──
    ax_f = fig.add_subplot(gs[2, 1])
    for s in samples:
        if s['acp'] == 300:
            if s['is_nc']:
                label = 'NC (300 mM)'
                ls, c = ':', COLORS['NC']
            elif s['timepoint'] == 90:
                label = 'Rxn 90 min'
                ls, c = '-', COLORS[300]
            else:
                label = 'Rxn 180 min'
                ls, c = '--', COLORS[300]
            ax_f.plot(s['time_arr'], s['corrected'],
                      color=c, linestyle=ls, alpha=0.9, label=label)

    ax_f.set_xlim(10.0, 12.5)
    ax_f.set_xlabel('Retention time (min)')
    ax_f.set_ylabel('RID signal (a.u.)')
    ax_f.set_title('300 mM AcP: Xyl/Xul region')
    ax_f.legend(frameon=False, fontsize=6)

    # Annotate Xyl and Xul peaks
    ax_f.axvline(11.095, color='gray', linestyle=':', alpha=0.4, linewidth=0.6)
    ax_f.axvline(11.67, color='gray', linestyle=':', alpha=0.4, linewidth=0.6)
    ymax_f = ax_f.get_ylim()[1]
    ax_f.text(11.095, ymax_f * 0.95, 'Xyl', ha='center', fontsize=6, color='#555')
    ax_f.text(11.67, ymax_f * 0.95, 'Xul', ha='center', fontsize=6, color='#555')

    # ── Panel labels ──
    panels = [ax_a, ax_b, ax_c, ax_d, ax_e, ax_f]
    labels = ['A', 'B', 'C', 'D', 'E', 'F']
    for ax, label in zip(panels, labels):
        ax.text(-0.12, 1.08, label, transform=ax.transAxes,
                fontsize=11, fontweight='bold', va='top')

    fig.savefig(OUTPUT_DIR / '260225_AcP_optimization_multipanel.png',
                dpi=300, bbox_inches='tight', pad_inches=0.15)
    fig.savefig(OUTPUT_DIR / '260225_AcP_optimization_multipanel.pdf',
                bbox_inches='tight', pad_inches=0.15)
    print(f"Saved: 260225_AcP_optimization_multipanel.png/pdf")
    plt.close(fig)

    # ========================================
    #  Figure 2: Summary table as figure
    # ========================================
    fig2, ax_t = plt.subplots(figsize=(7, 3.5))
    ax_t.axis('off')

    # Build summary table
    table_data = []
    for acp in acp_vals:
        for t_min in [90, 180]:
            row_rxn = df_rxn[(df_rxn['AcP_mM'] == acp) & (df_rxn['minutes'] == t_min)]
            row_nc = df_nc[df_nc['AcP_mM'] == acp]
            if len(row_rxn) > 0:
                xyl_h = row_rxn['Xyl_area_halfx2'].values[0]
                xul_h = row_rxn['Xul_area_halfx2'].values[0] if pd.notna(row_rxn['Xul_area_halfx2'].values[0]) else 0
                nc_xyl = row_nc['Xyl_area_halfx2'].values[0] if len(row_nc) > 0 else 0
                delta_xyl = nc_xyl - xyl_h if nc_xyl > 0 else 'N/A'
                table_data.append([
                    f'{acp}',
                    f'{t_min}',
                    f'{xyl_h:,.0f}',
                    f'{xul_h:,.0f}',
                    f'{nc_xyl:,.0f}' if isinstance(nc_xyl, (int, float)) else 'N/A',
                    f'{delta_xyl:,.0f}' if isinstance(delta_xyl, (int, float)) else 'N/A',
                ])

    col_labels = ['AcP\n(mM)', 'Time\n(min)', 'Xyl Area\n(Rxn)', 'Xul Area\n(Rxn)',
                  'Xyl Area\n(NC)', '\u0394Xyl\n(NC-Rxn)']

    table = ax_t.table(cellText=table_data, colLabels=col_labels,
                       cellLoc='center', loc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(7)
    table.scale(1, 1.4)

    # Style header
    for j in range(len(col_labels)):
        cell = table[0, j]
        cell.set_facecolor('#2C3E50')
        cell.set_text_props(color='white', fontweight='bold')

    # Alternate row colors
    for i in range(1, len(table_data) + 1):
        for j in range(len(col_labels)):
            cell = table[i, j]
            if i % 2 == 0:
                cell.set_facecolor('#ECF0F1')
            else:
                cell.set_facecolor('white')

    ax_t.set_title('260225 AcP Optimization: Half-Peak Area Summary (D = 20x)',
                    fontsize=10, fontweight='bold', pad=15)

    fig2.savefig(OUTPUT_DIR / '260225_summary_table.png',
                 dpi=300, bbox_inches='tight', pad_inches=0.2)
    print(f"Saved: 260225_summary_table.png")
    plt.close(fig2)

    # ========================================
    #  Figure 3: Xul-focused production plot
    # ========================================
    fig3, (ax3a, ax3b) = plt.subplots(1, 2, figsize=(7, 3))

    # Panel A: Grouped bar (Xul height by condition)
    x = np.arange(len(acp_vals))
    width = 0.35
    bars_a = ax3a.bar(x - width/2, xul_90, width, color='#56B4E9',
                      edgecolor='white', label='90 min')
    bars_b = ax3a.bar(x + width/2, xul_180, width, color='#D55E00',
                      edgecolor='white', label='180 min')
    ax3a.set_xticks(x)
    ax3a.set_xticklabels([str(v) for v in acp_vals])
    ax3a.set_xlabel('AcP (mM)')
    ax3a.set_ylabel('D-Xylulose half-peak area (a.u.)')
    ax3a.set_title('Xylulose production')
    ax3a.legend(frameon=False)

    # Panel B: Ratio plot (180min / 90min)
    ratios = [x180/x90 if x90 > 0 else 0 for x90, x180 in zip(xul_90, xul_180)]
    bar_colors = ['#009E73' if r > 1 else '#CC79A7' for r in ratios]
    ax3b.bar(x, ratios, 0.5, color=bar_colors, edgecolor='white')
    ax3b.axhline(1.0, color='gray', linestyle='--', linewidth=0.7, alpha=0.7)
    ax3b.set_xticks(x)
    ax3b.set_xticklabels([str(v) for v in acp_vals])
    ax3b.set_xlabel('AcP (mM)')
    ax3b.set_ylabel('Xul area ratio (180 min / 90 min)')
    ax3b.set_title('Time-dependent conversion')

    for i, r in enumerate(ratios):
        ax3b.text(i, r + 0.02, f'{r:.2f}', ha='center', va='bottom', fontsize=7)

    # Panel labels
    ax3a.text(-0.12, 1.08, 'A', transform=ax3a.transAxes,
              fontsize=11, fontweight='bold', va='top')
    ax3b.text(-0.12, 1.08, 'B', transform=ax3b.transAxes,
              fontsize=11, fontweight='bold', va='top')

    fig3.tight_layout()
    fig3.savefig(OUTPUT_DIR / '260225_Xul_production.png',
                 dpi=300, bbox_inches='tight', pad_inches=0.15)
    fig3.savefig(OUTPUT_DIR / '260225_Xul_production.pdf',
                 bbox_inches='tight', pad_inches=0.15)
    print(f"Saved: 260225_Xul_production.png/pdf")
    plt.close(fig3)

    print("\nAll 260225 visualizations complete!")


if __name__ == '__main__':
    main()
