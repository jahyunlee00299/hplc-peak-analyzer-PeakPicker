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
        print("\n❌ Export 취소됨")
        return None

    # Find .D folders
    print(f"\n'{base_dir}' 에서 .D 폴더 검색 중...")
    print("  (하위 폴더 포함 재귀적 검색)")
    d_folders = auto_export_keyboard_final.find_all_d_folders(base_dir, recursive=True)

    if not d_folders:
        print(f"\n❌ .D 폴더를 찾을 수 없습니다.")
        return None

    print(f"\n✅ {len(d_folders)}개 .D 폴더 발견")

    # Set output directory
    default_output = os.path.join(os.getcwd(), "result")
    base_dir_name = Path(base_dir).name
    output_dir = os.path.join(default_output, base_dir_name)

    print(f"\n출력 경로: {output_dir}")
    os.makedirs(output_dir, exist_ok=True)

    # Confirm
    print("\n" + "="*80)
    confirm = input(f"\n{len(d_folders)}개 파일을 Export 하시겠습니까? (y/n): ").strip().lower()
    if confirm != 'y':
        print("\n❌ Export 취소됨")
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
        output_csv = os.path.join(output_dir, f"{folder_name}.csv")

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
    print(f"  출력 디렉토리: {output_dir}")

    if failed:
        print(f"\n  실패: {len(failed)}개")
        for name in failed[:5]:
            print(f"    - {name}")
        if len(failed) > 5:
            print(f"    ... 외 {len(failed)-5}개")

    if success_count == 0:
        print("\n❌ Export된 파일이 없습니다.")
        return None

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
        print(f"\n❌ 데이터 디렉토리가 없습니다: {data_dir}")
        return False

    # Count CSV files
    csv_files = list(Path(data_dir).glob("*.csv")) + list(Path(data_dir).glob("*.CSV"))

    if not csv_files:
        print(f"\n❌ CSV 파일이 없습니다: {data_dir}")
        return False

    print(f"\n✅ {len(csv_files)}개 CSV 파일 발견")
    print(f"   디렉토리: {data_dir}")

    # Analysis settings
    print(f"\n분석 설정:")
    print(f"  - 베이스라인 보정: 활성화")
    print(f"  - 피크 디컨볼루션: {'활성화' if enable_deconvolution else '비활성화'}")
    if enable_deconvolution:
        print(f"  - 비대칭도 임계값: {asymmetry_threshold}")

    # Confirm
    confirm = input(f"\n분석을 시작하시겠습니까? (y/n): ").strip().lower()
    if confirm != 'y':
        print("\n❌ 분석 취소됨")
        return False

    print("\n" + "="*80)
    print("분석 시작")
    print("="*80)

    # Import analyzer
    from hplc_analyzer_enhanced import EnhancedHPLCAnalyzer

    # Create output directory
    output_dir = Path(data_dir) / "analysis_results"

    # Create analyzer
    analyzer = EnhancedHPLCAnalyzer(
        data_directory=data_dir,
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
            print("\n❌ --skip-export를 사용할 때는 --data-dir이 필요합니다.")
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
        print("\n⚠️  분석 중 오류가 발생했습니다.")
        return 1

    # Complete
    print("\n" + "="*80)
    print("  전체 워크플로우 완료!")
    print("="*80)
    print(f"\n✅ CSV 파일: {data_dir}")
    print(f"✅ 분석 결과: {Path(data_dir) / 'analysis_results'}")
    print("\nExcel 파일을 확인하여 결과를 검토하세요.")
    print("="*80)

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
