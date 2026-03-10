# HPLC Quantification Agent Prompt
# ──────────────────────────────────────────────────────────────
# 사용법 (CEO에서 호출):
#
#   from pathlib import Path
#   prompt = Path(r"C:/Users/Jahyun/PeakPicker/scripts/hplc_quant_agent_prompt.md").read_text(encoding="utf-8")
#   prompt = prompt.replace("{{DATA_DIR}}", r"C:/Chem32/1/DATA/.../MyExperiment")
#   prompt = prompt.replace("{{COMPOUNDS}}", "ADP,D-Xylose")          # 쉼표 구분
#   prompt = prompt.replace("{{GROUPS}}", "NEW:NEW_D1,NEW_D2,NEW_D3,NEW_D4;OLD:OLD_D1,OLD_D2,OLD_D3,OLD_D4")  # 선택사항
#   prompt = prompt.replace("{{TASK_NAME}}", "AckA_Pre_260304")
#   Agent(subagent_type="general-purpose", prompt=prompt)
#
# ──────────────────────────────────────────────────────────────

당신은 HPLC 데이터 정량 분석 에이전트입니다.
아래 작업을 순서대로 수행하고, 완료 후 결과 파일 경로와 2줄 요약만 보고하세요.

## 입력 파라미터

- DATA_DIR: {{DATA_DIR}}
- COMPOUNDS: {{COMPOUNDS}}
- GROUPS: {{GROUPS}}
- TASK_NAME: {{TASK_NAME}}

## 출력 경로

- 결과 CSV: `C:/Users/Jahyun/lab-analyses/{{TASK_NAME}}_quant.csv`
- 크로마토그램 overlay PNG: `C:/Users/Jahyun/lab-analyses/{{TASK_NAME}}_overlay.png`
- 정량 바 차트 PNG: `C:/Users/Jahyun/lab-analyses/{{TASK_NAME}}_bar.png`

## 수행 작업

### Step 1. 표준곡선 로드

```python
import yaml
from pathlib import Path

method_path = r"C:/Users/Jahyun/PeakPicker/methods/hpx87h_sugars.yaml"
with open(method_path, encoding="utf-8") as f:
    method = yaml.safe_load(f)

std_curves = method["standard_curves"]
compounds_list = method.get("compounds", [])

# 요청된 화합물의 slope/intercept/rt_range 추출
target_compounds = [c.strip() for c in "{{COMPOUNDS}}".split(",")]

# RT window: compounds 섹션에서 로드 (모든 화합물에 RT 등록됨)
rt_windows = {c["name"]: (c["rt_min"], c["rt_max"]) for c in compounds_list}

calibration = {}
for comp in target_compounds:
    if comp not in std_curves:
        print(f"[WARN] {comp} 표준곡선 없음 — hpx87h_sugars.yaml standard_curves 확인 필요")
        continue
    if comp not in rt_windows:
        print(f"[WARN] {comp} RT window 없음 — hpx87h_sugars.yaml compounds 섹션 확인 필요")
        continue
    calibration[comp] = {
        "slope": std_curves[comp]["slope"],
        "intercept": std_curves[comp]["intercept"],
        "unit": std_curves[comp].get("unit", "mM"),
        "rt_min": rt_windows[comp][0],
        "rt_max": rt_windows[comp][1],
    }
    print(f"  {comp}: slope={calibration[comp]['slope']}, RT {rt_windows[comp][0]}-{rt_windows[comp][1]} min")
```

**지원 화합물** (`hpx87h_sugars.yaml` 기준):
- D-Xylose (10.8-11.5), D-Xylulose (11.5-12.0), Acetate (17.0-17.7)
- D-Ribose (12.1-12.9), D-Ribulose+D-Ribose (12.0-12.9), D-dRib-5P (6.9-7.55)
- ADP (15.5-17.0), Formate (15.5-17.0), D-Fructose (9.5-10.5)

**RT 추정 화합물** (표준 주입으로 확인 권장):
- Ribitol (12.3-13.2 추정), Formate (15.5-17.0 user-specified)

### Step 2. .D 파일 읽기 및 피크 적분

```python
import rainbow as rb
import numpy as np
from scipy.integrate import trapezoid
from scipy.signal import find_peaks
import os, re

base = r"{{DATA_DIR}}"
samples = sorted([d for d in os.listdir(base) if d.endswith(".D")])

results = []

for sname in samples:
    ds = rb.read(os.path.join(base, sname))
    if not ds.analog:
        continue
    f = ds.analog[0]
    t = f.xlabels
    y = f.data[:, 0].astype(float)

    row = {"sample": sname.replace(".D", "")}

    for comp in target_compounds:
        if comp not in calibration:
            continue

        slope = calibration[comp]["slope"]
        intercept = calibration[comp]["intercept"]

        # RT window
        rt_lo, rt_hi = rt_windows.get(comp, (14.5, 17.5))
        mask = (t >= rt_lo) & (t <= rt_hi)
        t_w, y_w = t[mask], y[mask]

        if len(t_w) < 5:
            row[f"{comp}_area"] = 0
            row[f"{comp}_conc_mM"] = 0
            continue

        # 선형 베이스라인 보정
        baseline = np.linspace(y_w[0], y_w[-1], len(y_w))
        y_c = y_w - baseline
        y_c = np.clip(y_c, 0, None)

        # 적분 (nRIU * min → nRIU*s: *60)
        area = float(trapezoid(y_c, t_w) * 60)
        conc = (area - intercept) / slope

        row[f"{comp}_rt"] = float(t_w[np.argmax(y_c)])
        row[f"{comp}_area"] = round(area, 1)
        row[f"{comp}_conc_mM"] = round(conc, 4)

    results.append(row)
```

### Step 3. CSV 저장

```python
import pandas as pd

df = pd.DataFrame(results)
out_csv = r"C:/Users/Jahyun/lab-analyses/{{TASK_NAME}}_quant.csv"
df.to_csv(out_csv, index=False, encoding="utf-8-sig")
print(df.to_string(index=False))
```

### Step 4. 샘플 메타데이터 파싱 & 실험 유형 자동 감지

샘플명에서 날짜·조건·시간·NC 여부를 추출하고, 실험 유형을 결정합니다.

```python
import re

# ── 시간 단위 패턴 ──────────────────────────────────────────────
TIME_PATTERN = re.compile(r'_?(\d+)(MIN|H|HR|SEC)(_|$)', re.IGNORECASE)

def parse_sample_meta(name):
    """
    샘플명 파싱 → dict(date, condition, time_min, is_nc, is_std)
    예:
      260304_ACKA_NEW_D1_5MIN_RE → date=260304, condition=NEW_D1, time_min=5, is_nc=False
      260225_ACP_100_90MIN       → date=260225, condition=ACP_100, time_min=90
      260212_ACP_NC_30MIN        → date=260212, condition=ACP, time_min=30, is_nc=True
    """
    n = name.upper()
    is_nc  = 'NC' in n
    is_std = 'STD' in n

    # 시간 추출
    m = TIME_PATTERN.search(name.upper())
    if m:
        val, unit = int(m.group(1)), m.group(2).upper()
        time_min = val * 60 if unit in ('H', 'HR') else (val / 60 if unit == 'SEC' else val)
    else:
        time_min = None

    # 날짜 추출 (앞 6자리 숫자)
    date_m = re.match(r'^(\d{6})_', name)
    date = date_m.group(1) if date_m else None

    # 조건: 날짜 제거, 시간부 제거, _RE/_REPEAT 접미사 제거
    cond = name
    if date:
        cond = cond[len(date)+1:]
    cond = TIME_PATTERN.sub('', cond)          # 시간부 제거
    cond = re.sub(r'_?(RE|REPEAT|RPT)$', '', cond, flags=re.IGNORECASE)
    cond = cond.strip('_')

    return {
        "sample": name,
        "date": date,
        "condition": cond,
        "time_min": time_min,
        "is_nc": is_nc,
        "is_std": is_std,
    }

meta_list = [parse_sample_meta(r["sample"]) for r in results]
df_meta = pd.DataFrame(meta_list)
df = df.merge(df_meta, on="sample", how="left")

print("\n[샘플 메타데이터]")
print(df[["sample","condition","time_min","is_nc","is_std"]].to_string(index=False))

# ── 실험 유형 자동 감지 ──────────────────────────────────────────
rxn_samples = df[~df["is_nc"] & ~df["is_std"]]
unique_times = rxn_samples["time_min"].dropna().unique()
unique_conds = rxn_samples["condition"].unique()
n_compounds   = len(target_compounds)

if len(unique_times) >= 3:
    exp_type = "timecourse"
elif n_compounds >= 3:
    exp_type = "mass_balance"
else:
    exp_type = "condition_compare"

print(f"\n[실험 유형 감지] → {exp_type}")
print(f"  unique timepoints: {sorted(unique_times)}")
print(f"  unique conditions: {list(unique_conds)}")
print(f"  compounds: {target_compounds}")
```

### Step 5. Overlay 크로마토그램

GROUPS 파라미터 우선, 없으면 감지된 조건으로 자동 그룹화합니다.

```python
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import rcParams

rcParams['font.family'] = 'Arial'
rcParams['font.size'] = 9
rcParams['axes.linewidth'] = 0.8
OKABE_ITO = ['#0072B2','#56B4E9','#009E73','#F0E442','#E69F00','#D55E00','#CC79A7','#999999']

# GROUPS 파싱 (명시된 경우 우선)
groups_raw = "{{GROUPS}}"
if groups_raw and groups_raw != "{{GROUPS}}":
    groups = {}
    for seg in groups_raw.split(";"):
        gname, members = seg.split(":")
        groups[gname.strip()] = [m.strip() for m in members.split(",")]
elif exp_type == "timecourse":
    # 조건별로 그룹 (각 그룹 내에서 시간순 정렬)
    groups = {}
    for cond in sorted(unique_conds):
        members = df[df["condition"] == cond].sort_values("time_min")["sample"].tolist()
        if members:
            groups[cond] = [s.replace(".D","") for s in members]
else:
    groups = {"All": [r["sample"] for r in results]}

for comp in target_compounds:
    rt_lo, rt_hi = calibration.get(comp, {}).get("rt_min", 14.5), calibration.get(comp, {}).get("rt_max", 17.5)
    rt_center = (rt_lo + rt_hi) / 2
    x_lo, x_hi = rt_lo - 1.5, rt_hi + 1.5

    n_groups = len(groups)
    fig, axes = plt.subplots(1, n_groups, figsize=(5.5 * n_groups, 4), sharey=False)
    if n_groups == 1:
        axes = [axes]

    for ax, (gname, members) in zip(axes, groups.items()):
        # NC 오버레이 (검정 점선)
        for sname in samples:
            label = sname.replace(".D", "")
            if "NC" in label.upper() or "STD" in label.upper():
                ds = rb.read(os.path.join(base, sname))
                if not ds.analog: continue
                f2 = ds.analog[0]
                t2, y2 = f2.xlabels, f2.data[:, 0].astype(float)
                mask2 = (t2 >= x_lo) & (t2 <= x_hi)
                ax.plot(t2[mask2], y2[mask2], color='black', lw=1.3, ls='--', label=label, zorder=5)

        for ci, member in enumerate(members):
            match = [s for s in samples if member.replace(".D","") in s]
            if not match: continue
            ds = rb.read(os.path.join(base, match[0]))
            if not ds.analog: continue
            f2 = ds.analog[0]
            t2, y2 = f2.xlabels, f2.data[:, 0].astype(float)
            mask2 = (t2 >= x_lo) & (t2 <= x_hi)
            # timecourse면 라벨에 시간 표시
            row_m = df[df["sample"] == member.replace(".D","")]
            tlabel = f"{member} ({int(row_m['time_min'].iloc[0])}min)" if not row_m.empty and row_m['time_min'].iloc[0] else member
            ax.plot(t2[mask2], y2[mask2], color=OKABE_ITO[ci % 8], lw=1.2, label=tlabel)

        ax.axvline(x=rt_center, color='red', lw=0.7, ls=':', alpha=0.5)
        ax.set_title(f"{gname} — {comp}", fontsize=10, fontweight='bold')
        ax.set_xlabel('Time (min)', fontsize=9)
        ax.set_ylabel('RI (nRIU)', fontsize=9)
        ax.legend(fontsize=8, frameon=False, loc='upper left')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

    plt.tight_layout()
    out_overlay = rf"C:/Users/Jahyun/lab-analyses/{{{{TASK_NAME}}}}_overlay_{comp.replace(' ','_').replace('-','')}.png"
    plt.savefig(out_overlay, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Overlay 저장: {out_overlay}")
```

### Step 6. 실험 유형별 정량 그래프

실험 유형에 따라 자동으로 적합한 플롯을 선택합니다.

```python
for comp in target_compounds:
    col = f"{comp}_conc_mM"
    if col not in df.columns:
        continue
    df_rxn = df[~df["is_std"]].copy()   # STD 제외, NC는 포함

    comp_safe = comp.replace(' ','_').replace('-','').replace('+','')

    # ── A. Timecourse: 조건별 라인플롯 ──────────────────────────
    if exp_type == "timecourse":
        fig, ax = plt.subplots(figsize=(7, 4))
        cond_groups = df_rxn[~df_rxn["is_nc"]].groupby("condition")
        for ci, (cond, grp) in enumerate(cond_groups):
            grp_sorted = grp.sort_values("time_min")
            ax.plot(grp_sorted["time_min"], grp_sorted[col],
                    color=OKABE_ITO[ci % 8], marker='o', lw=1.5, ms=5, label=cond)
        # NC가 있으면 수평선으로 표시
        nc_vals = df_rxn[df_rxn["is_nc"]][col].dropna()
        if not nc_vals.empty:
            ax.axhline(nc_vals.mean(), color='black', ls='--', lw=1, label=f'NC ({nc_vals.mean():.2f})')
        ax.set_xlabel('Time (min)', fontsize=10)
        ax.set_ylabel(f'[{comp}] (mM)', fontsize=10)
        ax.set_title(f'{comp} Timecourse — {{{{TASK_NAME}}}}', fontsize=11, fontweight='bold')
        ax.legend(fontsize=8, frameon=False)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        plt.tight_layout()
        out = rf"C:/Users/Jahyun/lab-analyses/{{{{TASK_NAME}}}}_timecourse_{comp_safe}.png"
        plt.savefig(out, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"Timecourse 저장: {out}")

    # ── B. Mass balance: 조건별 스택 바 ──────────────────────────
    elif exp_type == "mass_balance":
        pivot = df_rxn[~df_rxn["is_nc"]].set_index("condition")[
            [f"{c}_conc_mM" for c in target_compounds if f"{c}_conc_mM" in df.columns]
        ].clip(lower=0)
        pivot.columns = [c.replace("_conc_mM","") for c in pivot.columns]
        fig, ax = plt.subplots(figsize=(max(6, len(pivot)*0.8), 4))
        pivot.plot(kind='bar', stacked=True, ax=ax,
                   color=OKABE_ITO[:len(pivot.columns)], edgecolor='black', linewidth=0.5)
        ax.set_ylabel('Concentration (mM)', fontsize=10)
        ax.set_title(f'Mass Balance — {{{{TASK_NAME}}}}', fontsize=11, fontweight='bold')
        ax.tick_params(axis='x', rotation=45, labelsize=8)
        ax.legend(fontsize=8, frameon=False, loc='upper right')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        plt.tight_layout()
        out = rf"C:/Users/Jahyun/lab-analyses/{{{{TASK_NAME}}}}_massbalance.png"
        plt.savefig(out, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"Mass balance 저장: {out}")
        break   # mass_balance는 화합물 통합 그래프이므로 1회만

    # ── C. Condition compare: 조건별 바 차트 (시간대 subplot) ────
    else:
        time_points = sorted(df_rxn[~df_rxn["is_nc"]]["time_min"].dropna().unique())
        if not time_points:
            time_points = [None]
        n_tp = len(time_points)
        fig, axes = plt.subplots(1, n_tp, figsize=(max(5, n_tp * 4), 4), sharey=True)
        if n_tp == 1:
            axes = [axes]
        for ax, tp in zip(axes, time_points):
            if tp is None:
                sub = df_rxn[~df_rxn["is_nc"]]
            else:
                sub = df_rxn[~df_rxn["is_nc"] & (df_rxn["time_min"] == tp)]
            colors = [OKABE_ITO[i % 8] for i in range(len(sub))]
            bars = ax.bar(sub["condition"], sub[col], color=colors,
                          edgecolor='black', linewidth=0.5)
            # NC 기준선
            nc_tp = df_rxn[df_rxn["is_nc"] & (df_rxn["time_min"] == tp)][col].dropna()
            if not nc_tp.empty:
                ax.axhline(nc_tp.mean(), color='black', ls='--', lw=0.8, label='NC')
                ax.legend(fontsize=7, frameon=False)
            for bar, val in zip(bars, sub[col]):
                if val > 0:
                    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                            f'{val:.2f}', ha='center', va='bottom', fontsize=7)
            title_tp = f"{int(tp)} min" if tp else "single"
            ax.set_title(f'{title_tp}', fontsize=9, fontweight='bold')
            ax.set_ylabel(f'[{comp}] (mM)', fontsize=9)
            ax.tick_params(axis='x', rotation=40, labelsize=8)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
        fig.suptitle(f'{comp} — {{{{TASK_NAME}}}}', fontsize=11, fontweight='bold')
        plt.tight_layout()
        out = rf"C:/Users/Jahyun/lab-analyses/{{{{TASK_NAME}}}}_bar_{comp_safe}.png"
        plt.savefig(out, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"Bar chart 저장: {out}")
```

### Step 7. 완료 보고

다음 형식으로만 보고하세요:

```
결과 파일:
  - CSV: C:/Users/Jahyun/lab-analyses/{{TASK_NAME}}_quant.csv
  - Overlay: C:/Users/Jahyun/lab-analyses/{{TASK_NAME}}_overlay_*.png
  - 정량 그래프: C:/Users/Jahyun/lab-analyses/{{TASK_NAME}}_{timecourse|bar|massbalance}_*.png

실험 유형: {timecourse | condition_compare | mass_balance}
요약: {화합물} 정량 완료 ({n}개 샘플).
{핵심 관찰 1줄}
```
