"""
260302_rpm_buffer 조건별·시간별 농도 추이 시각화
"""
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

DATA = Path(r"C:\Chem32\1\DATA\260302_rpm_buffer")
df = pd.read_csv(DATA / "quantification_results_mM.csv")

# 조건 목록
conditions = sorted(df['condition'].unique())
time_order = [0, 3, 6, 16]
compounds = ['Galactose', 'Galactitol', 'Formate']
colors = {'Galactose': '#e74c3c', 'Galactitol': '#2ecc71', 'Formate': '#3498db'}

# ===== 1) 전체 조건 비교 그래프 =====
fig, axes = plt.subplots(1, 3, figsize=(20, 7))

for idx, comp in enumerate(compounds):
    ax = axes[idx]
    col = f'{comp}_conc_mM'

    for cond in conditions:
        cond_df = df[df['condition'] == cond].sort_values('time_h')
        times = cond_df['time_h'].values
        concs = cond_df[col].values
        ax.plot(times, concs, 'o-', label=cond, markersize=6, linewidth=1.5)

    ax.set_xlabel('Time (h)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Concentration (mM)', fontsize=12, fontweight='bold')
    ax.set_title(comp, fontsize=14, fontweight='bold', color=colors[comp])
    ax.set_xticks(time_order)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7, loc='best', ncol=2)

plt.suptitle('260302 RPM Buffer - 조건별 시간 추이', fontsize=16, fontweight='bold', y=1.02)
plt.tight_layout()
plt.savefig(DATA / "condition_timecourse_all.png", dpi=150, bbox_inches='tight')
plt.close()
print("Saved: condition_timecourse_all.png")


# ===== 2) 조건별 개별 그래프 (세 물질 같이) =====
n_cond = len(conditions)
ncols = 3
nrows = (n_cond + ncols - 1) // ncols

fig, axes = plt.subplots(nrows, ncols, figsize=(7*ncols, 5*nrows))
axes = axes.flatten()

for i, cond in enumerate(conditions):
    ax = axes[i]
    cond_df = df[df['condition'] == cond].sort_values('time_h')
    times = cond_df['time_h'].values

    for comp in compounds:
        concs = cond_df[f'{comp}_conc_mM'].values
        ax.plot(times, concs, 'o-', label=comp, color=colors[comp],
                markersize=8, linewidth=2)
        # 값 표시
        for t, c in zip(times, concs):
            if c > 0:
                ax.annotate(f'{c:.1f}', (t, c), textcoords='offset points',
                           xytext=(0, 8), fontsize=7, ha='center',
                           color=colors[comp])

    ax.set_xlabel('Time (h)', fontsize=10)
    ax.set_ylabel('Conc (mM)', fontsize=10)
    ax.set_title(cond, fontsize=12, fontweight='bold')
    ax.set_xticks(time_order)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

# 빈 subplot 제거
for j in range(i+1, len(axes)):
    axes[j].set_visible(False)

plt.suptitle('260302 RPM Buffer - 각 조건별 세 물질 농도 변화',
             fontsize=16, fontweight='bold', y=1.01)
plt.tight_layout()
plt.savefig(DATA / "condition_timecourse_individual.png", dpi=150, bbox_inches='tight')
plt.close()
print("Saved: condition_timecourse_individual.png")


# ===== 3) 요약 테이블 깔끔하게 출력 =====
print("\n" + "="*110)
print("조건별·시간별 농도 (mM)")
print("="*110)
print(f"{'Condition':<20} {'Time':>5}  {'DF':>4}  {'Galactose':>12} {'Galactitol':>12} {'Formate':>12}")
print("-"*110)

prev_cond = None
for _, row in df.sort_values(['condition', 'time_h']).iterrows():
    cond = row['condition']
    if prev_cond and cond != prev_cond:
        print("-"*110)
    prev_cond = cond

    df_val = 200 if row['time_h'] == 0 else 20
    gal = row['Galactose_conc_mM']
    galtol = row['Galactitol_conc_mM']
    form = row['Formate_conc_mM']

    gal_s = f"{gal:.2f}" if gal > 0 else "n.d."
    galtol_s = f"{galtol:.2f}" if galtol > 0 else "n.d."
    form_s = f"{form:.2f}" if form > 0 else "n.d."

    print(f"{cond:<20} {row['time_h']:>4}h  {df_val:>4}x  {gal_s:>12} {galtol_s:>12} {form_s:>12}")

print("="*110)
print("n.d. = not detected (area <= 0 or below noise)")
