"""
260828 ChiralPak AD-H baseline separation check (D-Gal / L-Gal / D-Man / Galactitol, standard)
- Notion/Asana source: "Baseline 분리 확인 (D-Gal/L-Gal/mannose/galactitol, standard)"
- Overlay chromatograms, detect top peaks per standard, and check RT overlap.
- Peak-shape / area-vs-injection-amount check to judge whether the standard
  concentration can be lowered (10 mM injected samples asked about specifically).
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
from scipy.signal import find_peaks, peak_widths

PEAKPICKER_SRC = os.path.expanduser(r"~\PeakPicker\src")
sys.path.insert(0, PEAKPICKER_SRC)
from chemstation_parser import ChemstationParser

DATA_DIR = os.path.expanduser(r"~\scratch\hplc_baseline_260831")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PNG = os.path.join(SCRIPT_DIR, "peakpicker_260828_ADH_baseline_standard.png")
OUTPUT_XLSX = os.path.join(SCRIPT_DIR, "260828_ADH_baseline_standard_results.xlsx")

# (folder, label, stock_mM, dilution_pct, inj_uL, color)
SAMPLES = [
    ("260828_ADH_D_GAL_1M_0_5PERCENT.D",     "D-Gal 5 mM",        1000, 0.5, 60, "#1f77b4"),
    ("260828_ADH_L_GAL_1M_1PERCENT.D",       "L-Gal 10 mM",       1000, 1.0, 60, "#ff7f0e"),
    ("260828_ADH_D_MAN_1M_1PERCENT.D",       "D-Man 10 mM",       1000, 1.0, 60, "#2ca02c"),
    ("260828_ADH_GALACTITOL_100MM_1PERCENT.D","Galactitol 1 mM",   100, 1.0, 60, "#9b59b6"),
]


def load_sample(folder_name):
    ch_path = os.path.join(DATA_DIR, folder_name, "RID1A.ch")
    if not os.path.exists(ch_path):
        print(f"  [WARN] File not found: {ch_path}")
        return None, None
    parser = ChemstationParser(ch_path)
    time, intensity = parser.read()
    return time, intensity


def detect_top_peaks(time, intensity, n=3, prominence_frac=0.02, distance_pts=40,
                      rt_lo=None, rt_hi=None):
    """Detect top-N peaks. If rt_lo/rt_hi given, restrict search to that RT
    window so the solvent-front/injection-artifact region (~5-8 min on this
    method) does not get picked as the 'main' peak."""
    if rt_lo is not None or rt_hi is not None:
        lo = rt_lo if rt_lo is not None else time[0]
        hi = rt_hi if rt_hi is not None else time[-1]
        mask = (time >= lo) & (time <= hi)
        search_time, search_sig = time[mask], intensity[mask]
        offset = np.where(mask)[0][0] if mask.any() else 0
    else:
        search_time, search_sig = time, intensity
        offset = 0

    prominence = max(np.ptp(search_sig) * prominence_frac, 50)
    peaks, props = find_peaks(search_sig, prominence=prominence, distance=distance_pts)
    peaks = peaks + offset
    if len(peaks) == 0:
        return []
    order = np.argsort(props["prominences"])[::-1][:n]
    out = []
    for i in order:
        p = peaks[i]
        widths, width_heights, left_ips, right_ips = peak_widths(intensity, [p], rel_height=0.5)
        rt = float(time[p])
        # convert index-width to minutes (assume uniform sampling)
        dt = float(time[1] - time[0])
        fwhm_min = float(widths[0] * dt)
        out.append({
            "rt_min": rt,
            "height": float(intensity[p]),
            "prominence": float(props["prominences"][i]),
            "fwhm_min": fwhm_min,
        })
    out.sort(key=lambda d: d["rt_min"])
    return out


def get_area(time, intensity, rt_lo, rt_hi):
    mask = (time >= rt_lo) & (time <= rt_hi)
    if mask.sum() < 2:
        return 0.0
    baseline = np.interp(time[mask], [time[mask][0], time[mask][-1]],
                          [intensity[mask][0], intensity[mask][-1]])
    return float(np.trapz(np.maximum(intensity[mask] - baseline, 0), time[mask] * 60))


def main():
    print("=" * 70)
    print("260828 ADH baseline separation check - D-Gal/L-Gal/D-Man/Galactitol")
    print("=" * 70)

    loaded = {}
    for folder, label, stock_mM, pct, inj_uL, color in SAMPLES:
        t, sig = load_sample(folder)
        if t is not None:
            conc_mM = stock_mM * pct / 100.0
            mass_nmol = conc_mM * (inj_uL / 1000.0) * 1000  # mM * mL * 1000 = nmol... check below
            # conc(mM) * inj_vol(uL) = amount in nmol: mM = mmol/L = umol/mL -> umol = mM*mL
            amount_nmol = conc_mM * (inj_uL / 1000.0) * 1000.0  # umol -> nmol
            loaded[folder] = {
                "time": t, "intensity": sig, "label": label, "color": color,
                "conc_mM": conc_mM, "inj_uL": inj_uL, "amount_nmol": amount_nmol,
            }
            print(f"  OK  {label:20s}  {len(t):6d} pts  conc={conc_mM:.2f} mM  inj={inj_uL} uL  amount={amount_nmol:.1f} nmol")
        else:
            print(f"  FAIL {label}")

    if not loaded:
        print("No samples loaded.")
        return

    # -- Peak detection (top 3 per sample: analyte + likely solvent-front/artifact) -----
    # Solvent front / injection artifact sits at ~5-8 min on this method
    # (large negative dip common to every sample, incl. blank matrix) -- exclude it.
    ANALYTE_RT_LO, ANALYTE_RT_HI = 8.0, 22.0

    print(f"\n--- Top peaks per standard (prominence-ranked, RT {ANALYTE_RT_LO}-{ANALYTE_RT_HI} min only) ---")
    print(f"    (RT < {ANALYTE_RT_LO} min excluded: solvent-front / injection artifact, common to all samples)")
    peak_table = {}
    for folder, d in loaded.items():
        peaks = detect_top_peaks(d["time"], d["intensity"], n=3,
                                  rt_lo=ANALYTE_RT_LO, rt_hi=ANALYTE_RT_HI)
        peak_table[folder] = peaks
        print(f"\n{d['label']}:")
        for pk in peaks:
            print(f"  RT={pk['rt_min']:7.3f} min  height={pk['height']:9.1f}  "
                  f"prom={pk['prominence']:9.1f}  FWHM={pk['fwhm_min']:.3f} min")

    # -- Main-peak RT + separation check --------------------------------------
    print("\n--- Main analyte peak (highest prominence) & baseline separation ---")
    main_peaks = {}
    for folder, d in loaded.items():
        peaks = peak_table[folder]
        if not peaks:
            continue
        main_pk = max(peaks, key=lambda p: p["prominence"])
        main_peaks[folder] = main_pk
        print(f"  {d['label']:20s}  main RT = {main_pk['rt_min']:.3f} min  FWHM = {main_pk['fwhm_min']:.3f} min")

    rts = sorted(((d["label"], main_peaks[f]["rt_min"]) for f, d in loaded.items() if f in main_peaks),
                 key=lambda x: x[1])
    print("\n  RT order (low -> high):")
    for i, (label, rt) in enumerate(rts):
        gap = "" if i == 0 else f"   gap from prev = {rt - rts[i-1][1]:+.3f} min"
        print(f"    {label:20s}  RT={rt:.3f}{gap}")

    # -- Peak-shape / area vs injection-amount check (for the 20 mM-lowering question) --
    print("\n--- Peak shape vs injection amount (for the question: OK to lower to ~20 mM equiv concentration?) ---")
    print(f"{'Sample':20s}  {'Amount(nmol)':>13s}  {'RT(min)':>8s}  {'Height':>10s}  {'FWHM(min)':>10s}  "
          f"{'Area(win)':>12s}  {'Area/Amount':>12s}  {'Tailing(approx)':>16s}")
    shape_rows = []
    for folder, d in loaded.items():
        pk = main_peaks.get(folder)
        if pk is None:
            continue
        rt = pk["rt_min"]
        half_win = max(pk["fwhm_min"] * 2.5, 1.0)
        lo, hi = rt - half_win, rt + half_win
        area = get_area(d["time"], d["intensity"], lo, hi)
        amount = d["amount_nmol"]
        area_per_amount = area / amount if amount > 0 else float("nan")

        # crude asymmetry/tailing check: compare left vs right half-width at 10% height
        t, sig = d["time"], d["intensity"]
        mask = (t >= lo) & (t <= hi)
        tt, yy = t[mask], sig[mask]
        baseline = np.interp(tt, [tt[0], tt[-1]], [yy[0], yy[-1]])
        yy_corr = yy - baseline
        apex_i = int(np.argmax(yy_corr))
        thresh = yy_corr[apex_i] * 0.1
        left_idx = np.where(yy_corr[:apex_i] <= thresh)[0]
        right_idx = np.where(yy_corr[apex_i:] <= thresh)[0]
        if len(left_idx) and len(right_idx):
            t_left = tt[left_idx[-1]]
            t_right = tt[apex_i + right_idx[0]]
            t_apex = tt[apex_i]
            a_half = t_apex - t_left
            b_half = t_right - t_apex
            tailing = b_half / a_half if a_half > 0 else float("nan")
        else:
            tailing = float("nan")

        print(f"{d['label']:20s}  {amount:13.1f}  {rt:8.3f}  {pk['height']:10.1f}  {pk['fwhm_min']:10.3f}  "
              f"{area:12.1f}  {area_per_amount:12.2f}  {tailing:16.2f}")
        shape_rows.append({
            "label": d["label"], "amount_nmol": amount, "rt_min": rt,
            "height": pk["height"], "fwhm_min": pk["fwhm_min"], "area": area,
            "area_per_amount": area_per_amount, "tailing_factor": tailing,
            "conc_mM": d["conc_mM"],
        })

    # ==========================================================================
    # Figure: overlay + zoom
    # ==========================================================================
    fig, axes = plt.subplots(2, 1, figsize=(14, 12))
    fig.suptitle(
        "260828 ChiralPak AD-H Baseline Separation - D-Gal/L-Gal/D-Man/Galactitol (standard)\n"
        "AD_H_0.5_40C_60INJ_300BAR_30MIN_YR.M | 60 uL inj | RID",
        fontsize=12, fontweight="bold"
    )

    ax = axes[0]
    for folder, d in loaded.items():
        ax.plot(d["time"], d["intensity"], color=d["color"], linewidth=1.3, label=d["label"])
    ax.set_xlim(0, 30)
    ax.set_title("(a) Full chromatogram overlay", fontsize=10, fontweight="bold")
    ax.set_xlabel("Retention Time (min)")
    ax.set_ylabel("RID Signal (nRIU)")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    ax = axes[1]
    for folder, d in loaded.items():
        ax.plot(d["time"], d["intensity"], color=d["color"], linewidth=1.5, label=d["label"])
        pk = main_peaks.get(folder)
        if pk:
            ax.annotate(f"{pk['rt_min']:.2f}", (pk['rt_min'], pk['height']),
                        textcoords="offset points", xytext=(0, 8), fontsize=8, color=d["color"])
    if rts:
        lo = min(r for _, r in rts) - 1.5
        hi = max(r for _, r in rts) + 1.5
        ax.set_xlim(max(lo, ANALYTE_RT_LO - 1.5), hi)
    ax.set_title("(b) Zoom on main analyte peaks (baseline separation check)", fontsize=10, fontweight="bold")
    ax.set_xlabel("Retention Time (min)")
    ax.set_ylabel("RID Signal (nRIU)")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    plt.tight_layout(rect=[0, 0, 1, 0.94])
    plt.savefig(OUTPUT_PNG, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\nChromatogram saved: {OUTPUT_PNG}")

    # ==========================================================================
    # Excel export
    # ==========================================================================
    try:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Main_Peak_RT"
        ws.append(["Sample", "Conc_mM", "Amount_nmol", "RT_min", "Height", "FWHM_min",
                   "Area_window", "Area_per_Amount", "Tailing_factor"])
        for row in shape_rows:
            ws.append([row["label"], row["conc_mM"], row["amount_nmol"], row["rt_min"],
                       row["height"], row["fwhm_min"], row["area"],
                       row["area_per_amount"], row["tailing_factor"]])

        ws2 = wb.create_sheet("All_Detected_Peaks")
        ws2.append(["Sample", "RT_min", "Height", "Prominence", "FWHM_min"])
        for folder, d in loaded.items():
            for pk in peak_table[folder]:
                ws2.append([d["label"], pk["rt_min"], pk["height"], pk["prominence"], pk["fwhm_min"]])

        wb.save(OUTPUT_XLSX)
        print(f"Excel saved: {OUTPUT_XLSX}")
    except ImportError:
        print("[WARN] openpyxl not installed, skipping Excel export.")

    print("\nDone.")


if __name__ == "__main__":
    main()
