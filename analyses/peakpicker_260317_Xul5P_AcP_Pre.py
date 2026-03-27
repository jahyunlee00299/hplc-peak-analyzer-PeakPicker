"""
260317_Xul5P_AcP_Pre RID Chromatogram Analysis
- Xul 5P production pretest: AcP 농도 x ATP 농도 x 반응 시간
- AcP: 100, 150, 200, 300 mM
- ATP: Control(없음), 0.04, 0.2, 1, 5 mM
- 시간: 1.5h, 3h
- 분석: 크로마토그램 오버레이, 피크 면적 정량, 디스커션 그래프
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import os
import re
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy.signal import find_peaks

PEAKPICKER_SRC = r"C:\Users\Jahyun\PeakPicker\src"
sys.path.insert(0, PEAKPICKER_SRC)
from chemstation_parser import ChemstationParser

# ── 경로 설정 ──────────────────────────────────────────────────────
DATA_DIR = r"C:\Chem32\1\DATA\2. D-Xyl cascade HPLC\Xul 5P production\Pretest\260317_Xul5P_AcP_Pre"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PNG = os.path.join(SCRIPT_DIR, "peakpicker_260317_Xul5P_AcP_Pre.png")

# ── 샘플 정의 ──────────────────────────────────────────────────────
# (folder, label, acp_mM, atp_mM, time_h, is_control)
SAMPLES = [
    # Control (ATP 없음)
    ("260317_XUL5P_100_C_1_5H.D",      "100mM AcP  C 1.5h",  100, None, 1.5, True),
    ("260317_XUL5P_100_C_3H.D",        "100mM AcP  C 3h",    100, None, 3.0, True),
    # 100 mM AcP
    ("260317_XUL5P_100_0_04ATP_1_5H.D","100mM 0.04mM ATP 1.5h", 100, 0.04, 1.5, False),
    ("260317_XUL5P_100_0_04ATP_3H.D",  "100mM 0.04mM ATP 3h",   100, 0.04, 3.0, False),
    ("260317_XUL5P_100_0_2ATP_1_5H.D", "100mM 0.2mM ATP 1.5h",  100, 0.2,  1.5, False),
    ("260317_XUL5P_100_0_2ATP_3H.D",   "100mM 0.2mM ATP 3h",    100, 0.2,  3.0, False),
    ("260317_XUL5P_100_1ATP_1_5H.D",   "100mM 1mM ATP 1.5h",    100, 1.0,  1.5, False),
    ("260317_XUL5P_100_1ATP_3H.D",     "100mM 1mM ATP 3h",      100, 1.0,  3.0, False),
    ("260317_XUL5P_100_5ATP_1_5H.D",   "100mM 5mM ATP 1.5h",    100, 5.0,  1.5, False),
    ("260317_XUL5P_100_5ATP_3H.D",     "100mM 5mM ATP 3h",      100, 5.0,  3.0, False),
    # 150 mM AcP
    ("260317_XUL5P_150_5ATP_C_1_5H.D", "150mM AcP C 1.5h",     150, None, 1.5, True),
    ("260317_XUL5P_150_5ATP_C_3H.D",   "150mM AcP C 3h",       150, None, 3.0, True),
    ("260317_XUL5P_150_5ATP__1_5H.D",  "150mM 5mM ATP 1.5h",   150, 5.0,  1.5, False),
    ("260317_XUL5P_150_5ATP__3H.D",    "150mM 5mM ATP 3h",     150, 5.0,  3.0, False),
    # 200 mM AcP
    ("260317_XUL5P_200_5ATP_C_1_5H.D", "200mM AcP C 1.5h",     200, None, 1.5, True),
    ("260317_XUL5P_200_5ATP_C_3H.D",   "200mM AcP C 3h",       200, None, 3.0, True),
    ("260317_XUL5P_200_5ATP_1_5H.D",   "200mM 5mM ATP 1.5h",   200, 5.0,  1.5, False),
    ("260317_XUL5P_200_5ATP_3H.D",     "200mM 5mM ATP 3h",     200, 5.0,  3.0, False),
    # 300 mM AcP
    ("260317_XUL5P_300_5ATP_C_1_5H.D", "300mM AcP C 1.5h",     300, None, 1.5, True),
    ("260317_XUL5P_300_5ATP_C_3H.D",   "300mM AcP C 3h",       300, None, 3.0, True),
    ("260317_XUL5P_300_5ATP_1_5H.D",   "300mM 5mM ATP 1.5h",   300, 5.0,  1.5, False),
    ("260317_XUL5P_300_5ATP_3H.D",     "300mM 5mM ATP 3h",     300, 5.0,  3.0, False),
]

# ── RT 윈도우 (이전 실험 기반, 조정 가능) ──────────────────────────
KNOWN_WINDOWS = {
    "Product":   (7.00,  7.55),   # Xul-5P product peak (RT ~7.25 min, confirmed)
    "Pi":        (9.00,  9.80),   # Inorganic phosphate (RT ~9.4 min)
    "D-Xylose":  (10.80, 11.50),  # Substrate (RT ~11.1 min)
    "D-Xylulose":(11.50, 12.10),
    "Acetate":   (17.00, 17.80),  # Acetate (RT ~17.3 min)
}

WINDOW_COLORS = {
    "Product":    "#e8d5f0",
    "Pi":         "#d5f0e8",
    "D-Xylose":   "#fff0cc",
    "D-Xylulose": "#ffe0cc",
    "Acetate":    "#f0d5d5",
}

# ATP 농도별 색상
ATP_COLORS = {
    None: "#888888",   # Control
    0.04: "#aec7e8",
    0.2:  "#1f77b4",
    1.0:  "#ff7f0e",
    5.0:  "#d62728",
}

# AcP 농도별 색상
ACP_COLORS = {
    100: "#1f77b4",
    150: "#ff7f0e",
    200: "#2ca02c",
    300: "#d62728",
}


def load_sample(folder_name):
    ch_path = os.path.join(DATA_DIR, folder_name, "RID1A.ch")
    if not os.path.exists(ch_path):
        print(f"  [WARN] 파일 없음: {ch_path}")
        return None, None
    parser = ChemstationParser(ch_path)
    time, intensity = parser.read()
    return time, intensity


def get_area(time, intensity, rt_lo, rt_hi):
    mask = (time >= rt_lo) & (time <= rt_hi)
    if mask.sum() < 2:
        return 0.0
    return float(np.trapz(intensity[mask], time[mask] * 60))  # nRIU*s


def detect_peaks(time, intensity, prominence=300, distance_pts=40):
    peaks, _ = find_peaks(intensity, prominence=prominence, distance=distance_pts)
    return [(float(time[p]), float(intensity[p])) for p in peaks]


def _add_rt_windows(ax, y_top=None):
    for cmp, (lo, hi) in KNOWN_WINDOWS.items():
        ax.axvspan(lo, hi, alpha=0.15, color=WINDOW_COLORS[cmp], zorder=0)
        if y_top is not None:
            ax.text((lo + hi) / 2, y_top * 0.97, cmp,
                    ha="center", va="top", fontsize=6, color="#555555",
                    rotation=90, clip_on=True)


def main():
    print("=" * 65)
    print("260317_Xul5P_AcP_Pre - RID Chromatogram Analysis")
    print("=" * 65)

    # ── 데이터 로드 ────────────────────────────────────────────────
    loaded = {}
    for folder, label, acp, atp, time_h, is_ctrl in SAMPLES:
        t, sig = load_sample(folder)
        if t is not None:
            loaded[folder] = {
                "time": t, "intensity": sig, "label": label,
                "acp": acp, "atp": atp, "time_h": time_h, "is_ctrl": is_ctrl
            }
            print(f"  OK  {label:35s}  {len(t):5d} pts")
        else:
            print(f"  FAIL {label}")

    if not loaded:
        print("로드된 샘플 없음.")
        return

    # ── 피크 면적 계산 ─────────────────────────────────────────────
    area_table = {}
    for folder, d in loaded.items():
        areas = {cmp: get_area(d["time"], d["intensity"], lo, hi)
                 for cmp, (lo, hi) in KNOWN_WINDOWS.items()}
        area_table[folder] = areas

    # ── 면적 테이블 출력 ───────────────────────────────────────────
    print(f"\n{'Sample':35s}", end="")
    for cmp in KNOWN_WINDOWS:
        print(f"  {cmp:10s}", end="")
    print()
    print("-" * (35 + 14 * len(KNOWN_WINDOWS)))
    for folder, d in loaded.items():
        print(f"{d['label']:35s}", end="")
        for cmp in KNOWN_WINDOWS:
            print(f"  {area_table[folder][cmp]:10.0f}", end="")
        print()

    # ── 피크 검출 요약 ─────────────────────────────────────────────
    print("\n--- 검출된 주요 피크 RT (prominence >= 300) ---")
    for folder, d in loaded.items():
        peaks = detect_peaks(d["time"], d["intensity"])
        peak_str = "  ".join([f"{rt:.2f}" for rt, _ in peaks])
        print(f"  {d['label']:35s}: {peak_str}")

    # ==============================================================
    # 그래프 1: 크로마토그램 오버레이
    # 상단 2패널: 100mM AcP, ATP 농도별 (1.5h / 3h)
    # 하단 2패널: 5mM ATP, AcP 농도별 (1.5h / 3h)
    # ==============================================================
    fig1, axes = plt.subplots(2, 2, figsize=(20, 14))
    fig1.suptitle(
        "260317 Xul-5P Production Pretest - RID Chromatogram Overlay\n"
        "HPX-87H | 5 mM H2SO4 | 0.5 mL/min | 65C | RID",
        fontsize=13, fontweight="bold"
    )

    def _plot_overlay(ax, samples_list, title):
        for f, d, color, ls, lw, zo in samples_list:
            ax.plot(d["time"], d["intensity"], color=color, linestyle=ls,
                    linewidth=lw, label=d["label"], zorder=zo)
        y_top = ax.get_ylim()[1]
        _add_rt_windows(ax, y_top)
        ax.set_xlim(5, 20)
        ax.set_title(title, fontsize=10, fontweight="bold")
        ax.set_xlabel("Retention Time (min)", fontsize=9)
        ax.set_ylabel("RID Signal (nRIU)", fontsize=9)
        ax.legend(fontsize=7, loc="upper right", ncol=1)

    # ── 패널 [0,0]: 100mM AcP, ATP 농도별, 1.5h ───────────────────
    ax = axes[0, 0]
    panel_samples = []
    # Control
    ctrl_1h5 = [(f, d) for f, d in loaded.items()
                if d["acp"] == 100 and d["is_ctrl"] and abs(d["time_h"] - 1.5) < 0.1]
    for f, d in ctrl_1h5:
        panel_samples.append((f, d, "#888888", "--", 1.0, 1))
    # ATP 농도별
    for atp_v in [0.04, 0.2, 1.0, 5.0]:
        match = [(f, d) for f, d in loaded.items()
                 if d["acp"] == 100 and d["atp"] == atp_v and abs(d["time_h"] - 1.5) < 0.1]
        for f, d in match:
            panel_samples.append((f, d, ATP_COLORS[atp_v], "-", 1.5, 2))
    _plot_overlay(ax, panel_samples, "100 mM AcP, ATP conc. effect (1.5 h)")

    # ── 패널 [0,1]: 100mM AcP, ATP 농도별, 3h ────────────────────
    ax = axes[0, 1]
    panel_samples = []
    ctrl_3h = [(f, d) for f, d in loaded.items()
               if d["acp"] == 100 and d["is_ctrl"] and abs(d["time_h"] - 3.0) < 0.1]
    for f, d in ctrl_3h:
        panel_samples.append((f, d, "#888888", "--", 1.0, 1))
    for atp_v in [0.04, 0.2, 1.0, 5.0]:
        match = [(f, d) for f, d in loaded.items()
                 if d["acp"] == 100 and d["atp"] == atp_v and abs(d["time_h"] - 3.0) < 0.1]
        for f, d in match:
            panel_samples.append((f, d, ATP_COLORS[atp_v], "-", 1.5, 2))
    _plot_overlay(ax, panel_samples, "100 mM AcP, ATP conc. effect (3 h)")

    # ── 패널 [1,0]: 5mM ATP, AcP 농도별, 1.5h ───────────────────
    ax = axes[1, 0]
    panel_samples = []
    for acp_v in [100, 150, 200, 300]:
        # control
        ctrl = [(f, d) for f, d in loaded.items()
                if d["acp"] == acp_v and d["is_ctrl"] and abs(d["time_h"] - 1.5) < 0.1]
        for f, d in ctrl:
            panel_samples.append((f, d, ACP_COLORS[acp_v], "--", 1.0, 1))
        # 5mM ATP
        rxn = [(f, d) for f, d in loaded.items()
               if d["acp"] == acp_v and d["atp"] == 5.0 and abs(d["time_h"] - 1.5) < 0.1]
        for f, d in rxn:
            panel_samples.append((f, d, ACP_COLORS[acp_v], "-", 1.8, 2))
    _plot_overlay(ax, panel_samples, "5 mM ATP, AcP conc. effect (1.5 h)\n(dashed=Control, solid=+ATP)")

    # ── 패널 [1,1]: 5mM ATP, AcP 농도별, 3h ────────────────────
    ax = axes[1, 1]
    panel_samples = []
    for acp_v in [100, 150, 200, 300]:
        ctrl = [(f, d) for f, d in loaded.items()
                if d["acp"] == acp_v and d["is_ctrl"] and abs(d["time_h"] - 3.0) < 0.1]
        for f, d in ctrl:
            panel_samples.append((f, d, ACP_COLORS[acp_v], "--", 1.0, 1))
        rxn = [(f, d) for f, d in loaded.items()
               if d["acp"] == acp_v and d["atp"] == 5.0 and abs(d["time_h"] - 3.0) < 0.1]
        for f, d in rxn:
            panel_samples.append((f, d, ACP_COLORS[acp_v], "-", 1.8, 2))
    _plot_overlay(ax, panel_samples, "5 mM ATP, AcP conc. effect (3 h)\n(dashed=Control, solid=+ATP)")

    plt.tight_layout(rect=[0, 0, 1, 0.94])
    png1 = OUTPUT_PNG.replace(".png", "_chromatogram.png")
    plt.savefig(png1, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\nChromatogram saved: {png1}")

    # ==============================================================
    # 그래프 2: Discussion 그래프
    # (a) ATP 농도 vs Xul-5P 면적 (100mM AcP, 1.5h vs 3h)
    # (b) AcP 농도 vs Xul-5P 면적 (5mM ATP, 1.5h vs 3h)
    # (c) 시간 비교 bar chart (모든 조건, Xul-5P)
    # (d) D-Xylose 소비 vs Xul-5P 생성 scatter
    # ==============================================================
    fig2, axes2 = plt.subplots(2, 2, figsize=(16, 12))
    fig2.suptitle(
        "260317 Xul-5P Production - Discussion Graphs",
        fontsize=13, fontweight="bold"
    )

    # ── (a) ATP 농도 vs Xul-5P 면적 (AcP=100mM) ──────────────────
    ax = axes2[0, 0]
    atp_vals_ordered = [0.04, 0.2, 1.0, 5.0]
    atp_labels = ["0.04", "0.2", "1", "5"]

    for th, marker, ls in [(1.5, "o", "-"), (3.0, "s", "--")]:
        areas_15 = []
        for atp_v in atp_vals_ordered:
            match = [f for f, d in loaded.items()
                     if d["acp"] == 100 and d["atp"] == atp_v
                     and abs(d["time_h"] - th) < 0.1 and not d["is_ctrl"]]
            if match:
                areas_15.append(area_table[match[0]]["Product"])
            else:
                areas_15.append(np.nan)
        ax.plot(range(len(atp_vals_ordered)), areas_15,
                marker=marker, linestyle=ls, linewidth=1.8, markersize=7,
                color="#1f77b4" if th == 1.5 else "#d62728",
                label=f"{th}h")

    # Control 수평선
    ctrl_samples_100 = [f for f, d in loaded.items()
                        if d["acp"] == 100 and d["is_ctrl"]]
    if ctrl_samples_100:
        ctrl_avg = np.mean([area_table[f]["Product"] for f in ctrl_samples_100])
        ax.axhline(ctrl_avg, color="gray", linestyle=":", linewidth=1.2,
                   label="Control (avg)")

    ax.set_xticks(range(len(atp_vals_ordered)))
    ax.set_xticklabels(atp_labels)
    ax.set_xlabel("ATP Concentration (mM)", fontsize=10)
    ax.set_ylabel("Product Peak Area (nRIU*s)", fontsize=10)
    ax.set_title("(a) ATP conc. effect on Product\n(AcP = 100 mM)", fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # ── (b) AcP 농도 vs Xul-5P 면적 (ATP=5mM) ───────────────────
    ax = axes2[0, 1]
    acp_vals_ordered = [100, 150, 200, 300]

    for th, marker, ls, color in [(1.5, "o", "-", "#1f77b4"),
                                   (3.0, "s", "--", "#d62728")]:
        areas_b = []
        for acp_v in acp_vals_ordered:
            match = [f for f, d in loaded.items()
                     if d["acp"] == acp_v and d["atp"] == 5.0
                     and abs(d["time_h"] - th) < 0.1 and not d["is_ctrl"]]
            if match:
                areas_b.append(area_table[match[0]]["Product"])
            else:
                areas_b.append(np.nan)
        ax.plot(acp_vals_ordered, areas_b,
                marker=marker, linestyle=ls, linewidth=1.8, markersize=7,
                color=color, label=f"{th}h")

    ax.set_xlabel("AcP Concentration (mM)", fontsize=10)
    ax.set_ylabel("Product Peak Area (nRIU*s)", fontsize=10)
    ax.set_title("(b) AcP conc. effect on Product\n(ATP = 5 mM)", fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # ── (c) 반응 시간 비교 bar chart (5mM ATP, 모든 AcP 농도) ─────
    ax = axes2[1, 0]
    x = np.arange(len(acp_vals_ordered))
    width = 0.35
    bars_1h5 = []
    bars_3h = []
    for acp_v in acp_vals_ordered:
        m1 = [f for f, d in loaded.items()
              if d["acp"] == acp_v and d["atp"] == 5.0
              and abs(d["time_h"] - 1.5) < 0.1]
        m3 = [f for f, d in loaded.items()
              if d["acp"] == acp_v and d["atp"] == 5.0
              and abs(d["time_h"] - 3.0) < 0.1]
        bars_1h5.append(area_table[m1[0]]["Product"] if m1 else 0)
        bars_3h.append(area_table[m3[0]]["Product"] if m3 else 0)

    ax.bar(x - width/2, bars_1h5, width, label="1.5 h", color="#5aade0", alpha=0.85)
    ax.bar(x + width/2, bars_3h,  width, label="3 h",   color="#e05a5a", alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{v} mM" for v in acp_vals_ordered])
    ax.set_xlabel("AcP Concentration", fontsize=10)
    ax.set_ylabel("Product Peak Area (nRIU*s)", fontsize=10)
    ax.set_title("(c) Time comparison: 1.5h vs 3h\n(ATP = 5 mM)", fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, axis="y")

    # ── (d) D-Xylose 감소 vs Xul-5P 생성 scatter ─────────────────
    ax = axes2[1, 1]
    rxn_samples = [(f, d) for f, d in loaded.items() if not d["is_ctrl"]]
    ctrl_map = {}
    for f, d in loaded.items():
        if d["is_ctrl"]:
            key = (d["acp"], d["time_h"])
            if key not in ctrl_map:
                ctrl_map[key] = area_table[f]

    scatter_x, scatter_y, scatter_colors, scatter_labels = [], [], [], []
    for f, d in rxn_samples:
        ctrl_key = (d["acp"], d["time_h"])
        ctrl_areas = ctrl_map.get(ctrl_key)
        if ctrl_areas is None:
            continue
        xyl_decrease = ctrl_areas["D-Xylose"] - area_table[f]["D-Xylose"]
        xul5p_increase = area_table[f]["Product"] - ctrl_areas["Product"]
        scatter_x.append(xyl_decrease)
        scatter_y.append(xul5p_increase)
        scatter_colors.append(ACP_COLORS.get(d["acp"], "#333333"))
        scatter_labels.append(d["label"])

    if scatter_x:
        ax.scatter(scatter_x, scatter_y, c=scatter_colors, s=60, alpha=0.8,
                   edgecolors="white", linewidth=0.5, zorder=3)
        # AcP 범례
        for acp_v, color in ACP_COLORS.items():
            if acp_v is not None:
                ax.scatter([], [], c=color, s=50, label=f"AcP {acp_v} mM")
        ax.axhline(0, color="gray", linewidth=0.8, linestyle=":")
        ax.axvline(0, color="gray", linewidth=0.8, linestyle=":")

    ax.set_xlabel("D-Xylose Decrease (vs control, nRIU*s)", fontsize=10)
    ax.set_ylabel("Product Increase (vs control, nRIU*s)", fontsize=10)
    ax.set_title("(d) D-Xylose consumption vs Product formation", fontsize=10)
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(True, alpha=0.3)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    png2 = OUTPUT_PNG.replace(".png", "_discussion.png")
    plt.savefig(png2, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"디스커션 그래프 저장: {png2}")
    print("\n완료.")


if __name__ == "__main__":
    main()
