"""
Validation of peak_integrator against Chemstation reference values.

Test sample: NE 100mM Xyl (no enzyme control)
  - D-Xylose RT=11.105, Chemstation area=312105.1
"""

import sys
sys.path.insert(0, r"C:\Users\Jahyun\PeakPicker")

from src.chemstation_parser import read_chemstation_file
from src.peak_integrator import find_peak_boundaries, integrate_peak, integrate_peak_detailed

CH_FILE = (
    r"C:\Chem32\1\DATA\2. D-Xyl cascade HPLC\Xul 5P production\Pretest"
    r"\260324_Xul5P_Test\XUL5P_NE_100XYL_100ACP_1ATP_1_5H.D\RID1A.ch"
)
CHEMSTATION_XYL_AREA = 312105.1
CHEMSTATION_XYL_RT = 11.105


def main():
    time, intensity = read_chemstation_file(CH_FILE)
    print(f"Loaded: {len(time)} points, {time[0]:.3f}-{time[-1]:.3f} min\n")

    # --- Test 1: full mode on D-Xylose ---
    print("=" * 60)
    print("Test 1: D-Xylose (full mode)")
    print("=" * 60)
    result = integrate_peak_detailed(time, intensity, rt_hint=11.1, mode="full")
    pct_diff = (result["area"] - CHEMSTATION_XYL_AREA) / CHEMSTATION_XYL_AREA * 100
    print(f"  Peak RT:    {result['peak_rt']:.3f} min (Chemstation: {CHEMSTATION_XYL_RT})")
    print(f"  Boundaries: {result['rt_lo']:.3f} - {result['rt_hi']:.3f} min")
    print(f"  Peak max:   {result['peak_max']:.1f} nRIU")
    print(f"  Area:       {result['area']:.1f} nRIU*s")
    print(f"  Chemstation:{CHEMSTATION_XYL_AREA:.1f} nRIU*s")
    print(f"  Difference: {pct_diff:+.2f}%")
    print()

    # --- Test 2: left_half mode on D-Xylose ---
    print("=" * 60)
    print("Test 2: D-Xylose (left_half mode)")
    print("=" * 60)
    result_lh = integrate_peak_detailed(time, intensity, rt_hint=11.1, mode="left_half")
    print(f"  Peak RT:    {result_lh['peak_rt']:.3f} min")
    print(f"  Boundaries: {result_lh['rt_lo']:.3f} - {result_lh['rt_hi']:.3f} min")
    print(f"  Area (L):   {result_lh['area']:.1f} nRIU*s")
    print()

    # --- Test 3: right_half mode on D-Xylose ---
    print("=" * 60)
    print("Test 3: D-Xylose (right_half mode)")
    print("=" * 60)
    result_rh = integrate_peak_detailed(time, intensity, rt_hint=11.1, mode="right_half")
    print(f"  Peak RT:    {result_rh['peak_rt']:.3f} min")
    print(f"  Boundaries: {result_rh['rt_lo']:.3f} - {result_rh['rt_hi']:.3f} min")
    print(f"  Area (R):   {result_rh['area']:.1f} nRIU*s")
    print()

    # --- Test 4: left + right should approximate full ---
    print("=" * 60)
    print("Test 4: left_half + right_half vs full")
    print("=" * 60)
    sum_halves = result_lh["area"] + result_rh["area"]
    print(f"  Left + Right: {sum_halves:.1f} nRIU*s")
    print(f"  Full:         {result['area']:.1f} nRIU*s")
    print(f"  Ratio:        {sum_halves / result['area']:.4f}")
    print()

    # --- Summary ---
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    if abs(pct_diff) < 5.0:
        print(f"  PASS: Full mode area within 5% of Chemstation ({pct_diff:+.2f}%)")
    else:
        print(f"  WARN: Full mode area differs by {pct_diff:+.2f}% from Chemstation")


if __name__ == "__main__":
    main()
