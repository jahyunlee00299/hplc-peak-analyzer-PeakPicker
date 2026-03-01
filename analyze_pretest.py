r"""
Xul 5P Production Pretest 전체 데이터 분석
==========================================
C:\Chem32\1\DATA\2. D-Xyl cascade HPLC\Xul 5P production\Pretest
10개 실험 세트, 228개 .ch 파일 일괄 분석
"""

import sys
import os
import re
import numpy as np
from pathlib import Path
from scipy.integrate import trapezoid
from scipy import signal
from scipy.ndimage import minimum_filter1d, uniform_filter1d
import warnings
warnings.filterwarnings('ignore')

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from chemstation_parser import ChemstationParser

# ============================================================
#  설정
# ============================================================
BASE_DIR = Path(r'C:\Chem32\1\DATA\2. D-Xyl cascade HPLC\Xul 5P production\Pretest')
OUTPUT_DIR = Path(__file__).parent / 'result' / 'pretest_analysis'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PYTHON = sys.executable


def rolling_min_baseline(intensity, window_frac=0.15):
    """Rolling-minimum 기반 베이스라인 추정 (RID에 적합)"""
    win = max(int(len(intensity) * window_frac), 50)
    base = minimum_filter1d(intensity, size=win)
    base = uniform_filter1d(base, size=win * 2)
    return base


def detect_peaks_simple(time, corrected, min_prominence_frac=0.02, min_height_frac=0.01):
    """간단한 피크 검출 (노이즈 적응형)"""
    sig_range = np.ptp(corrected)
    if sig_range < 1.0:
        return [], {}

    noise_deriv = np.diff(corrected)
    noise_mad = np.median(np.abs(noise_deriv - np.median(noise_deriv)))
    noise_std = noise_mad * 1.4826

    min_prom = max(sig_range * min_prominence_frac, noise_std * 5)
    min_ht = max(sig_range * min_height_frac, noise_std * 5)

    peaks, props = signal.find_peaks(
        corrected, prominence=min_prom, height=min_ht, width=3, distance=20
    )
    return peaks, props


def compute_peak_area(time, corrected, pk_idx, all_peaks):
    """피크 면적 계산 (경계 설정 포함)"""
    pk_h = corrected[pk_idx]
    thr = pk_h * 0.05  # 5% threshold

    left = pk_idx
    while left > 0 and corrected[left] > thr:
        left -= 1
    right = pk_idx
    while right < len(corrected) - 1 and corrected[right] > thr:
        right += 1

    # 인접 피크와의 valley로 경계 제한
    sorted_all = np.sort(all_peaks)
    pk_pos = np.searchsorted(sorted_all, pk_idx)
    if pk_pos > 0:
        prev_pk = sorted_all[pk_pos - 1]
        valley = prev_pk + np.argmin(corrected[prev_pk:pk_idx])
        left = max(left, valley)
    if pk_pos < len(sorted_all) - 1:
        next_pk = sorted_all[pk_pos + 1]
        valley = pk_idx + np.argmin(corrected[pk_idx:next_pk])
        right = min(right, valley)

    if right <= left + 1:
        return 0.0, left, right

    t_sec = time[left:right + 1] * 60
    sig = corrected[left:right + 1]
    area = trapezoid(sig, t_sec)
    return area, left, right


def parse_sample_name(dirname):
    """샘플 디렉토리명에서 조건 정보 추출"""
    return dirname.replace('.D', '').strip()


def analyze_experiment(exp_dir):
    """하나의 실험 디렉토리 내 모든 .ch 파일 분석"""
    exp_name = exp_dir.name
    results = []

    ch_files = list(exp_dir.rglob('RID1A.ch'))
    if not ch_files:
        ch_files = list(exp_dir.rglob('*.ch'))

    for ch_file in sorted(ch_files):
        sample_dir = ch_file.parent.name
        sample_name = parse_sample_name(sample_dir)

        try:
            parser = ChemstationParser(str(ch_file))
            time, intensity = parser.read()

            # 베이스라인 보정
            baseline = rolling_min_baseline(intensity)
            corrected = np.maximum(intensity - baseline, 0)

            # 피크 검출
            peaks, props = detect_peaks_simple(time, corrected)

            # 주요 피크 정보
            peak_info = []
            for pk_idx in peaks:
                area, left, right = compute_peak_area(time, corrected, pk_idx, peaks)
                peak_info.append({
                    'rt': time[pk_idx],
                    'height': corrected[pk_idx],
                    'area': area,
                    'left': left,
                    'right': right,
                })

            # 면적순 정렬
            peak_info.sort(key=lambda x: x['area'], reverse=True)

            results.append({
                'sample': sample_name,
                'file': str(ch_file),
                'n_points': len(time),
                'time_range': (time[0], time[-1]),
                'n_peaks': len(peaks),
                'peaks': peak_info[:10],  # 상위 10개
                'time': time,
                'intensity': intensity,
                'corrected': corrected,
                'baseline': baseline,
            })

        except Exception as e:
            results.append({
                'sample': sample_name,
                'file': str(ch_file),
                'error': str(e),
            })

    return exp_name, results


def print_experiment_summary(exp_name, results):
    """실험 결과 요약 출력"""
    print(f"\n{'=' * 80}")
    print(f"  실험: {exp_name}")
    print(f"{'=' * 80}")

    ok_results = [r for r in results if 'error' not in r]
    err_results = [r for r in results if 'error' in r]

    print(f"  총 파일: {len(results)}  |  성공: {len(ok_results)}  |  에러: {len(err_results)}")

    if err_results:
        for r in err_results[:3]:
            print(f"    [에러] {r['sample']}: {r['error']}")

    if not ok_results:
        return

    # 피크 테이블
    print(f"\n  {'샘플':<45s} {'피크수':>5s}  {'RT1(min)':>8s}  {'높이1':>10s}  {'면적1':>12s}")
    print("  " + "-" * 90)

    for r in ok_results:
        n_pk = r['n_peaks']
        if n_pk > 0 and r['peaks']:
            p1 = r['peaks'][0]
            print(f"  {r['sample']:<45s} {n_pk:>5d}  {p1['rt']:>8.2f}  {p1['height']:>10.1f}  {p1['area']:>12.1f}")
        else:
            print(f"  {r['sample']:<45s} {n_pk:>5d}  {'N/A':>8s}  {'N/A':>10s}  {'N/A':>12s}")


def plot_experiment_overview(exp_name, results, output_dir):
    """실험별 크로마토그램 오버레이 플롯"""
    ok_results = [r for r in results if 'error' not in r and r.get('corrected') is not None]
    if not ok_results:
        return

    n = len(ok_results)
    n_cols = min(4, n)
    n_rows = min(4, (n + n_cols - 1) // n_cols)  # 최대 4x4
    n_show = n_rows * n_cols

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(4 * n_cols, 3 * n_rows))
    if n_rows == 1 and n_cols == 1:
        axes = np.array([[axes]])
    elif n_rows == 1:
        axes = axes[np.newaxis, :]
    elif n_cols == 1:
        axes = axes[:, np.newaxis]

    for idx in range(n_show):
        ax = axes[idx // n_cols, idx % n_cols]
        if idx < len(ok_results):
            r = ok_results[idx]
            ax.plot(r['time'], r['corrected'], 'b-', lw=0.5)

            # 피크 마커
            for p in r['peaks'][:5]:
                pk_t = p['rt']
                pk_h = p['height']
                ax.plot(pk_t, pk_h, 'rv', markersize=4)

            short_name = r['sample']
            if len(short_name) > 35:
                short_name = short_name[:32] + '...'
            ax.set_title(short_name, fontsize=7)
            ax.tick_params(labelsize=6)
        else:
            ax.set_visible(False)

    fig.suptitle(f'{exp_name}', fontsize=11, fontweight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.95])

    safe_name = re.sub(r'[^\w\-_]', '_', exp_name)
    outpath = output_dir / f'{safe_name}_overview.png'
    fig.savefig(str(outpath), dpi=120)
    plt.close(fig)
    print(f"  플롯 저장: {outpath.name}")


def plot_overlay(exp_name, results, output_dir):
    """실험 내 모든 크로마토그램 오버레이"""
    ok_results = [r for r in results if 'error' not in r and r.get('corrected') is not None]
    if not ok_results or len(ok_results) < 2:
        return

    fig, ax = plt.subplots(figsize=(12, 5))
    cmap = plt.cm.tab20(np.linspace(0, 1, min(len(ok_results), 20)))

    for idx, r in enumerate(ok_results[:20]):
        color = cmap[idx % 20]
        short = r['sample']
        if len(short) > 30:
            short = short[:27] + '...'
        ax.plot(r['time'], r['corrected'], color=color, lw=0.7, label=short, alpha=0.8)

    ax.set_xlabel('시간 (min)')
    ax.set_ylabel('보정 신호 (RID)')
    ax.set_title(f'{exp_name} - 크로마토그램 오버레이')
    ax.legend(fontsize=5, ncol=2, loc='upper right')
    ax.grid(True, alpha=0.2)
    plt.tight_layout()

    safe_name = re.sub(r'[^\w\-_]', '_', exp_name)
    outpath = output_dir / f'{safe_name}_overlay.png'
    fig.savefig(str(outpath), dpi=120)
    plt.close(fig)
    print(f"  오버레이 저장: {outpath.name}")


# ============================================================
#  메인
# ============================================================
if __name__ == '__main__':
    print("=" * 80)
    print("  Xul 5P Production Pretest - 전체 데이터 분석")
    print(f"  데이터 경로: {BASE_DIR}")
    print("=" * 80)

    # 실험 디렉토리 찾기
    exp_dirs = sorted([d for d in BASE_DIR.iterdir() if d.is_dir()])
    print(f"\n발견된 실험 세트: {len(exp_dirs)}개")
    for d in exp_dirs:
        n_ch = len(list(d.rglob('RID1A.ch')))
        print(f"  - {d.name} ({n_ch} runs)")

    # 전체 분석
    all_experiments = {}
    for exp_dir in exp_dirs:
        exp_name, results = analyze_experiment(exp_dir)
        all_experiments[exp_name] = results
        print_experiment_summary(exp_name, results)
        plot_experiment_overview(exp_name, results, OUTPUT_DIR)
        plot_overlay(exp_name, results, OUTPUT_DIR)

    # ============================================================
    #  전체 통계 요약
    # ============================================================
    print("\n" + "=" * 80)
    print("  전체 요약 통계")
    print("=" * 80)

    total_files = 0
    total_ok = 0
    total_peaks = 0

    for exp_name, results in all_experiments.items():
        ok = [r for r in results if 'error' not in r]
        total_files += len(results)
        total_ok += len(ok)
        peaks = sum(r['n_peaks'] for r in ok)
        total_peaks += peaks
        print(f"  {exp_name:<50s}  파일:{len(results):>3d}  성공:{len(ok):>3d}  총피크:{peaks:>4d}")

    print(f"\n  전체: {total_files}개 파일  |  성공: {total_ok}개  |  총 검출 피크: {total_peaks}개")
    print(f"\n  결과 저장 위치: {OUTPUT_DIR}")
    print("  완료!")
