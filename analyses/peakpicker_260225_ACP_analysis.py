"""
260225_ACP LC-RID Chromatogram Analysis
- 12개 .D 파일: 100/150/200/300 mM ACP x 90MIN/180MIN + NC
- 전체 크로마토그램 오버레이 및 피크 RT 목록 출력
- YAML Unknown 섹션 업데이트용 피크 동정 보조
"""

import os
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.signal import find_peaks

# chemstation_parser.py 가 있는 경로 추가
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PEAKPICKER_SRC = r"C:\Users\Jahyun\PeakPicker\src"
sys.path.insert(0, PEAKPICKER_SRC)

from chemstation_parser import ChemstationParser

# ── 경로 설정 ────────────────────────────────────────────────────
DATA_DIR = r"C:\Chem32\1\DATA\2. D-Xyl cascade HPLC\Xul 5P production\Pretest\260225_ACP"
OUTPUT_PNG = os.path.join(SCRIPT_DIR, "peakpicker_260225_ACP_chromatogram.png")

# ── 샘플 정의 ────────────────────────────────────────────────────
SAMPLES = [
    # (folder, label, conc_mM, time_min, is_nc, color_group)
    ("260225_ACP_100_NC_90MIN.D",  "NC 100mM",  100, None, True,  "gray"),
    ("260225_ACP_150_NC_90MIN.D",  "NC 150mM",  150, None, True,  "gray"),
    ("260225_ACP_200_NC_90MIN.D",  "NC 200mM",  200, None, True,  "gray"),
    ("260225_ACP_300_NC_90MIN.D",  "NC 300mM",  300, None, True,  "gray"),
    ("260225_ACP_100_90MIN.D",     "100mM 90'", 100,  90, False, "#1f77b4"),
    ("260225_ACP_150_90MIN.D",     "150mM 90'", 150,  90, False, "#ff7f0e"),
    ("260225_ACP_200_90MIN.D",     "200mM 90'", 200,  90, False, "#2ca02c"),
    ("260225_ACP_300_90MIN.D",     "300mM 90'", 300,  90, False, "#d62728"),
    ("260225_ACP_100_180MIN.D",    "100mM 180'",100, 180, False, "#aec7e8"),
    ("260225_ACP_150_180MIN.D",    "150mM 180'",150, 180, False, "#ffbb78"),
    ("260225_ACP_200_180MIN.D",    "200mM 180'",200, 180, False, "#98df8a"),
    ("260225_ACP_300_180MIN.D",    "300mM 180'",300, 180, False, "#ff9896"),
]

# YAML에서 가져온 RT 윈도우 (compound -> (rt_min, rt_max))
KNOWN_WINDOWS = {
    "Unknown_6.95": (6.75, 7.05),
    "Unknown_7.25": (7.05, 7.50),
    "Unknown_9.4":  (9.10, 9.80),
    "D-Xylose":     (10.80, 11.50),
    "D-Xylulose":   (11.50, 12.00),
    "Acetate":      (17.00, 17.70),
}

WINDOW_COLORS = {
    "Unknown_6.95": "#e8d5f0",
    "Unknown_7.25": "#d5e8f0",
    "Unknown_9.4":  "#d5f0e8",
    "D-Xylose":     "#fff0cc",
    "D-Xylulose":   "#ffe0cc",
    "Acetate":      "#f0d5d5",
}


def load_sample(folder_name):
    """RID1A.ch 파일 로드 후 (time, intensity) 반환"""
    ch_path = os.path.join(DATA_DIR, folder_name, "RID1A.ch")
    if not os.path.exists(ch_path):
        print(f"  [WARN] 파일 없음: {ch_path}")
        return None, None
    parser = ChemstationParser(ch_path)
    time, intensity = parser.read()
    return time, intensity


def get_area_in_window(time, intensity, rt_lo, rt_hi):
    """RT 윈도우 내 적분 면적 (사다리꼴)"""
    mask = (time >= rt_lo) & (time <= rt_hi)
    if mask.sum() < 2:
        return 0.0
    t_seg = time[mask]
    i_seg = intensity[mask]
    return float(np.trapz(i_seg, t_seg * 60))  # nRIU * s


def detect_peaks(time, intensity, prominence=500, distance_pts=50):
    """크로마토그램에서 피크 검출 후 (RT, height) 리스트 반환"""
    peaks, props = find_peaks(intensity, prominence=prominence, distance=distance_pts)
    result = [(float(time[p]), float(intensity[p])) for p in peaks]
    return result


def main():
    print("=" * 60)
    print("260225_ACP RID Chromatogram Analysis")
    print("=" * 60)

    # ── 데이터 로드 ──────────────────────────────────────────────
    loaded = {}
    for folder, label, conc, rxn_time, is_nc, color in SAMPLES:
        t, sig = load_sample(folder)
        if t is not None:
            loaded[folder] = {"time": t, "intensity": sig, "label": label,
                               "conc": conc, "rxn_time": rxn_time,
                               "is_nc": is_nc, "color": color}
            print(f"  OK  {label:15s}  {len(t):5d} pts  "
                  f"{t[0]:.2f}-{t[-1]:.2f} min")
        else:
            print(f"  FAIL {label}")

    if not loaded:
        print("로드된 샘플 없음. 경로 확인 필요.")
        return

    # ── 피크 검출 (모든 샘플) ────────────────────────────────────
    print("\n--- 검출된 주요 피크 (prominence >= 500 nRIU) ---")
    all_peak_rts = []
    for folder, data in loaded.items():
        peaks = detect_peaks(data["time"], data["intensity"], prominence=500)
        rts = [p[0] for p in peaks]
        all_peak_rts.extend(rts)
        peak_str = "  ".join([f"{rt:.2f}" for rt, _ in peaks])
        print(f"  {data['label']:15s}: {peak_str}")

    # ── 윈도우별 면적 테이블 ─────────────────────────────────────
    print("\n--- RT 윈도우별 면적 (nRIU*s) ---")
    header = f"{'Sample':15s}" + "".join([f"  {k:12s}" for k in KNOWN_WINDOWS])
    print(header)
    print("-" * len(header))

    area_table = {}
    for folder, data in loaded.items():
        areas = {}
        for cmp, (lo, hi) in KNOWN_WINDOWS.items():
            areas[cmp] = get_area_in_window(data["time"], data["intensity"], lo, hi)
        area_table[folder] = areas
        row = f"{data['label']:15s}" + "".join([f"  {areas[k]:12.0f}" for k in KNOWN_WINDOWS])
        print(row)

    # ── ACP 농도에 따라 증가하는 피크 분석 ─────────────────────
    print("\n--- ACP 농도 증가에 따른 피크 변화 (90MIN 반응) ---")
    rxn_90 = [(f, d) for f, d in loaded.items() if not d["is_nc"] and d["rxn_time"] == 90]
    rxn_90_sorted = sorted(rxn_90, key=lambda x: x[1]["conc"])
    nc_representative = [(f, d) for f, d in loaded.items() if d["is_nc"]]
    # NC 평균 면적
    nc_areas = {}
    for cmp in KNOWN_WINDOWS:
        vals = [area_table[f][cmp] for f, d in nc_representative if f in area_table]
        nc_areas[cmp] = np.mean(vals) if vals else 0.0

    print(f"\n  NC 평균 면적:")
    for cmp, area in nc_areas.items():
        print(f"    {cmp:15s}: {area:10.0f}")

    print(f"\n  90MIN 반응 샘플 (NC 대비):")
    for f, d in rxn_90_sorted:
        diffs = {cmp: area_table[f][cmp] - nc_areas[cmp] for cmp in KNOWN_WINDOWS}
        diff_str = "  ".join([f"{cmp}: {v:+.0f}" for cmp, v in diffs.items() if abs(v) > 200])
        print(f"    {d['label']:15s}  {diff_str}")

    # ── 플롯 ────────────────────────────────────────────────────
    fig, axes = plt.subplots(3, 1, figsize=(18, 16))
    fig.suptitle("260225_ACP RID Chromatogram Overlay\n"
                 "HPX-87H, 5mM H2SO4, 0.5mL/min, 65C, RID",
                 fontsize=13, fontweight="bold")

    # -- 패널 0: NC 오버레이 --
    ax = axes[0]
    ax.set_title("Negative Controls (NC) — 100/150/200/300 mM ACP", fontsize=11)
    nc_samples = [(f, d) for f, d in loaded.items() if d["is_nc"]]
    nc_colors = ["#555555", "#888888", "#aaaaaa", "#cccccc"]
    for i, (f, d) in enumerate(nc_samples):
        ax.plot(d["time"], d["intensity"], color=nc_colors[i % 4],
                linewidth=1.2, label=d["label"])
    _add_rt_windows(ax)
    ax.legend(fontsize=8, loc="upper right")
    ax.set_xlim(5, 22)
    ax.set_xlabel("Retention Time (min)", fontsize=9)
    ax.set_ylabel("RID Signal (nRIU)", fontsize=9)

    # -- 패널 1: 90MIN 반응 --
    ax = axes[1]
    ax.set_title("Reaction Samples — 90 MIN", fontsize=11)
    rxn_90_all = [(f, d) for f, d in loaded.items() if not d["is_nc"] and d["rxn_time"] == 90]
    for f, d in sorted(rxn_90_all, key=lambda x: x[1]["conc"]):
        ax.plot(d["time"], d["intensity"], color=d["color"], linewidth=1.5,
                label=d["label"])
    _add_rt_windows(ax)
    ax.legend(fontsize=8, loc="upper right")
    ax.set_xlim(5, 22)
    ax.set_xlabel("Retention Time (min)", fontsize=9)
    ax.set_ylabel("RID Signal (nRIU)", fontsize=9)

    # -- 패널 2: 180MIN 반응 --
    ax = axes[2]
    ax.set_title("Reaction Samples — 180 MIN", fontsize=11)
    rxn_180_all = [(f, d) for f, d in loaded.items() if not d["is_nc"] and d["rxn_time"] == 180]
    for f, d in sorted(rxn_180_all, key=lambda x: x[1]["conc"]):
        ax.plot(d["time"], d["intensity"], color=d["color"], linewidth=1.5,
                label=d["label"])
    _add_rt_windows(ax)
    ax.legend(fontsize=8, loc="upper right")
    ax.set_xlim(5, 22)
    ax.set_xlabel("Retention Time (min)", fontsize=9)
    ax.set_ylabel("RID Signal (nRIU)", fontsize=9)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    plt.savefig(OUTPUT_PNG, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n플롯 저장: {OUTPUT_PNG}")

    # ── 피크 RT 클러스터링 요약 ──────────────────────────────────
    print("\n--- 공통 피크 RT 클러스터 (전체 샘플) ---")
    if all_peak_rts:
        arr = np.array(sorted(all_peak_rts))
        clusters = _cluster_rts(arr, gap=0.3)
        for center, members in clusters:
            known = _match_known_window(center)
            tag = f"  -> {known}" if known else ""
            print(f"  RT {center:.2f} min  (n={len(members):2d}  "
                  f"range {min(members):.2f}-{max(members):.2f}){tag}")

    print("\n완료.")


def _add_rt_windows(ax):
    """알려진 RT 윈도우를 배경 음영으로 추가"""
    ymin, ymax = ax.get_ylim()
    for cmp, (lo, hi) in KNOWN_WINDOWS.items():
        ax.axvspan(lo, hi, alpha=0.18, color=WINDOW_COLORS[cmp], zorder=0)
        ax.text((lo + hi) / 2, ax.get_ylim()[1] * 0.95, cmp,
                ha="center", va="top", fontsize=6.5, color="#555555",
                rotation=90, clip_on=True)


def _cluster_rts(arr, gap=0.3):
    """RT 배열을 gap 기준으로 클러스터링 -> (중앙값, 멤버 리스트) 리스트"""
    clusters = []
    current = [arr[0]]
    for rt in arr[1:]:
        if rt - current[-1] <= gap:
            current.append(rt)
        else:
            clusters.append((float(np.median(current)), current))
            current = [rt]
    clusters.append((float(np.median(current)), current))
    return clusters


def _match_known_window(rt):
    """RT가 알려진 윈도우에 속하면 화합물명 반환"""
    for cmp, (lo, hi) in KNOWN_WINDOWS.items():
        if lo <= rt <= hi:
            return cmp
    return None


if __name__ == "__main__":
    main()
