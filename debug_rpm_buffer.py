"""0h 샘플들의 10-12분 구간 확인"""
import sys, numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))
from chemstation_parser import ChemstationParser
from scipy.signal import savgol_filter
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

DATA = Path(r"C:\Chem32\1\DATA\260302_rpm_buffer")

# 0h 샘플들만 확인
samples_0h = sorted(DATA.glob("*_0H.D"))

fig, axes = plt.subplots(len(samples_0h), 1, figsize=(18, 3.5*len(samples_0h)))
if len(samples_0h) == 1:
    axes = [axes]

for ax, d_folder in zip(axes, samples_0h):
    ch_file = d_folder / "RID1A.ch"
    parser = ChemstationParser(str(ch_file))
    time, intensity = parser.read()

    # 스무딩
    intensity_s = savgol_filter(intensity, 11, 3)

    # 10.5-12.1 구간
    mask = (time >= 10.0) & (time <= 12.5)
    t = time[mask]
    raw = intensity[mask]
    smooth = intensity_s[mask]

    # 로컬 베이스라인 (10.5-12.1)
    bl_mask = (t >= 10.5) & (t <= 12.1)
    bl_t = t[bl_mask]
    bl_raw = smooth[bl_mask]
    bl_left = np.mean(bl_raw[:5])
    bl_right = np.mean(bl_raw[-5:])
    local_bl = np.interp(bl_t, [bl_t[0], bl_t[-1]], [bl_left, bl_right])

    ax.plot(t, raw, 'b-', lw=0.5, alpha=0.5, label='raw')
    ax.plot(t, smooth, 'b-', lw=1, label='smooth')
    ax.plot(bl_t, local_bl, 'r--', lw=1.5, label='local BL')

    # valley 표시
    valley_mask = (bl_t >= 11.0) & (bl_t <= 11.6)
    if np.any(valley_mask):
        v_idx = np.where(valley_mask)[0]
        corr = bl_raw - local_bl
        v_local = v_idx[np.argmin(corr[v_idx])]
        ax.axvline(bl_t[v_local], color='green', ls=':', lw=2, label=f'valley={bl_t[v_local]:.2f}')

    # 타겟 윈도우
    ax.axvspan(10.8, 11.0, alpha=0.15, color='orange', label='Gal')
    ax.axvspan(11.6, 11.8, alpha=0.15, color='purple', label='Galtol')

    ax.set_title(d_folder.stem, fontsize=10, fontweight='bold')
    ax.legend(fontsize=7, ncol=4)
    ax.grid(True, alpha=0.3)

plt.suptitle('0h 샘플 - 10~12.5분 구간 (Galactose/Galactitol 영역)', fontsize=14, fontweight='bold')
plt.tight_layout()
out = DATA / "debug_0h_galactose_region.png"
plt.savefig(out, dpi=150, bbox_inches='tight')
print(f'Saved: {out}')
