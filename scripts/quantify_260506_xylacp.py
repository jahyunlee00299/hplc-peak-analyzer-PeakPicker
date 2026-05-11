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
    "D-Xylose":   {"rt": (10.80, 11.50), "slope": 22786.19, "intercept":   207.54, "half": "left"},
    "D-Xylulose": {"rt": (11.50, 12.10), "slope": 23465.27, "intercept":   -59.45, "half": "right"},
    "Xul-5P":     {"rt": (7.00,  7.55),  "slope": 52961.53, "intercept":  3008.37, "half": None},
    "Acetate":    {"rt": (17.00, 17.80), "slope":  8708.00,  "intercept":  -901.60, "half": None},
}

# Folder → correct sample name mapping (run order, excl. blank)
SAMPLE_MAP = [
    ("NV--0101.D",                "blank"),
    ("260506_XYLACP_50_1_4H.D",   "XylAcP_50_1"),
    ("260506_XYLACP_50_2_4H.D",   "XylAcP_50_2"),
    ("260506_XYLACP_50_3_4H.D",   "XylAcP_50_3"),
    ("260506_XYLACP_50_4_4H.D",   "XylAcP_50_4"),
    ("260506_XYLACP_50_5_4H.D",   "XylAcP_50_5"),
    ("260506_XYLACP_50_NC_4H.D",  "XylAcP_100_1"),
    ("260506_XYLACP_100_1_4H.D",  "XylAcP_100_2"),
    ("260506_XYLACP_100_2_4H.D",  "XylAcP_100_3"),
    ("260506_XYLACP_100_3_4H.D",  "XylAcP_100_4"),
    ("260506_XYLACP_100_4_4H.D",  "XylAcP_100_5"),
    ("260506_XYLACP_100_5_4H.D",  "XylAcP_150_1"),
    ("260506_XYLACP_100_NC_4H.D", "XylAcP_150_2"),
    ("260506_XYLACP_150_1_4H.D",  "XylAcP_150_3"),
    ("260506_XYLACP_150_2_4H.D",  "XylAcP_150_4"),
    ("260506_XYLACP_150_3_4H.D",  "XylAcP_150_5"),
    ("260506_XYLACP_150_4_4H.D",  "XylAcP_200_1"),
    ("260506_XYLACP_150_5_4H.D",  "XylAcP_200_2"),
    ("260506_XYLACP_150_NC_4H.D", "XylAcP_200_3"),
    ("260506_XYLACP_200_1_4H.D",  "XylAcP_200_4"),
    ("260506_XYLACP_200_2_4H.D",  "XylAcP_200_5"),
    ("260506_XYLACP_200_3_4H.D",  "NC_50"),
    ("260506_XYLACP_200_4_4H.D",  "NC_100"),
    ("260506_XYLACP_200_5_4H.D",  "NC_150"),
    ("260506_XYLACP_200_NC_4H.D", "NC_200"),
]

# ── Peak integration ──────────────────────────────────────────────────────────

def integrate_window(t, y, rt_min, rt_max, half=None):
    """Trapezoid integration within [rt_min, rt_max]; optionally left/right half."""
    mask = (t >= rt_min) & (t <= rt_max)
    t_w, y_w = t[mask], y[mask]
    if len(t_w) < 2:
        return 0.0, None
    if half == "left":
        # find apex in window, integrate left side
        apex = np.argmax(y_w)
        t_w, y_w = t_w[:apex+1], y_w[:apex+1]
    elif half == "right":
        apex = np.argmax(y_w)
        t_w, y_w = t_w[apex:], y_w[apex:]
    area = float(np.trapezoid(y_w, t_w))
    rt_peak = float(t_w[np.argmax(y_w)]) if len(t_w) else None
    return area, rt_peak


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

    row = {"sample": sample}
    for cname, cfg in COMPOUNDS.items():
        area, rt_det = integrate_window(t, y, cfg["rt"][0], cfg["rt"][1], cfg.get("half"))
        conc_diluted = area_to_conc(area, cfg["slope"], cfg["intercept"])
        conc_orig    = conc_diluted * DILUTION if conc_diluted is not None else None
        row[f"{cname}_area"]    = round(area, 1)
        row[f"{cname}_rt"]      = round(rt_det, 3) if rt_det else None
        row[f"{cname}_mM"]      = round(conc_orig, 2) if conc_orig is not None else None
    rows.append(row)

df = pd.DataFrame(rows)

# ── NC subtract ───────────────────────────────────────────────────────────────
# NC_50 → baseline for 50mM AcP samples, etc.
nc_map = {}
for acp in [50, 100, 150, 200]:
    nc_row = df[df["sample"] == f"NC_{acp}"]
    if not nc_row.empty:
        nc_map[acp] = nc_row.iloc[0]

def get_acp(sample_name):
    import re
    m = re.search(r"XylAcP_(\d+)_", sample_name)
    return int(m.group(1)) if m else None

net_rows = []
for _, row in df.iterrows():
    acp = get_acp(row["sample"])
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
