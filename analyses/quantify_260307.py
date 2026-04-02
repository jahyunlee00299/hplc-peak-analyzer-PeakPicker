"""
260307_cool_freeze_azide_tris_300_500 피크 정량
- 10분대 (~9.3 min)
- 11분대 (~11.0 min)
- 11.6분대 (~11.6 min)
- 15분대 (~14.97 min)
- 16분대 (~15.9 min)

valley drop-line 베이스라인으로 면적 계산
결과: console 출력 + Excel 저장
"""
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.integrate import trapezoid
from scipy.signal import savgol_filter, find_peaks
from rainbow.agilent.chemstation import parse_ch

DATA_DIR = Path(r"C:\Chem32\1\DATA\260307_cool_freeze_azide_tris_300_500")
OUT_XLSX  = DATA_DIR / "260307_peaks_summary.xlsx"

# 피크 탐색 설정 (search: apex 탐색 구간, left/right: valley 구간)
TARGETS = {
    '10min': {
        'search':       (8.8,  10.2),
        'left_valley':  (8.0,   8.8),
        'right_valley': (10.2, 10.7),
    },
    '11min': {
        'search':       (10.4, 11.3),
        'left_valley':  (10.0, 10.5),
        'right_valley': (11.3, 11.55),
    },
    '11.6min': {
        'search':       (11.4, 11.9),
        'left_valley':  (11.3, 11.55),
        'right_valley': (11.9, 12.3),
    },
    '15min': {
        'search':       (14.5, 15.5),
        'left_valley':  (14.0, 14.6),
        'right_valley': (15.5, 15.7),
    },
    '16min': {
        'search':       (15.6, 16.3),
        'left_valley':  (15.5, 15.7),
        'right_valley': (16.3, 16.8),
    },
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

    # apex 탐색 (wider = left_valley_min ~ right_valley_max)
    mask = (time >= lv_min) & (time <= rv_max)
    if not np.any(mask):
        return np.nan, np.nan

    idx = np.where(mask)[0]
    seg = intensity[idx]
    t_seg = time[idx]

    noise = np.std(np.diff(seg)) * 1.4826
    min_prom = max(noise * 3, np.ptp(seg) * 0.01)
    peaks, _ = find_peaks(seg, prominence=min_prom, distance=3)

    # search 범위 안의 최대 피크 선택
    peak_global = None
    best_h = -np.inf
    for p in peaks:
        if s_min <= t_seg[p] <= s_max and seg[p] > best_h:
            best_h = seg[p]
            peak_global = idx[p]

    if peak_global is None:
        return np.nan, np.nan

    peak_rt = time[peak_global]

    # valley 찾기
    left_idx  = find_valley(time, intensity, lv_min, lv_max)
    right_idx = find_valley(time, intensity, rv_min, rv_max)
    if left_idx is None or right_idx is None:
        return np.nan, peak_rt

    # drop-line 베이스라인
    t_seg2 = time[left_idx:right_idx + 1]
    i_seg2 = intensity[left_idx:right_idx + 1]
    bl = np.interp(t_seg2, [t_seg2[0], t_seg2[-1]], [i_seg2[0], i_seg2[-1]])
    corr = i_seg2 - bl

    # peak 상대 인덱스
    peak_rel = peak_global - left_idx
    if not (0 <= peak_rel < len(corr)):
        return np.nan, peak_rt

    peak_h = corr[peak_rel]
    noise2 = np.std(np.diff(i_seg2)) * 0.5
    if noise2 > 0 and peak_h < noise2 * 3:
        return np.nan, peak_rt

    # 피크 경계 (apex에서 좌우로 2% 높이 기준)
    threshold = max(peak_h * 0.02, noise2 * 0.5)
    left = peak_rel
    while left > 0 and corr[left] > threshold:
        left -= 1
    right = peak_rel
    while right < len(corr) - 1 and corr[right] > threshold:
        right += 1

    area = trapezoid(np.maximum(corr[left:right + 1], 0),
                     t_seg2[left:right + 1] * 60)  # min→sec
    return area, peak_rt


def process_all():
    d_folders = sorted(DATA_DIR.glob("*.D"))
    if not d_folders:
        print("No .D folders found.")
        return

    rows = []
    for folder in d_folders:
        ch = folder / "RID1A.ch"
        if not ch.exists():
            print(f"  [skip] RID1A.ch 없음: {folder.stem}")
            continue

        result = parse_ch(str(ch))
        time = np.asarray(result.xlabels, dtype=float)
        sig  = np.asarray(result.data, dtype=float).flatten()
        n = min(len(time), len(sig))
        time, sig = time[:n], sig[:n]

        # 가벼운 스무딩
        wl = min(11, (len(sig) // 2) * 2 - 1)
        if wl >= 5:
            sig = savgol_filter(sig, wl, 3)

        row = {'sample': folder.stem}
        for label, cfg in TARGETS.items():
            area, rt = quantify_peak(time, sig, cfg)
            row[f'{label}_RT']   = round(rt,   3) if not np.isnan(rt)   else None
            row[f'{label}_area'] = round(area,  1) if not np.isnan(area) else None

        rows.append(row)

    df = pd.DataFrame(rows)
    return df


def print_table(df):
    labels = list(TARGETS.keys())
    print(f"\n{'샘플':<42}", end="")
    for lb in labels:
        print(f"  {lb:>9}RT  {lb:>9}Area", end="")
    print()
    print("-" * (42 + len(labels) * 26))

    for _, row in df.iterrows():
        print(f"{row['sample']:<42}", end="")
        for lb in labels:
            rt   = row.get(f'{lb}_RT')
            area = row.get(f'{lb}_area')
            rt_s   = f"{rt:.2f}" if rt is not None else "  --  "
            area_s = f"{area:.0f}" if area is not None else "  --  "
            print(f"  {rt_s:>12}  {area_s:>12}", end="")
        print()


def save_excel(df, path):
    """피크별 시트 + 전체 합산 시트로 저장"""
    labels = list(TARGETS.keys())

    with pd.ExcelWriter(path, engine='openpyxl') as writer:
        # Sheet 1: 전체 요약 (샘플 × 피크)
        summary_rows = []
        for _, row in df.iterrows():
            for lb in labels:
                rt   = row.get(f'{lb}_RT')
                area = row.get(f'{lb}_area')
                if rt is not None or area is not None:
                    summary_rows.append({
                        'sample':    row['sample'],
                        'peak':      lb,
                        'RT (min)':  rt,
                        'Area':      area,
                    })
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name='All_peaks', index=False)

        # Sheet 2: 피벗 (샘플 × 피크)  area만
        pivot = df[['sample'] + [f'{lb}_area' for lb in labels]].copy()
        pivot.columns = ['sample'] + labels
        pivot.to_excel(writer, sheet_name='Area_pivot', index=False)

        # Sheet 3: 피벗 RT
        pivot_rt = df[['sample'] + [f'{lb}_RT' for lb in labels]].copy()
        pivot_rt.columns = ['sample'] + labels
        pivot_rt.to_excel(writer, sheet_name='RT_pivot', index=False)

    print(f"\nExcel 저장 완료: {path}")


if __name__ == '__main__':
    print("=" * 60)
    print("  260307 피크 정량")
    print("=" * 60)

    df = process_all()
    if df is None or df.empty:
        print("분석 결과 없음.")
    else:
        print_table(df)
        save_excel(df, OUT_XLSX)
        print("\n완료.")
