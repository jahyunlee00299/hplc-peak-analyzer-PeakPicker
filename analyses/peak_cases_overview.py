"""
Peak Cases Overview: 3 samples x 5 zoom panels
Visualize difficult peak cases for algorithm development.
"""
import sys, os, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

PEAKPICKER_SRC = r"C:\Users\Jahyun\PeakPicker\src"
sys.path.insert(0, PEAKPICKER_SRC)
from chemstation_parser import ChemstationParser

# -- Data paths ---------------------------------------------------------------
DATA_260324 = r"C:\Chem32\1\DATA\2. D-Xyl cascade HPLC\Xul 5P production\Pretest\260324_Xul5P_Test"
DATA_260317 = r"C:\Chem32\1\DATA\2. D-Xyl cascade HPLC\Xul 5P production\Pretest\260317_Xul5P_AcP_Pre"

SAMPLES = [
    (os.path.join(DATA_260324, "XUL5P_NE_100XYL_100ACP_1ATP_1_5H.D", "RID1A.ch"),
     "NE control (Xyl-rich)"),
    (os.path.join(DATA_260324, "XUL5P_3X3X_100XYL_150ACP_1ATP_1_5H.D", "RID1A.ch"),
     "3X3X 150AcP (Xyl consumed)"),
    (os.path.join(DATA_260317, "260317_XUL5P_300_5ATP_3H.D", "RID1A.ch"),
     "300 5ATP 3H (Product max)"),
]

# -- RT windows from current analysis scripts ---------------------------------
KNOWN_WINDOWS = {
    "Product (Xul-5P)": (7.00, 7.55),
    "Pi":               (9.00, 9.80),
    "D-Xylose":         (10.80, 11.50),
    "D-Xylulose":       (11.50, 12.10),
    "Acetate":          (17.00, 17.70),
}

# -- Zoom columns: (title, x_min, x_max, relevant windows) -------------------
ZOOM_COLS = [
    ("Full (5-20 min)", 5.0, 20.0, list(KNOWN_WINDOWS.keys())),
    ("Product (6.5-8.5)", 6.5, 8.5, ["Product (Xul-5P)"]),
    ("Pi (8.5-10.5)", 8.5, 10.5, ["Pi"]),
    ("Xyl+Xylulose (10.0-12.5)", 10.0, 12.5, ["D-Xylose", "D-Xylulose"]),
    ("Acetate (16.5-18.5)", 16.5, 18.5, ["Acetate"]),
]

OUTPUT = r"C:\Users\Jahyun\PeakPicker\analyses\peak_cases_overview.png"

# -- Load data ----------------------------------------------------------------
print("Loading chromatograms...")
loaded = []
for path, label in SAMPLES:
    if not os.path.exists(path):
        print(f"  WARNING: {path} not found, skipping")
        loaded.append(None)
        continue
    parser = ChemstationParser(path)
    time, intensity = parser.read()
    loaded.append((time, intensity, label))
    print(f"  Loaded: {label} ({len(time)} points, {time[0]:.2f}-{time[-1]:.2f} min)")

# -- Plot ---------------------------------------------------------------------
fig, axes = plt.subplots(3, 5, figsize=(24, 12), constrained_layout=True)

WINDOW_COLORS = {
    "Product (Xul-5P)": "#e8d5f0",
    "Pi":               "#d5f0e8",
    "D-Xylose":         "#fff0cc",
    "D-Xylulose":       "#ffe0cc",
    "Acetate":          "#f0d5d5",
}

for row_idx, data in enumerate(loaded):
    if data is None:
        for col_idx in range(5):
            axes[row_idx, col_idx].text(0.5, 0.5, "Data not found",
                ha='center', va='center', transform=axes[row_idx, col_idx].transAxes)
        continue

    time, intensity, label = data

    for col_idx, (col_title, xmin, xmax, windows) in enumerate(ZOOM_COLS):
        ax = axes[row_idx, col_idx]

        # Mask to zoom range
        mask = (time >= xmin) & (time <= xmax)
        t = time[mask]
        sig = intensity[mask]

        if len(t) == 0:
            ax.text(0.5, 0.5, "No data in range",
                ha='center', va='center', transform=ax.transAxes)
            continue

        # Plot signal
        ax.plot(t, sig, 'k-', linewidth=0.7, alpha=0.9)

        # Draw RT windows as shaded regions + red dashed boundaries
        for wname in windows:
            wmin, wmax = KNOWN_WINDOWS[wname]
            if wmax < xmin or wmin > xmax:
                continue
            color = WINDOW_COLORS.get(wname, "#e0e0e0")
            ax.axvspan(wmin, wmax, alpha=0.25, color=color, zorder=0)
            ax.axvline(wmin, color='red', linestyle='--', linewidth=0.8, alpha=0.7)
            ax.axvline(wmax, color='red', linestyle='--', linewidth=0.8, alpha=0.7)
            # Label window in zoom panels (not full)
            if col_idx > 0:
                mid = (max(wmin, xmin) + min(wmax, xmax)) / 2
                ax.text(mid, ax.get_ylim()[1] if ax.get_ylim()[1] != 1 else sig.max() * 0.95,
                        wname, ha='center', va='top', fontsize=7, color='red', alpha=0.8)

        ax.set_xlim(xmin, xmax)

        # Y label for first column
        if col_idx == 0:
            ax.set_ylabel(label, fontsize=9, fontweight='bold')

        # Column title on top row
        if row_idx == 0:
            ax.set_title(col_title, fontsize=10, fontweight='bold')

        # X label on bottom row
        if row_idx == 2:
            ax.set_xlabel("RT (min)", fontsize=8)

        ax.tick_params(labelsize=7)

# Re-do text labels after ylim is set
for row_idx, data in enumerate(loaded):
    if data is None:
        continue
    time, intensity, label = data
    for col_idx, (col_title, xmin, xmax, windows) in enumerate(ZOOM_COLS):
        if col_idx == 0:
            continue
        ax = axes[row_idx, col_idx]
        yhi = ax.get_ylim()[1]
        for wname in windows:
            wmin, wmax = KNOWN_WINDOWS[wname]
            if wmax < xmin or wmin > xmax:
                continue
            mid = (max(wmin, xmin) + min(wmax, xmax)) / 2
            ax.text(mid, yhi * 0.97, wname, ha='center', va='top',
                    fontsize=7, color='red', alpha=0.8,
                    bbox=dict(boxstyle='round,pad=0.15', fc='white', ec='none', alpha=0.7))

fig.suptitle("Peak Cases Overview: Difficult Integration Cases for Algorithm Development",
             fontsize=13, fontweight='bold', y=1.01)

plt.savefig(OUTPUT, dpi=150, bbox_inches='tight', facecolor='white')
print(f"\nSaved: {OUTPUT}")
print("Done.")
