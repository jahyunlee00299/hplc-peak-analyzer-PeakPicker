"""
Module 2 Cofactor (NAD) - 24H 최종 결과
D1=2mM, D2=1mM, D3=0.5mM, D4=0.25mM, D5=0.125mM (2-fold dilution)
Tukey HSD 유의성 검정 포함
"""
import sys
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
from scipy import stats
from itertools import combinations

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

out_dir = Path(r'C:\Chem32\1\DATA\260216_cofactor_m2_main_new\quantification_results')
df = pd.read_csv(out_dir / 'all_peaks_detailed.csv')

# Calibration & dilution
tag_y0, tag_a = 1220.254, 64498.76
form_y0, form_a = 10.4596, 5440.724
DF = 66.666666

# NAD 농도 매핑
NAD_MAP = {'D1': 2.0, 'D2': 1.0, 'D3': 0.5, 'D4': 0.25, 'D5': 0.125}
NAD_LABELS = {d: f'{v} mM' for d, v in NAD_MAP.items()}
DOSES = ['D1', 'D2', 'D3', 'D4', 'D5']

# RT 매칭 & 정량
p8 = df[(df['rt_min'] >= 10.5) & (df['rt_min'] <= 11.2)].copy()
p9 = df[(df['rt_min'] >= 11.3) & (df['rt_min'] <= 12.0)].copy()
p8['conc'] = ((p8['area_nRIUs'] - tag_y0) / tag_a) * DF
p8['compound'] = 'Tagatose'
p9['conc'] = ((p9['area_nRIUs'] - form_y0) / form_a) * DF
p9['compound'] = 'Formate'

quant = pd.concat([p8, p9], ignore_index=True)
quant = quant[~quant['is_nc']].copy()
quant['NAD_mM'] = quant['cofactor_dose'].map(NAD_MAP)

# 24H만
q24 = quant[quant['time_h'] == '24H'].copy()


# ===== Tukey HSD =====
def tukey_hsd(groups_data, group_names, alpha=0.05):
    """Manual Tukey HSD implementation"""
    k = len(groups_data)
    all_data = np.concatenate(groups_data)
    N = len(all_data)
    ns = [len(g) for g in groups_data]
    means = [np.mean(g) for g in groups_data]

    # MSw (within-group mean square)
    ss_within = sum(np.sum((g - np.mean(g))**2) for g in groups_data)
    df_within = N - k
    if df_within <= 0:
        return {}
    ms_within = ss_within / df_within

    results = {}
    for i, j in combinations(range(k), 2):
        if ns[i] == 0 or ns[j] == 0:
            continue
        diff = abs(means[i] - means[j])
        se = np.sqrt(ms_within * (1.0/ns[i] + 1.0/ns[j]) / 2.0)
        if se == 0:
            continue
        q_stat = diff / se

        # Approximate p-value using t-distribution (conservative)
        t_stat = q_stat / np.sqrt(2)
        df_eff = df_within
        p_val = 2 * (1 - stats.t.cdf(t_stat, df_eff))
        # Bonferroni correction
        n_comp = k * (k - 1) / 2
        p_adj = min(p_val * n_comp, 1.0)

        sig = ''
        if p_adj < 0.001:
            sig = '***'
        elif p_adj < 0.01:
            sig = '**'
        elif p_adj < 0.05:
            sig = '*'
        else:
            sig = 'ns'

        results[(group_names[i], group_names[j])] = {
            'diff': diff, 'q': q_stat, 'p_adj': p_adj, 'sig': sig,
            'mean_i': means[i], 'mean_j': means[j]
        }
    return results


def add_significance_brackets(ax, x1, x2, y, sig_text, h=0.02, color='black'):
    """Add significance bracket between two bars"""
    if sig_text == 'ns':
        return
    y_range = ax.get_ylim()[1] - ax.get_ylim()[0]
    tip = y_range * h
    ax.plot([x1, x1, x2, x2], [y, y + tip, y + tip, y], lw=1.2, color=color)
    ax.text((x1 + x2) / 2, y + tip, sig_text, ha='center', va='bottom',
            fontsize=9, fontweight='bold', color=color)


# ===== 통계 분석 =====
print("=" * 80)
print("Tukey HSD Test Results (24H)")
print("=" * 80)

hsd_results = {}
for compound in ['Tagatose', 'Formate']:
    for enz in ['RO', 'RS']:
        sub = q24[(q24['compound'] == compound) & (q24['enzyme'] == enz)]
        groups = []
        names = []
        for d in DOSES:
            vals = sub[sub['cofactor_dose'] == d]['conc'].values
            if len(vals) > 0:
                groups.append(vals)
                names.append(d)

        if len(groups) < 2:
            continue

        # One-way ANOVA first
        if all(len(g) >= 2 for g in groups):
            f_stat, anova_p = stats.f_oneway(*groups)
        else:
            f_stat, anova_p = np.nan, np.nan

        key = f"{compound}_{enz}"
        print(f"\n--- {compound} / {enz} ---")
        print(f"ANOVA: F={f_stat:.3f}, p={anova_p:.4f} {'***' if anova_p<0.001 else '**' if anova_p<0.01 else '*' if anova_p<0.05 else 'ns'}")

        hsd = tukey_hsd(groups, names)
        hsd_results[key] = hsd

        for (n1, n2), res in sorted(hsd.items()):
            print(f"  {NAD_LABELS[n1]:>8} vs {NAD_LABELS[n2]:<8}: diff={res['diff']:.2f}, p_adj={res['p_adj']:.4f} {res['sig']}")

# ===== 그래프: 24H Bar Chart with HSD =====
fig, axes = plt.subplots(2, 2, figsize=(16, 13))

for row, compound in enumerate(['Tagatose', 'Formate']):
    for col, enz in enumerate(['RO', 'RS']):
        ax = axes[row, col]
        sub = q24[(q24['compound'] == compound) & (q24['enzyme'] == enz)]

        x = np.arange(len(DOSES))
        means, sds, ns_list = [], [], []
        individual_pts = []

        for d in DOSES:
            vals = sub[sub['cofactor_dose'] == d]['conc'].values
            means.append(np.mean(vals) if len(vals) > 0 else 0)
            sds.append(np.std(vals, ddof=1) if len(vals) > 1 else 0)
            ns_list.append(len(vals))
            individual_pts.append(vals)

        # Bar + error bar
        colors = ['#E53935', '#FF7043', '#66BB6A', '#42A5F5', '#AB47BC']
        bars = ax.bar(x, means, yerr=sds, capsize=6, width=0.6,
                      color=colors, edgecolor='black', linewidth=1, alpha=0.85,
                      error_kw={'elinewidth': 1.5, 'capthick': 1.5})

        # Individual data points (jitter)
        for i, pts in enumerate(individual_pts):
            jitter = np.random.uniform(-0.12, 0.12, size=len(pts))
            ax.scatter(np.full(len(pts), i) + jitter, pts,
                       color='black', s=30, zorder=5, alpha=0.6, edgecolors='white', linewidths=0.5)

        # Mean values on bars
        for i, (m, s, n) in enumerate(zip(means, sds, ns_list)):
            if m > 0:
                ax.text(i, m + s + (ax.get_ylim()[1] if ax.get_ylim()[1] > 0 else max(means) * 1.1) * 0.02,
                        f'{m:.1f}', ha='center', va='bottom', fontsize=9, fontweight='bold')

        # HSD significance brackets
        key = f"{compound}_{enz}"
        if key in hsd_results:
            hsd = hsd_results[key]
            # Show significant pairs only (adjacent doses for clarity)
            sig_pairs = [(n1, n2, res) for (n1, n2), res in hsd.items() if res['sig'] != 'ns']
            sig_pairs.sort(key=lambda x: abs(DOSES.index(x[0]) - DOSES.index(x[1])))

            y_max = max(m + s for m, s in zip(means, sds)) if means else 0
            bracket_y = y_max * 1.08
            bracket_step = y_max * 0.08

            shown = 0
            for n1, n2, res in sig_pairs:
                if shown >= 6:  # max 6 brackets
                    break
                i1, i2 = DOSES.index(n1), DOSES.index(n2)
                add_significance_brackets(ax, i1, i2, bracket_y + shown * bracket_step,
                                          res['sig'], h=0.015)
                shown += 1

        ax.set_xticks(x)
        ax.set_xticklabels([f'{NAD_MAP[d]}\nmM' for d in DOSES], fontsize=11)
        ax.set_xlabel('NAD concentration', fontsize=12, fontweight='bold')
        ax.set_ylabel(f'{compound} conc.', fontsize=12, fontweight='bold')
        ax.set_title(f'{compound} - {enz} (24H)', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.2, axis='y')

        # y축 여유
        cur_ylim = ax.get_ylim()
        ax.set_ylim(0, cur_ylim[1] * 1.45)

plt.tight_layout(h_pad=3, w_pad=2)
f1 = out_dir / 'final_24H_with_HSD.png'
plt.savefig(f1, dpi=200, bbox_inches='tight')
plt.close()
print(f"\nPlot: {f1}")

# ===== 그래프 2: RO vs RS 같은 축에 (24H) =====
fig, axes = plt.subplots(1, 2, figsize=(16, 7))

for ax, compound in zip(axes, ['Tagatose', 'Formate']):
    x = np.arange(len(DOSES))
    width = 0.35

    for offset, enz, color, label in [(-width/2, 'RO', '#42A5F5', 'RO'),
                                       (width/2, 'RS', '#EF5350', 'RS')]:
        sub = q24[(q24['compound'] == compound) & (q24['enzyme'] == enz)]
        means, sds = [], []
        individual_pts = []
        for d in DOSES:
            vals = sub[sub['cofactor_dose'] == d]['conc'].values
            means.append(np.mean(vals) if len(vals) > 0 else 0)
            sds.append(np.std(vals, ddof=1) if len(vals) > 1 else 0)
            individual_pts.append(vals)

        bars = ax.bar(x + offset, means, width, yerr=sds, capsize=4,
                      label=label, color=color, edgecolor='black', linewidth=0.8, alpha=0.85,
                      error_kw={'elinewidth': 1.2, 'capthick': 1.2})

        for i, pts in enumerate(individual_pts):
            jitter = np.random.uniform(-0.06, 0.06, size=len(pts))
            ax.scatter(np.full(len(pts), x[i] + offset) + jitter, pts,
                       color='black', s=20, zorder=5, alpha=0.5, edgecolors='white', linewidths=0.3)

        for i, (m, s) in enumerate(zip(means, sds)):
            if m > 0:
                ax.text(x[i] + offset, m + s + 1, f'{m:.1f}',
                        ha='center', va='bottom', fontsize=8, fontweight='bold')

    ax.set_xticks(x)
    ax.set_xticklabels([f'{NAD_MAP[d]} mM' for d in DOSES], fontsize=11)
    ax.set_xlabel('NAD concentration (mM)', fontsize=13, fontweight='bold')
    ax.set_ylabel(f'{compound} concentration', fontsize=13, fontweight='bold')
    ax.set_title(f'{compound} (24H) - RO vs RS', fontsize=15, fontweight='bold')
    ax.legend(fontsize=12, framealpha=0.9)
    ax.grid(True, alpha=0.2, axis='y')

plt.tight_layout()
f2 = out_dir / 'final_24H_RO_vs_RS.png'
plt.savefig(f2, dpi=200, bbox_inches='tight')
plt.close()
print(f"Plot: {f2}")

# ===== Excel 업데이트 =====
excel_file = out_dir / 'cofactor_m2_FINAL_summary.xlsx'
with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
    # Summary 24H with NAD concentration
    rows = []
    for compound in ['Tagatose', 'Formate']:
        sub = q24[q24['compound'] == compound]
        for d in DOSES:
            for enz in ['RO', 'RS']:
                vals = sub[(sub['cofactor_dose'] == d) & (sub['enzyme'] == enz)]['conc']
                rows.append({
                    'Compound': compound,
                    'NAD_mM': NAD_MAP[d],
                    'Dose_Label': d,
                    'Enzyme': enz,
                    'Mean': round(vals.mean(), 2) if len(vals) > 0 else np.nan,
                    'SD': round(vals.std(ddof=1), 2) if len(vals) > 1 else np.nan,
                    'N': len(vals),
                    'Rep1': round(vals.values[0], 2) if len(vals) > 0 else np.nan,
                    'Rep2': round(vals.values[1], 2) if len(vals) > 1 else np.nan,
                    'Rep3': round(vals.values[2], 2) if len(vals) > 2 else np.nan,
                })
    pd.DataFrame(rows).to_excel(writer, sheet_name='24H_Summary', index=False)

    # HSD results
    hsd_rows = []
    for key, hsd in hsd_results.items():
        compound, enz = key.rsplit('_', 1)
        for (n1, n2), res in hsd.items():
            hsd_rows.append({
                'Compound': compound,
                'Enzyme': enz,
                'Group1': f'{NAD_LABELS[n1]}',
                'Group2': f'{NAD_LABELS[n2]}',
                'Mean_Diff': round(res['diff'], 2),
                'p_adjusted': round(res['p_adj'], 5),
                'Significance': res['sig']
            })
    pd.DataFrame(hsd_rows).to_excel(writer, sheet_name='Tukey_HSD', index=False)

print(f"Excel: {excel_file}")
