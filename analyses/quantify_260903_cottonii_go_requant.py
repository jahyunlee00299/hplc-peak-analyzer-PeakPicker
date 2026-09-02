"""
260903 Cottonii (K. alvarezii) bioreactor GO-difference requantification
==========================================================================
Re-integrates all 90 raw HPX-87H chromatograms (45 GO-untreated + 45 GO-treated
COTTONII_REACTOR injections, 260624/260625) using PeakPicker's established
valley-to-valley integration pattern (precedent: quantify_260302_48H_GO.py,
quantify_260810_remaining_batches.py).

Purpose: re-derive residual D-galactose (gal = untreated_combined - treated_tag)
per vial/replicate under several candidate quantification schemes, so the
propagated error at each scheme can be compared against the spreadsheet's
existing gal column (Cottonii_bioreactor_3반복 sheet of
manuscript-figures/tagatose/rawdata/figure_raw_Data.xlsx).

Vial <-> timepoint mapping (see DECISION_LOG.md D1):
  - vial 1-7 (of 15) map 1:1, in order, to spreadsheet t = 0,1,3,4.5,6,9,12 h
    (high confidence: unambiguous monotonic-decrease/rise shape match).
  - vial 8-15 (8 vials) supply only 6 of the remaining timepoints (15,18,24,36,
    48,66 h) -- WHICH 2 are "extra" could not be identified (the region is flat
    within ~1-3% CV in both the combined-peak and tag-peak windows, in all 3
    replicates, and the best-fit 2-vial-drop choice is not consistent across
    replicates/columns). Per D1, all 8 plateau vials are kept and treated as a
    single 8-point "post-plateau" ensemble per replicate for late-time scheme
    comparison, rather than forcing an arbitrary unique subset.
  - Untreated<->treated pairing uses vial index + replicate directly (same
    vial number = same physical sample; unambiguous, independent of the
    timepoint-identity question above).

Windows (HPX-87H, 5mM H2SO4, 0.5 mL/min, 65C, RID, 19.99 min runtime):
  ~6.83 min, ~9.4 min, ~10.94 min (largest; untreated=GAL+TAG combined,
  treated=TAG only), ~11.74 min (Galactitol), ~12.85 min, ~15.93 min (Formate,
  present + chemically inert in BOTH injections -> internal normalization
  candidate), ~17.98 min.
"""
import sys
import io
import re
import json
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import numpy as np
import pandas as pd
from scipy.integrate import trapezoid
from rainbow.agilent.chemstation import parse_ch

DATA_DIR = Path(r"C:\Users\Jahyun\scratch\cot7z\260624_cottonii_bioreactor")
OUT_DIR = Path(r"C:\Users\Jahyun\scratch\cottonii_requant\results")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# apex-search windows; all peaks integrated valley-to-valley between the
# midpoint-to-neighbor bounds (same construction as quantify_260810_remaining_batches.py)
APEX_WINDOWS = {
    "p6.8":     (6.5,  7.1),
    "p9.4":     (9.1,  9.7),
    "p10.9":    (10.5, 11.5),   # untreated: GAL+TAG combined | treated: TAG only
    "p11.7":    (11.55, 11.95),  # Galactitol
    "p12.9":    (12.6, 13.1),
    "p15.9":    (15.5, 16.3),   # Formate -- internal reference candidate
    "p18.0":    (17.6, 18.4),
}
REGION_START_RT = 5.0
REGION_END_RT = 19.5
MAX_VALLEY_SEARCH_MIN = 1.0

# spreadsheet timepoints, in order, for the vial1-7 <-> t0..t12 confirmed mapping
EARLY_TIMEPOINTS = [0, 1, 3, 4.5, 6, 9, 12]
PLATEAU_TIMEPOINTS_NOMINAL = [15, 18, 24, 36, 48, 66]  # 6 slots, 8 plateau vials (D1: ambiguous)


def vial_key(name):
    m = re.match(r'(?:260625_)?COTTONII_REACTOR(?:_GO)?_(\d+)_(\d+)\.D', name)
    return int(m.group(1)), int(m.group(2))


def find_valley(time, intensity, lo, hi):
    mask = (time >= lo) & (time <= hi)
    if not np.any(mask):
        return None
    idx_local = np.argmin(intensity[mask])
    return np.where(mask)[0][idx_local]


def integrate_valley_to_valley(time, intensity, apex_windows, region_start_rt, region_end_rt, max_valley_search_min):
    """Same construction as quantify_260810_remaining_batches.py: apex-in-window,
    valley bounded by neighboring apex (or region edge), linear baseline, trapezoid area."""
    names = list(apex_windows.keys())
    apex_idx = {}
    for name, (lo, hi) in apex_windows.items():
        mask = (time >= lo) & (time <= hi)
        if not mask.any():
            continue
        local_idx = np.argmax(intensity[mask])
        apex_idx[name] = np.where(mask)[0][local_idx]

    region_mask = (time >= region_start_rt) & (time <= region_end_rt)
    region_idx = np.where(region_mask)[0]
    left_bound_idx = region_idx[0]
    right_bound_idx = region_idx[-1]

    results = {}
    ordered = [n for n in names if n in apex_idx]
    for i, name in enumerate(ordered):
        a_idx = apex_idx[name]
        apex_rt = time[a_idx]

        left_bound_rt = time[left_bound_idx] if i == 0 else time[apex_idx[ordered[i - 1]]]
        left_lo = max(left_bound_rt, apex_rt - max_valley_search_min)
        left_valley_idx = find_valley(time, intensity, left_lo, apex_rt)

        right_bound_rt = time[right_bound_idx] if i == len(ordered) - 1 else time[apex_idx[ordered[i + 1]]]
        right_hi = min(right_bound_rt, apex_rt + max_valley_search_min)
        right_valley_idx = find_valley(time, intensity, apex_rt, right_hi)

        if left_valley_idx is None or right_valley_idx is None:
            continue

        l, r = left_valley_idx, right_valley_idx
        t_win = time[l:r + 1]
        y_win = intensity[l:r + 1]
        left_y = intensity[l]
        right_y = intensity[r]
        baseline = np.interp(t_win, [t_win[0], t_win[-1]], [left_y, right_y])
        area = trapezoid(np.maximum(y_win - baseline, 0), t_win * 60.0)

        results[name] = {
            'rt_min': round(float(time[a_idx]), 3),
            'height': round(float(intensity[a_idx] - np.interp(time[a_idx], [t_win[0], t_win[-1]], [left_y, right_y])), 1),
            'area': round(float(area), 1),
            'left_rt': round(float(time[l]), 3),
            'right_rt': round(float(time[r]), 3),
        }
    return results


def read_rid(ch_path):
    r = parse_ch(str(ch_path))
    time = np.asarray(r.xlabels, dtype=float)
    sig = np.asarray(r.data, dtype=float).flatten()
    n = min(len(time), len(sig))
    return time[:n], sig[:n]


def process_all():
    untreated = sorted(
        (d for d in DATA_DIR.glob("COTTONII_REACTOR_*.D") if not d.stem.startswith("COTTONII_REACTOR_GO")),
        key=lambda d: vial_key(d.name))
    treated = sorted(DATA_DIR.glob("260625_COTTONII_REACTOR_GO_*.D"), key=lambda d: vial_key(d.name))

    print(f"Untreated: {len(untreated)}  Treated: {len(treated)}")

    rows = []
    for kind, folders in [("untreated", untreated), ("treated", treated)]:
        for d in folders:
            ch = d / "RID1A.ch"
            if not ch.exists():
                print(f"  [skip] {d.name}: RID1A.ch missing")
                continue
            time, sig = read_rid(ch)
            matched = integrate_valley_to_valley(
                time, sig, APEX_WINDOWS, REGION_START_RT, REGION_END_RT, MAX_VALLEY_SEARCH_MIN)
            v, rep = vial_key(d.name)
            for peak_name, pk in matched.items():
                row = {'kind': kind, 'sample': d.stem, 'vial': v, 'replicate': rep, 'peak': peak_name}
                row.update(pk)
                rows.append(row)
            print(f"  {kind:>9} vial={v:2d} rep={rep}: {len(matched)} peaks matched")

    df = pd.DataFrame(rows)
    return df


def annotate_timepoints(df):
    """Attach spreadsheet timepoint label (D1 mapping) where confidently known.
    vial 1-7 -> t=0..12 (confident). vial 8-15 -> 'plateau' (ambiguous identity,
    kept as an 8-point ensemble per D1)."""
    def label(v):
        if 1 <= v <= 7:
            return EARLY_TIMEPOINTS[v - 1]
        return 'plateau'
    df = df.copy()
    df['timepoint_h'] = df['vial'].map(label)
    return df


def main():
    df = process_all()
    df = annotate_timepoints(df)

    long_path = OUT_DIR / "all_peaks_long.csv"
    df.to_csv(long_path, index=False, encoding='utf-8-sig')
    print(f"\nSaved long-format peak table: {long_path}  ({len(df)} rows)")

    # wide area pivot per kind, for convenience
    for kind in ['untreated', 'treated']:
        sub = df[df['kind'] == kind]
        wide = sub.pivot_table(index=['vial', 'replicate', 'timepoint_h'], columns='peak', values='area').reset_index()
        wide_path = OUT_DIR / f"area_pivot_{kind}.csv"
        wide.to_csv(wide_path, index=False, encoding='utf-8-sig')
        print(f"Saved {kind} area pivot: {wide_path}")

    # also dump raw JSON for downstream scripts
    json_path = OUT_DIR / "all_peaks.json"
    json_path.write_text(json.dumps(df.to_dict(orient='records'), indent=2, ensure_ascii=False), encoding='utf-8')
    print(f"Saved JSON: {json_path}")


if __name__ == '__main__':
    main()
