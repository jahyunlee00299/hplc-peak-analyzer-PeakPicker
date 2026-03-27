"""
xul5p_260324_enhanced_viz.py
============================
XylA/XylB cascade 실험 (260317 + 260324) 통합 시각화
- 외부 파일 없이 실행 가능 (수치 하드코딩)
- Figure 1: 4패널 정량값 기반 그래프
- Figure 2: 3패널 Discussion 그래프
출판 품질 (Nature/ACS 스타일)

Author : Claude Code
Date   : 2026-03-27
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy.stats import linregress
from scipy.optimize import curve_fit
import warnings
warnings.filterwarnings('ignore')

# ─────────────────────────────────────────────────────────────────────────────
# 출력 경로
# ─────────────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_FIG1 = os.path.join(SCRIPT_DIR, "xul5p_260324_enhanced_viz_fig1.png")
OUT_FIG2 = os.path.join(SCRIPT_DIR, "xul5p_260324_enhanced_viz_fig2.png")

# ─────────────────────────────────────────────────────────────────────────────
# 정량 변환 상수
# 260317 결과는 이미 mM 정량값
# 260324 결과는 peak area (nRIU·s) → mM 변환 필요
#   D-dRib-5P 표준 slope 추정: 260317 데이터에서 역산
#   100 mM Xyl, 3X:3X, 1.5h → product 102.9 mM = area 242,074 nRIU·s
#   slope ≈ 102.9 / 242,074 ≈ 4.25e-4 mM / (nRIU·s)
# ─────────────────────────────────────────────────────────────────────────────
AREA_TO_MM = 102.9 / 242074  # mM per (nRIU·s)

def area_to_mM(area):
    return area * AREA_TO_MM

# ─────────────────────────────────────────────────────────────────────────────
# 실험 데이터 (하드코딩)
# ─────────────────────────────────────────────────────────────────────────────

# ── 260324 실험 (a) Enzyme ratio ─────────────────────────────────────────────
# 조건: 100 mM Xyl, 100 mM AcP, 1 mM ATP, 1.5h
enz_ratio_labels  = ["1X:1X", "1X:3X", "3X:1X", "3X:3X"]
enz_ratio_area    = [242074, 238222, 238689, 267160]   # nRIU·s
enz_ratio_mM      = [area_to_mM(a) for a in enz_ratio_area]
# 260317 정량값 (같은 조건 1mM ATP, 100mM Xyl)
enz_ratio_mM_ref  = [58.1, 51.7, 50.8, 102.9]         # mM (260317)
XYL_INIT_ENZ      = 100.0  # mM
enz_ratio_conv     = [p / XYL_INIT_ENZ * 100 for p in enz_ratio_mM_ref]

# ── 260324 실험 (b) ATP dose-response ────────────────────────────────────────
# 260324: 3X:3X, 100 mM Xyl, 120 mM AcP, 1.5h
atp_conc_324      = [0.125, 0.25, 0.5, 1.0]
atp_area_324      = [290000, 290000, 292000, 268000]
atp_mM_324        = [area_to_mM(a) for a in atp_area_324]
# 260317: 100 mM AcP, 100 mM Xyl, 1.5h
atp_conc_317      = [0.04, 0.2, 1.0, 5.0]
atp_mM_317_1h5    = [17, 95, 135, 95]    # mM, 1.5h
atp_mM_317_3h     = [25, 97, 132, 88]    # mM, 3h

# ── 260324 실험 (c) Substrate concentration ───────────────────────────────────
xyl_conc_324      = [25, 50, 100, 200]
sub_area_324      = [110000, 185000, 330000, 520000]   # nRIU·s
sub_mM_324        = [area_to_mM(a) for a in sub_area_324]
# 260317 정량값
xyl_conc_317      = [25, 50, 100, 100, 100, 200]
acp_conc_317      = [30, 60, 100, 120, 150, 240]
sub_mM_317        = [21.0, 19.8, 102.9, 58.4, 78.9, 166.5]
sub_conv_317      = [95, 96, 54, 80, 89, 78]   # %
# 비교용 통일된 데이터 (AcP = 1.2x)
xyl_conc_main     = [25, 50, 100, 200]
sub_mM_main       = [21.0, 19.8, 58.4, 166.5]   # 260317 AcP=1.2x 조건
sub_conv_main     = [95, 96, 80, 78]

# ── 260324 실험 (d) FED batch ─────────────────────────────────────────────────
fed_labels        = ["FED AcP\nDW", "FED EM2\nAcP DW", "FED XylB3X\nDW"]
fed_product_area  = [220000, 255000, 182000]
fed_pi_area       = [50000, 42000, 17000]
fed_xyl_area      = [80000, 83000, 107000]
fed_acetate_area  = [9000, 9000, 107000]
fed_product_mM    = [area_to_mM(a) for a in fed_product_area]
fed_pi_mM         = [area_to_mM(a) for a in fed_pi_area]
fed_xyl_mM        = [area_to_mM(a) for a in fed_xyl_area]
fed_acetate_mM    = [area_to_mM(a) for a in fed_acetate_area]

# ── 260317 실험 (a) AcP effect ────────────────────────────────────────────────
# ATP = 5 mM, 1.5h vs 3h
acp_conc_effect   = [100, 150, 200, 300]
acp_mM_1h5        = [95, 140, 180, 213]
acp_mM_3h         = [88, 160, 220, 272]

# ─────────────────────────────────────────────────────────────────────────────
# 스타일 설정 (Nature/ACS)
# ─────────────────────────────────────────────────────────────────────────────
PALETTE = {
    "blue"    : "#2166AC",
    "red"     : "#D6604D",
    "green"   : "#4DAC26",
    "orange"  : "#F4A582",
    "purple"  : "#762A83",
    "gray"    : "#888888",
    "lightblue": "#92C5DE",
    "darkblue" : "#053061",
}

plt.rcParams.update({
    "font.family"       : "Arial",
    "font.size"         : 10,
    "axes.linewidth"    : 0.8,
    "axes.spines.top"   : False,
    "axes.spines.right" : False,
    "xtick.direction"   : "out",
    "ytick.direction"   : "out",
    "xtick.major.width" : 0.8,
    "ytick.major.width" : 0.8,
    "legend.frameon"    : False,
    "figure.dpi"        : 150,
    "savefig.dpi"       : 300,
    "savefig.bbox"      : "tight",
})

ENZ_COLORS   = [PALETTE["lightblue"], PALETTE["blue"],
                PALETTE["orange"],    PALETTE["red"]]
ATP_COLORS_P = [PALETTE["lightblue"], PALETTE["blue"],
                PALETTE["orange"],    PALETTE["red"]]
SUB_COLORS   = [PALETTE["lightblue"], PALETTE["blue"],
                PALETTE["orange"],    PALETTE["red"]]


# ─────────────────────────────────────────────────────────────────────────────
# Figure 1: 4패널
# ─────────────────────────────────────────────────────────────────────────────
def make_figure1():
    fig = plt.figure(figsize=(14, 11))
    fig.suptitle(
        "XylA/XylB Cascade Optimization — 260324 & 260317 Combined Analysis",
        fontsize=13, fontweight="bold", y=0.98
    )
    gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.42, wspace=0.38)

    # ── Panel (a): Enzyme ratio bar chart with conversion% label ─────────────
    ax_a = fig.add_subplot(gs[0, 0])
    bars = ax_a.bar(
        range(4), enz_ratio_mM_ref,
        color=ENZ_COLORS, edgecolor="white", linewidth=0.6,
        alpha=0.88, width=0.6
    )
    # Conversion% 라벨
    for i, (bar, conv, prod) in enumerate(zip(bars, enz_ratio_conv, enz_ratio_mM_ref)):
        ax_a.text(
            bar.get_x() + bar.get_width() / 2,
            prod + 3,
            f"{conv:.0f}%",
            ha="center", va="bottom", fontsize=9, fontweight="bold",
            color=PALETTE["darkblue"]
        )
    ax_a.set_xticks(range(4))
    ax_a.set_xticklabels(enz_ratio_labels, fontsize=10)
    ax_a.set_xlabel("XylA : XylB ratio", fontsize=11)
    ax_a.set_ylabel("Xul-5P produced (mM)", fontsize=11)
    ax_a.set_title("(a) Enzyme Ratio\n100 mM Xyl, 100 mM AcP, 1 mM ATP, 1.5 h",
                   fontsize=10)
    ax_a.set_ylim(0, 125)
    ax_a.yaxis.grid(True, linewidth=0.5, alpha=0.5, color="#cccccc")
    ax_a.set_axisbelow(True)
    # NE control 수평선
    ax_a.axhline(0, color=PALETTE["gray"], linestyle=":", linewidth=1.0,
                 label="NE control (≈0)")
    ax_a.legend(fontsize=8)

    # ── Panel (b): ATP dose-response curve (양쪽 실험 오버레이) ──────────────
    ax_b = fig.add_subplot(gs[0, 1])
    # 260317 1.5h
    ax_b.plot(atp_conc_317, atp_mM_317_1h5,
              marker="o", linewidth=1.8, markersize=7,
              color=PALETTE["blue"], label="260317 (1.5 h)",
              zorder=3)
    # 260317 3h
    ax_b.plot(atp_conc_317, atp_mM_317_3h,
              marker="s", linewidth=1.8, markersize=7, linestyle="--",
              color=PALETTE["red"], label="260317 (3 h)",
              zorder=3)
    # 260324 (xlog 스케일에서 1.0 mM만 겹침)
    ax_b.plot(atp_conc_324, atp_mM_324,
              marker="^", linewidth=1.8, markersize=7, linestyle="-.",
              color=PALETTE["green"], label="260324 (1.5 h, 120 mM AcP)",
              zorder=3)
    # 1 mM ATP 경계 표시
    ax_b.axvline(1.0, color=PALETTE["gray"], linestyle=":", linewidth=0.9,
                 alpha=0.7)
    ax_b.set_xscale("log")
    ax_b.set_xlabel("ATP concentration (mM)", fontsize=11)
    ax_b.set_ylabel("Xul-5P produced (mM)", fontsize=11)
    ax_b.set_title("(b) ATP Dose-Response\n260317 vs 260324 overlay",
                   fontsize=10)
    ax_b.legend(fontsize=8)
    ax_b.yaxis.grid(True, linewidth=0.5, alpha=0.5, color="#cccccc")
    ax_b.set_axisbelow(True)
    ax_b.text(1.2, 120, "1 mM ATP →\noptimum", fontsize=8,
              color=PALETTE["gray"], va="top")

    # ── Panel (c): Substrate conc - linear regression with R² ─────────────────
    ax_c = fig.add_subplot(gs[1, 0])
    # 메인 데이터 (AcP=1.2x)
    ax_c.scatter(xyl_conc_main, sub_mM_main,
                 color=ENZ_COLORS, s=70, zorder=4,
                 edgecolors="white", linewidth=0.8,
                 label="Product (AcP=1.2× Xyl)")
    # 선형회귀
    slope, intercept, r_val, p_val, se = linregress(xyl_conc_main, sub_mM_main)
    x_fit = np.linspace(20, 210, 200)
    y_fit = slope * x_fit + intercept
    ax_c.plot(x_fit, y_fit, "--", color=PALETTE["gray"],
              linewidth=1.4, alpha=0.8,
              label=f"Linear fit (R²={r_val**2:.3f})")
    # 100 mM AcP (부족) 조건 별도 표시
    ax_c.scatter([100], [102.9], marker="D", color=PALETTE["purple"],
                 s=80, zorder=5, edgecolors="white",
                 label="100 mM Xyl / 100 mM AcP (54%)")
    for i, (x, y, conv) in enumerate(zip(xyl_conc_main, sub_mM_main,
                                          sub_conv_main)):
        ax_c.annotate(f"{conv}%",
                      xy=(x, y), xytext=(6, 4), textcoords="offset points",
                      fontsize=8, color=PALETTE["darkblue"])
    ax_c.set_xlabel("Initial D-Xylose (mM)", fontsize=11)
    ax_c.set_ylabel("Xul-5P produced (mM)", fontsize=11)
    ax_c.set_title("(c) Substrate Concentration\n3X:3X, 1 mM ATP, 1.5 h",
                   fontsize=10)
    ax_c.legend(fontsize=8)
    ax_c.yaxis.grid(True, linewidth=0.5, alpha=0.5, color="#cccccc")
    ax_c.set_axisbelow(True)

    # ── Panel (d): FED batch compound profile (grouped bar) ─────────────────
    ax_d = fig.add_subplot(gs[1, 1])
    x_fed   = np.arange(3)
    width_d = 0.20
    cmp_names = ["Xul-5P", "Pi", "D-Xylose", "Acetate"]
    cmp_data  = [fed_product_mM, fed_pi_mM, fed_xyl_mM, fed_acetate_mM]
    cmp_colors_d = [PALETTE["purple"], PALETTE["red"],
                    PALETTE["orange"], PALETTE["green"]]
    for i, (name, data, color) in enumerate(zip(cmp_names, cmp_data,
                                                  cmp_colors_d)):
        offset = (i - 1.5) * width_d
        bars_d = ax_d.bar(x_fed + offset, data,
                          width_d, label=name,
                          color=color, alpha=0.85,
                          edgecolor="white", linewidth=0.5)
    ax_d.set_xticks(x_fed)
    ax_d.set_xticklabels(fed_labels, fontsize=10)
    ax_d.set_xlabel("FED batch condition (30 min)", fontsize=11)
    ax_d.set_ylabel("Estimated concentration (mM)", fontsize=11)
    ax_d.set_title("(d) FED Batch Compound Profile\n3X:3X, 30 min",
                   fontsize=10)
    ax_d.legend(fontsize=8, loc="upper right")
    ax_d.yaxis.grid(True, linewidth=0.5, alpha=0.5, color="#cccccc")
    ax_d.set_axisbelow(True)
    # XylB3X Acetate 급증 주석
    ax_d.annotate(
        "Acetate spike\n(AcP→Acetate\nno XylB?)",
        xy=(2 + 1.5 * width_d, fed_acetate_mM[2]),
        xytext=(2.1, fed_acetate_mM[2] + 8),
        fontsize=7.5, color=PALETTE["green"],
        arrowprops=dict(arrowstyle="->", color=PALETTE["green"],
                        lw=0.8)
    )

    plt.savefig(OUT_FIG1)
    plt.close()
    print(f"Figure 1 saved: {OUT_FIG1}")


# ─────────────────────────────────────────────────────────────────────────────
# Figure 2: 3패널 Discussion
# ─────────────────────────────────────────────────────────────────────────────
def mm_kinetics(S, Vmax, Km):
    """Michaelis-Menten 함수"""
    return Vmax * S / (Km + S)


def make_figure2():
    fig = plt.figure(figsize=(14, 5.5))
    fig.suptitle(
        "XylA/XylB Cascade — Discussion Analysis (260317)",
        fontsize=13, fontweight="bold", y=1.01
    )
    gs = gridspec.GridSpec(1, 3, figure=fig, wspace=0.40)

    # ── Panel (a): AcP 농도 효과 + 포화곡선 + Km 추정 ─────────────────────
    ax_a = fig.add_subplot(gs[0, 0])

    # 데이터 포인트
    ax_a.plot(acp_conc_effect, acp_mM_1h5,
              "o-", color=PALETTE["blue"], linewidth=1.8, markersize=7,
              label="1.5 h", zorder=3)
    ax_a.plot(acp_conc_effect, acp_mM_3h,
              "s--", color=PALETTE["red"], linewidth=1.8, markersize=7,
              label="3 h", zorder=3)

    # Michaelis-Menten fitting (1.5h 데이터)
    try:
        S_arr = np.array(acp_conc_effect, dtype=float)
        V_arr = np.array(acp_mM_1h5, dtype=float)
        popt, _ = curve_fit(mm_kinetics, S_arr, V_arr,
                            p0=[300, 150], maxfev=5000)
        Vmax_est, Km_est = popt
        x_fit = np.linspace(0, 350, 500)
        y_fit = mm_kinetics(x_fit, Vmax_est, Km_est)
        ax_a.plot(x_fit, y_fit, ":", color=PALETTE["blue"],
                  linewidth=1.6, alpha=0.7,
                  label=f"MM fit (Vmax≈{Vmax_est:.0f}, Km≈{Km_est:.0f} mM)")
        # Km 수직선
        ax_a.axvline(Km_est, color=PALETTE["gray"], linestyle=":",
                     linewidth=0.9, alpha=0.6)
        ax_a.text(Km_est + 8, 20, f"Km≈{Km_est:.0f} mM",
                  fontsize=8, color=PALETTE["gray"])
    except Exception as e:
        print(f"  [WARN] MM fitting failed: {e}")

    ax_a.set_xlabel("AcP concentration (mM)", fontsize=11)
    ax_a.set_ylabel("Xul-5P produced (mM)", fontsize=11)
    ax_a.set_title("(a) AcP Effect on Xul-5P\n(5 mM ATP, 100 mM Xyl)",
                   fontsize=10)
    ax_a.legend(fontsize=8)
    ax_a.yaxis.grid(True, linewidth=0.5, alpha=0.5, color="#cccccc")
    ax_a.set_axisbelow(True)
    ax_a.set_xlim(50, 350)
    ax_a.set_ylim(0, 310)

    # ── Panel (b): Conversion% vs Xyl concentration ───────────────────────────
    ax_b = fig.add_subplot(gs[0, 1])

    # AcP = 1.2x 조건만
    xyl_b  = np.array([25, 50, 100, 200], dtype=float)
    conv_b = np.array([95, 96, 80, 78], dtype=float)
    # AcP = 1.0x (100 mM) 조건
    xyl_b2  = np.array([100], dtype=float)
    conv_b2 = np.array([54], dtype=float)
    # AcP = 1.5x 조건
    xyl_b3  = np.array([100], dtype=float)
    conv_b3 = np.array([89], dtype=float)

    sc1 = ax_b.scatter(xyl_b, conv_b,
                       c=PALETTE["blue"], s=70, zorder=4,
                       edgecolors="white", label="AcP = 1.2× Xyl",
                       linewidth=0.8)
    sc2 = ax_b.scatter(xyl_b2, conv_b2,
                       c=PALETTE["red"], s=90, marker="D", zorder=5,
                       edgecolors="white", label="AcP = 1.0× Xyl",
                       linewidth=0.8)
    sc3 = ax_b.scatter(xyl_b3, conv_b3,
                       c=PALETTE["green"], s=90, marker="^", zorder=5,
                       edgecolors="white", label="AcP = 1.5× Xyl",
                       linewidth=0.8)
    # 연결선 (1.2x)
    ax_b.plot(xyl_b, conv_b, "-", color=PALETTE["blue"],
              linewidth=1.2, alpha=0.5, zorder=2)

    # 라벨
    for x, c, label in [(25, 95, "25 mM"), (50, 96, "50 mM"),
                         (100, 80, "100 mM\n(1.2×)"), (200, 78, "200 mM")]:
        ax_b.annotate(f"{c}%",
                      xy=(x, c), xytext=(5, -10), textcoords="offset points",
                      fontsize=8, color=PALETTE["darkblue"])

    ax_b.axhline(80, color=PALETTE["gray"], linestyle=":", linewidth=0.9,
                 alpha=0.6, label="80% target")
    ax_b.set_xlabel("Initial D-Xylose (mM)", fontsize=11)
    ax_b.set_ylabel("Conversion (%)", fontsize=11)
    ax_b.set_title("(b) Conversion vs [Xylose]\n(3X:3X, 1 mM ATP, 1.5 h)",
                   fontsize=10)
    ax_b.set_ylim(40, 105)
    ax_b.set_xlim(10, 220)
    ax_b.legend(fontsize=8)
    ax_b.yaxis.grid(True, linewidth=0.5, alpha=0.5, color="#cccccc")
    ax_b.set_axisbelow(True)

    # ── Panel (c): ATP catalytic turnover (Pi 생성량 기반) ────────────────────
    ax_c = fig.add_subplot(gs[0, 2])

    # Pi 생성량 = Xul-5P 생성량 (1:1 화학양론)
    # ATP 1 mM → 촉매 순환 횟수 = Xul-5P (mM) / ATP (mM)
    atp_init_vals = [0.04, 0.2, 1.0, 5.0]
    product_vals  = atp_mM_317_1h5   # 1.5h 결과
    turnovers     = [p / a for p, a in zip(product_vals, atp_init_vals)]

    bars_c = ax_c.bar(range(4), turnovers,
                      color=ATP_COLORS_P, edgecolor="white",
                      linewidth=0.6, alpha=0.88, width=0.6)

    # 수치 라벨
    for bar, tn in zip(bars_c, turnovers):
        ax_c.text(
            bar.get_x() + bar.get_width() / 2,
            tn + 10,
            f"×{tn:.0f}",
            ha="center", va="bottom", fontsize=9, fontweight="bold",
            color=PALETTE["darkblue"]
        )

    ax_c.set_xticks(range(4))
    ax_c.set_xticklabels([f"{a} mM" for a in atp_init_vals], fontsize=9)
    ax_c.set_xlabel("Initial ATP (mM)", fontsize=11)
    ax_c.set_ylabel("Estimated ATP turnover (×)", fontsize=11)
    ax_c.set_title("(c) ATP Catalytic Turnover\n(Product / ATP_initial, 1.5 h)",
                   fontsize=10)
    ax_c.yaxis.grid(True, linewidth=0.5, alpha=0.5, color="#cccccc")
    ax_c.set_axisbelow(True)

    # 최적 ATP 농도 표시
    max_idx = turnovers.index(max(turnovers))
    ax_c.annotate(
        "Highest\nturnover",
        xy=(max_idx, turnovers[max_idx]),
        xytext=(max_idx + 0.5, turnovers[max_idx] * 0.9),
        fontsize=8, color=PALETTE["red"],
        arrowprops=dict(arrowstyle="->", color=PALETTE["red"], lw=0.8)
    )

    plt.tight_layout()
    plt.savefig(OUT_FIG2)
    plt.close()
    print(f"Figure 2 saved: {OUT_FIG2}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main():
    print("=" * 65)
    print("XylA/XylB Cascade — Enhanced Visualization")
    print("260317 + 260324 Combined Analysis")
    print("=" * 65)

    print("\n[Figure 1] 4-panel quantitative analysis...")
    make_figure1()

    print("\n[Figure 2] 3-panel discussion analysis...")
    make_figure2()

    print("\n--- Summary ---")
    print(f"Area→mM conversion factor : {AREA_TO_MM:.4e} mM/(nRIU·s)")
    print(f"  (calibrated from: 3X:3X, 100mM Xyl, 1.5h → 102.9 mM = 242,074 nRIU·s)")
    print(f"\nFigures saved:")
    print(f"  {OUT_FIG1}")
    print(f"  {OUT_FIG2}")
    print("\nDone.")


if __name__ == "__main__":
    main()
