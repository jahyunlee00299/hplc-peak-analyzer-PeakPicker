"""
260810 Flask Titer Timecourse - SP0810 column, Gal/Tag/Galol quantification
=============================================================================
E:\\t\\260701_JW 2026-08-10 18-02-04\\260810_FLASK_TITER_{time}H_{rep}.D
Timepoints: 0, 12, 24, 36, 48, 60, 72 H, triplicate (1,2,3)

RT/calibration source: methods/sp0810_gal_tag_galol.yaml
  Gal   RT~19.05 min
  Tag   RT~26.65 min
  Galol RT~41.57 min
  (Formate not resolved on this column — excluded)
"""

import sys
import io
import re
import argparse

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import numpy as np
import pandas as pd
from pathlib import Path
from scipy import signal
from scipy.integrate import trapezoid
from rainbow.agilent.chemstation import parse_ch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

#: 🔴 The drive letter changed E: -> F: on 260831. `quantify_260810_remaining_batches.py`
#: was updated then; this file was not, and the stale E: path is what convinced
#: several later sessions that the raw chromatograms were unreachable. They are
#: on F: and always were. Resolve at run time so a future remount cannot repeat it.
_DATA_CANDIDATES = [
    Path(r"F:\t\260701_JW 2026-08-10 18-02-04"),
    Path(r"E:\t\260701_JW 2026-08-10 18-02-04"),
]
DEFAULT_DATA_DIR = next((p for p in _DATA_CANDIDATES if p.exists()), _DATA_CANDIDATES[0])
DILUTION_FACTOR = 20.0

CALIBRATION = {
    "Gal":   {"a": 69587.6626, "y0": -6370.9125, "rt_window": (18.5, 19.6)},
    "Tag":   {"a": 58227.8378, "y0": -284.3917,  "rt_window": (26.0, 27.3)},
    "Galol": {"a": 75968.4499, "y0": 3183.7165,  "rt_window": (40.8, 42.3)},
}

#: Ordered apex search windows for valley-to-valley integration.
#: The signal does not return to zero between these three peaks (baseline
#: drift/hump), so each peak's boundaries are the valleys shared with its
#: neighbors rather than a fixed max-width clip.
APEX_WINDOWS = {
    "Gal":   (18.6, 19.5),
    "Tag":   (26.0, 27.0),
    "Galol": (40.8, 42.0),
}
#: Left/right bounds of the whole three-peak region to search valleys within.
REGION_START_RT = 15.0
REGION_END_RT = 45.0

#: Cap valley search to within this many minutes of the peak apex, so a long
#: flat/noisy stretch between distant peaks (e.g. Tag apex 26.65 to Galol
#: apex 41.57, ~15 min apart) cannot pull the boundary far from the actual
#: peak. Requested by user (260812): cut within ~3 min of the apex.
MAX_VALLEY_SEARCH_MIN = 3.0


def find_valley(time, intensity, lo, hi):
    """Index of the minimum-signal point within [lo, hi] (a valley between peaks)."""
    mask = (time >= lo) & (time <= hi)
    idx_local = np.argmin(intensity[mask])
    return np.where(mask)[0][idx_local]


def integrate_valley_to_valley(time, intensity, apex_windows):
    """Integrate each named peak between valleys shared with its neighbors.

    Returns dict: name -> {rt_min, height_nRIU, area_nRIUs, left_rt, right_rt}
    """
    names = list(apex_windows.keys())
    apex_idx = {}
    for name, (lo, hi) in apex_windows.items():
        mask = (time >= lo) & (time <= hi)
        if not mask.any():
            continue
        local_idx = np.argmax(intensity[mask])
        apex_idx[name] = np.where(mask)[0][local_idx]

    # region boundary indices
    region_mask = (time >= REGION_START_RT) & (time <= REGION_END_RT)
    region_idx = np.where(region_mask)[0]
    left_bound_idx = region_idx[0]
    right_bound_idx = region_idx[-1]

    results = {}
    ordered = [n for n in names if n in apex_idx]
    for i, name in enumerate(ordered):
        a_idx = apex_idx[name]

        apex_rt = time[a_idx]

        if i == 0:
            left_bound_rt = time[left_bound_idx]
        else:
            left_bound_rt = time[apex_idx[ordered[i - 1]]]
        left_lo = max(left_bound_rt, apex_rt - MAX_VALLEY_SEARCH_MIN)
        left_valley_idx = find_valley(time, intensity, left_lo, apex_rt)

        if i == len(ordered) - 1:
            right_bound_rt = time[right_bound_idx]
        else:
            right_bound_rt = time[apex_idx[ordered[i + 1]]]
        right_hi = min(right_bound_rt, apex_rt + MAX_VALLEY_SEARCH_MIN)
        right_valley_idx = find_valley(time, intensity, apex_rt, right_hi)

        l, r = left_valley_idx, right_valley_idx
        t_win = time[l:r + 1]
        y_win = intensity[l:r + 1]
        left_y = intensity[l]
        right_y = intensity[r]
        baseline = np.interp(t_win, [t_win[0], t_win[-1]], [left_y, right_y])
        area = trapezoid(np.maximum(y_win - baseline, 0), t_win * 60.0)

        results[name] = {
            'rt_min': round(float(time[a_idx]), 3),
            'height_nRIU': round(float(intensity[a_idx] - np.interp(time[a_idx], [t_win[0], t_win[-1]], [left_y, right_y])), 1),
            'area_nRIUs': round(float(area), 1),
            'left_rt': round(float(time[l]), 3),
            'right_rt': round(float(time[r]), 3),
        }
    return results


def read_rid_data(ch_path):
    result = parse_ch(str(ch_path))
    if result is None:
        raise ValueError(f"Cannot parse: {ch_path}")
    time = result.xlabels
    intensity = result.data.flatten()
    return time, intensity


def estimate_noise(intensity):
    derivative = np.diff(intensity)
    mad = np.median(np.abs(derivative - np.median(derivative)))
    return max(mad * 1.4826, 0.1)


def detect_peaks(time, intensity):
    noise_level = estimate_noise(intensity)
    signal_range = np.ptp(intensity)

    major_prominence = max(signal_range * 0.005, noise_level * 5)
    major_peaks, major_props = signal.find_peaks(
        intensity, prominence=major_prominence, height=noise_level * 5, width=3, distance=20
    )
    minor_prominence = max(noise_level * 3, signal_range * 0.001)
    minor_peaks, minor_props = signal.find_peaks(
        intensity, prominence=minor_prominence, height=noise_level * 3, width=2, distance=10
    )

    all_peaks = list(major_peaks)
    all_prominences = list(major_props['prominences'])
    for i, mp in enumerate(minor_peaks):
        if not any(abs(mp - majp) < 10 for majp in major_peaks):
            all_peaks.append(mp)
            all_prominences.append(minor_props['prominences'][i])

    if not all_peaks:
        return []

    sort_idx = np.argsort(all_peaks)
    peaks = np.array(all_peaks)[sort_idx]
    prominences = np.array(all_prominences)[sort_idx]

    peak_data = []
    for i, peak_idx in enumerate(peaks):
        peak_height = intensity[peak_idx]
        threshold = max(peak_height * 0.01, noise_level * 0.5)

        left = peak_idx
        while left > 0 and intensity[left] > threshold:
            left -= 1
        right = peak_idx
        while right < len(intensity) - 1 and intensity[right] > threshold:
            right += 1

        if i < len(peaks) - 1:
            region = intensity[peak_idx:peaks[i + 1]]
            if len(region) > 0:
                right = min(right, peak_idx + np.argmin(region))
        if i > 0:
            region = intensity[peaks[i - 1]:peak_idx]
            if len(region) > 0:
                left = max(left, peaks[i - 1] + np.argmin(region))

        dt = np.mean(np.diff(time))
        max_w = int(2.0 / dt) if dt > 0 else 1000
        if right - left > max_w:
            half = max_w // 2
            left = max(0, peak_idx - half)
            right = min(len(intensity) - 1, peak_idx + half)

        left = max(0, left)
        right = min(len(intensity) - 1, right)

        peak_time_sec = time[left:right + 1] * 60
        peak_signal = intensity[left:right + 1]
        area = trapezoid(np.maximum(peak_signal, 0), peak_time_sec)

        peak_data.append({
            'peak_number': i + 1,
            'rt_min': round(time[peak_idx], 3),
            'height_nRIU': round(peak_height, 1),
            'area_nRIUs': round(area, 1),
            'width_min': round(time[right] - time[left], 4),
            'prominence': round(prominences[i], 1),
            'snr': round(peak_height / noise_level, 1) if noise_level > 0 else 0,
        })

    peak_data.sort(key=lambda p: p['rt_min'])
    return peak_data


def parse_sample_name(folder_name):
    info = {'folder': folder_name, 'time_h': None, 'replicate': None}
    m = re.search(r'_(\d+)H_(\d+)\.D$', folder_name, re.IGNORECASE)
    if m:
        info['time_h'] = int(m.group(1))
        info['replicate'] = int(m.group(2))
    return info


def match_compound(rt):
    for name, cal in CALIBRATION.items():
        lo, hi = cal['rt_window']
        if lo <= rt <= hi:
            return name
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", dest="data_dir", default=None)
    args = parser.parse_args()

    data_dir = Path(args.data_dir) if args.data_dir else DEFAULT_DATA_DIR
    output_dir = data_dir / "quantification_results"
    output_dir.mkdir(parents=True, exist_ok=True)

    d_folders = sorted(
        d for d in data_dir.iterdir()
        if d.is_dir() and d.suffix.upper() == '.D'
        and re.search(r'FLASK_TITER_\d+H_\d+\.D$', d.name, re.IGNORECASE)
    )
    print(f"총 {len(d_folders)}개 FLASK_TITER .D 폴더 발견\n")

    all_peak_rows = []
    quant_rows = []
    errors = []

    for idx, d_folder in enumerate(d_folders, 1):
        ch_file = d_folder / "RID1A.ch"
        if not ch_file.exists():
            errors.append(f"[SKIP] {d_folder.name}: RID1A.ch 없음")
            continue

        meta = parse_sample_name(d_folder.name)
        label = f"[{idx}/{len(d_folders)}]"

        try:
            time, intensity = read_rid_data(ch_file)
            matched = integrate_valley_to_valley(time, intensity, APEX_WINDOWS)

            for compound, pk in matched.items():
                row = {'sample': d_folder.name.replace('.D', ''), 'time_h': meta['time_h'],
                       'replicate': meta['replicate'], 'compound': compound}
                row.update(pk)
                all_peak_rows.append(row)

            print(f"{label} {d_folder.name}: 매칭 {list(matched.keys())}")

            qrow = {'sample': d_folder.name.replace('.D', ''), 'time_h': meta['time_h'],
                    'replicate': meta['replicate']}
            for compound, cal in CALIBRATION.items():
                if compound in matched:
                    area = matched[compound]['area_nRIUs']
                    conc = max((area - cal['y0']) / cal['a'], 0.0) * DILUTION_FACTOR
                    qrow[f'{compound}_rt_min'] = matched[compound]['rt_min']
                    qrow[f'{compound}_area'] = area
                    qrow[f'{compound}_mM'] = round(conc, 3)
                else:
                    qrow[f'{compound}_rt_min'] = None
                    qrow[f'{compound}_area'] = None
                    qrow[f'{compound}_mM'] = None
            quant_rows.append(qrow)

        except Exception as e:
            err_msg = f"{label} {d_folder.name}: {e}"
            print(f"  [ERROR] {err_msg}")
            errors.append(err_msg)

    if not quant_rows:
        print("\n분석된 결과가 없습니다.")
        return

    all_peaks_df = pd.DataFrame(all_peak_rows)
    quant_df = pd.DataFrame(quant_rows).sort_values(['time_h', 'replicate']).reset_index(drop=True)

    summary_cols = [f'{c}_mM' for c in CALIBRATION]
    summary_df = (
        quant_df.groupby('time_h')[summary_cols]
        .agg(['mean', 'std', 'count'])
        .reset_index()
        .sort_values('time_h')
    )
    summary_df.columns = ['time_h'] + [f'{m}_{s}' for m, s in summary_df.columns.tolist()[1:]]

    all_peaks_path = output_dir / "all_peaks_detailed.csv"
    quant_path = output_dir / "quant_by_replicate.csv"
    summary_path = output_dir / "summary_by_timepoint.csv"
    excel_path = output_dir / "260810_sp0810_flask_titer_results.xlsx"

    all_peaks_df.to_csv(all_peaks_path, index=False, encoding='utf-8-sig')
    quant_df.to_csv(quant_path, index=False, encoding='utf-8-sig')
    summary_df.to_csv(summary_path, index=False, encoding='utf-8-sig')

    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        all_peaks_df.to_excel(writer, sheet_name='All_Peaks', index=False)
        quant_df.to_excel(writer, sheet_name='Quant_by_Replicate', index=False)
        summary_df.to_excel(writer, sheet_name='Summary_by_Timepoint', index=False)

    print(f"\n{'=' * 70}")
    print("정량 결과 요약 (mean +/- std, n)")
    print(f"{'=' * 70}")
    print(summary_df.round(2).to_string(index=False))

    if errors:
        print(f"\n에러 {len(errors)}건:")
        for e in errors:
            print(f"  {e}")

    print(f"\n결과 위치: {output_dir}")
    print(f"Excel: {excel_path}")


if __name__ == '__main__':
    main()
