"""
HPLC 크로마토그램 시그널 통합 분석 스크립트
==========================================

Chemstation에서 export된 CSV 파일들을 읽어
시그널 데이터 통합 + 피크 분석 + 보고서를 생성합니다.

입력: result/<시퀀스명>/csv/ 폴더의 CSV 파일들
출력:
  result/<시퀀스명>/
  ├── signal_data_all.xlsx         # 전체 raw 시그널 통합 (샘플별 시트 + 오버레이)
  ├── batch_peak_summary.xlsx      # 전체 피크 요약 통합
  ├── chromatogram_overlay.png     # 전체 오버레이 플롯
  ├── <샘플명>_peaks.xlsx          # 개별 피크 정보
  └── <샘플명>_chromatogram.png    # 개별 크로마토그램 플롯

사용법:
    python analyze_d_folders.py [csv_폴더_경로]
"""

import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib
matplotlib.use('Agg')

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from src.solid.application.workflow import WorkflowBuilder
from src.solid.domain import AnalysisResult, ChromatogramData

# 기본 CSV 폴더 경로
DEFAULT_CSV_DIR = (
    PROJECT_ROOT / "result"
    / "230224_METHOD OPTIMIZE 2026-02-16 16-00-14"
    / "csv"
)


def read_chemstation_csv(csv_path: Path) -> pd.DataFrame:
    """Chemstation export CSV를 읽습니다 (UTF-16-LE, tab-separated)."""
    df = pd.read_csv(
        csv_path,
        sep='\t',
        encoding='utf-16-le',
        header=None,
        names=['Time (min)', 'Intensity (mAU)'],
    )
    return df


def main():
    # CSV 폴더 결정
    if len(sys.argv) > 1:
        csv_dir = Path(sys.argv[1])
    else:
        csv_dir = DEFAULT_CSV_DIR

    if not csv_dir.exists():
        print(f"[오류] CSV 폴더가 존재하지 않습니다: {csv_dir}")
        sys.exit(1)

    # CSV 파일 탐색
    csv_files = sorted(csv_dir.glob('*.csv'))
    if not csv_files:
        print(f"[오류] CSV 파일이 없습니다: {csv_dir}")
        sys.exit(1)

    # 출력 디렉토리 (csv 폴더의 상위)
    output_dir = csv_dir.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("  HPLC 크로마토그램 시그널 통합 분석")
    print("=" * 70)
    print(f"  CSV 폴더 : {csv_dir}")
    print(f"  출력 경로: {output_dir}")
    print(f"  CSV 파일 : {len(csv_files)}개")
    for f in csv_files:
        print(f"    - {f.name}")
    print("=" * 70)

    # 1) 워크플로우 구성 (baseline + peak detector만 사용, reader는 직접 처리)
    workflow = (
        WorkflowBuilder()
        .with_csv_reader()
        .with_default_baseline()
        .with_default_peak_detector()
        .with_excel_exporter(output_dir)
        .with_plot_exporter(output_dir)
        .build()
    )

    all_signal_data = {}  # {sample_name: DataFrame}
    all_results = []      # (sample_name, AnalysisResult)

    print()
    for i, csv_file in enumerate(csv_files, 1):
        sample_name = csv_file.stem
        print(f"[{i}/{len(csv_files)}] {sample_name}")

        # Raw 시그널 읽기
        try:
            df = read_chemstation_csv(csv_file)
            all_signal_data[sample_name] = df
            print(f"    시그널: {len(df)}pts, "
                  f"Time {df['Time (min)'].min():.2f}-{df['Time (min)'].max():.2f}min, "
                  f"Intensity {df['Intensity (mAU)'].min():.3f}-{df['Intensity (mAU)'].max():.3f} mAU")
        except Exception as e:
            print(f"    [오류] CSV 읽기 실패: {e}")
            continue

        # 피크 분석 (ChromatogramData 직접 생성 → baseline → peak detect)
        try:
            time_arr = df['Time (min)'].values
            intensity_arr = df['Intensity (mAU)'].values

            chromatogram = ChromatogramData(
                time=time_arr,
                intensity=intensity_arr,
                sample_name=sample_name,
                detector_type='UV-Vis',
                metadata={'file_path': str(csv_file)},
            )

            baseline_result = workflow.baseline_corrector.correct(time_arr, intensity_arr)
            peaks = workflow.peak_detector.detect(time_arr, intensity_arr, baseline_result.baseline)

            result = AnalysisResult(
                chromatogram=chromatogram,
                baseline_result=baseline_result,
                peaks=peaks,
            )
            all_results.append((sample_name, result))

            # 개별 Excel export
            if workflow.data_exporter:
                workflow.data_exporter.export_with_metadata(
                    result, output_dir / f"{sample_name}_peaks.xlsx"
                )

            # 개별 plot export
            if workflow.plot_exporter:
                workflow.plot_exporter.export_chromatogram(
                    time_arr, intensity_arr, peaks,
                    output_dir / f"{sample_name}_chromatogram.png",
                    title=f"HPLC Chromatogram: {sample_name}",
                    detector_type='UV-Vis',
                )

            total_area = sum(p.area for p in peaks) if peaks else 0
            print(f"    피크: {len(peaks)}개, 총 면적: {total_area:.4f}")
            for j, p in enumerate(peaks, 1):
                pct = (p.area / total_area * 100) if total_area > 0 else 0
                print(f"      #{j}: RT={p.rt:.3f}min, H={p.height:.4f}, "
                      f"A={p.area:.4f} ({pct:.1f}%)")
        except Exception as e:
            print(f"    [오류] 피크 분석 실패: {e}")
            import traceback
            traceback.print_exc()

    # 2) 시그널 데이터 통합 Excel
    print("\n" + "-" * 70)
    print("  통합 보고서 생성")
    print("-" * 70)

    if all_signal_data:
        signal_path = output_dir / "signal_data_all.xlsx"
        with pd.ExcelWriter(signal_path, engine='openpyxl') as writer:
            for name, df in all_signal_data.items():
                df.to_excel(writer, sheet_name=name[:31], index=False)

            # 오버레이 시트
            overlay = {}
            for name, df in all_signal_data.items():
                overlay[f'{name}_Time'] = df['Time (min)'].reset_index(drop=True)
                overlay[f'{name}_mAU'] = df['Intensity (mAU)'].reset_index(drop=True)
            pd.DataFrame(overlay).to_excel(writer, sheet_name='All Overlay', index=False)

        print(f"  시그널 통합: {signal_path.name}")

    # 3) 피크 요약 통합 Excel
    if all_results:
        summary_path = output_dir / "batch_peak_summary.xlsx"
        summary_rows = []
        peaks_rows = []

        for name, result in all_results:
            peaks = result.peaks
            total_area = sum(p.area for p in peaks) if peaks else 0
            summary_rows.append({
                '샘플명': name,
                '피크 수': len(peaks),
                '총 면적': round(total_area, 6),
            })
            for j, p in enumerate(peaks, 1):
                pct = (p.area / total_area * 100) if total_area > 0 else 0
                peaks_rows.append({
                    '샘플명': name,
                    '피크 #': j,
                    'RT (min)': round(p.rt, 3),
                    'RT Start': round(p.rt_start, 3),
                    'RT End': round(p.rt_end, 3),
                    '높이 (mAU)': round(p.height, 6),
                    '면적': round(p.area, 6),
                    '너비 (min)': round(p.width, 3),
                    '% 면적': round(pct, 2),
                })

        with pd.ExcelWriter(summary_path, engine='openpyxl') as writer:
            pd.DataFrame(summary_rows).to_excel(writer, sheet_name='샘플 요약', index=False)
            if peaks_rows:
                pd.DataFrame(peaks_rows).to_excel(writer, sheet_name='전체 피크', index=False)

        print(f"  피크 요약: {summary_path.name}")

    # 4) 오버레이 플롯
    if all_signal_data:
        overlay_path = output_dir / "chromatogram_overlay.png"
        fig, ax = plt.subplots(figsize=(14, 7))

        for name, df in all_signal_data.items():
            ax.plot(df['Time (min)'], df['Intensity (mAU)'],
                    linewidth=0.8, alpha=0.8, label=name)

        ax.set_xlabel('Retention Time (min)', fontsize=12, fontweight='bold')
        ax.set_ylabel('Absorbance (mAU)', fontsize=12, fontweight='bold')
        ax.set_title('Chromatogram Overlay - All Samples', fontsize=14, fontweight='bold')
        ax.legend(fontsize=8, loc='upper right')
        ax.grid(True, alpha=0.3, linestyle='--')
        plt.tight_layout()
        plt.savefig(overlay_path, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"  오버레이 플롯: {overlay_path.name}")

    # 완료
    print("\n" + "=" * 70)
    print(f"  완료! {len(all_signal_data)}개 샘플 처리")
    print(f"  결과: {output_dir}")
    print("=" * 70)


if __name__ == "__main__":
    main()
