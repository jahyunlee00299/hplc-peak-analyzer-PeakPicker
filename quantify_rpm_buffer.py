"""
260302_rpm_buffer 데이터 정량 (valley drop-line 베이스라인)
- Galactose: RT 10.8-11.0
- Galactitol: RT 11.6-11.8
- Formate: RT 15.8-15.9
각 피크 양쪽 valley를 찾아 drop-line 베이스라인으로 면적 계산
"""
import numpy as np
import pandas as pd
from pathlib import Path
import sys
import re

from rainbow.agilent.chemstation import parse_ch
from scipy.integrate import trapezoid
from scipy.signal import savgol_filter, find_peaks

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False


# 각 피크별 설정
# search: 피크 정점 탐색 범위
# left_valley: 왼쪽 valley 탐색 범위
# right_valley: 오른쪽 valley 탐색 범위
TARGETS = {
    'Galactose': {
        'search': (10.8, 11.1),
        'left_valley':  (10.4, 10.8),
        'right_valley': (11.1, 11.4),
    },
    'Galactitol': {
        'search': (11.5, 11.8),
        'left_valley':  (11.3, 11.5),
        'right_valley': (11.8, 12.1),
    },
    'Formate': {
        'search': (15.8, 16.0),
        'left_valley':  (15.5, 15.8),
        'right_valley': (16.0, 16.3),
    },
}

# 스탠다드커브: Area = a * conc(mM) + y0
STD_CURVE = {
    'Galactose':  {'y0': 2822.042,  'a': 60920.61},
    'Galactitol': {'y0': 1576.354,  'a': 54589.67},
    'Formate':    {'y0': 10.4596,   'a': 5440.7244},
}

DATA_DIR = Path(r"C:\Chem32\1\DATA\260302_rpm_buffer")


def find_valley(time, intensity, rt_min, rt_max):
    """주어진 RT 범위에서 최소값(valley) 인덱스 반환"""
    mask = (time >= rt_min) & (time <= rt_max)
    if not np.any(mask):
        return None
    idx = np.where(mask)[0]
    min_local = idx[np.argmin(intensity[idx])]
    return min_local


def has_real_peak(time, intensity, search_min, search_max, wider_min, wider_max):
    """
    실제 피크(local maximum)가 있는지 확인.
    wider 범위에서 find_peaks를 돌려 search 범위 안에 피크가 있는지 체크.
    """
    mask = (time >= wider_min) & (time <= wider_max)
    if not np.any(mask):
        return False, None

    idx = np.where(mask)[0]
    seg = intensity[idx]
    t_seg = time[idx]

    # find_peaks: prominence 기반으로 실제 피크 검출
    noise = np.std(np.diff(seg)) * 1.4826
    min_prom = max(noise * 3, np.ptp(seg) * 0.01)

    peaks, props = find_peaks(seg, prominence=min_prom, distance=3)

    if len(peaks) == 0:
        return False, None

    # search 범위 안에 있는 피크 찾기
    for p in peaks:
        if search_min <= t_seg[p] <= search_max:
            return True, idx[p]  # 원본 인덱스 반환

    return False, None


def quantify_peak(time, intensity, target_info):
    """
    Valley drop-line 방식으로 단일 피크 면적 계산.
    1. 실제 피크(local max) 존재 확인
    2. 왼쪽/오른쪽 valley 찾기
    3. Valley 사이 직선 = 베이스라인
    4. 베이스라인 위 면적 적분
    """
    s_min, s_max = target_info['search']
    lv_min, lv_max = target_info['left_valley']
    rv_min, rv_max = target_info['right_valley']

    # 1) 실제 피크가 있는지 확인 (wider 범위에서)
    wider_min = lv_min
    wider_max = rv_max
    is_peak, peak_global_idx = has_real_peak(time, intensity, s_min, s_max, wider_min, wider_max)

    if not is_peak:
        return 0.0, None

    peak_rt = time[peak_global_idx]

    # 2) Valley 찾기
    left_idx = find_valley(time, intensity, lv_min, lv_max)
    right_idx = find_valley(time, intensity, rv_min, rv_max)

    if left_idx is None or right_idx is None:
        return 0.0, peak_rt

    # 3) Drop-line 베이스라인
    t_seg = time[left_idx:right_idx+1]
    i_seg = intensity[left_idx:right_idx+1]
    bl = np.interp(t_seg, [t_seg[0], t_seg[-1]],
                   [i_seg[0], i_seg[-1]])
    corrected = i_seg - bl

    # 피크 위치 (세그먼트 내 상대 인덱스)
    peak_rel = peak_global_idx - left_idx
    if peak_rel < 0 or peak_rel >= len(corrected):
        return 0.0, peak_rt

    peak_height = corrected[peak_rel]

    # S/N 체크
    noise = np.std(np.diff(i_seg)) * 0.5
    if noise > 0 and peak_height < noise * 3:
        return 0.0, peak_rt

    # 4) 피크 경계 찾기 (peak에서 좌우로)
    threshold = max(peak_height * 0.02, noise * 0.5)

    left = peak_rel
    while left > 0 and corrected[left] > threshold:
        left -= 1

    right = peak_rel
    while right < len(corrected) - 1 and corrected[right] > threshold:
        right += 1

    # 면적 (mAU·s)
    peak_t = t_seg[left:right+1] * 60  # min->sec
    peak_s = corrected[left:right+1]
    area = trapezoid(np.maximum(peak_s, 0), peak_t)

    return area, peak_rt


def area_to_conc(area, compound):
    if area is None or area <= 0:
        return 0.0
    sc = STD_CURVE[compound]
    conc = (area - sc['y0']) / sc['a']
    return max(conc, 0.0)


def parse_sample_name(name):
    time_match = re.search(r'_(\d+)H$', name)
    time_h = time_match.group(1) if time_match else '?'
    cond_match = re.match(r'260302_1CELL_(.+?)_\d+H$', name)
    condition = cond_match.group(1) if cond_match else name
    return condition, time_h


def process_sample(d_folder):
    ch_file = d_folder / "RID1A.ch"
    if not ch_file.exists():
        return None

    result = parse_ch(str(ch_file))
    time = np.asarray(result.xlabels, dtype=float)
    intensity = np.asarray(result.data, dtype=float).flatten()
    min_len = min(len(time), len(intensity))
    time = time[:min_len]
    intensity = intensity[:min_len]

    # 가벼운 스무딩
    if len(intensity) > 15:
        wl = min(11, len(intensity) // 2 * 2 - 1)
        if wl >= 5:
            intensity = savgol_filter(intensity, wl, 3)

    condition, time_h = parse_sample_name(d_folder.stem)
    dilution = 200 if time_h == '0' else 20

    result = {'sample': d_folder.stem, 'condition': condition,
              'time_h': int(time_h) if time_h.isdigit() else -1}

    for name, info in TARGETS.items():
        area, peak_rt = quantify_peak(time, intensity, info)
        conc_raw = area_to_conc(area, name)
        conc_final = conc_raw * dilution
        result[f'{name}_area'] = area
        result[f'{name}_RT'] = peak_rt
        result[f'{name}_conc_mM'] = conc_final

    return result


def main():
    d_folders = sorted(DATA_DIR.glob("*.D"))
    print(f"총 {len(d_folders)}개 샘플\n")

    results = []
    for d_folder in d_folders:
        print(f"  {d_folder.stem}", end="")
        try:
            r = process_sample(d_folder)
            if r:
                results.append(r)
                vals = []
                for n in ['Galactose','Galactitol','Formate']:
                    a = r[f'{n}_area']
                    c = r[f'{n}_conc_mM']
                    vals.append(f"A={a:.0f}/C={c:.1f}")
                print(f"  -> {vals[0]} | {vals[1]} | {vals[2]}")
            else:
                print("  -> skip")
        except Exception as e:
            print(f"  -> ERR: {e}")

    if not results:
        return

    df = pd.DataFrame(results)
    df = df.sort_values(['condition', 'time_h'])

    # ===== 정리표 (Area + mM 둘 다) =====
    print(f"\n{'='*140}")
    print("조건별·시간별 결과 (Valley drop-line baseline)")
    print(f"{'='*140}")
    header = (f"{'Condition':<20} {'Time':>5} {'DF':>4}  "
              f"{'Gal_Area':>10} {'Gal_mM':>9}  "
              f"{'Galtol_Area':>11} {'Galtol_mM':>10}  "
              f"{'Form_Area':>10} {'Form_mM':>9}")
    print(header)
    print("-"*140)

    prev_cond = None
    for _, row in df.iterrows():
        cond = row['condition']
        if prev_cond and cond != prev_cond:
            print("-"*140)
        prev_cond = cond

        df_val = 200 if row['time_h'] == 0 else 20

        def fmt_area(v):
            return f"{v:.0f}" if v > 0 else "0"
        def fmt_conc(v):
            return f"{v:.2f}" if v > 0 else "n.d."

        print(f"{cond:<20} {row['time_h']:>4}h {df_val:>4}x  "
              f"{fmt_area(row['Galactose_area']):>10} {fmt_conc(row['Galactose_conc_mM']):>9}  "
              f"{fmt_area(row['Galactitol_area']):>11} {fmt_conc(row['Galactitol_conc_mM']):>10}  "
              f"{fmt_area(row['Formate_area']):>10} {fmt_conc(row['Formate_conc_mM']):>9}")

    print("="*140)

    # CSV 저장
    out_file = DATA_DIR / "quantification_results_mM.csv"
    df.to_csv(out_file, index=False, encoding='utf-8-sig')
    print(f"\n전체 결과: {out_file}")

    # 요약 CSV
    summary_rows = []
    for _, row in df.iterrows():
        df_val = 200 if row['time_h'] == 0 else 20
        summary_rows.append({
            'Condition': row['condition'], 'Time_h': row['time_h'], 'DF': df_val,
            'Galactose_area': row['Galactose_area'], 'Galactose_mM': row['Galactose_conc_mM'],
            'Galactitol_area': row['Galactitol_area'], 'Galactitol_mM': row['Galactitol_conc_mM'],
            'Formate_area': row['Formate_area'], 'Formate_mM': row['Formate_conc_mM'],
        })
    summary_df = pd.DataFrame(summary_rows)
    summary_out = DATA_DIR / "summary_by_condition.csv"
    summary_df.to_csv(summary_out, index=False, encoding='utf-8-sig')
    print(f"요약: {summary_out}")

    # 시각화
    _plot_timecourse(df)


def _plot_timecourse(df):
    conditions = sorted(df['condition'].unique())
    compounds = ['Galactose', 'Galactitol', 'Formate']
    colors = {'Galactose': '#e74c3c', 'Galactitol': '#2ecc71', 'Formate': '#3498db'}
    time_order = [0, 3, 6, 16]

    ncols = 3
    nrows = (len(conditions) + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(7*ncols, 5*nrows))
    axes = axes.flatten()

    for i, cond in enumerate(conditions):
        ax = axes[i]
        cond_df = df[df['condition'] == cond].sort_values('time_h')
        times = cond_df['time_h'].values

        for comp in compounds:
            concs = cond_df[f'{comp}_conc_mM'].values
            ax.plot(times, concs, 'o-', label=comp, color=colors[comp],
                    markersize=8, linewidth=2)
            for t, c in zip(times, concs):
                if c > 0:
                    ax.annotate(f'{c:.1f}', (t, c), textcoords='offset points',
                               xytext=(0, 8), fontsize=7, ha='center', color=colors[comp])

        ax.set_xlabel('Time (h)')
        ax.set_ylabel('Conc (mM)')
        ax.set_title(cond, fontsize=12, fontweight='bold')
        ax.set_xticks(time_order)
        ax.legend(fontsize=9)
        ax.grid(True, alpha=0.3)

    for j in range(i+1, len(axes)):
        axes[j].set_visible(False)

    plt.suptitle('260302 RPM Buffer - 조건별 농도 변화 (mM)', fontsize=16, fontweight='bold', y=1.01)
    plt.tight_layout()
    out = DATA_DIR / "condition_timecourse.png"
    plt.savefig(out, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"그래프: {out}")


if __name__ == '__main__':
    main()
