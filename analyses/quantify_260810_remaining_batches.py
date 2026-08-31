"""
260810 Flask Titer Timecourse - remaining 3 batches (SP0810 batch 2 + HPX87H batches 3,4)
=============================================================================
Reuses the valley-to-valley integration logic from quantify_260810_sp0810_flask_titer.py.
Batch 1 (E:\\t\\260701_JW 2026-08-10 18-02-04, SP0810) already processed separately.

Batches processed here:
  2. E:\\t\\260701_JW 2026-08-12 17-10-44            (SP0810, _F/_RE samples, 12-60H)
  3. E:\\t\\2026-08-12 240528_PAUSED_HPX87H 17-03-25   (HPX87H, plain samples, 0-72H)
  4. E:\\t\\2026-08-13 240528_PAUSED_HPX87H 18-29-16   (HPX87H, _F/_RE samples, 12-60H)

Calibration source: PeakPicker/methods/sp0810_gal_tag_galol.yaml, dgal_tagatose_hpx87h.yaml
  SP0810:  Gal RT~19.05  / Tag RT~26.65 / Galol RT~41.57
  HPX87H:  D-Gal+Tag (co-eluting) RT~11.0 / Galactitol RT~12.2 / Formate RT~14.8
"""

import sys
import io
import re

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import numpy as np
import pandas as pd
from pathlib import Path
from scipy.integrate import trapezoid
from rainbow.agilent.chemstation import parse_ch

DILUTION_FACTOR = 20.0

BATCHES = [
    {
        "name": "batch2_260812_SP0810",
        "data_dir": Path(r"F:\t\260701_JW 2026-08-12 17-10-44"),
        "column": "SP0810",
        "apex_windows": {
            "Gal":   (18.6, 19.5),
            "Tag":   (26.0, 27.0),
            "Galol": (40.8, 42.0),
        },
        "region_start_rt": 15.0,
        "region_end_rt": 45.0,
        "max_valley_search_min": 3.0,
        "calibration": {
            "Gal":   {"a": 69587.6626, "y0": -6370.9125},
            "Tag":   {"a": 58227.8378, "y0": -284.3917},
            "Galol": {"a": 75968.4499, "y0": 3183.7165},
        },
    },
    {
        "name": "batch3_260812_HPX87H",
        "data_dir": Path(r"F:\t\2026-08-12 240528_PAUSED_HPX87H 17-03-25"),
        "column": "HPX-87H",
        "apex_windows": {
            "Gal_Tag": (10.5, 11.5),
            "Galol":   (11.8, 12.8),
            # Formate RT corrected 260831: real peak sits at ~15.9 min, not
            # 14.4-15.3 (that window only ever caught noise; see Notion card
            # 3cbf91ac-a96f-817a-9638-fec2a0b05c32 and
            # diag_260810_t0_formate_window_mismatch.png). Confirmed against
            # _F (formate-fed) replicates in batch4, which peak at 15.92-15.93
            # with height 2500-3100 -- consistent, unambiguous signal.
            "Formate": (15.5, 16.3),
        },
        "region_start_rt": 8.0,
        "region_end_rt": 17.0,
        "max_valley_search_min": 1.5,
        "calibration": {
            # yaml stores conc(mM) = slope*area + intercept; convert to area-based a/y0:
            # a = 1/slope, y0 = -intercept/slope
            "Gal_Tag": {"a": 1 / 1.641481e-05, "y0": -(-0.046323) / 1.641481e-05},
            "Galol":   {"a": 1 / 1.831848e-05, "y0": -(-0.028876) / 1.831848e-05},
            "Formate": {"a": 1 / 1.837991e-04, "y0": -(-0.001922) / 1.837991e-04},
        },
    },
    {
        "name": "batch4_260813_HPX87H",
        "data_dir": Path(r"F:\t\2026-08-13 240528_PAUSED_HPX87H 18-29-16"),
        "column": "HPX-87H",
        "apex_windows": {
            "Gal_Tag": (10.5, 11.5),
            "Galol":   (11.8, 12.8),
            "Formate": (15.5, 16.3),
        },
        "region_start_rt": 8.0,
        "region_end_rt": 17.0,
        "max_valley_search_min": 1.5,
        "calibration": {
            "Gal_Tag": {"a": 1 / 1.641481e-05, "y0": -(-0.046323) / 1.641481e-05},
            "Galol":   {"a": 1 / 1.831848e-05, "y0": -(-0.028876) / 1.831848e-05},
            "Formate": {"a": 1 / 1.837991e-04, "y0": -(-0.001922) / 1.837991e-04},
        },
    },
]


def find_valley(time, intensity, lo, hi):
    mask = (time >= lo) & (time <= hi)
    idx_local = np.argmin(intensity[mask])
    return np.where(mask)[0][idx_local]


def integrate_valley_to_valley(time, intensity, apex_windows, region_start_rt, region_end_rt, max_valley_search_min):
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

        if i == 0:
            left_bound_rt = time[left_bound_idx]
        else:
            left_bound_rt = time[apex_idx[ordered[i - 1]]]
        left_lo = max(left_bound_rt, apex_rt - max_valley_search_min)
        left_valley_idx = find_valley(time, intensity, left_lo, apex_rt)

        if i == len(ordered) - 1:
            right_bound_rt = time[right_bound_idx]
        else:
            right_bound_rt = time[apex_idx[ordered[i + 1]]]
        right_hi = min(right_bound_rt, apex_rt + max_valley_search_min)
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
    return result.xlabels, result.data.flatten()


def parse_sample_name(folder_name):
    """Extract time_h, replicate, and variant (plain/F/RE) from folder name."""
    info = {'folder': folder_name, 'time_h': None, 'replicate': None, 'variant': 'plain'}
    m = re.search(r'_(\d+)H_(\d+)(_F|_RE)?\.D$', folder_name, re.IGNORECASE)
    if m:
        info['time_h'] = int(m.group(1))
        info['replicate'] = int(m.group(2))
        if m.group(3):
            info['variant'] = m.group(3).lstrip('_').upper()
    return info


def process_batch(cfg):
    data_dir = cfg["data_dir"]
    output_dir = data_dir / "quantification_results"
    output_dir.mkdir(parents=True, exist_ok=True)

    d_folders = sorted(
        d for d in data_dir.iterdir()
        if d.is_dir() and d.suffix.upper() == '.D'
        and re.search(r'FLASK_TITER_\d+H_\d+(_F|_RE)?\.D$', d.name, re.IGNORECASE)
    )
    print(f"\n{'=' * 70}\n{cfg['name']} ({cfg['column']}) — {data_dir}\n{'=' * 70}")
    print(f"총 {len(d_folders)}개 FLASK_TITER .D 폴더 발견")

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
            matched = integrate_valley_to_valley(
                time, intensity, cfg["apex_windows"],
                cfg["region_start_rt"], cfg["region_end_rt"], cfg["max_valley_search_min"]
            )

            for compound, pk in matched.items():
                row = {'sample': d_folder.name.replace('.D', ''), 'time_h': meta['time_h'],
                       'replicate': meta['replicate'], 'variant': meta['variant'], 'compound': compound}
                row.update(pk)
                all_peak_rows.append(row)

            print(f"{label} {d_folder.name}: 매칭 {list(matched.keys())}")

            qrow = {'sample': d_folder.name.replace('.D', ''), 'time_h': meta['time_h'],
                    'replicate': meta['replicate'], 'variant': meta['variant']}
            for compound, cal in cfg["calibration"].items():
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
        print("분석된 결과가 없습니다.")
        return

    all_peaks_df = pd.DataFrame(all_peak_rows)
    quant_df = pd.DataFrame(quant_rows).sort_values(['time_h', 'replicate', 'variant']).reset_index(drop=True)

    summary_cols = [f'{c}_mM' for c in cfg["calibration"]]
    summary_df = (
        quant_df.groupby(['time_h', 'variant'])[summary_cols]
        .agg(['mean', 'std', 'count'])
        .reset_index()
        .sort_values(['time_h', 'variant'])
    )
    summary_df.columns = ['time_h', 'variant'] + [f'{m}_{s}' for m, s in summary_df.columns.tolist()[2:]]

    all_peaks_path = output_dir / "all_peaks_detailed.csv"
    quant_path = output_dir / "quant_by_replicate.csv"
    summary_path = output_dir / "summary_by_timepoint.csv"
    excel_path = output_dir / f"{cfg['name']}_results.xlsx"

    all_peaks_df.to_csv(all_peaks_path, index=False, encoding='utf-8-sig')
    quant_df.to_csv(quant_path, index=False, encoding='utf-8-sig')
    summary_df.to_csv(summary_path, index=False, encoding='utf-8-sig')

    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        all_peaks_df.to_excel(writer, sheet_name='All_Peaks', index=False)
        quant_df.to_excel(writer, sheet_name='Quant_by_Replicate', index=False)
        summary_df.to_excel(writer, sheet_name='Summary_by_Timepoint', index=False)

    print(f"\n정량 결과 요약 (mean +/- std, n) — {cfg['name']}")
    print(summary_df.round(2).to_string(index=False))

    if errors:
        print(f"\n에러 {len(errors)}건:")
        for e in errors:
            print(f"  {e}")

    print(f"결과 위치: {output_dir}")
    return quant_df, summary_df


def main():
    for cfg in BATCHES:
        process_batch(cfg)


if __name__ == '__main__':
    main()
