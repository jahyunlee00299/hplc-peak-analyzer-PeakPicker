"""
260903 Cottonii GO-difference: Scheme E -- two-sided (separately fit) calibration
=====================================================================================
Follow-up to the D7 adversarial review of compare_260903_cottonii_go_schemes.py's
Scheme B (Formate-normalized, single shared area->mM slope k). The review found
the sheet's own implied treated-side calibration (sheet tag_mM / this reanalysis's
treated p10.9 area) scatters 1.87-3.12x the shared k used everywhere else --
meaning the original spreadsheet's method almost certainly did NOT use one shared
linear slope for both untreated and treated sides.

This script fits each side's calibration SEPARATELY against the sheet's own
values at the confidently-mapped early timepoints (vial1-7 <-> t=0..12h, per
DECISION_LOG D1), instead of Formate-normalizing the treated area onto a shared
untreated-side scale.

RESULT (see DECISION_LOG D8): this scheme tracks the sheet noticeably better at
EARLY timepoints than either Scheme A (raw) or Scheme B (formate-corrected) --
consistently closer mean, tight SD. BUT extrapolating the 2-parameter treated-side
fit (fitted only on t=1-12h treated areas ~19k-68k) to the plateau region
(treated areas ~77k-95k, well outside the fitted range) produces ALL 24 plateau
gal values NEGATIVE (mean=-9.33 mM) -- a linear-extrapolation failure, not an
improvement. This scheme is therefore NOT a ready answer either; kept here as a
documented, working diagnostic for whoever picks this up next, not as a
recommendation.

To make this scheme usable, the missing piece is an independent treated-side
calibration point (or points) in the plateau's concentration range -- e.g. a
GO-treated injection of a known low-gal standard, or spiked-recovery samples --
which this raw dataset does not contain.
"""
import sys
import io
from pathlib import Path

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import numpy as np
import pandas as pd

RESULTS_DIR = Path(r"C:\Users\Jahyun\scratch\cottonii_requant\results")
EARLY_TIMEPOINTS = [0, 1, 3, 4.5, 6, 9, 12]

SHEET_GALTAG = {
    1: [131.86607670062577, 120.10513150804795, 116.2861942799401, 110.56721053588596,
        108.39704198778115, 104.45236735287128, 103.23891930320636],
    2: [131.79201310017004, 121.10518709186084, 113.1959430783017, 114.54064390927067,
        107.20014006162229, 101.42449241048192, 99.86712136508382],
    3: [131.11086434917044, 122.14923435324941, 114.8768191170129, 111.86988946588716,
        107.44498329397987, 100.80053284033063, 102.106757368226],
}
SHEET_TAG = {
    1: [0, 23.431816511971594, 46.473810734818464, 57.5472023252326, 65.24461157476104,
        80.39746158872784, 92.94705732440343],
    2: [0, 26.419987765263045, 44.18415422831855, 60.52431393396846, 67.55338989661406,
        85.39745453949644, 88.01672979821863],
    3: [0, 28.165034298273063, 50.147059783572224, 60.681836348012595, 66.94945061494747,
        77.17342015902646, 90.99704560304069],
}


def load_areas():
    return pd.read_csv(RESULTS_DIR / "area_pivot_untreated.csv"), pd.read_csv(RESULTS_DIR / "area_pivot_treated.csv")


def fit_calibrations(untreated, treated):
    rows = []
    for rep in [1, 2, 3]:
        for vial, th in zip(range(1, 8), EARLY_TIMEPOINTS):
            ua = untreated[(untreated.vial == vial) & (untreated.replicate == rep)]['p10.9'].values[0]
            ta = treated[(treated.vial == vial) & (treated.replicate == rep)]['p10.9'].values[0]
            rows.append({'vial': vial, 'rep': rep, 'time_h': th, 'u_area': ua, 't_area': ta,
                         'galtag_mM': SHEET_GALTAG[rep][vial - 1], 'tag_mM': SHEET_TAG[rep][vial - 1]})
    df = pd.DataFrame(rows)

    Xu, Yu = df['u_area'].values, df['galtag_mM'].values
    Au = np.vstack([Xu, np.ones_like(Xu)]).T
    coef_u, *_ = np.linalg.lstsq(Au, Yu, rcond=None)
    r2_u = 1 - np.sum((Yu - Au @ coef_u) ** 2) / np.sum((Yu - Yu.mean()) ** 2)

    df_excl0 = df[df.time_h > 0]  # t=0 tag=0 by construction, degenerate for a treated-side fit
    Xt, Yt = df_excl0['t_area'].values, df_excl0['tag_mM'].values
    At = np.vstack([Xt, np.ones_like(Xt)]).T
    coef_t, *_ = np.linalg.lstsq(At, Yt, rcond=None)
    r2_t = 1 - np.sum((Yt - At @ coef_t) ** 2) / np.sum((Yt - Yt.mean()) ** 2)

    return df, coef_u, r2_u, coef_t, r2_t


def main():
    untreated, treated = load_areas()
    df, coef_u, r2_u, coef_t, r2_t = fit_calibrations(untreated, treated)

    print(f"untreated calib: galtag_mM = {coef_u[0]:.6e}*area + {coef_u[1]:.4f}  R2={r2_u:.5f}")
    print(f"treated calib (excl t=0): tag_mM = {coef_t[0]:.6e}*area + {coef_t[1]:.4f}  R2={r2_t:.5f}")

    def u_mM(area):
        return coef_u[0] * area + coef_u[1]

    def t_mM(area):
        return coef_t[0] * area + coef_t[1]

    print("\n=== Scheme E early timepoints (in-range: should be trusted) ===")
    for th in EARLY_TIMEPOINTS:
        sub = df[df.time_h == th]
        gal_vals = u_mM(sub.u_area.values) - t_mM(sub.t_area.values)
        print(f"  t={th:5}h  gal_mean={gal_vals.mean():8.3f}  gal_sd={gal_vals.std(ddof=1):7.3f}  n_neg={(gal_vals < 0).sum()}")

    plateau_u = untreated[untreated.vial >= 8]
    plateau_t = treated[treated.vial >= 8]
    pm = plateau_u.merge(plateau_t, on=['vial', 'replicate'], suffixes=('_u', '_t'))
    pm['gal_E'] = u_mM(pm['p10.9_u'].values) - t_mM(pm['p10.9_t'].values)
    pm.to_csv(RESULTS_DIR / "scheme_E_plateau.csv", index=False, encoding='utf-8-sig')

    print(f"\n=== Scheme E plateau (OUT-OF-RANGE extrapolation -- NOT trustworthy, see DECISION_LOG D8) ===")
    print(f"  mean={pm.gal_E.mean():.3f}  SD={pm.gal_E.std(ddof=1):.3f}  n_neg={(pm.gal_E < 0).sum()}/{len(pm)}")
    print("  Treated-side fit range (t_area): "
          f"{df[df.time_h>0].t_area.min():.0f}-{df[df.time_h>0].t_area.max():.0f}  "
          f"vs plateau t_area range: {pm['p10.9_t'].min():.0f}-{pm['p10.9_t'].max():.0f}  "
          "(plateau lies well outside the fitted domain -- linear extrapolation is not valid here)")
    print(f"\nSaved: {RESULTS_DIR / 'scheme_E_plateau.csv'}")


if __name__ == '__main__':
    main()
