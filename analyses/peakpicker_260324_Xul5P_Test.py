"""
260324_Xul5P_Test RID Chromatogram Analysis
- XylA:XylB ratio optimization + substrate conc optimization + ATP conc optimization
- fed-batch experiments included
- NE = negative control (no enzyme)
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.signal import find_peaks

PEAKPICKER_SRC = r"C:\Users\Jahyun\PeakPicker\src"
sys.path.insert(0, PEAKPICKER_SRC)
from chemstation_parser import ChemstationParser

# -- Path setup ---------------------------------------------------------------
DATA_DIR = r"C:\Chem32\1\DATA\2. D-Xyl cascade HPLC\Xul 5P production\Pretest\260324_Xul5P_Test"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PNG = os.path.join(SCRIPT_DIR, "peakpicker_260324_Xul5P_Test.png")
OUTPUT_XLSX = os.path.join(SCRIPT_DIR, "260324_Xul5P_Test_results.xlsx")

# -- Sample definitions -------------------------------------------------------
# (folder, label, xyla_ratio, xylb_ratio, xyl_mM, acp_mM, atp_mM, time_h, condition)
SAMPLES = [
    # Enzyme ratio comparison (100XYL, 100ACP, 1ATP, 1.5h)
    ("XUL5P_1X1X_100XYL_100ACP_1ATP_1_5H.D", "1X:1X 100Xyl 100AcP 1ATP 1.5h", 1, 1, 100, 100, 1.0, 1.5, "enzyme_ratio"),
    ("XUL5P_1X3X_100XYL_100ACP_1ATP_1_5H.D", "1X:3X 100Xyl 100AcP 1ATP 1.5h", 1, 3, 100, 100, 1.0, 1.5, "enzyme_ratio"),
    ("XUL5P_3X1X_100XYL_100ACP_1ATP_1_5H.D", "3X:1X 100Xyl 100AcP 1ATP 1.5h", 3, 1, 100, 100, 1.0, 1.5, "enzyme_ratio"),
    ("XUL5P_3X3X_100XYL_100ACP_1ATP_1_5H.D", "3X:3X 100Xyl 100AcP 1ATP 1.5h", 3, 3, 100, 100, 1.0, 1.5, "enzyme_ratio"),
    # ATP concentration optimization (3X:3X, 100XYL, 120ACP, 1.5h)
    ("XUL5P_3X3X_100XYL_120ACP_0_125ATP_1_5H.D", "3X:3X 100Xyl 120AcP 0.125ATP 1.5h", 3, 3, 100, 120, 0.125, 1.5, "atp_conc"),
    ("XUL5P_3X3X_100XYL_120ACP_0_25ATP_1_5H.D",  "3X:3X 100Xyl 120AcP 0.25ATP 1.5h",  3, 3, 100, 120, 0.25,  1.5, "atp_conc"),
    ("XUL5P_3X3X_100XYL_120ACP_0_5ATP_1_5H.D",   "3X:3X 100Xyl 120AcP 0.5ATP 1.5h",   3, 3, 100, 120, 0.5,   1.5, "atp_conc"),
    ("XUL5P_3X3X_100XYL_120ACP_1ATP_1_5H.D",     "3X:3X 100Xyl 120AcP 1ATP 1.5h",     3, 3, 100, 120, 1.0,   1.5, "atp_conc"),
    # Substrate concentration optimization (3X:3X, 1ATP, 1.5h, AcP:Xyl=1.2x)
    ("XUL5P_3X3X_100XYL_150ACP_1ATP_1_5H.D", "3X:3X 100Xyl 150AcP 1ATP 1.5h", 3, 3, 100, 150, 1.0, 1.5, "substrate_conc"),
    ("XUL5P_3X3X_200XYL_240ACP_1ATP_1_5H.D", "3X:3X 200Xyl 240AcP 1ATP 1.5h", 3, 3, 200, 240, 1.0, 1.5, "substrate_conc"),
    ("XUL5P_3X3X_25XYL_30ACP_1ATP_1_5H.D",   "3X:3X 25Xyl 30AcP 1ATP 1.5h",   3, 3,  25,  30, 1.0, 1.5, "substrate_conc"),
    ("XUL5P_3X3X_50XYL_60ACP_1ATP_1_5H.D",   "3X:3X 50Xyl 60AcP 1ATP 1.5h",   3, 3,  50,  60, 1.0, 1.5, "substrate_conc"),
    # FED batch
    ("XUL5P_FED_ACP_DW_30M.D",       "FED AcP DW 30min",      3, 3, None, None, None, 0.5, "fed_batch"),
    ("XUL5P_FED_EM2_ACP_DW_30M.D",   "FED EM2 AcP DW 30min",  3, 3, None, None, None, 0.5, "fed_batch"),
    ("XUL5P_FED_XYLB3X_DW_30M.D",    "FED XylB3X DW 30min",   3, 3, None, None, None, 0.5, "fed_batch"),
    # NE (no enzyme) controls
    ("XUL5P_NE_100XYL_100ACP_1ATP_1_5H.D", "NE 100Xyl 100AcP 1ATP 1.5h", 0, 0, 100, 100, 1.0, 1.5, "NE"),
    ("XUL5P_NE_100XYL_120ACP_1ATP_1_5H.D", "NE 100Xyl 120AcP 1ATP 1.5h", 0, 0, 100, 120, 1.0, 1.5, "NE"),
    ("XUL5P_NE_200XYL_240ACP_1ATP_1_5H.D", "NE 200Xyl 240AcP 1ATP 1.5h", 0, 0, 200, 240, 1.0, 1.5, "NE"),
    ("XUL5P_NE_25XYL_30ACP_1ATP_1_5H.D",   "NE 25Xyl 30AcP 1ATP 1.5h",   0, 0,  25,  30, 1.0, 1.5, "NE"),
    ("XUL5P_NE_50XYL_60ACP_1ATP_1_5H.D",   "NE 50Xyl 60AcP 1ATP 1.5h",   0, 0,  50,  60, 1.0, 1.5, "NE"),
]

# -- RT windows ---------------------------------------------------------------
KNOWN_WINDOWS = {
    "Product":   (7.00,  7.55),
    "Pi":        (9.00,  9.80),
    "D-Xylose":  (10.80, 11.50),
    "D-Xylulose":(11.50, 12.10),
    "Acetate":   (17.00, 17.80),
}

WINDOW_COLORS = {
    "Product":    "#e8d5f0",
    "Pi":         "#d5f0e8",
    "D-Xylose":   "#fff0cc",
    "D-Xylulose": "#ffe0cc",
    "Acetate":    "#f0d5d5",
}

# -- Color maps ----------------------------------------------------------------
ENZYME_RATIO_COLORS = {
    (1, 1): "#aec7e8",
    (1, 3): "#1f77b4",
    (3, 1): "#ff7f0e",
    (3, 3): "#d62728",
}

ATP_COLORS = {
    0.125: "#aec7e8",
    0.25:  "#1f77b4",
    0.5:   "#ff7f0e",
    1.0:   "#d62728",
}

SUBSTRATE_COLORS = {
    25:  "#aec7e8",
    50:  "#1f77b4",
    100: "#ff7f0e",
    200: "#d62728",
}

FED_COLORS = {
    "FED AcP DW 30min":     "#1f77b4",
    "FED EM2 AcP DW 30min": "#ff7f0e",
    "FED XylB3X DW 30min":  "#2ca02c",
}


def load_sample(folder_name):
    ch_path = os.path.join(DATA_DIR, folder_name, "RID1A.ch")
    if not os.path.exists(ch_path):
        print(f"  [WARN] File not found: {ch_path}")
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
    print("260324_Xul5P_Test - RID Chromatogram Analysis")
    print("=" * 65)

    # -- Load data -------------------------------------------------------------
    loaded = {}
    for folder, label, xyla, xylb, xyl, acp, atp, time_h, cond in SAMPLES:
        t, sig = load_sample(folder)
        if t is not None:
            loaded[folder] = {
                "time": t, "intensity": sig, "label": label,
                "xyla": xyla, "xylb": xylb, "xyl": xyl,
                "acp": acp, "atp": atp, "time_h": time_h, "condition": cond,
            }
            print(f"  OK  {label:45s}  {len(t):5d} pts")
        else:
            print(f"  FAIL {label}")

    if not loaded:
        print("No samples loaded.")
        return

    # -- Peak area calculation -------------------------------------------------
    area_table = {}
    for folder, d in loaded.items():
        areas = {cmp: get_area(d["time"], d["intensity"], lo, hi)
                 for cmp, (lo, hi) in KNOWN_WINDOWS.items()}
        area_table[folder] = areas

    # -- Area table printout ---------------------------------------------------
    print(f"\n{'Sample':45s}", end="")
    for cmp in KNOWN_WINDOWS:
        print(f"  {cmp:>12s}", end="")
    print()
    print("-" * (45 + 14 * len(KNOWN_WINDOWS)))
    for folder, d in loaded.items():
        print(f"{d['label']:45s}", end="")
        for cmp in KNOWN_WINDOWS:
            print(f"  {area_table[folder][cmp]:12.0f}", end="")
        print()

    # -- Peak detection summary ------------------------------------------------
    print("\n--- Detected peaks (prominence >= 300) ---")
    for folder, d in loaded.items():
        peaks = detect_peaks(d["time"], d["intensity"])
        peak_str = "  ".join([f"{rt:.2f}" for rt, _ in peaks])
        print(f"  {d['label']:45s}: {peak_str}")

    # ==========================================================================
    # Figure 1: Chromatogram overlay (4 panels)
    # ==========================================================================
    fig, axes = plt.subplots(2, 2, figsize=(20, 14))
    fig.suptitle(
        "260324 Xul-5P Test - RID Chromatogram Overlay\n"
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

    # -- Panel (a): Enzyme ratio comparison ------------------------------------
    ax = axes[0, 0]
    panel_samples = []
    # NE control (100Xyl 100AcP)
    ne_100 = [(f, d) for f, d in loaded.items()
              if d["condition"] == "NE" and d["xyl"] == 100 and d["acp"] == 100]
    for f, d in ne_100:
        panel_samples.append((f, d, "#888888", "--", 1.0, 1))
    # Enzyme ratios
    for (xa, xb), color in ENZYME_RATIO_COLORS.items():
        match = [(f, d) for f, d in loaded.items()
                 if d["condition"] == "enzyme_ratio" and d["xyla"] == xa and d["xylb"] == xb]
        for f, d in match:
            panel_samples.append((f, d, color, "-", 1.5, 2))
    _plot_overlay(ax, panel_samples, "(a) Enzyme Ratio Comparison\n(100 mM Xyl, 100 mM AcP, 1 mM ATP, 1.5 h)")

    # -- Panel (b): ATP concentration effect -----------------------------------
    ax = axes[0, 1]
    panel_samples = []
    # NE control (100Xyl 120AcP)
    ne_120 = [(f, d) for f, d in loaded.items()
              if d["condition"] == "NE" and d["xyl"] == 100 and d["acp"] == 120]
    for f, d in ne_120:
        panel_samples.append((f, d, "#888888", "--", 1.0, 1))
    # ATP concentrations
    for atp_v, color in sorted(ATP_COLORS.items()):
        match = [(f, d) for f, d in loaded.items()
                 if d["condition"] == "atp_conc" and d["atp"] == atp_v]
        for f, d in match:
            panel_samples.append((f, d, color, "-", 1.5, 2))
    _plot_overlay(ax, panel_samples, "(b) ATP Concentration Effect\n(3X:3X, 100 mM Xyl, 120 mM AcP, 1.5 h)")

    # -- Panel (c): Substrate concentration scale-up ---------------------------
    ax = axes[1, 0]
    panel_samples = []
    # NE controls for each substrate conc
    for xyl_v in [25, 50, 100, 200]:
        ne_match = [(f, d) for f, d in loaded.items()
                    if d["condition"] == "NE" and d["xyl"] == xyl_v]
        for f, d in ne_match:
            panel_samples.append((f, d, SUBSTRATE_COLORS.get(xyl_v, "#888888"), "--", 0.8, 1))
    # Substrate conc samples (include 150AcP as 100Xyl variant)
    for xyl_v, color in sorted(SUBSTRATE_COLORS.items()):
        match = [(f, d) for f, d in loaded.items()
                 if d["condition"] == "substrate_conc" and d["xyl"] == xyl_v]
        for f, d in match:
            panel_samples.append((f, d, color, "-", 1.5, 2))
    _plot_overlay(ax, panel_samples, "(c) Substrate Concentration Scale-up\n(3X:3X, 1 mM ATP, 1.5 h)")

    # -- Panel (d): FED batch --------------------------------------------------
    ax = axes[1, 1]
    panel_samples = []
    # Reference: 3X:3X standard reaction
    ref_3x3x = [(f, d) for f, d in loaded.items()
                if d["condition"] == "enzyme_ratio" and d["xyla"] == 3 and d["xylb"] == 3]
    for f, d in ref_3x3x:
        panel_samples.append((f, d, "#888888", "--", 1.0, 1))
    # FED batch samples
    for f, d in loaded.items():
        if d["condition"] == "fed_batch":
            color = FED_COLORS.get(d["label"], "#333333")
            panel_samples.append((f, d, color, "-", 1.8, 2))
    _plot_overlay(ax, panel_samples, "(d) FED Batch vs Standard Reaction\n(dashed = 3X:3X standard)")

    plt.tight_layout(rect=[0, 0, 1, 0.94])
    png1 = OUTPUT_PNG.replace(".png", "_chromatogram.png")
    plt.savefig(png1, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\nChromatogram saved: {png1}")

    # ==========================================================================
    # Figure 2: Discussion graphs (4 panels)
    # ==========================================================================
    fig2, axes2 = plt.subplots(2, 2, figsize=(16, 12))
    fig2.suptitle(
        "260324 Xul-5P Test - Discussion Graphs",
        fontsize=13, fontweight="bold"
    )

    # -- (a) Enzyme ratio vs Product area --------------------------------------
    ax = axes2[0, 0]
    ratio_labels = ["1X:1X", "1X:3X", "3X:1X", "3X:3X"]
    ratio_keys = [(1, 1), (1, 3), (3, 1), (3, 3)]
    product_areas = []
    for xa, xb in ratio_keys:
        match = [f for f, d in loaded.items()
                 if d["condition"] == "enzyme_ratio" and d["xyla"] == xa and d["xylb"] == xb]
        if match:
            product_areas.append(area_table[match[0]]["Product"])
        else:
            product_areas.append(0)

    colors_bar = [ENZYME_RATIO_COLORS[k] for k in ratio_keys]
    bars = ax.bar(range(len(ratio_labels)), product_areas, color=colors_bar, alpha=0.85,
                  edgecolor="white", linewidth=0.5)
    # NE control line
    ne_100_f = [f for f, d in loaded.items()
                if d["condition"] == "NE" and d["xyl"] == 100 and d["acp"] == 100]
    if ne_100_f:
        ne_val = area_table[ne_100_f[0]]["Product"]
        ax.axhline(ne_val, color="gray", linestyle=":", linewidth=1.2, label="NE control")
    ax.set_xticks(range(len(ratio_labels)))
    ax.set_xticklabels(ratio_labels)
    ax.set_xlabel("XylA:XylB Ratio", fontsize=10)
    ax.set_ylabel("Product Peak Area (nRIU*s)", fontsize=10)
    ax.set_title("(a) Enzyme Ratio vs Product\n(100 mM Xyl, 100 mM AcP, 1 mM ATP)", fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, axis="y")
    # Value labels on bars
    for bar, val in zip(bars, product_areas):
        if val > 0:
            ax.text(bar.get_x() + bar.get_width()/2, val + max(product_areas)*0.02,
                    f"{val:.0f}", ha="center", va="bottom", fontsize=8)

    # -- (b) ATP concentration vs Product area ---------------------------------
    ax = axes2[0, 1]
    atp_vals = [0.125, 0.25, 0.5, 1.0]
    atp_labels = ["0.125", "0.25", "0.5", "1.0"]
    atp_areas = []
    for atp_v in atp_vals:
        match = [f for f, d in loaded.items()
                 if d["condition"] == "atp_conc" and d["atp"] == atp_v]
        if match:
            atp_areas.append(area_table[match[0]]["Product"])
        else:
            atp_areas.append(0)

    ax.plot(range(len(atp_vals)), atp_areas, marker="o", linewidth=1.8, markersize=8,
            color="#1f77b4", label="Product area")
    # NE control line
    ne_120_f = [f for f, d in loaded.items()
                if d["condition"] == "NE" and d["xyl"] == 100 and d["acp"] == 120]
    if ne_120_f:
        ne_val = area_table[ne_120_f[0]]["Product"]
        ax.axhline(ne_val, color="gray", linestyle=":", linewidth=1.2, label="NE control")
    ax.set_xticks(range(len(atp_vals)))
    ax.set_xticklabels(atp_labels)
    ax.set_xlabel("ATP Concentration (mM)", fontsize=10)
    ax.set_ylabel("Product Peak Area (nRIU*s)", fontsize=10)
    ax.set_title("(b) ATP Conc. Effect on Product\n(3X:3X, 100 mM Xyl, 120 mM AcP)", fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # -- (c) Substrate concentration vs Product area ---------------------------
    ax = axes2[1, 0]
    xyl_vals = [25, 50, 100, 200]
    xyl_areas_rxn = []
    xyl_areas_ne = []
    for xyl_v in xyl_vals:
        # Reaction sample
        match = [f for f, d in loaded.items()
                 if d["condition"] == "substrate_conc" and d["xyl"] == xyl_v]
        if match:
            xyl_areas_rxn.append(area_table[match[0]]["Product"])
        else:
            xyl_areas_rxn.append(0)
        # NE control
        ne_match = [f for f, d in loaded.items()
                    if d["condition"] == "NE" and d["xyl"] == xyl_v]
        if ne_match:
            xyl_areas_ne.append(area_table[ne_match[0]]["Product"])
        else:
            xyl_areas_ne.append(0)

    x_pos = np.arange(len(xyl_vals))
    width = 0.35
    ax.bar(x_pos - width/2, xyl_areas_rxn, width, label="Reaction", color="#5aade0", alpha=0.85)
    ax.bar(x_pos + width/2, xyl_areas_ne, width, label="NE control", color="#cccccc", alpha=0.85)
    ax.set_xticks(x_pos)
    ax.set_xticklabels([f"{v} mM" for v in xyl_vals])
    ax.set_xlabel("D-Xylose Concentration", fontsize=10)
    ax.set_ylabel("Product Peak Area (nRIU*s)", fontsize=10)
    ax.set_title("(c) Substrate Conc. vs Product\n(3X:3X, 1 mM ATP, AcP=1.2x Xyl)", fontsize=10)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, axis="y")

    # -- (d) All compounds bar chart (best conditions) -------------------------
    ax = axes2[1, 1]
    fed_samples = [(f, d) for f, d in loaded.items() if d["condition"] == "fed_batch"]
    if fed_samples:
        fed_labels = [d["label"] for _, d in fed_samples]
        compounds = list(KNOWN_WINDOWS.keys())
        x_pos = np.arange(len(fed_labels))
        n_cmp = len(compounds)
        bar_w = 0.8 / n_cmp
        cmp_colors = ["#9b59b6", "#2ecc71", "#f1c40f", "#e67e22", "#e74c3c"]
        for i, cmp in enumerate(compounds):
            vals = [area_table[f][cmp] for f, _ in fed_samples]
            ax.bar(x_pos + i * bar_w - 0.4 + bar_w/2, vals, bar_w,
                   label=cmp, color=cmp_colors[i], alpha=0.85)
        ax.set_xticks(x_pos)
        ax.set_xticklabels(fed_labels, fontsize=8, rotation=15, ha="right")
        ax.set_ylabel("Peak Area (nRIU*s)", fontsize=10)
        ax.set_title("(d) FED Batch Compound Profile", fontsize=10)
        ax.legend(fontsize=7, ncol=2)
        ax.grid(True, alpha=0.3, axis="y")

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    png2 = OUTPUT_PNG.replace(".png", "_discussion.png")
    plt.savefig(png2, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Discussion graph saved: {png2}")

    # ==========================================================================
    # Excel export
    # ==========================================================================
    try:
        import openpyxl
        wb = openpyxl.Workbook()

        # Sheet 1: Peak areas
        ws = wb.active
        ws.title = "Peak_Areas"
        headers = ["Sample", "Condition", "XylA", "XylB", "Xyl_mM", "AcP_mM", "ATP_mM", "Time_h"]
        headers += list(KNOWN_WINDOWS.keys())
        ws.append(headers)
        for folder, d in loaded.items():
            row = [d["label"], d["condition"], d["xyla"], d["xylb"],
                   d["xyl"] if d["xyl"] is not None else "",
                   d["acp"] if d["acp"] is not None else "",
                   d["atp"] if d["atp"] is not None else "",
                   d["time_h"]]
            row += [area_table[folder][cmp] for cmp in KNOWN_WINDOWS]
            ws.append(row)

        # Sheet 2: Peak detection
        ws2 = wb.create_sheet("Peak_Detection")
        ws2.append(["Sample", "Detected_Peaks_RT"])
        for folder, d in loaded.items():
            peaks = detect_peaks(d["time"], d["intensity"])
            peak_str = ", ".join([f"{rt:.2f}" for rt, _ in peaks])
            ws2.append([d["label"], peak_str])

        wb.save(OUTPUT_XLSX)
        print(f"Excel saved: {OUTPUT_XLSX}")
    except ImportError:
        print("[WARN] openpyxl not installed, skipping Excel export.")
        # Fallback to CSV
        import csv
        csv_path = OUTPUT_XLSX.replace(".xlsx", ".csv")
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            headers = ["Sample", "Condition", "XylA", "XylB", "Xyl_mM", "AcP_mM", "ATP_mM", "Time_h"]
            headers += list(KNOWN_WINDOWS.keys())
            writer.writerow(headers)
            for folder, d in loaded.items():
                row = [d["label"], d["condition"], d["xyla"], d["xylb"],
                       d["xyl"], d["acp"], d["atp"], d["time_h"]]
                row += [area_table[folder][cmp] for cmp in KNOWN_WINDOWS]
                writer.writerow(row)
        print(f"CSV fallback saved: {csv_path}")

    print("\nDone.")


if __name__ == "__main__":
    main()
