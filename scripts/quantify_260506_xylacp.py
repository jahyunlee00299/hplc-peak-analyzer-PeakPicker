"""
XylAcP production quantification — 260506 run
===============================================
Compounds : D-Xylose (10.80–11.50), D-Xylulose (11.50–12.10),
            Xul-5P   (7.00–7.55),   Acetate    (17.00–17.80)
Dilution  : 10x
NC subtract: net production = rxn_conc - NC_conc (matched by acp_mM)

Folder-name shift correction (confirmed 2026-05-11):
  50_NC folder → XylAcP_100_1, etc.  See XylAcPSampleParser.post_classify().
"""

import sys
from pathlib import Path

# --- repo root on sys.path ---
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo))

import numpy as np
import pandas as pd
from scipy.signal import find_peaks
from src.chemstation_parser import ChemstationParser

# ── Config ────────────────────────────────────────────────────────────────────
BASE = Path(r'C:\tmp_hplc')   # junction to the run folder (avoids en-dash in path)
DILUTION = 10.0

# Calibration: conc(mM) = (area - intercept) / slope
COMPOUNDS = {
    "D-Xylose":   {"rt": (10.80, 11.50), "slope": 22786.19, "intercept":   207.54, "half": None},
    "D-Xylulose": {"rt": (11.50, 12.10), "slope": 23465.27, "intercept":   -59.45, "half": None},
    "Xul-5P":     {"rt": (7.00,  7.55),  "slope": 52961.53, "intercept":  3008.37, "half": None},
    "Acetate":    {"rt": (17.00, 17.80), "slope":  8708.00,  "intercept":  -901.60, "half": None},
}

# Folder → correct sample name mapping (run order, excl. blank)
# Folder names match sequence table 1:1 (no offset).
# NE samples (no enzyme) were mislabeled during pipetting:
#   200_3=NE_50, 200_4=NE_100, 200_5=NE_150, 200_NC=NE_200
# _NC_ folders (50/100/150) are actually rxn samples (mislabeled).
# Correct identity confirmed by Xul-5P/Xyl pattern (2026-05-11).
SAMPLE_MAP = [
    ("NV--0101.D",                    "blank"),
    ("260506_XYLACP_50_1_4H.D",       "Xyl50_r1.0"),
    ("260506_XYLACP_50_2_4H.D",       "Xyl50_r1.2"),
    ("260506_XYLACP_50_3_4H.D",       "Xyl50_r1.5"),
    ("260506_XYLACP_50_4_4H.D",       "Xyl50_r2.0"),
    ("260506_XYLACP_50_5_4H.D",       "Xyl50_r2.5"),
    ("260506_XYLACP_50_NC_4H.D",      "Xyl100_r1.0"),  # mislabeled
    ("260506_XYLACP_100_1_4H.D",      "Xyl100_r1.2"),  # mislabeled
    ("260506_XYLACP_100_2_4H.D",      "Xyl100_r1.5"),  # mislabeled
    ("260506_XYLACP_100_3_4H.D",      "Xyl100_r2.0"),  # mislabeled
    ("260506_XYLACP_100_4_4H.D",      "Xyl100_r2.5"),  # mislabeled
    ("260506_XYLACP_100_5_4H.D",      "Xyl150_r1.0"),  # mislabeled
    ("260506_XYLACP_100_NC_4H.D",     "Xyl150_r1.2"),  # mislabeled
    ("260506_XYLACP_150_1_4H.D",      "Xyl150_r1.5"),  # mislabeled
    ("260506_XYLACP_150_2_4H.D",      "Xyl150_r2.0"),  # mislabeled
    ("260506_XYLACP_150_3_4H.D",      "Xyl150_r2.5"),  # mislabeled
    ("260506_XYLACP_150_4_4H.D",      "Xyl200_r1.0"),  # mislabeled
    ("260506_XYLACP_150_5_4H.D",      "Xyl200_r1.2"),  # mislabeled
    ("260506_XYLACP_150_NC_4H.D",     "Xyl200_r1.5"),  # mislabeled
    ("260506_XYLACP_200_1_4H.D",      "Xyl200_r2.0"),  # mislabeled
    ("260506_XYLACP_200_2_4H.D",      "Xyl200_r2.5"),  # mislabeled
    ("260506_XYLACP_200_3_4H.D",      "NE_50"),        # mislabeled
    ("260506_XYLACP_200_4_4H.D",      "NE_100"),       # mislabeled
    ("260506_XYLACP_200_5_4H.D",      "NE_150"),       # mislabeled
    ("260506_XYLACP_200_NC_4H.D",     "NE_200"),       # mislabeled
]

# ── Peak integration ──────────────────────────────────────────────────────────

def find_valley_rt(t, y, rt_min, rt_max):
    """Find the RT of the valley (minimum) between two peaks in [rt_min, rt_max]."""
    mask = (t >= rt_min) & (t <= rt_max)
    t_w, y_w = t[mask], y[mask]
    if len(t_w) < 2:
        return (rt_min + rt_max) / 2
    return float(t_w[np.argmin(y_w)])


def integrate_window(t, y, rt_min, rt_max, half=None, split_rt=None):
    """Trapezoid integration within [rt_min, rt_max].

    half='left'  → integrate from rt_min to split_rt (Xyl side)
    half='right' → integrate from split_rt to rt_max (Xlu side)
    half=None    → integrate full window

    t is in minutes; area converted to nRIU·s (*60) to match calibration units.
    Returns (area_nRIU_s, rt_of_apex_min).
    """
    if half == "left" and split_rt is not None:
        rt_max = split_rt
    elif half == "right" and split_rt is not None:
        rt_min = split_rt

    mask = (t >= rt_min) & (t <= rt_max)
    t_w, y_w = t[mask], y[mask]
    if len(t_w) < 2:
        return 0.0, None
    area_sec = float(np.trapezoid(y_w, t_w)) * 60.0
    rt_peak = float(t_w[np.argmax(y_w)])
    return area_sec, rt_peak


def area_to_conc(area, slope, intercept):
    """conc(mM) in diluted sample → multiply by DILUTION for original."""
    if slope == 0:
        return None
    c = (area - intercept) / slope
    return max(c, 0.0)


# ── Main ──────────────────────────────────────────────────────────────────────

rows = []
for folder, sample in SAMPLE_MAP:
    if sample == "blank":
        continue
    ch = BASE / folder / "RID1A.ch"
    if not ch.exists():
        print(f"[SKIP] {sample}: no RID1A.ch")
        continue
    t, y = ChemstationParser(str(ch)).read()

    is_ne = sample.startswith("NE_")

    # Xyl/Xlu split: valley between the two apexes (rxn only)
    if not is_ne:
        split_rt = find_valley_rt(t, y, 11.10, 11.80)
    else:
        split_rt = None

    row = {"sample": sample, "split_rt": round(split_rt, 3) if split_rt else None}
    for cname, cfg in COMPOUNDS.items():
        if is_ne and cname == "D-Xylulose":
            # NE has no Xlu peak — skip
            row[f"{cname}_area"] = 0.0
            row[f"{cname}_rt"]   = None
            row[f"{cname}_mM"]   = 0.0
            continue

        if cname == "D-Xylose":
            if is_ne:
                # NE: left half of single Xyl peak (apex → left), matching calibration basis
                xyl_apex_rt = find_valley_rt(t, y, 10.80, 11.80)  # apex = argmax in window
                mask_xyl = (t >= 10.80) & (t <= 11.80)
                xyl_apex_rt = float(t[mask_xyl][np.argmax(y[mask_xyl])])
                area, rt_det = integrate_window(t, y, 10.80, 12.10, half="left", split_rt=xyl_apex_rt)
            else:
                # rxn: left of valley between Xyl/Xlu apexes
                area, rt_det = integrate_window(t, y, 10.80, 12.10, half="left", split_rt=split_rt)
        elif cname == "D-Xylulose":
            # rxn: right of valley
            area, rt_det = integrate_window(t, y, 10.80, 12.10, half="right", split_rt=split_rt)
        else:
            area, rt_det = integrate_window(t, y, cfg["rt"][0], cfg["rt"][1])

        conc_diluted = area_to_conc(area, cfg["slope"], cfg["intercept"])
        conc_orig    = conc_diluted * DILUTION if conc_diluted is not None else None
        row[f"{cname}_area"] = round(area, 1)
        row[f"{cname}_rt"]   = round(rt_det, 3) if rt_det else None
        row[f"{cname}_mM"]   = round(conc_orig, 2) if conc_orig is not None else None
    rows.append(row)

df = pd.DataFrame(rows)

# ── NC subtract ───────────────────────────────────────────────────────────────
# NC_50 → baseline for 50mM AcP samples, etc.
nc_map = {}
for acp in [50, 100, 150, 200]:
    nc_row = df[df["sample"] == f"NE_{acp}"]
    if not nc_row.empty:
        nc_map[acp] = nc_row.iloc[0]

def get_xyl(sample_name):
    import re
    m = re.search(r"Xyl(\d+)_r", sample_name)
    return int(m.group(1)) if m else None

net_rows = []
for _, row in df.iterrows():
    acp = get_xyl(row["sample"])
    if acp is None or acp not in nc_map:
        continue
    nc = nc_map[acp]
    net = {"sample": row["sample"], "acp_mM": acp}
    for cname in COMPOUNDS:
        rxn  = row.get(f"{cname}_mM") or 0.0
        nc_c = nc.get(f"{cname}_mM")  or 0.0
        net[f"{cname}_net_mM"] = round(rxn - nc_c, 2)
    net_rows.append(net)

df_net = pd.DataFrame(net_rows)

# ── Summary: mean ± std per AcP group ────────────────────────────────────────
summary_rows = []
for acp in [50, 100, 150, 200]:
    grp = df_net[df_net["acp_mM"] == acp]
    r = {"acp_mM": acp, "n": len(grp)}
    for cname in COMPOUNDS:
        col = f"{cname}_net_mM"
        if col in grp:
            r[f"{cname}_mean"] = round(grp[col].mean(), 2)
            r[f"{cname}_std"]  = round(grp[col].std(), 2)
    summary_rows.append(r)

df_sum = pd.DataFrame(summary_rows)

# ── Output ────────────────────────────────────────────────────────────────────
out_dir = repo / "results" / "260506_XylAcP"
out_dir.mkdir(parents=True, exist_ok=True)

raw_path  = out_dir / "raw_quant.csv"
net_path  = out_dir / "net_quant.csv"
sum_path  = out_dir / "summary.csv"

df.to_csv(raw_path, index=False)
df_net.to_csv(net_path, index=False)
df_sum.to_csv(sum_path, index=False)

print("\n=== Raw quantification (mM, 10x dilution corrected) ===")
cols = ["sample"] + [f"{c}_mM" for c in COMPOUNDS]
print(df[[c for c in cols if c in df.columns]].to_string(index=False))

print("\n=== Net production (rxn - NC, mM) ===")
print(df_net.to_string(index=False))

print("\n=== Summary (mean ± std per AcP group) ===")
print(df_sum.to_string(index=False))

print(f"\nSaved: {raw_path}, {net_path}, {sum_path}")
