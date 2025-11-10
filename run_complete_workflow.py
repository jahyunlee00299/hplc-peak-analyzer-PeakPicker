"""
Complete HPLC Analysis Workflow
================================

자동 Export → 피크 분석 → 디컨볼루션을 한번에 실행하는 통합 스크립트

사용법:
    python run_complete_workflow.py

기능:
    1. Chemstation에서 CSV 자동 export (auto_export_keyboard_final.py)
    2. 베이스라인 보정 및 피크 검출
    3. 필요시 자동 피크 디컨볼루션
    4. Excel 리포트 생성

Author: PeakPicker Project
Date: 2025-11-10
"""

import os
import sys
from pathlib import Path
import subprocess
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


def run_auto_export():
    """
    Run auto export to generate CSV files from Chemstation.

    Returns:
        output_dir: Directory where CSV files were saved
    """
    print("\n" + "="*80)
    print("STEP 1: AUTO EXPORT FROM CHEMSTATION")
    print("="*80)

    # Import and run auto_export_keyboard_final
    import auto_export_keyboard_final

    # Get data directory from user
    base_dir = auto_export_keyboard_final.get_data_directory()

    if base_dir is None:
        print("\n[X] Export 취소됨")
        return None

    # Find .D folders
    print(f"\n'{base_dir}' 에서 .D 폴더 검색 중...")
    print("  (하위 폴더 포함 재귀적 검색)")
    d_folders = auto_export_keyboard_final.find_all_d_folders(base_dir, recursive=True)

    if not d_folders:
        print(f"\n[X] .D 폴더를 찾을 수 없습니다.")
        return None

    print(f"\n[OK] {len(d_folders)}개 .D 폴더 발견")

    # Set output directory
    default_output = os.path.join(os.getcwd(), "result")
    base_dir_name = Path(base_dir).name
    output_dir = os.path.join(default_output, base_dir_name)

    # Create csv subdirectory for CSV files
    csv_dir = os.path.join(output_dir, "csv")

    print(f"\n출력 경로: {csv_dir}")
    os.makedirs(csv_dir, exist_ok=True)

    # Confirm
    print("\n" + "="*80)
    confirm = input(f"\n{len(d_folders)}개 파일을 Export 하시겠습니까? (y/n): ").strip().lower()
    if confirm != 'y':
        print("\n[X] Export 취소됨")
        return None

    # Run export
    print("\n5초 후 시작...")
    import time
    for i in range(5, 0, -1):
        print(f"  {i}...")
        time.sleep(1)

    print("\n" + "="*80)
    print("EXPORT 시작")
    print("="*80)

    import pyautogui
    pyautogui.PAUSE = 0.2

    success_count = 0
    failed = []
    start_time = time.time()

    for i, d_folder in enumerate(d_folders, 1):
        folder_name = Path(d_folder).name.replace('.D', '')
        output_csv = os.path.join(csv_dir, f"{folder_name}.csv")

        # Skip if already exists
        if os.path.exists(output_csv):
            print(f"\n[{i}/{len(d_folders)}] 건너뜀: {folder_name} (이미 존재)")
            success_count += 1
            continue

        print(f"\n[{i}/{len(d_folders)}] {folder_name}")

        # Export
        if auto_export_keyboard_final.export_one_file(d_folder, output_csv):
            success_count += 1
        else:
            failed.append(folder_name)

        # Progress
        if i > 0:
            elapsed = time.time() - start_time
            avg_time = elapsed / i
            remaining = (len(d_folders) - i) * avg_time
            print(f"\n  진행: {success_count}/{i} 성공, 남은 시간: {remaining/60:.1f}분")

    # Summary
    total_time = time.time() - start_time
    print("\n" + "="*80)
    print("EXPORT 완료")
    print("="*80)
    print(f"\n  성공: {success_count}/{len(d_folders)} 파일")
    print(f"  소요 시간: {total_time/60:.1f}분")
    print(f"  출력 디렉토리: {csv_dir}")

    if failed:
        print(f"\n  실패: {len(failed)}개")
        for name in failed[:5]:
            print(f"    - {name}")
        if len(failed) > 5:
            print(f"    ... 외 {len(failed)-5}개")

    if success_count == 0:
        print("\n[X] Export된 파일이 없습니다.")
        return None

    # Open export folder
    print("\nExport 폴더를 여는 중...")
    try:
        if sys.platform == 'win32':
            os.startfile(str(output_dir))
        elif sys.platform == 'darwin':  # macOS
            subprocess.run(['open', str(output_dir)])
        else:  # linux
            subprocess.run(['xdg-open', str(output_dir)])
    except Exception as e:
        print(f"폴더 열기 실패: {e}")

    return output_dir


def run_analysis(data_dir, enable_deconvolution=True, asymmetry_threshold=1.2):
    """
    Run HPLC analysis on CSV files.

    Args:
        data_dir: Directory containing CSV files
        enable_deconvolution: Enable peak deconvolution
        asymmetry_threshold: Asymmetry threshold for deconvolution

    Returns:
        True if successful, False otherwise
    """
    print("\n" + "="*80)
    print("STEP 2: PEAK ANALYSIS & DECONVOLUTION")
    print("="*80)

    if not data_dir or not os.path.exists(data_dir):
        print(f"\n[X] 데이터 디렉토리가 없습니다: {data_dir}")
        return False

    # Check for csv subdirectory first, fall back to main directory
    csv_subdir = Path(data_dir) / "csv"
    if csv_subdir.exists():
        csv_search_dir = csv_subdir
    else:
        csv_search_dir = Path(data_dir)

    # Count CSV files
    csv_files = list(csv_search_dir.glob("*.csv")) + list(csv_search_dir.glob("*.CSV"))

    if not csv_files:
        print(f"\n[X] CSV 파일이 없습니다: {csv_search_dir}")
        return False

    print(f"\n[OK] {len(csv_files)}개 CSV 파일 발견")
    print(f"   디렉토리: {csv_search_dir}")

    # Analysis settings
    print(f"\n분석 설정:")
    print(f"  - 베이스라인 보정: 활성화")
    print(f"  - 피크 디컨볼루션: {'활성화' if enable_deconvolution else '비활성화'}")
    if enable_deconvolution:
        print(f"  - 비대칭도 임계값: {asymmetry_threshold}")

    # Confirm
    confirm = input(f"\n분석을 시작하시겠습니까? (y/n): ").strip().lower()
    if confirm != 'y':
        print("\n[X] 분석 취소됨")
        return False

    print("\n" + "="*80)
    print("분석 시작")
    print("="*80)

    # Import analyzer
    from hplc_analyzer_enhanced import EnhancedHPLCAnalyzer

    # Create output directory for exported Excel files
    output_dir = Path(data_dir) / "exported"

    # Create analyzer (use csv_search_dir for reading CSV files)
    analyzer = EnhancedHPLCAnalyzer(
        data_directory=str(csv_search_dir),
        output_directory=str(output_dir),
        use_hybrid_baseline=True,
        enable_deconvolution=enable_deconvolution,
        deconvolution_asymmetry_threshold=asymmetry_threshold
    )

    # Run analysis
    results = analyzer.batch_analyze(file_pattern="*.csv")

    # Summary
    successful = sum(1 for r in results if 'error' not in r)

    print("\n" + "="*80)
    print("분석 완료")
    print("="*80)
    print(f"\n  성공: {successful}/{len(results)} 파일")
    print(f"  결과 저장: {output_dir}")

    # Deconvolution statistics
    if enable_deconvolution:
        total_deconvolved = 0
        total_components = 0

        for r in results:
            if 'error' not in r and 'deconvolution_results' in r:
                for dr in r['deconvolution_results']:
                    if dr and dr.success and dr.n_components > 1:
                        total_deconvolved += 1
                        total_components += dr.n_components

        if total_deconvolved > 0:
            print(f"\n  디컨볼루션 통계:")
            print(f"    - 분리된 피크: {total_deconvolved}개")
            print(f"    - 총 컴포넌트: {total_components}개")

    return successful > 0


def run_visualization(data_dir):
    """
    Create visualizations and summaries for analysis results.

    Args:
        data_dir: Directory containing CSV and analysis results

    Returns:
        True if successful, False otherwise
    """
    print("\n" + "="*80)
    print("STEP 3: VISUALIZATION & SUMMARY")
    print("="*80)

    exported_dir = Path(data_dir) / "exported"

    if not exported_dir.exists():
        print(f"\n[X] exported 디렉토리가 없습니다: {exported_dir}")
        return False

    # Find Excel files
    excel_files = sorted(list(exported_dir.glob("*_peaks.xlsx")))

    if not excel_files:
        print(f"\n[X] 분석 결과 파일이 없습니다: {exported_dir}")
        return False

    print(f"\n[OK] {len(excel_files)}개 분석 파일 발견")

    # Create output folders
    baseline_plots_dir = Path(data_dir) / "baseline_plots"
    deconv_plots_dir = Path(data_dir) / "deconvolution_plots"
    baseline_plots_dir.mkdir(exist_ok=True)
    deconv_plots_dir.mkdir(exist_ok=True)

    # Import visualization tools
    sys.path.insert(0, str(Path(__file__).parent / 'src'))
    from peak_models import gaussian
    from hybrid_baseline import HybridBaselineCorrector

    # Track statistics
    viz_count = 0
    baseline_viz_count = 0
    stats = []
    baseline_stats = []

    # Check for csv subdirectory
    csv_subdir = Path(data_dir) / "csv"
    csv_search_dir = csv_subdir if csv_subdir.exists() else Path(data_dir)

    # Process each file for baseline visualization
    print("\n베이스라인 플롯 생성 중...")
    for excel_file in excel_files:
        sample_name = excel_file.stem.replace('_peaks', '')
        csv_file = csv_search_dir / f"{sample_name}.csv"

        if not csv_file.exists():
            continue

        try:
            # Load chromatogram
            df_csv = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
            time = df_csv[0].values
            intensity = df_csv[1].values

            # Calculate baseline with flat peaks
            corrector = HybridBaselineCorrector(time, intensity)
            baseline, params = corrector.optimize_baseline_with_linear_peaks()
            corrected = intensity - baseline
            corrected = np.maximum(corrected, 0)

            # Store baseline statistics
            method = params.get('method', 'robust_fit_with_flat_peaks')
            baseline_area = np.trapz(baseline, time)
            signal_area = np.trapz(intensity, time)
            baseline_ratio = baseline_area / signal_area if signal_area > 0 else 0

            baseline_stats.append({
                'Sample': sample_name,
                'Method': method,
                'Baseline_Area': baseline_area,
                'Total_Signal_Area': signal_area,
                'Baseline_Ratio_%': baseline_ratio * 100,
                'Max_Intensity': intensity.max(),
                'Max_Baseline': baseline.max()
            })

            # Create baseline plot
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8))

            # Plot 1: Original + Baseline
            ax1.plot(time, intensity, 'b-', linewidth=1.5, label='Original Signal', alpha=0.7)
            ax1.plot(time, baseline, 'r-', linewidth=2, label='Baseline', alpha=0.8)
            ax1.fill_between(time, baseline, intensity, alpha=0.2, color='yellow', label='Area to Remove')

            ax1.set_xlabel('Retention Time (min)', fontsize=12)
            ax1.set_ylabel('Intensity', fontsize=12)
            ax1.set_title(f'{sample_name} - Baseline Correction', fontsize=14, fontweight='bold')
            ax1.legend(fontsize=10)
            ax1.grid(True, alpha=0.3)

            # Add method info
            info_text = f'Method: {method}\nBaseline Ratio: {baseline_ratio*100:.2f}%'
            ax1.text(0.02, 0.98, info_text, transform=ax1.transAxes,
                    fontsize=10, verticalalignment='top',
                    bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

            # Plot 2: Corrected Signal
            ax2.plot(time, corrected, 'g-', linewidth=1.5, label='Corrected Signal')
            ax2.axhline(y=0, color='k', linestyle='--', alpha=0.3)

            ax2.set_xlabel('Retention Time (min)', fontsize=12)
            ax2.set_ylabel('Intensity', fontsize=12)
            ax2.set_title(f'{sample_name} - After Baseline Correction', fontsize=14, fontweight='bold')
            ax2.legend(fontsize=10)
            ax2.grid(True, alpha=0.3)

            plt.tight_layout()
            output_file = baseline_plots_dir / f"{sample_name}_baseline.png"
            plt.savefig(output_file, dpi=150, bbox_inches='tight')
            plt.close()

            baseline_viz_count += 1

        except Exception as e:
            print(f"  Warning: {sample_name} 베이스라인 시각화 실패: {e}")
            continue

    print(f"  베이스라인 플롯: {baseline_viz_count}개 생성")

    # Process each file for deconvolution visualization
    print("\n디컨볼루션 플롯 생성 중...")
    for excel_file in excel_files:
        sample_name = excel_file.stem.replace('_peaks', '')
        csv_file = csv_search_dir / f"{sample_name}.csv"

        if not csv_file.exists():
            continue

        # Load analysis results
        try:
            df_peaks = pd.read_excel(excel_file, sheet_name='Peaks')
            try:
                df_deconv = pd.read_excel(excel_file, sheet_name='Deconvolved_Peaks')
                has_deconv = True
            except:
                df_deconv = None
                has_deconv = False

            # Collect statistics
            n_peaks = len(df_peaks)
            n_deconvolved = 0
            n_components = 0

            if has_deconv and df_deconv is not None:
                grouped = df_deconv.groupby('Original_Peak_Number')
                n_deconvolved = sum(1 for _, g in grouped if len(g) > 1)
                n_components = len(df_deconv)

            stats.append({
                'sample': sample_name,
                'n_peaks': n_peaks,
                'n_deconvolved': n_deconvolved,
                'n_components': n_components
            })

            # Create visualization only if peaks were deconvolved
            if n_deconvolved > 0:
                # Load chromatogram
                df_csv = pd.read_csv(csv_file, header=None, sep='\t', encoding='utf-16-le')
                time = df_csv[0].values
                intensity = df_csv[1].values

                # Create figure
                fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))

                # Plot 1: Full chromatogram
                ax1.plot(time, intensity, 'b-', linewidth=1.5, label='Chromatogram', alpha=0.7)
                for idx, row in df_peaks.iterrows():
                    rt = row['retention_time']
                    height = row['height']
                    ax1.plot(rt, height, 'ro', markersize=8, alpha=0.7)
                    ax1.text(rt, height * 1.1, f"{idx+1}", ha='center', fontsize=9)

                ax1.set_xlabel('Retention Time (min)', fontsize=12)
                ax1.set_ylabel('Intensity', fontsize=12)
                ax1.set_title(f'{sample_name} - Peak Detection', fontsize=14, fontweight='bold')
                ax1.legend(fontsize=10)
                ax1.grid(True, alpha=0.3)

                # Plot 2: Deconvolved peaks
                ax2.plot(time, intensity, 'gray', linewidth=1.5, label='Original', alpha=0.5)

                colors = plt.cm.tab10(np.linspace(0, 1, 10))
                grouped = df_deconv.groupby('Original_Peak_Number')

                for peak_num, group in grouped:
                    if len(group) > 1:
                        for idx, row in group.iterrows():
                            rt = row['Component_RT']
                            amp = row['Component_Height']
                            sigma = row['Sigma']

                            t_range = np.linspace(rt - 3*sigma, rt + 3*sigma, 100)
                            gaussian_curve = gaussian(t_range, amp, rt, sigma)

                            color = colors[int(peak_num - 1) % 10]
                            label = f"Peak {int(peak_num)}.{int(row['Component_Number'])}"
                            if row['Is_Shoulder']:
                                label += " (shoulder)"

                            ax2.plot(t_range, gaussian_curve, '--', color=color,
                                    linewidth=2, alpha=0.8, label=label)
                            ax2.plot(rt, amp, 'o', color=color, markersize=8)

                ax2.set_xlabel('Retention Time (min)', fontsize=12)
                ax2.set_ylabel('Intensity', fontsize=12)
                ax2.set_title(f'{sample_name} - Deconvolved Components', fontsize=14, fontweight='bold')
                ax2.legend(fontsize=9, ncol=2)
                ax2.grid(True, alpha=0.3)

                plt.tight_layout()
                output_file = deconv_plots_dir / f"{sample_name}_deconvolution.png"
                plt.savefig(output_file, dpi=150, bbox_inches='tight')
                plt.close()

                viz_count += 1

        except Exception as e:
            print(f"  Warning: {sample_name} 디컨볼루션 시각화 실패: {e}")
            continue

    print(f"  디컨볼루션 플롯: {viz_count}개 생성")

    # Create deconvolution summary plot
    if stats:
        df_stats = pd.DataFrame(stats)
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

        # Plot 1: Peak detection statistics
        samples_to_show = df_stats.head(10)
        x_pos = np.arange(len(samples_to_show))

        ax1.bar(x_pos, samples_to_show['n_peaks'], alpha=0.7, color='blue', label='Total Peaks')
        ax1.bar(x_pos, samples_to_show['n_deconvolved'], alpha=0.7, color='red', label='Deconvolved')

        ax1.set_xlabel('Sample', fontsize=12)
        ax1.set_ylabel('Number of Peaks', fontsize=12)
        ax1.set_title('Peak Detection Statistics', fontsize=14, fontweight='bold')
        ax1.set_xticks(x_pos)
        ax1.set_xticklabels(samples_to_show['sample'], rotation=45, ha='right', fontsize=8)
        ax1.legend(fontsize=10)
        ax1.grid(True, alpha=0.3, axis='y')

        # Plot 2: Overall summary
        total_peaks = df_stats['n_peaks'].sum()
        total_deconvolved = df_stats['n_deconvolved'].sum()
        total_components = df_stats['n_components'].sum()

        categories = ['Total\nPeaks', 'Deconvolved\nPeaks', 'Total\nComponents']
        values = [total_peaks, total_deconvolved, total_components]
        colors_bar = ['blue', 'red', 'green']

        ax2.bar(categories, values, color=colors_bar, alpha=0.7)
        for i, v in enumerate(values):
            ax2.text(i, v, str(v), ha='center', va='bottom', fontweight='bold', fontsize=12)

        ax2.set_ylabel('Count', fontsize=12)
        ax2.set_title('Overall Deconvolution Summary', fontsize=14, fontweight='bold')
        ax2.grid(True, alpha=0.3, axis='y')

        plt.tight_layout()
        summary_file = deconv_plots_dir / "deconvolution_summary.png"
        plt.savefig(summary_file, dpi=150, bbox_inches='tight')
        plt.close()

    # Create summary Excel files
    print("\n서머리 파일 생성 중...")

    # 1. Baseline Summary
    if baseline_stats:
        try:
            # Save Excel only
            baseline_summary_file = Path(data_dir) / "BASELINE_SUMMARY.xlsx"
            df_baseline = pd.DataFrame(baseline_stats)
            df_baseline.to_excel(baseline_summary_file, index=False, engine='openpyxl')
            print(f"  베이스라인 서머리: {baseline_summary_file.name}")

        except Exception as e:
            print(f"  베이스라인 서머리 생성 실패: {e}")

    # 2. RT-based Pivot Table Summary
    if stats:
        try:
            summary_excel = Path(data_dir) / "PEAK_SUMMARY.xlsx"

            with pd.ExcelWriter(summary_excel, engine='openpyxl') as writer:
                # Sheet 1: Sample Summary
                df_stats = pd.DataFrame(stats)
                df_stats.to_excel(writer, sheet_name='Sample_Summary', index=False)

                # Sheet 2: All Peaks Combined
                all_peaks = []
                for excel_file in excel_files:
                    sample_name = excel_file.stem.replace('_peaks', '')
                    try:
                        df_peaks = pd.read_excel(excel_file, sheet_name='Peaks')
                        df_peaks['sample_name'] = sample_name
                        all_peaks.append(df_peaks)
                    except:
                        pass

                if all_peaks:
                    df_all_peaks = pd.concat(all_peaks, ignore_index=True)
                    cols = ['sample_name'] + [c for c in df_all_peaks.columns if c != 'sample_name']
                    df_all_peaks = df_all_peaks[cols]
                    df_all_peaks.to_excel(writer, sheet_name='All_Peaks', index=False)

                    # Sheet 3: RT-based Pivot (Area only)
                    # Round RT to 1 decimal place, Samples as rows, RT as columns
                    df_all_peaks['RT_rounded'] = df_all_peaks['retention_time'].round(1)

                    pivot_area = df_all_peaks.pivot_table(
                        index='sample_name',
                        columns='RT_rounded',
                        values='area',
                        aggfunc='sum'
                    )

                    # Sort columns by: 1) number of non-NaN values (desc), 2) max value (desc)
                    non_empty_counts = pivot_area.notna().sum(axis=0)
                    max_values = pivot_area.max(axis=0).fillna(0)

                    sort_df = pd.DataFrame({
                        'rt': pivot_area.columns,
                        'count': non_empty_counts,
                        'max_val': max_values
                    })
                    sort_df = sort_df.sort_values(['count', 'max_val'], ascending=[False, False])

                    # Reorder columns based on sorted RT values
                    pivot_area = pivot_area[sort_df['rt'].tolist()]

                    # Fill NaN with empty string
                    pivot_area = pivot_area.fillna('')

                    # Rename columns to include RT_ prefix
                    pivot_area.columns = [f'RT_{rt}' for rt in pivot_area.columns]

                    pivot_area.to_excel(writer, sheet_name='RT_Pivot_Area')

                # Sheet 4: All Deconvolved Peaks Combined
                all_deconv = []
                for excel_file in excel_files:
                    sample_name = excel_file.stem.replace('_peaks', '')
                    try:
                        df_deconv = pd.read_excel(excel_file, sheet_name='Deconvolved_Peaks')
                        df_deconv['sample_name'] = sample_name
                        all_deconv.append(df_deconv)
                    except:
                        pass

                if all_deconv:
                    df_all_deconv = pd.concat(all_deconv, ignore_index=True)
                    cols = ['sample_name'] + [c for c in df_all_deconv.columns if c != 'sample_name']
                    df_all_deconv = df_all_deconv[cols]
                    df_all_deconv.to_excel(writer, sheet_name='All_Deconvolved_Peaks', index=False)

            print(f"  피크 서머리: {summary_excel.name}")

        except Exception as e:
            print(f"  피크 서머리 생성 실패: {e}")

    print("\n" + "="*80)
    print("시각화 및 서머리 완료")
    print("="*80)
    print(f"\n  베이스라인 플롯: {baseline_viz_count}개 → {baseline_plots_dir.name}/")
    print(f"  디컨볼루션 플롯: {viz_count}개 → {deconv_plots_dir.name}/")
    print(f"  베이스라인 서머리: BASELINE_SUMMARY.xlsx")
    print(f"  피크 서머리: PEAK_SUMMARY.xlsx (RT 기준 피벗 포함)")
    print(f"  저장 위치: {data_dir}")

    return True


def main():
    """Main workflow"""

    print("="*80)
    print("  COMPLETE HPLC ANALYSIS WORKFLOW")
    print("  Chemstation Auto Export → Peak Analysis → Deconvolution")
    print("="*80)

    parser = argparse.ArgumentParser(
        description='Complete HPLC workflow: Export → Analysis → Deconvolution'
    )
    parser.add_argument(
        '--skip-export',
        action='store_true',
        help='Skip export step (use existing CSV files)'
    )
    parser.add_argument(
        '--data-dir',
        help='Data directory (required if --skip-export is used)'
    )
    parser.add_argument(
        '--no-deconvolution',
        action='store_true',
        help='Disable peak deconvolution'
    )
    parser.add_argument(
        '--asymmetry-threshold',
        type=float,
        default=1.2,
        help='Asymmetry threshold for deconvolution (default: 1.2)'
    )

    args = parser.parse_args()

    # Step 1: Export (optional)
    if args.skip_export:
        if not args.data_dir:
            print("\n[X] --skip-export를 사용할 때는 --data-dir이 필요합니다.")
            return 1

        data_dir = args.data_dir
        print(f"\n[SKIP] Export 단계 건너뜀")
        print(f"       데이터 디렉토리: {data_dir}")
    else:
        data_dir = run_auto_export()

        if data_dir is None:
            print("\n프로그램을 종료합니다.")
            return 1

    # Step 2: Analysis
    success = run_analysis(
        data_dir,
        enable_deconvolution=not args.no_deconvolution,
        asymmetry_threshold=args.asymmetry_threshold
    )

    if not success:
        print("\n[!]  분석 중 오류가 발생했습니다.")
        return 1

    # Step 3: Visualization
    viz_success = run_visualization(data_dir)

    # Complete
    print("\n" + "="*80)
    print("  전체 워크플로우 완료!")
    print("="*80)
    csv_dir = Path(data_dir) / 'csv'
    if csv_dir.exists():
        print(f"\n[OK] CSV 파일: {csv_dir}/")
    else:
        print(f"\n[OK] CSV 파일: {data_dir}/")
    print(f"[OK] 개별 피크 파일: {Path(data_dir) / 'exported'}/")
    if viz_success:
        print(f"[OK] 베이스라인 플롯: {Path(data_dir) / 'baseline_plots'}/")
        print(f"[OK] 디컨볼루션 플롯: {Path(data_dir) / 'deconvolution_plots'}/")
        print(f"[OK] 서머리 파일: BASELINE_SUMMARY.xlsx, PEAK_SUMMARY.xlsx")
    print("\nExcel 파일과 시각화를 확인하여 결과를 검토하세요.")
    print("="*80)

    # Open result folder (main data directory)
    result_dir = Path(data_dir)
    if result_dir.exists():
        print("\n결과 폴더를 여는 중...")
        try:
            if sys.platform == 'win32':
                os.startfile(str(result_dir))
            elif sys.platform == 'darwin':  # macOS
                subprocess.run(['open', str(result_dir)])
            else:  # linux
                subprocess.run(['xdg-open', str(result_dir)])
        except Exception as e:
            print(f"폴더 열기 실패: {e}")

    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n[중단] 사용자가 중단했습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n[오류] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
