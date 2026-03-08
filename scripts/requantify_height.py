"""
Height-based HPLC quantification for Xul 5P Pretest experiments.

Uses peak HEIGHT instead of area to avoid PeakPicker vs Chemstation area discrepancy.
Height-based standard curves match Chemstation within ~1% (R^2 > 0.9999).

Standard curves (from Chemstation heights of pure Xyl/Xul standards):
  Xyl: H = 36.55 + 3028.73 * conc(mg/mL)   R^2 = 0.999994
  Xul: H = -5.92 + 2576.69 * conc(mg/mL)   R^2 = 0.999924

Half-peak note:
  Peak height is the SAME regardless of left/right half-peak method.
  So height-based quantification naturally handles co-eluting peaks.

Dilution factors (from Production Excel Sheet3 + named sheets):
  260106, 260108: D=10
  260114: D=50
  260115: D=100
  260126: D=4
  260127, 260129: D=10 (estimated, same era as 260106)
  260210, 260212, 260225: D=20
"""
import os
import sys
import csv
import re
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from chemstation_parser import ChemstationParser

# ── Standard curves (height-based) ──
STD_XYL = {'slope': 3028.73, 'intercept': 36.55, 'MW': 150.13}  # mg/mL
STD_XUL = {'slope': 2576.69, 'intercept': -5.92, 'MW': 150.13}  # mg/mL

# ── Dilution factors per experiment ──
DILUTION = {
    '260106': 10,
    '260108': 10,
    '260114': 50,
    '260115': 100,
    '260126': 4,
    '260127': 10,   # estimated
    '260129': 10,   # estimated
    '260210': 20,
    '260212': 20,
    '260225': 20,
}

# ── RT windows (min) ──
# Group A (260106-260210): Xyl ~11.28-11.31, Xul ~11.93-11.96
# Group B (260212, 260225): Xyl ~11.07-11.10, Xul ~11.64-11.67
RT_GROUP_A = {'Xyl': (10.9, 11.55), 'Xul': (11.60, 12.25)}
RT_GROUP_B = {'Xyl': (10.7, 11.35), 'Xul': (11.35, 11.95)}
LATE_EXPERIMENTS = {'260212', '260225'}  # experiments with shifted RTs

PRETEST_DIR = r'C:\Chem32\1\DATA\2. D-Xyl cascade HPLC\Xul 5P production\Pretest'
OUTPUT_CSV = os.path.join(os.path.dirname(__file__), 'result', 'pretest_analysis',
                          'quantification_height.csv')


def get_dilution(experiment_name):
    """Extract D from experiment folder name."""
    for key, d in DILUTION.items():
        if experiment_name.startswith(key):
            return d
    return None


def get_rt_windows(experiment_name):
    """Return RT windows based on experiment group."""
    date_code = experiment_name[:6]
    if date_code in LATE_EXPERIMENTS:
        return RT_GROUP_B
    return RT_GROUP_A


def estimate_baseline(time_min, signal, peak_rt):
    """
    Estimate local baseline at peak_rt using flat regions away from peaks.
    Uses median of signal in pre-peak (8.5-9.5 min) and post-peak (13.5-14.5 min)
    regions, then linearly interpolates at the peak position.
    """
    # Pre-peak baseline region
    pre_mask = (time_min >= 8.5) & (time_min <= 9.5)
    # Post-peak baseline region
    post_mask = (time_min >= 13.5) & (time_min <= 14.5)

    if pre_mask.sum() < 3 or post_mask.sum() < 3:
        # Fallback: use 5th percentile of wider region
        wide_mask = ((time_min >= 7.0) & (time_min <= 9.5)) | \
                    ((time_min >= 13.0) & (time_min <= 16.0))
        if wide_mask.sum() > 10:
            return np.percentile(signal[wide_mask], 5)
        return 0.0

    bl_pre = np.median(signal[pre_mask])
    bl_post = np.median(signal[post_mask])
    t_pre = 9.0   # center of pre-peak region
    t_post = 14.0  # center of post-peak region

    # Linear interpolation at peak_rt
    baseline = bl_pre + (bl_post - bl_pre) * (peak_rt - t_pre) / (t_post - t_pre)
    return baseline


def measure_peak_height(time_min, signal, rt_lo, rt_hi):
    """
    Measure peak height in the given RT window.
    Uses wide-region baseline estimation (matching Chemstation's baseline method).
    Validates that apex is a real peak (not a monotonic tail from adjacent peak).
    Returns (height, apex_rt) or (None, None) if no peak found.
    """
    mask = (time_min >= rt_lo) & (time_min <= rt_hi)
    if mask.sum() < 5:
        return None, None

    idx = np.where(mask)[0]
    region_signal = signal[idx]
    region_time = time_min[idx]
    n = len(region_signal)

    # Find apex (maximum signal in RT window)
    apex_local = np.argmax(region_signal)
    apex_signal = region_signal[apex_local]
    apex_rt = region_time[apex_local]

    # Validate: apex must not be at the very edge of the window (monotonic tail)
    edge_margin = max(3, n // 8)
    if apex_local < edge_margin or apex_local > n - edge_margin - 1:
        # Apex at edge = likely a tail from adjacent peak, not a real peak
        return None, None

    # Validate: signal should drop on both sides of apex
    left_min = np.min(region_signal[:apex_local]) if apex_local > 0 else apex_signal
    right_min = np.min(region_signal[apex_local:]) if apex_local < n - 1 else apex_signal
    drop_left = apex_signal - left_min
    drop_right = apex_signal - right_min
    # Require at least 30% drop on each side relative to peak height above baseline
    baseline = estimate_baseline(time_min, signal, apex_rt)
    height = apex_signal - baseline

    if height < 50:
        return None, None

    if drop_left < height * 0.15 or drop_right < height * 0.15:
        return None, None

    return float(height), float(apex_rt)


def height_to_conc(height, std, dilution):
    """Convert peak height to reaction concentration (mg/mL and mM)."""
    conc_vial = (height - std['intercept']) / std['slope']  # mg/mL in HPLC vial
    if conc_vial < 0:
        conc_vial = 0.0
    conc_reaction_mg = conc_vial * dilution  # mg/mL in reaction
    conc_reaction_mM = conc_reaction_mg / std['MW'] * 1000  # mM
    return conc_vial, conc_reaction_mg, conc_reaction_mM


def parse_sample_info(d_name, experiment_name):
    """Extract condition and time point from .D folder name."""
    name = d_name.replace('.D', '')

    # Extract time info
    time_str = ''
    for pattern in [r'_(\d+)H\.', r'_(\d+)H$', r'_(\d+)MIN',
                    r'_(\d+)_(\d+)H', r'_(\d+)h']:
        m = re.search(pattern, name, re.IGNORECASE)
        if m:
            groups = m.groups()
            if len(groups) == 2:
                time_str = f"{groups[0]}.{groups[1]}h"
            elif 'MIN' in pattern.upper():
                time_str = f"{int(groups[0])/60:.1f}h"
            else:
                time_str = f"{groups[0]}h"
            break

    # Determine if NC/Control
    is_nc = 'CONTROL' in name.upper() or '_NC_' in name.upper() or '_NC.' in name.upper()

    return {'sample_name': name, 'time': time_str, 'is_nc': is_nc}


def main():
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)

    experiments = sorted([d for d in os.listdir(PRETEST_DIR)
                         if os.path.isdir(os.path.join(PRETEST_DIR, d))])

    rows = []
    stats = {'total': 0, 'success': 0, 'no_peak': 0, 'error': 0}

    for exp in experiments:
        exp_path = os.path.join(PRETEST_DIR, exp)
        d_dirs = sorted([d for d in os.listdir(exp_path) if d.endswith('.D')])
        D = get_dilution(exp)
        rt_win = get_rt_windows(exp)

        if D is None:
            print(f"SKIP {exp}: unknown dilution factor")
            continue

        print(f"\n{exp} (D={D})")
        for dd in d_dirs:
            stats['total'] += 1
            d_path = os.path.join(exp_path, dd)
            ch_files = [f for f in os.listdir(d_path) if f.endswith('.ch')]
            if not ch_files:
                stats['error'] += 1
                continue

            ch_path = os.path.join(d_path, ch_files[0])
            try:
                parser = ChemstationParser(ch_path)
                parser.read()
                time_min = parser.time
                signal = parser.data
            except Exception as e:
                print(f"  ERROR {dd}: {e}")
                stats['error'] += 1
                continue

            info = parse_sample_info(dd, exp)

            # Measure Xyl peak height
            xyl_h, xyl_rt = measure_peak_height(
                time_min, signal, rt_win['Xyl'][0], rt_win['Xyl'][1])
            # Measure Xul peak height
            xul_h, xul_rt = measure_peak_height(
                time_min, signal, rt_win['Xul'][0], rt_win['Xul'][1])

            # Convert to concentrations
            if xyl_h is not None:
                xyl_vial, xyl_rxn_mg, xyl_rxn_mM = height_to_conc(xyl_h, STD_XYL, D)
            else:
                xyl_vial = xyl_rxn_mg = xyl_rxn_mM = None

            if xul_h is not None:
                xul_vial, xul_rxn_mg, xul_rxn_mM = height_to_conc(xul_h, STD_XUL, D)
            else:
                xul_vial = xul_rxn_mg = xul_rxn_mM = None

            if xyl_h is None and xul_h is None:
                stats['no_peak'] += 1
            else:
                stats['success'] += 1

            row = {
                'experiment': exp,
                'sample': info['sample_name'],
                'time': info['time'],
                'is_NC': info['is_nc'],
                'D': D,
                'Xyl_RT': f"{xyl_rt:.3f}" if xyl_rt else '',
                'Xyl_Height': f"{xyl_h:.1f}" if xyl_h else '',
                'Xyl_vial_mg_mL': f"{xyl_vial:.4f}" if xyl_vial is not None else '',
                'Xyl_rxn_mg_mL': f"{xyl_rxn_mg:.2f}" if xyl_rxn_mg is not None else '',
                'Xyl_rxn_mM': f"{xyl_rxn_mM:.2f}" if xyl_rxn_mM is not None else '',
                'Xul_RT': f"{xul_rt:.3f}" if xul_rt else '',
                'Xul_Height': f"{xul_h:.1f}" if xul_h else '',
                'Xul_vial_mg_mL': f"{xul_vial:.4f}" if xul_vial is not None else '',
                'Xul_rxn_mg_mL': f"{xul_rxn_mg:.2f}" if xul_rxn_mg is not None else '',
                'Xul_rxn_mM': f"{xul_rxn_mM:.2f}" if xul_rxn_mM is not None else '',
            }
            rows.append(row)

            # Print summary for NC samples
            if info['is_nc']:
                xyl_str = f"Xyl={xyl_rxn_mg:.1f}mg/mL" if xyl_rxn_mg else "Xyl=N/A"
                xul_str = f"Xul={xul_rxn_mg:.1f}mg/mL" if xul_rxn_mg else "Xul=N/A"
                print(f"  NC {info['time']}: {xyl_str}, {xul_str}")

    # Write CSV
    fieldnames = ['experiment', 'sample', 'time', 'is_NC', 'D',
                  'Xyl_RT', 'Xyl_Height', 'Xyl_vial_mg_mL', 'Xyl_rxn_mg_mL', 'Xyl_rxn_mM',
                  'Xul_RT', 'Xul_Height', 'Xul_vial_mg_mL', 'Xul_rxn_mg_mL', 'Xul_rxn_mM']
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n--- Summary ---")
    print(f"Total files: {stats['total']}")
    print(f"Successfully quantified: {stats['success']}")
    print(f"No peak detected: {stats['no_peak']}")
    print(f"Parse errors: {stats['error']}")
    print(f"Output: {OUTPUT_CSV}")


if __name__ == '__main__':
    main()
