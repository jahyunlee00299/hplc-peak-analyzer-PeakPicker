"""
Full LC data batch analysis script
==================================
Directly reads the .ch files in every .D folder under C:\\Chem32\\1\\DATA\\,
performs peak detection + baseline correction, and outputs the results to Excel

Usage:
    conda activate PeakPicker
    python batch_analyze_all.py                    # analyze everything
    python batch_analyze_all.py --folder "ProjectA" # a single folder only
    python batch_analyze_all.py --test              # test mode (3 files per folder only)
"""

import sys
import time
import traceback
import argparse
from pathlib import Path
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

import numpy as np
import pandas as pd
from scipy import signal
from scipy.integrate import trapezoid

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from chemstation_parser import ChemstationParser
from hybrid_baseline import HybridBaselineCorrector


# ---------------------------------------------------------------------------
# Core analysis function (can be called in worker processes)
# ---------------------------------------------------------------------------

def analyze_single_d_folder(d_folder_path: str, channel: str = "auto") -> dict:
    """
    Analyze a single .D folder

    Args:
        d_folder_path: path to the .D folder
        channel: channel filename. If "auto", automatically searches RID1A.ch -> vwd1A.ch in order

    Returns:
        Analysis result dictionary
    """
    d_folder = Path(d_folder_path)
    sample_name = d_folder.name.replace('.D', '')

    # Auto-detect the channel
    if channel == "auto":
        for candidate in ['RID1A.ch', 'vwd1A.ch', 'DAD1A.ch']:
            if (d_folder / candidate).exists():
                channel = candidate
                break
        else:
            # Look for any .ch file
            ch_files = list(d_folder.glob('*.ch'))
            if ch_files:
                channel = ch_files[0].name
            else:
                return {
                    'sample_name': sample_name, 'd_folder': str(d_folder),
                    'channel': 'none', 'status': 'error',
                    'error': 'No .ch file found', 'peaks': [],
                }

    ch_file = d_folder / channel

    result = {
        'sample_name': sample_name,
        'd_folder': str(d_folder),
        'channel': channel,
        'status': 'error',
        'error': None,
        'peaks': [],
    }

    if not ch_file.exists():
        result['error'] = f'{channel} not found'
        return result

    try:
        # 1. Parse the .ch file
        parser = ChemstationParser(str(ch_file))
        time_arr, intensity = parser.read()
        metadata = parser.get_metadata()

        if len(time_arr) < 50:
            result['error'] = 'Too few data points'
            return result

        result['time_range'] = f"{time_arr[0]:.2f}-{time_arr[-1]:.2f}"
        result['num_points'] = len(time_arr)
        result['time_source'] = metadata.get('time_source', 'unknown')

        # 2. Baseline correction
        corrector = HybridBaselineCorrector(time_arr, intensity)
        baseline, bl_params = corrector.optimize_baseline_with_linear_peaks()
        corrected = intensity - baseline
        corrected = np.maximum(corrected, 0)

        # 3. Noise estimation
        noise_level = _estimate_noise(corrected)

        # 4. Peak detection (2-pass adaptive)
        peaks_detected, peak_data = _detect_peaks(time_arr, corrected, noise_level)

        result['status'] = 'ok'
        result['num_peaks'] = len(peak_data)
        result['total_area'] = sum(p['area'] for p in peak_data)
        result['peaks'] = peak_data
        result['baseline_method'] = bl_params.get('method', 'unknown')

    except Exception as e:
        result['error'] = f'{type(e).__name__}: {e}'

    return result


def _estimate_noise(intensity: np.ndarray) -> float:
    """Estimate the noise level"""
    noise_region = np.percentile(intensity, 25)
    threshold = max(noise_region * 1.5, np.percentile(intensity, 30))
    quiet_mask = intensity < threshold

    if np.any(quiet_mask) and np.sum(quiet_mask) > 10:
        noise_std = np.std(intensity[quiet_mask])
    else:
        low_pct = np.percentile(intensity, 10)
        if low_pct > 0:
            noise_std = np.std(intensity[intensity < low_pct])
        else:
            noise_std = np.std(intensity[intensity < np.percentile(intensity, 20)])
        if noise_std == 0 or np.isnan(noise_std):
            noise_std = np.std(intensity) * 0.01

    result = max(noise_std, np.percentile(intensity, 5) * 0.01, 1.0)
    if np.isnan(result) or result <= 0:
        result = max(np.std(intensity) * 0.01, 1.0)
    return result


def _detect_peaks(time_arr: np.ndarray, intensity: np.ndarray, noise_level: float) -> tuple:
    """2-pass adaptive peak detection"""
    signal_range = np.ptp(intensity)

    # Pass 1: major peaks
    major_prom = max(signal_range * 0.005, noise_level * 3)
    major_peaks, major_props = signal.find_peaks(
        intensity, prominence=major_prom, height=noise_level * 3,
        width=3, distance=20
    )

    # Pass 2: minor peaks
    minor_prom = noise_level * 2
    minor_peaks, minor_props = signal.find_peaks(
        intensity, prominence=minor_prom, height=noise_level * 2,
        width=2, distance=5
    )

    # Merge
    all_peaks = list(major_peaks)
    all_proms = list(major_props['prominences'])
    min_dist = 10

    for i, mp in enumerate(minor_peaks):
        if all(abs(mp - ep) >= min_dist for ep in major_peaks):
            all_peaks.append(mp)
            all_proms.append(minor_props['prominences'][i])

    sort_idx = np.argsort(all_peaks)
    peaks = np.array(all_peaks)[sort_idx]
    proms = np.array(all_proms)[sort_idx]

    # Compute peak data
    dt = np.mean(np.diff(time_arr))
    max_width_samples = int(2.0 / dt) if dt > 0 else 2000

    peak_data = []
    for i, pidx in enumerate(peaks):
        peak_height = intensity[pidx]
        threshold = peak_height * 0.01

        # Left boundary
        left = pidx
        while left > 0 and intensity[left] > threshold:
            left -= 1

        # Right boundary
        right = pidx
        while right < len(intensity) - 1 and intensity[right] > threshold:
            right += 1

        # Valley constraints
        if i < len(peaks) - 1:
            valley_region = intensity[pidx:peaks[i + 1]]
            if len(valley_region) > 0:
                right = min(right, pidx + np.argmin(valley_region))
        if i > 0:
            valley_region = intensity[peaks[i - 1]:pidx]
            if len(valley_region) > 0:
                left = max(left, peaks[i - 1] + np.argmin(valley_region))

        # Width constraint
        if right - left > max_width_samples:
            half = max_width_samples // 2
            left = max(0, pidx - half)
            right = min(len(intensity) - 1, pidx + half)

        left = max(0, left)
        right = min(len(intensity) - 1, right)

        # Area (seconds)
        peak_time = time_arr[left:right + 1]
        peak_int = intensity[left:right + 1]
        area = trapezoid(peak_int, peak_time * 60) if len(peak_time) > 1 else 0

        snr = peak_height / noise_level if noise_level > 0 else float('inf')

        peak_data.append({
            'peak_number': i + 1,
            'retention_time': round(float(time_arr[pidx]), 3),
            'height': round(float(peak_height), 2),
            'area': round(float(area), 2),
            'width_min': round(float(time_arr[right] - time_arr[left]), 3),
            'start_time': round(float(time_arr[left]), 3),
            'end_time': round(float(time_arr[right]), 3),
            'snr': round(float(snr), 1),
        })

    return peaks, peak_data


# ---------------------------------------------------------------------------
# Batch orchestrator
# ---------------------------------------------------------------------------

def find_all_d_folders(base_dir: str, folder_filter: str = None) -> dict:
    """
    Organize every .D folder under base_dir by project folder

    Returns:
        {project_name: [d_folder_path, ...], ...}
    """
    base = Path(base_dir)
    projects = {}

    for item in sorted(base.iterdir()):
        if not item.is_dir():
            continue
        name = item.name
        # Apply the filter
        if folder_filter and folder_filter.lower() not in name.lower():
            continue

        d_folders = sorted([
            str(d) for d in item.rglob('*.D')
            if d.is_dir()
        ])

        if d_folders:
            projects[name] = d_folders

    # Also check for .D folders directly under base_dir
    direct_d = sorted([
        str(d) for d in base.glob('*.D')
        if d.is_dir()
    ])
    if direct_d:
        projects['_root'] = direct_d

    return projects


def batch_analyze(
    base_dir: str,
    output_dir: str,
    folder_filter: str = None,
    max_per_folder: int = None,
    channels: list = None,
    n_workers: int = None,
):
    """
    Run the full batch analysis

    Args:
        base_dir: C:\\Chem32\\1\\DATA
        output_dir: folder to save results to
        folder_filter: process only a specific folder
        max_per_folder: max files per folder (for testing)
        channels: list of channels to analyze
        n_workers: number of parallel workers
    """
    if channels is None:
        channels = ['auto']
    if n_workers is None:
        n_workers = max(1, multiprocessing.cpu_count() - 1)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # 1. Discover .D folders
    print("=" * 80)
    print("  LC DATA BATCH ANALYSIS")
    print(f"  Base: {base_dir}")
    print(f"  Output: {output_dir}")
    print(f"  Workers: {n_workers}")
    print("=" * 80)

    projects = find_all_d_folders(base_dir, folder_filter)
    total_files = sum(len(v) for v in projects.values())

    print(f"\nProjects: {len(projects)}, total .D files: {total_files}")
    for pname, dlist in projects.items():
        count = len(dlist)
        if max_per_folder:
            count = min(count, max_per_folder)
        print(f"  {pname}: {count} files")

    # 2. Analyze per project
    all_results = []
    master_summary = []
    t_start = time.time()
    processed = 0

    for proj_name, d_folders in projects.items():
        if max_per_folder:
            d_folders = d_folders[:max_per_folder]

        print(f"\n{'=' * 60}")
        print(f"  PROJECT: {proj_name} ({len(d_folders)} files)")
        print(f"{'=' * 60}")

        proj_results = []
        proj_out = out / proj_name
        proj_out.mkdir(parents=True, exist_ok=True)

        for channel in channels:
            ch_tag = channel.replace('.ch', '')

            # Parallel analysis
            tasks = [(df, channel) for df in d_folders]

            if n_workers > 1 and len(tasks) > 4:
                with ProcessPoolExecutor(max_workers=n_workers) as executor:
                    futures = {
                        executor.submit(analyze_single_d_folder, df, ch): df
                        for df, ch in tasks
                    }
                    for future in as_completed(futures):
                        r = future.result()
                        proj_results.append(r)
                        processed += 1
                        _print_progress(r, processed, total_files, t_start)
            else:
                for df, ch in tasks:
                    r = analyze_single_d_folder(df, ch)
                    proj_results.append(r)
                    processed += 1
                    _print_progress(r, processed, total_files, t_start)

            # Save Excel per channel
            _export_project_results(proj_results, proj_out, proj_name, ch_tag)

        all_results.extend(proj_results)

        # Project summary
        ok_count = sum(1 for r in proj_results if r['status'] == 'ok')
        err_count = sum(1 for r in proj_results if r['status'] == 'error')
        total_peaks = sum(r.get('num_peaks', 0) for r in proj_results)

        master_summary.append({
            'Project': proj_name,
            'Total_Files': len(d_folders),
            'Success': ok_count,
            'Errors': err_count,
            'Total_Peaks': total_peaks,
        })

        print(f"\n  {proj_name}: {ok_count}/{len(d_folders)} succeeded, {total_peaks} peaks")

    # 3. Master summary
    elapsed = time.time() - t_start
    _export_master_summary(all_results, master_summary, out, elapsed)

    print(f"\n{'=' * 80}")
    print("  All done!")
    print(f"  Processed: {processed} files in {elapsed:.0f}s ({elapsed/60:.1f}min)")
    print(f"  Results: {out}")
    print(f"{'=' * 80}")


def _print_progress(result: dict, done: int, total: int, t_start: float):
    """Print progress"""
    status = "OK" if result['status'] == 'ok' else f"ERR: {result.get('error', '?')}"
    n_peaks = result.get('num_peaks', 0)
    elapsed = time.time() - t_start
    rate = done / elapsed if elapsed > 0 else 0
    eta = (total - done) / rate if rate > 0 else 0

    print(f"  [{done}/{total}] {result['sample_name']}: {status}"
          f" ({n_peaks} peaks) "
          f"[{elapsed:.0f}s elapsed, ETA {eta:.0f}s]")


def _export_project_results(results: list, proj_out: Path, proj_name: str, ch_tag: str):
    """Save the per-project results to Excel"""
    ok_results = [r for r in results if r['status'] == 'ok']
    if not ok_results:
        return

    output_file = proj_out / f"{proj_name}_{ch_tag}_peaks.xlsx"

    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        # Sheet 1: Summary
        summary_rows = []
        for r in results:
            row = {
                'Sample': r['sample_name'],
                'Status': r['status'],
                'Num_Peaks': r.get('num_peaks', 0),
                'Total_Area': r.get('total_area', 0),
                'Time_Range': r.get('time_range', ''),
                'Time_Source': r.get('time_source', ''),
                'Error': r.get('error', ''),
            }
            summary_rows.append(row)
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name='Summary', index=False)

        # Sheet 2: All Peaks
        all_peaks = []
        for r in ok_results:
            for p in r['peaks']:
                row = {'Sample': r['sample_name']}
                row.update(p)
                all_peaks.append(row)

        if all_peaks:
            df_peaks = pd.DataFrame(all_peaks)
            # % area per sample
            for sample in df_peaks['Sample'].unique():
                mask = df_peaks['Sample'] == sample
                sample_total = df_peaks.loc[mask, 'area'].sum()
                if sample_total > 0:
                    df_peaks.loc[mask, 'percent_area'] = (
                        df_peaks.loc[mask, 'area'] / sample_total * 100
                    ).round(2)
            df_peaks.to_excel(writer, sheet_name='All_Peaks', index=False)

            # Sheet 3: RT Pivot (Area)
            df_peaks['RT_rounded'] = df_peaks['retention_time'].round(1)
            pivot = df_peaks.pivot_table(
                index='Sample', columns='RT_rounded',
                values='area', aggfunc='sum'
            )
            # Sort columns by frequency then magnitude
            non_empty = pivot.notna().sum(axis=0)
            max_vals = pivot.max(axis=0).fillna(0)
            sort_df = pd.DataFrame({
                'rt': pivot.columns, 'count': non_empty, 'max': max_vals
            }).sort_values(['count', 'max'], ascending=[False, False])
            pivot = pivot[sort_df['rt'].tolist()].fillna('')
            pivot.columns = [f'RT_{rt}' for rt in pivot.columns]
            pivot.to_excel(writer, sheet_name='RT_Pivot_Area')

            # Sheet 4: RT Pivot (% Area)
            pivot_pct = df_peaks.pivot_table(
                index='Sample', columns='RT_rounded',
                values='percent_area', aggfunc='sum'
            )
            pivot_pct = pivot_pct[sort_df['rt'].tolist()].fillna('')
            pivot_pct.columns = [f'RT_{rt}' for rt in pivot_pct.columns]
            pivot_pct.to_excel(writer, sheet_name='RT_Pivot_Pct')

    print(f"    -> {output_file.name}")


def _export_master_summary(all_results: list, master_summary: list, out: Path, elapsed: float):
    """Save the master summary Excel"""
    master_file = out / "MASTER_SUMMARY.xlsx"

    with pd.ExcelWriter(master_file, engine='openpyxl') as writer:
        # Sheet 1: Project Summary
        df_master = pd.DataFrame(master_summary)
        # Totals row
        totals = {
            'Project': 'TOTAL',
            'Total_Files': df_master['Total_Files'].sum(),
            'Success': df_master['Success'].sum(),
            'Errors': df_master['Errors'].sum(),
            'Total_Peaks': df_master['Total_Peaks'].sum(),
        }
        df_master = pd.concat([df_master, pd.DataFrame([totals])], ignore_index=True)
        df_master.to_excel(writer, sheet_name='Project_Summary', index=False)

        # Sheet 2: Error Report
        errors = [
            {'Sample': r['sample_name'], 'Project': _get_project(r['d_folder']),
             'Error': r['error']}
            for r in all_results if r['status'] == 'error' and r['error']
        ]
        if errors:
            pd.DataFrame(errors).to_excel(writer, sheet_name='Errors', index=False)

        # Sheet 3: Analysis Info
        info = pd.DataFrame([{
            'Analysis_Date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'Total_Files': len(all_results),
            'Success': sum(1 for r in all_results if r['status'] == 'ok'),
            'Errors': sum(1 for r in all_results if r['status'] == 'error'),
            'Total_Peaks': sum(r.get('num_peaks', 0) for r in all_results),
            'Elapsed_Seconds': round(elapsed, 1),
            'Elapsed_Minutes': round(elapsed / 60, 1),
        }])
        info.to_excel(writer, sheet_name='Analysis_Info', index=False)

    print("\n  MASTER_SUMMARY.xlsx saved")


def _get_project(d_folder_path: str) -> str:
    """Extract the project name from a D folder path"""
    parts = Path(d_folder_path).parts
    # C:\Chem32\1\DATA\{project}\...\.D
    try:
        data_idx = [i for i, p in enumerate(parts) if p == 'DATA'][0]
        return parts[data_idx + 1] if data_idx + 1 < len(parts) else 'unknown'
    except (IndexError, ValueError):
        return 'unknown'


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Batch LC peak analysis for all Chem32 data'
    )
    parser.add_argument(
        '--base-dir',
        default=r'C:\Chem32\1\DATA',
        help='Base data directory (default: C:\\Chem32\\1\\DATA)'
    )
    parser.add_argument(
        '--output',
        default=r'C:\Chem32\1\DATA\analysis_results',
        help='Output directory for results'
    )
    parser.add_argument(
        '--folder',
        default=None,
        help='Filter by folder name (e.g., "ProjectA")'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Test mode: process max 3 files per folder'
    )
    parser.add_argument(
        '--channels',
        nargs='+',
        default=['auto'],
        help='Channel files to analyze (default: auto-detect)'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=None,
        help='Number of parallel workers (default: CPU count - 1)'
    )
    parser.add_argument(
        '--vwd',
        action='store_true',
        help='Also analyze VWD channel (vwd1A.ch)'
    )

    args = parser.parse_args()

    channels = list(args.channels)
    if args.vwd:
        channels.append('vwd1A.ch')

    batch_analyze(
        base_dir=args.base_dir,
        output_dir=args.output,
        folder_filter=args.folder,
        max_per_folder=3 if args.test else None,
        channels=channels,
        n_workers=args.workers,
    )


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[Interrupted] The user interrupted the process.")
        sys.exit(1)
    except Exception as e:
        print(f"\n[Error] {e}")
        traceback.print_exc()
        sys.exit(1)
