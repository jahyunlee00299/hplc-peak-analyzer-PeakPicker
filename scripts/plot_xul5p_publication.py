"""
Publication-quality figure: Xul-5P yield & titer, grouped bar chart.
Single-replicate data (260506), byproduct-corrected.

Layout:
  Panel A (top):    Xul-5P yield (%, P_ratio_cor_%)
  Panel B (bottom): Xul-5P titer (mM, Xul5P_cor_mM)
  X-axis groups: AcP:Xyl molar ratio (1.0 / 1.2 / 1.5 / 2.0 / 2.5)
  Bar colors:    Xyl conc (50/100/150/200 mM)
"""

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

plt.rcParams['font.family'] = 'Arial'
plt.rcParams['axes.unicode_minus'] = False

DATA = Path(__file__).resolve().parents[1] / "results" / "260506_XylAcP" / "final_results.csv"
OUT  = DATA.parent / "fig_xul5p_publication.png"

df = pd.read_csv(DATA)
xyl_levels = [50, 100, 150, 200]
ratios     = [1.0, 1.2, 1.5, 2.0, 2.5]
colors     = ['#2166ac', '#74c476', '#fd8d3c', '#d62728', '#756bb1']

n_groups = len(xyl_levels)
n_bars   = len(ratios)
bar_w    = 0.15
x        = np.arange(n_groups)

fig, axes = plt.subplots(2, 1, figsize=(7.5, 8), sharex=True)
fig.subplots_adjust(hspace=0.10)

for ax, ycol, ylabel, title_letter in zip(
    axes,
    ['P_ratio_cor_%', 'Xul5P_cor_mM'],
    ['Xul-5P yield (%)', 'Xul-5P titer (mM)'],
    ['A', 'B'],
):
    for i, (ratio, color) in enumerate(zip(ratios, colors)):
        sub = df[df['AcP_ratio'] == ratio].set_index('Xyl_mM')
        vals = [sub.loc[x_mM, ycol] if x_mM in sub.index else 0.0 for x_mM in xyl_levels]
        offset = (i - (n_bars - 1) / 2) * bar_w
        ax.bar(x + offset, vals, bar_w,
               color=color, label=f'r = {ratio}',
               edgecolor='white', linewidth=0.4)

    ax.set_ylabel(ylabel, fontsize=12)
    ax.tick_params(labelsize=11)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.text(-0.10, 1.04, title_letter, transform=ax.transAxes,
            fontsize=14, fontweight='bold', va='top')

    if ycol == 'P_ratio_cor_%':
        ax.set_ylim(0, 120)
        ax.axhline(100, color='gray', lw=0.8, ls='--', alpha=0.6)
        ax.yaxis.set_major_formatter(mtick.PercentFormatter())
        ax.legend(title='AcP : Xyl (r)', frameon=False, fontsize=10,
                  title_fontsize=10, loc='upper right', ncol=1,
                  handlelength=1.2, handleheight=0.9, borderpad=0.4)
    else:
        ax.set_ylim(0, max(df[ycol]) * 1.18)

axes[1].set_xlabel('Initial [D-Xylose] (mM)', fontsize=12)
axes[1].set_xticks(x)
axes[1].set_xticklabels(xyl_levels)

fig.tight_layout()
fig.savefig(OUT, dpi=300, bbox_inches='tight')
print(f"Saved: {OUT}")
plt.show()
