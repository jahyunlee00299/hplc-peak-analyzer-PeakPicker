"""
260903 Cottonii GO-difference: formal error propagation per scheme
=====================================================================
Success criterion (e) from the task brief: propagate uncertainty at each
timepoint for each scheme, and report which scheme removes negatives/
non-physical rises.

Error model: for a single injection, peak-area integration noise is estimated
from the local chromatographic baseline noise (std of the signal in a flat
region immediately flanking the peak, propagated through the trapezoidal
integration -- same construction PeakPicker already uses for min_prominence
detection, reused here for the uncertainty estimate rather than just peak
detection).

Propagation:
  Scheme A (absolute diff):     sigma_gal = sqrt(sigma_u^2 + sigma_t^2) * k
  Scheme B (formate-corrected): t_corr = t_area / R,  R = t_formate/u_formate
      sigma_gal = k * sqrt(sigma_u^2 + (sigma_t/R)^2 + (t_area/R^2 * sigma_R)^2)
      sigma_R = R * sqrt((sigma_t_formate/t_formate)^2 + (sigma_u_formate/u_formate)^2)
  (standard first-order propagation of independent Gaussian noise sources)

This is compared against the empirical (measured, replicate-to-replicate) SD
already computed in compare_260903_cottonii_go_schemes.py -- if the two agree,
the noise model is validated; if propagated sigma is much smaller than
empirical SD, an unmodeled source (e.g. real biological replicate variance,
not just chromatographic noise) dominates.
"""
import sys
import io
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import numpy as np
import pandas as pd
from rainbow.agilent.chemstation import parse_ch

DATA_DIR = Path(r"C:\Users\Jahyun\scratch\cot7z\260624_cottonii_bioreactor")
RESULTS_DIR = Path(r"C:\Users\Jahyun\scratch\cottonii_requant\results")

import re


def vial_key(name):
    m = re.match(r'(?:260625_)?COTTONII_REACTOR(?:_GO)?_(\d+)_(\d+)\.D', name)
    return int(m.group(1)), int(m.group(2))


def peak_area_uncertainty(time, intensity, left_rt, right_rt, noise_region_margin=0.3):
    """Estimate area uncertainty from local baseline noise (std of second-difference
    in a flanking flat region), propagated through the trapezoidal rule:
    sigma_area ~= sigma_noise * sqrt(n_points) * dt(seconds) [random baseline-noise
    contribution to a numerically-integrated boxcar-like region]. Uses the flanking
    region just outside [left_rt,right_rt] as the local noise estimate."""
    dt = np.median(np.diff(time))  # min
    lo_mask = (time >= left_rt - noise_region_margin) & (time <= left_rt)
    hi_mask = (time >= right_rt) & (time <= right_rt + noise_region_margin)
    flank = np.concatenate([intensity[lo_mask], intensity[hi_mask]])
    if len(flank) < 4:
        return np.nan
    noise_std = np.std(np.diff(flank))  # nRIU, point-to-point
    n_pts = int(round((right_rt - left_rt) / dt)) + 1
    sigma_area = noise_std * np.sqrt(n_pts) * dt * 60.0  # nRIU*s
    return float(sigma_area)


def read_rid(ch_path):
    r = parse_ch(str(ch_path))
    time = np.asarray(r.xlabels, dtype=float)
    sig = np.asarray(r.data, dtype=float).flatten()
    n = min(len(time), len(sig))
    return time[:n], sig[:n]


def main():
    all_peaks = pd.read_csv(RESULTS_DIR / "all_peaks_long.csv")

    untreated_folders = sorted(
        (d for d in DATA_DIR.glob("COTTONII_REACTOR_*.D") if not d.stem.startswith("COTTONII_REACTOR_GO")),
        key=lambda d: vial_key(d.name))
    treated_folders = sorted(DATA_DIR.glob("260625_COTTONII_REACTOR_GO_*.D"), key=lambda d: vial_key(d.name))

    sigma_rows = []
    for kind, folders in [('untreated', untreated_folders), ('treated', treated_folders)]:
        for d in folders:
            ch = d / "RID1A.ch"
            time, sig = read_rid(ch)
            v, rep = vial_key(d.name)
            sub = all_peaks[(all_peaks['kind'] == kind) & (all_peaks['vial'] == v) & (all_peaks['replicate'] == rep)]
            for _, row in sub.iterrows():
                sigma = peak_area_uncertainty(time, sig, row['left_rt'], row['right_rt'])
                sigma_rows.append({'kind': kind, 'vial': v, 'replicate': rep, 'peak': row['peak'],
                                    'area': row['area'], 'sigma_area': sigma})

    sigma_df = pd.DataFrame(sigma_rows)
    sigma_df.to_csv(RESULTS_DIR / "area_uncertainty.csv", index=False, encoding='utf-8-sig')
    print(f"Saved per-injection area uncertainty: {RESULTS_DIR / 'area_uncertainty.csv'}")

    # Typical relative uncertainty of the p10.9 peak (the one that matters for gal)
    p109 = sigma_df[sigma_df['peak'] == 'p10.9'].copy()
    p109['rel_sigma_pct'] = p109['sigma_area'] / p109['area'] * 100
    print("\nTypical p10.9 (combined/tag peak) relative area uncertainty from local baseline noise:")
    print(p109.groupby('kind')['rel_sigma_pct'].describe().to_string())

    p159 = sigma_df[sigma_df['peak'] == 'p15.9'].copy()
    p159['rel_sigma_pct'] = p159['sigma_area'] / p159['area'] * 100
    print("\nTypical p15.9 (Formate reference) relative area uncertainty:")
    print(p159.groupby('kind')['rel_sigma_pct'].describe().to_string())

    # Now propagate for scheme A and scheme B, at t=0 (vial1) and plateau (vial8-15) as
    # representative early/late cases
    k = 5.49621596e-04  # from compare_260903_cottonii_go_schemes.py anchor

    def get(kind, vial, rep, peak):
        row = sigma_df[(sigma_df.kind == kind) & (sigma_df.vial == vial) & (sigma_df.replicate == rep) & (sigma_df.peak == peak)]
        if row.empty:
            return np.nan, np.nan
        return row['area'].values[0], row['sigma_area'].values[0]

    print("\n=== Propagated sigma_gal (Scheme A vs Scheme B) at representative vials ===")
    print(f"{'vial':>4} {'rep':>3}  {'sigma_A(mM)':>12}  {'sigma_B(mM)':>12}  {'gal_A(mM)':>10}  {'gal_B(mM)':>10}")
    for vial in [1, 4, 7, 8, 11, 15]:
        for rep in [1, 2, 3]:
            u_area, u_sig = get('untreated', vial, rep, 'p10.9')
            t_area, t_sig = get('treated', vial, rep, 'p10.9')
            uf_area, uf_sig = get('untreated', vial, rep, 'p15.9')
            tf_area, tf_sig = get('treated', vial, rep, 'p15.9')
            if any(np.isnan(x) for x in [u_area, t_area, uf_area, tf_area]):
                continue

            gal_A_mM = (u_area - t_area) * k
            sigma_A = k * np.sqrt(u_sig**2 + t_sig**2)

            R = tf_area / uf_area
            t_corr = t_area / R
            gal_B_mM = (u_area - t_corr) * k
            sigma_R = R * np.sqrt((tf_sig / tf_area) ** 2 + (uf_sig / uf_area) ** 2)
            sigma_t_corr = t_corr * np.sqrt((t_sig / t_area) ** 2 + (sigma_R / R) ** 2)
            sigma_B = k * np.sqrt(u_sig**2 + sigma_t_corr**2)

            print(f"{vial:4d} {rep:3d}  {sigma_A:12.4f}  {sigma_B:12.4f}  {gal_A_mM:10.4f}  {gal_B_mM:10.4f}")

    print("\nNote: comparing these PROPAGATED (chromatographic baseline-noise-only) sigmas against")
    print("the EMPIRICAL (replicate-to-replicate) SD already in schemes_early_comparison_summary.csv")
    print("and plateau_ensemble_raw.csv shows whether baseline noise alone explains the observed")
    print("scatter, or whether unmodeled biological/injection variance dominates.")


if __name__ == '__main__':
    main()
