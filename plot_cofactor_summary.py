"""
Module 2 Cofactor (NAD) - Tagatose / Formate 정량 결과 정리
3반복 평균 ± 표준편차, GO 조건만
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

out_dir = Path(r'C:\Chem32\1\DATA\260216_cofactor_m2_main_new\quantification_results')
df = pd.read_csv(out_dir / 'all_peaks_detailed.csv')

# Calibration
tag_y0, tag_a = 1220.254, 64498.76
form_y0, form_a = 10.4596, 5440.724
DF = 66.666666

# RT 매칭
p8 = df[(df['rt_min'] >= 10.5) & (df['rt_min'] <= 11.2)].copy()
p9 = df[(df['rt_min'] >= 11.3) & (df['rt_min'] <= 12.0)].copy()

p8['conc'] = ((p8['area_nRIUs'] - tag_y0) / tag_a) * DF
p8['compound'] = 'Tagatose'
p9['conc'] = ((p9['area_nRIUs'] - form_y0) / form_a) * DF
p9['compound'] = 'Formate'

quant = pd.concat([p8, p9], ignore_index=True)
quant = quant[~quant['is_nc']].copy()

# ===== 3반복 평균/표준편차 테이블 =====
summary_rows = []
for compound in ['Tagatose', 'Formate']:
    sub = quant[quant['compound'] == compound]
    for dose in ['D1', 'D2', 'D3', 'D4', 'D5']:
        for enz in ['RO', 'RS']:
            for th in ['6H', '12H', '24H']:
                v = sub[(sub['cofactor_dose'] == dose) &
                        (sub['enzyme'] == enz) &
                        (sub['time_h'] == th)]['conc']
                summary_rows.append({
                    'Compound': compound,
                    'Cofactor': dose,
                    'Enzyme': enz,
                    'Time': th,
                    'Mean': round(v.mean(), 2) if len(v) > 0 else np.nan,
                    'SD': round(v.std(), 2) if len(v) > 1 else np.nan,
                    'N': len(v),
                    'Rep1': round(v.values[0], 2) if len(v) > 0 else np.nan,
                    'Rep2': round(v.values[1], 2) if len(v) > 1 else np.nan,
                    'Rep3': round(v.values[2], 2) if len(v) > 2 else np.nan,
                })

summary = pd.DataFrame(summary_rows)

# 콘솔 출력
for compound in ['Tagatose', 'Formate']:
    s = summary[summary['Compound'] == compound]
    print(f"\n{'='*80}")
    print(f"  {compound} (g/L)   |   DF = {DF:.1f}")
    print(f"{'='*80}")
    print(f"{'Cofactor':>8} {'Enzyme':>6} {'Time':>5} | {'Mean':>8} {'SD':>8} | {'Rep1':>8} {'Rep2':>8} {'Rep3':>8} | N")
    print("-" * 80)
    for _, r in s.iterrows():
        mean_s = f"{r['Mean']:.2f}" if not np.isnan(r['Mean']) else 'N.D.'
        sd_s = f"{r['SD']:.2f}" if not np.isnan(r['SD']) else '-'
        r1 = f"{r['Rep1']:.2f}" if not np.isnan(r['Rep1']) else '-'
        r2 = f"{r['Rep2']:.2f}" if not np.isnan(r['Rep2']) else '-'
        r3 = f"{r['Rep3']:.2f}" if not np.isnan(r['Rep3']) else '-'
        print(f"{r['Cofactor']:>8} {r['Enzyme']:>6} {r['Time']:>5} | {mean_s:>8} {sd_s:>8} | {r1:>8} {r2:>8} {r3:>8} | {r['N']}")

# ===== Excel 저장 =====
excel_file = out_dir / 'cofactor_m2_FINAL_summary.xlsx'
with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
    summary.to_excel(writer, sheet_name='Summary', index=False)

    # Tagatose wide format
    for compound in ['Tagatose', 'Formate']:
        s = summary[summary['Compound'] == compound]
        wide_rows = []
        for dose in ['D1', 'D2', 'D3', 'D4', 'D5']:
            for enz in ['RO', 'RS']:
                row = {'Cofactor': dose, 'Enzyme': enz}
                for th in ['6H', '12H', '24H']:
                    r = s[(s['Cofactor'] == dose) & (s['Enzyme'] == enz) & (s['Time'] == th)]
                    if len(r) > 0:
                        m = r.iloc[0]['Mean']
                        sd = r.iloc[0]['SD']
                        row[f'{th}_Mean'] = m
                        row[f'{th}_SD'] = sd
                    else:
                        row[f'{th}_Mean'] = np.nan
                        row[f'{th}_SD'] = np.nan
                wide_rows.append(row)
        pd.DataFrame(wide_rows).to_excel(writer, sheet_name=f'{compound}_Wide', index=False)

print(f"\nExcel: {excel_file}")

# ===== 그래프 1: Tagatose Time Course (RO / RS 분리) =====
color_d = {'D1': '#E53935', 'D2': '#FB8C00', 'D3': '#43A047', 'D4': '#1E88E5', 'D5': '#8E24AA'}
time_vals = [6, 12, 24]

fig, axes = plt.subplots(1, 2, figsize=(16, 6), sharey=True)

for ax, enz in zip(axes, ['RO', 'RS']):
    tag_sub = summary[(summary['Compound'] == 'Tagatose')]
    for dose in ['D1', 'D2', 'D3', 'D4', 'D5']:
        means, sds = [], []
        for th in ['6H', '12H', '24H']:
            r = tag_sub[(tag_sub['Cofactor'] == dose) & (tag_sub['Enzyme'] == enz) & (tag_sub['Time'] == th)]
            if len(r) > 0 and not np.isnan(r.iloc[0]['Mean']):
                means.append(r.iloc[0]['Mean'])
                sds.append(r.iloc[0]['SD'] if not np.isnan(r.iloc[0]['SD']) else 0)
            else:
                means.append(np.nan)
                sds.append(0)
        ax.errorbar(time_vals, means, yerr=sds, marker='o', linestyle='-',
                    linewidth=2.5, markersize=8, capsize=5, capthick=1.5,
                    color=color_d[dose], label=dose, alpha=0.9)

    ax.set_xlabel('Time (h)', fontsize=13, fontweight='bold')
    ax.set_ylabel('Tagatose concentration', fontsize=13, fontweight='bold')
    ax.set_title(f'Tagatose - {enz}', fontsize=15, fontweight='bold')
    ax.set_xticks(time_vals)
    ax.set_xticklabels(['6H', '12H', '24H'], fontsize=12)
    ax.legend(fontsize=11, framealpha=0.9, title='NAD dose', title_fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(4, 26)

plt.tight_layout()
f1 = out_dir / 'tagatose_timecourse.png'
plt.savefig(f1, dpi=200, bbox_inches='tight')
plt.close()
print(f"Plot: {f1}")

# ===== 그래프 2: Formate Time Course (RO / RS 분리) =====
fig, axes = plt.subplots(1, 2, figsize=(16, 6), sharey=True)

for ax, enz in zip(axes, ['RO', 'RS']):
    form_sub = summary[(summary['Compound'] == 'Formate')]
    for dose in ['D1', 'D2', 'D3', 'D4', 'D5']:
        means, sds = [], []
        for th in ['6H', '12H', '24H']:
            r = form_sub[(form_sub['Cofactor'] == dose) & (form_sub['Enzyme'] == enz) & (form_sub['Time'] == th)]
            if len(r) > 0 and not np.isnan(r.iloc[0]['Mean']):
                means.append(r.iloc[0]['Mean'])
                sds.append(r.iloc[0]['SD'] if not np.isnan(r.iloc[0]['SD']) else 0)
            else:
                means.append(np.nan)
                sds.append(0)
        ax.errorbar(time_vals, means, yerr=sds, marker='s', linestyle='-',
                    linewidth=2.5, markersize=8, capsize=5, capthick=1.5,
                    color=color_d[dose], label=dose, alpha=0.9)

    ax.set_xlabel('Time (h)', fontsize=13, fontweight='bold')
    ax.set_ylabel('Formate concentration', fontsize=13, fontweight='bold')
    ax.set_title(f'Formate - {enz}', fontsize=15, fontweight='bold')
    ax.set_xticks(time_vals)
    ax.set_xticklabels(['6H', '12H', '24H'], fontsize=12)
    ax.legend(fontsize=11, framealpha=0.9, title='NAD dose', title_fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(4, 26)

plt.tight_layout()
f2 = out_dir / 'formate_timecourse.png'
plt.savefig(f2, dpi=200, bbox_inches='tight')
plt.close()
print(f"Plot: {f2}")

# ===== 그래프 3: Bar chart (D1~D5, 24H 최종 비교) =====
fig, axes = plt.subplots(1, 2, figsize=(14, 6))

for ax, compound in zip(axes, ['Tagatose', 'Formate']):
    s24 = summary[(summary['Compound'] == compound) & (summary['Time'] == '24H')]
    x = np.arange(5)
    width = 0.35

    ro_means = [s24[(s24['Cofactor'] == d) & (s24['Enzyme'] == 'RO')]['Mean'].values for d in ['D1', 'D2', 'D3', 'D4', 'D5']]
    ro_sds = [s24[(s24['Cofactor'] == d) & (s24['Enzyme'] == 'RO')]['SD'].values for d in ['D1', 'D2', 'D3', 'D4', 'D5']]
    rs_means = [s24[(s24['Cofactor'] == d) & (s24['Enzyme'] == 'RS')]['Mean'].values for d in ['D1', 'D2', 'D3', 'D4', 'D5']]
    rs_sds = [s24[(s24['Cofactor'] == d) & (s24['Enzyme'] == 'RS')]['SD'].values for d in ['D1', 'D2', 'D3', 'D4', 'D5']]

    ro_m = [v[0] if len(v) > 0 else 0 for v in ro_means]
    ro_s = [v[0] if len(v) > 0 else 0 for v in ro_sds]
    rs_m = [v[0] if len(v) > 0 else 0 for v in rs_means]
    rs_s = [v[0] if len(v) > 0 else 0 for v in rs_sds]

    bars1 = ax.bar(x - width / 2, ro_m, width, yerr=ro_s, capsize=4,
                   label='RO', color='#42A5F5', edgecolor='black', linewidth=0.8, alpha=0.85)
    bars2 = ax.bar(x + width / 2, rs_m, width, yerr=rs_s, capsize=4,
                   label='RS', color='#EF5350', edgecolor='black', linewidth=0.8, alpha=0.85)

    ax.set_xlabel('NAD Dose', fontsize=13, fontweight='bold')
    ax.set_ylabel('Concentration (24H)', fontsize=13, fontweight='bold')
    ax.set_title(f'{compound} at 24H', fontsize=15, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(['D1', 'D2', 'D3', 'D4', 'D5'], fontsize=12)
    ax.legend(fontsize=12)
    ax.grid(True, alpha=0.2, axis='y')

    # 값 표시
    for bar_group, vals in [(bars1, ro_m), (bars2, rs_m)]:
        for bar, val in zip(bar_group, vals):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 2,
                        f'{val:.1f}', ha='center', va='bottom', fontsize=8, fontweight='bold')

plt.tight_layout()
f3 = out_dir / 'bar_24H_comparison.png'
plt.savefig(f3, dpi=200, bbox_inches='tight')
plt.close()
print(f"Plot: {f3}")

# ===== 그래프 4: 전체 조건 grouped bar (Tagatose) =====
fig, ax = plt.subplots(figsize=(18, 7))
tag_s = summary[summary['Compound'] == 'Tagatose']

x_pos = 0
xticks, xlabels = [], []
time_colors = {'6H': '#66BB6A', '12H': '#42A5F5', '24H': '#FFA726'}

for dose in ['D1', 'D2', 'D3', 'D4', 'D5']:
    group_start = x_pos
    for enz in ['RO', 'RS']:
        for th in ['6H', '12H', '24H']:
            r = tag_s[(tag_s['Cofactor'] == dose) & (tag_s['Enzyme'] == enz) & (tag_s['Time'] == th)]
            m = r.iloc[0]['Mean'] if len(r) > 0 and not np.isnan(r.iloc[0]['Mean']) else 0
            sd = r.iloc[0]['SD'] if len(r) > 0 and not np.isnan(r.iloc[0]['SD']) else 0
            hatch = '' if enz == 'RO' else '///'
            ax.bar(x_pos, m, yerr=sd, capsize=3, width=0.75,
                   color=time_colors[th], edgecolor='black', linewidth=0.5,
                   hatch=hatch, alpha=0.85)
            xticks.append(x_pos)
            xlabels.append(f'{enz}\n{th}')
            x_pos += 1
        x_pos += 0.3
    # Dose label
    mid = (group_start + x_pos - 1.3) / 2
    ax.text(mid, ax.get_ylim()[1] if ax.get_ylim()[1] > 0 else 80, dose,
            ha='center', fontsize=13, fontweight='bold', color=color_d[dose])
    x_pos += 1

ax.set_xticks(xticks)
ax.set_xticklabels(xlabels, fontsize=7)
ax.set_ylabel('Tagatose concentration', fontsize=13, fontweight='bold')
ax.set_title('Tagatose - Module 2 Cofactor (NAD) | Mean ± SD (n=3)', fontsize=15, fontweight='bold')
ax.grid(True, alpha=0.2, axis='y')

from matplotlib.patches import Patch
legend_el = [
    Patch(facecolor='#66BB6A', label='6H'), Patch(facecolor='#42A5F5', label='12H'),
    Patch(facecolor='#FFA726', label='24H'),
    Patch(facecolor='white', edgecolor='black', label='RO'),
    Patch(facecolor='white', edgecolor='black', hatch='///', label='RS')
]
ax.legend(handles=legend_el, fontsize=10, ncol=5, loc='upper right')
plt.tight_layout()
f4 = out_dir / 'tagatose_all_conditions.png'
plt.savefig(f4, dpi=200, bbox_inches='tight')
plt.close()
print(f"Plot: {f4}")

# 같은 형식으로 Formate
fig, ax = plt.subplots(figsize=(18, 7))
form_s = summary[summary['Compound'] == 'Formate']
x_pos = 0
xticks, xlabels = [], []

for dose in ['D1', 'D2', 'D3', 'D4', 'D5']:
    group_start = x_pos
    for enz in ['RO', 'RS']:
        for th in ['6H', '12H', '24H']:
            r = form_s[(form_s['Cofactor'] == dose) & (form_s['Enzyme'] == enz) & (form_s['Time'] == th)]
            m = r.iloc[0]['Mean'] if len(r) > 0 and not np.isnan(r.iloc[0]['Mean']) else 0
            sd = r.iloc[0]['SD'] if len(r) > 0 and not np.isnan(r.iloc[0]['SD']) else 0
            hatch = '' if enz == 'RO' else '///'
            ax.bar(x_pos, m, yerr=sd, capsize=3, width=0.75,
                   color=time_colors[th], edgecolor='black', linewidth=0.5,
                   hatch=hatch, alpha=0.85)
            xticks.append(x_pos)
            xlabels.append(f'{enz}\n{th}')
            x_pos += 1
        x_pos += 0.3
    mid = (group_start + x_pos - 1.3) / 2
    ax.text(mid, ax.get_ylim()[1] if ax.get_ylim()[1] > 0 else 800, dose,
            ha='center', fontsize=13, fontweight='bold', color=color_d[dose])
    x_pos += 1

ax.set_xticks(xticks)
ax.set_xticklabels(xlabels, fontsize=7)
ax.set_ylabel('Formate concentration', fontsize=13, fontweight='bold')
ax.set_title('Formate - Module 2 Cofactor (NAD) | Mean ± SD (n=3)', fontsize=15, fontweight='bold')
ax.grid(True, alpha=0.2, axis='y')
ax.legend(handles=legend_el, fontsize=10, ncol=5, loc='upper right')
plt.tight_layout()
f5 = out_dir / 'formate_all_conditions.png'
plt.savefig(f5, dpi=200, bbox_inches='tight')
plt.close()
print(f"Plot: {f5}")
