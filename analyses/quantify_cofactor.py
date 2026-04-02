"""
Cofactor M2 (NAD) 실험 - Tagatose / Formate 정량
==================================================
P8 = Tagatose (RT ~10.84 min)
P9 = Formate  (RT ~11.65 min)
Dilution factor = 66.666666
"""
import sys
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

df = pd.read_csv(r'C:\Chem32\1\DATA\260216_cofactor_m2_main_new\quantification_results\all_peaks_detailed.csv')
out_dir = Path(r'C:\Chem32\1\DATA\260216_cofactor_m2_main_new\quantification_results')

# ===== Calibration (Area = y0 + a * C) -> C = (Area - y0) / a =====
tag_y0, tag_a = 1220.254, 64498.76       # Tagatose
form_y0, form_a = 10.4596, 5440.724      # Formate (rightmost)
DF = 66.666666

# ===== RT 기반 피크 매칭 =====
p8 = df[(df['rt_min'] >= 10.5) & (df['rt_min'] <= 11.2)].copy()
p9 = df[(df['rt_min'] >= 11.3) & (df['rt_min'] <= 12.0)].copy()

p8['conc_diluted'] = (p8['area_nRIUs'] - tag_y0) / tag_a
p8['conc_original'] = p8['conc_diluted'] * DF
p8['compound'] = 'Tagatose'

p9['conc_diluted'] = (p9['area_nRIUs'] - form_y0) / form_a
p9['conc_original'] = p9['conc_diluted'] * DF
p9['compound'] = 'Formate'

quant = pd.concat([p8, p9], ignore_index=True)
time_order = {'6H': 0, '12H': 1, '24H': 2, '': 3}
quant['time_sort'] = quant['time_h'].map(time_order)
quant = quant.sort_values(['compound', 'cofactor_dose', 'enzyme', 'time_sort', 'replicate'])
non_nc = quant[~quant['is_nc']].copy()

# ===== 콘솔 출력 =====
for compound in ['Tagatose', 'Formate']:
    sub = non_nc[non_nc['compound'] == compound]
    print(f"\n{'='*70}")
    print(f"  {compound} (DF={DF:.1f})")
    print(f"{'='*70}")
    for dose in ['D1', 'D2', 'D3', 'D4', 'D5']:
        for enz in ['RO', 'RS']:
            print(f"\n  {dose}_{enz}:")
            for th in ['6H', '12H', '24H']:
                v = sub[(sub['cofactor_dose'] == dose) & (sub['enzyme'] == enz) & (sub['time_h'] == th)]['conc_original']
                if len(v) > 0:
                    vals_str = ", ".join([f"{x:.2f}" for x in v.values])
                    print(f"    {th:>4s}: {v.mean():.2f} +/- {v.std():.2f}  (n={len(v)})  [{vals_str}]")
                else:
                    print(f"    {th:>4s}: N.D.")

# ===== Excel =====
excel_file = out_dir / 'cofactor_m2_quantification_FINAL.xlsx'
with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
    cols_out = ['sample', 'compound', 'cofactor_dose', 'enzyme', 'replicate', 'time_h',
                'rt_min', 'height_nRIU', 'area_nRIUs', 'conc_diluted', 'conc_original']
    quant[cols_out].to_excel(writer, sheet_name='All_Data', index=False)

    for compound, sheet in [('Tagatose', 'Tagatose_Pivot'), ('Formate', 'Formate_Pivot')]:
        sub = non_nc[non_nc['compound'] == compound]
        if len(sub) > 0:
            piv = sub.pivot_table(values='conc_original',
                                  index=['cofactor_dose', 'enzyme'],
                                  columns='time_h',
                                  aggfunc=['mean', 'std', 'count'])
            piv.to_excel(writer, sheet_name=sheet)

    # Clean summary
    rows = []
    for compound in ['Tagatose', 'Formate']:
        sub = non_nc[non_nc['compound'] == compound]
        for dose in ['D1', 'D2', 'D3', 'D4', 'D5']:
            for enz in ['RO', 'RS']:
                for th in ['6H', '12H', '24H']:
                    v = sub[(sub['cofactor_dose'] == dose) &
                            (sub['enzyme'] == enz) &
                            (sub['time_h'] == th)]['conc_original']
                    rows.append({
                        'Compound': compound,
                        'Cofactor': dose,
                        'Enzyme': enz,
                        'Time': th,
                        'Mean': round(v.mean(), 3) if len(v) > 0 else None,
                        'Std': round(v.std(), 3) if len(v) > 1 else None,
                        'N': len(v),
                        'Indiv_Values': ', '.join([f'{x:.2f}' for x in v.values]) if len(v) > 0 else 'N.D.'
                    })
    pd.DataFrame(rows).to_excel(writer, sheet_name='Clean_Summary', index=False)

print(f"\nExcel: {excel_file}")

# ===== 그래프 =====
fig, axes = plt.subplots(2, 2, figsize=(20, 14))
color_map_dose = {'D1': '#E91E63', 'D2': '#FF9800', 'D3': '#4CAF50', 'D4': '#2196F3', 'D5': '#9C27B0'}

for idx, compound in enumerate(['Tagatose', 'Formate']):
    sub = non_nc[non_nc['compound'] == compound]

    # --- 왼쪽: bar chart (D1~D5 × RO/RS × Time) ---
    ax = axes[idx, 0]
    x_pos = 0
    x_ticks = []
    x_tick_labels = []
    group_centers = {}

    for dose in ['D1', 'D2', 'D3', 'D4', 'D5']:
        group_start = x_pos
        for enz in ['RO', 'RS']:
            for th_idx, th in enumerate(['6H', '12H', '24H']):
                v = sub[(sub['cofactor_dose'] == dose) & (sub['enzyme'] == enz) & (sub['time_h'] == th)]['conc_original']
                if len(v) > 0:
                    m, s = v.mean(), v.std() if len(v) > 1 else 0
                    time_colors = {'6H': '#81C784', '12H': '#64B5F6', '24H': '#FFB74D'}
                    hatch = '' if enz == 'RO' else '///'
                    bar = ax.bar(x_pos, m, yerr=s, capsize=2, width=0.7,
                                 color=time_colors[th], edgecolor='black', linewidth=0.5,
                                 hatch=hatch, alpha=0.85)
                x_ticks.append(x_pos)
                x_tick_labels.append(f'{enz}\n{th}')
                x_pos += 1
        group_centers[dose] = (group_start + x_pos - 1) / 2
        x_pos += 0.8  # gap between doses

    ax.set_xticks(x_ticks)
    ax.set_xticklabels(x_tick_labels, fontsize=6)
    ax.set_ylabel('Concentration (original)', fontsize=11, fontweight='bold')
    ax.set_title(f'{compound} - Module 2 Cofactor (NAD)', fontsize=13, fontweight='bold')
    ax.grid(True, alpha=0.2, axis='y')

    # D label on top
    for dose, cx in group_centers.items():
        ax.text(cx, ax.get_ylim()[1] * 0.95, dose, ha='center', fontsize=10,
                fontweight='bold', color=color_map_dose[dose],
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor=color_map_dose[dose], alpha=0.8))

    # Legend for hatch
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#81C784', label='6H'), Patch(facecolor='#64B5F6', label='12H'),
        Patch(facecolor='#FFB74D', label='24H'),
        Patch(facecolor='white', edgecolor='black', label='RO (solid)'),
        Patch(facecolor='white', edgecolor='black', hatch='///', label='RS (hatch)')
    ]
    ax.legend(handles=legend_elements, fontsize=8, loc='upper right', ncol=2)

    # --- 오른쪽: time course (line plot) ---
    ax2 = axes[idx, 1]
    time_vals = [6, 12, 24]

    for dose in ['D1', 'D2', 'D3', 'D4', 'D5']:
        for enz, ls, marker in [('RO', '-', 'o'), ('RS', '--', 's')]:
            means, stds = [], []
            for th in ['6H', '12H', '24H']:
                v = sub[(sub['cofactor_dose'] == dose) & (sub['enzyme'] == enz) & (sub['time_h'] == th)]['conc_original']
                means.append(v.mean() if len(v) > 0 else np.nan)
                stds.append(v.std() if len(v) > 1 else 0)
            color = color_map_dose[dose]
            ax2.errorbar(time_vals, means, yerr=stds, marker=marker, linestyle=ls,
                         linewidth=2, markersize=7, capsize=4, label=f'{dose}_{enz}',
                         color=color, alpha=0.85)

    ax2.set_xlabel('Time (h)', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Concentration (original)', fontsize=12, fontweight='bold')
    ax2.set_title(f'{compound} - Time Course (D1~D5, RO vs RS)', fontsize=13, fontweight='bold')
    ax2.set_xticks(time_vals)
    ax2.legend(fontsize=7, ncol=2, loc='best', framealpha=0.9)
    ax2.grid(True, alpha=0.3)

plt.tight_layout()
plot_file = out_dir / 'quantification_results_plot.png'
plt.savefig(plot_file, dpi=150, bbox_inches='tight')
plt.close()
print(f"Plot: {plot_file}")
