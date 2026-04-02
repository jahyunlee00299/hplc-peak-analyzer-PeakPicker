"""
260302_rpm_buffer 중 *48H_GO* 샘플 피크 정량
8~17분 구간 내 모든 유의미한 피크(valley drop-line 면적)

windows:
  ~8.5  : 8.0  - 8.8
  ~9.4  : 8.8  - 9.65
  ~9.8  : 9.65 - 10.1
  ~10.3 : 10.1 - 10.55
  ~10.8 : 10.55- 11.2   ← Galactose
  ~11.6 : 11.2 - 12.1   ← Galactitol
  ~14.5 : 14.0 - 15.3
  ~15.9 : 15.3 - 16.5   ← Formate
"""
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.integrate import trapezoid
from scipy.signal import savgol_filter, find_peaks
from rainbow.agilent.chemstation import parse_ch

DATA_DIR = Path(r"C:\Chem32\1\DATA\260302_rpm_buffer")
OUT_XLSX  = DATA_DIR / "260302_48H_GO_peaks.xlsx"

TARGETS = {
    '~8.5min':  {'search': (8.1,  8.75),  'left_valley': (7.5,  8.1),  'right_valley': (8.75, 9.0)},
    '~9.4min':  {'search': (8.8,  9.65),  'left_valley': (8.75, 8.9),  'right_valley': (9.65, 9.75)},
    '~9.8min':  {'search': (9.65, 10.05), 'left_valley': (9.55, 9.72), 'right_valley': (10.05,10.2)},
    '~10.3min': {'search': (10.1, 10.55), 'left_valley': (9.9,  10.1), 'right_valley': (10.55,10.65)},
    '~10.8min': {'search': (10.55,11.2),  'left_valley': (10.55,10.65),'right_valley': (11.2, 11.4)},
    '~11.6min': {'search': (11.2, 12.0),  'left_valley': (11.2, 11.4), 'right_valley': (12.0, 12.3)},
    '~14.5min': {'search': (14.0, 15.3),  'left_valley': (13.5, 14.1), 'right_valley': (15.3, 15.5)},
    '~15.9min': {'search': (15.3, 16.5),  'left_valley': (15.2, 15.4), 'right_valley': (16.5, 16.9)},
}


def find_valley(time, intensity, rt_min, rt_max):
    mask = (time >= rt_min) & (time <= rt_max)
    if not np.any(mask):
        return None
    idx = np.where(mask)[0]
    return idx[np.argmin(intensity[idx])]


def quantify_peak(time, intensity, cfg):
    s_min, s_max = cfg['search']
    lv_min, lv_max = cfg['left_valley']
    rv_min, rv_max = cfg['right_valley']

    mask = (time >= lv_min) & (time <= rv_max)
    if not np.any(mask):
        return np.nan, np.nan

    idx = np.where(mask)[0]
    seg = intensity[idx]
    t_seg = time[idx]

    noise = np.std(np.diff(seg)) * 1.4826
    min_prom = max(noise * 3, np.ptp(seg) * 0.01, 5.0)
    peaks, _ = find_peaks(seg, prominence=min_prom, distance=3)

    peak_global = None
    best_h = -np.inf
    for p in peaks:
        if s_min <= t_seg[p] <= s_max and seg[p] > best_h:
            best_h = seg[p]
            peak_global = idx[p]

    if peak_global is None:
        return np.nan, np.nan

    peak_rt = time[peak_global]

    left_idx  = find_valley(time, intensity, lv_min, lv_max)
    right_idx = find_valley(time, intensity, rv_min, rv_max)
    if left_idx is None or right_idx is None:
        return np.nan, peak_rt

    t_seg2 = time[left_idx:right_idx + 1]
    i_seg2 = intensity[left_idx:right_idx + 1]
    bl = np.interp(t_seg2, [t_seg2[0], t_seg2[-1]], [i_seg2[0], i_seg2[-1]])
    corr = i_seg2 - bl

    peak_rel = peak_global - left_idx
    if not (0 <= peak_rel < len(corr)):
        return np.nan, peak_rt

    peak_h = corr[peak_rel]
    noise2 = np.std(np.diff(i_seg2)) * 0.5
    if noise2 > 0 and peak_h < noise2 * 3:
        return np.nan, peak_rt

    threshold = max(peak_h * 0.02, noise2 * 0.5)
    left = peak_rel
    while left > 0 and corr[left] > threshold:
        left -= 1
    right = peak_rel
    while right < len(corr) - 1 and corr[right] > threshold:
        right += 1

    area = trapezoid(np.maximum(corr[left:right + 1], 0),
                     t_seg2[left:right + 1] * 60)
    return area, peak_rt


def process_all():
    folders = sorted(f for f in DATA_DIR.glob("*.D") if "48H_GO" in f.stem)
    print(f"샘플 {len(folders)}개 발견\n")
    rows = []
    for folder in folders:
        ch = folder / "RID1A.ch"
        if not ch.exists():
            print(f"  [skip] {folder.stem}")
            continue

        result = parse_ch(str(ch))
        time = np.asarray(result.xlabels, dtype=float)
        sig  = np.asarray(result.data, dtype=float).flatten()
        n = min(len(time), len(sig))
        time, sig = time[:n], sig[:n]
        wl = min(11, (n // 2) * 2 - 1)
        if wl >= 5:
            sig = savgol_filter(sig, wl, 3)

        row = {'sample': folder.stem}
        for label, cfg in TARGETS.items():
            area, rt = quantify_peak(time, sig, cfg)
            row[f'{label}_RT']   = round(rt,   2) if not np.isnan(rt)   else None
            row[f'{label}_area'] = round(area,  0) if not np.isnan(area) else None
        rows.append(row)
        print(f"  완료: {folder.stem}")

    return pd.DataFrame(rows)


def print_table(df):
    labels = list(TARGETS.keys())
    header = f"{'샘플':<42}"
    for lb in labels:
        header += f"  {lb:>9}RT  {lb[1:]:>9}Area"
    print(f"\n{header}")
    print("-" * len(header))
    for _, row in df.iterrows():
        line = f"{row['sample']:<42}"
        for lb in labels:
            rt   = row.get(f'{lb}_RT')
            area = row.get(f'{lb}_area')
            area_s = f"{int(area)}" if (area is not None and not (isinstance(area, float) and np.isnan(area))) else '--'
            line += f"  {str(rt) if rt else '--':>11}  {area_s:>12}"
        print(line)


def save_excel(df, path):
    labels = list(TARGETS.keys())
    with pd.ExcelWriter(path, engine='openpyxl') as writer:
        # Long format
        rows = []
        for _, row in df.iterrows():
            for lb in labels:
                rt   = row.get(f'{lb}_RT')
                area = row.get(f'{lb}_area')
                if rt is not None or area is not None:
                    rows.append({'sample': row['sample'], 'peak': lb,
                                 'RT (min)': rt, 'Area (mAU·s)': area})
        pd.DataFrame(rows).to_excel(writer, sheet_name='All_peaks', index=False)

        # Area pivot
        pivot = df[['sample'] + [f'{lb}_area' for lb in labels]].copy()
        pivot.columns = ['sample'] + labels
        pivot.to_excel(writer, sheet_name='Area_pivot', index=False)

        # RT pivot
        pivot_rt = df[['sample'] + [f'{lb}_RT' for lb in labels]].copy()
        pivot_rt.columns = ['sample'] + labels
        pivot_rt.to_excel(writer, sheet_name='RT_pivot', index=False)

    print(f"\nExcel 저장: {path}")


if __name__ == '__main__':
    print("=" * 60)
    print("  260302_rpm_buffer 48H_GO 피크 정량")
    print("=" * 60)
    df = process_all()
    if df.empty:
        print("결과 없음.")
    else:
        print_table(df)
        save_excel(df, OUT_XLSX)
        print("\n완료.")
