"""
Chemstation 자동 Export - 전체 자동 실행 버전
사용자 입력 없이 C:\Chem32\1\DATA의 모든 .D 파일을 자동으로 export
"""

import pyautogui
import pyperclip
import time
import os
import shutil
from pathlib import Path

# 안전 설정
pyautogui.PAUSE = 0.2
pyautogui.FAILSAFE = False  # Disable fail-safe to prevent mouse corner interruption


def find_all_d_folders(base_dir, recursive=True):
    """
    .D로 끝나는 모든 폴더 찾기

    Args:
        base_dir: 검색 시작 디렉토리
        recursive: 하위 폴더 재귀 검색 여부

    Returns:
        .D 폴더 경로 리스트 (정렬됨)
    """
    d_folders = []

    try:
        if recursive:
            for root, dirs, files in os.walk(base_dir):
                for dir_name in dirs:
                    if dir_name.endswith('.D'):
                        d_folders.append(os.path.join(root, dir_name))
        else:
            for item in Path(base_dir).iterdir():
                if item.is_dir() and item.name.endswith('.D'):
                    d_folders.append(str(item))
    except Exception as e:
        print(f"폴더 검색 중 오류: {e}")

    return sorted(d_folders)


def export_one_file(d_folder_path, output_csv_path):
    """
    키보드 단축키로 1개 파일 export

    순서:
    1. Alt+F -> Shift+G (Load Signal)
    2. 파일 경로 입력 + Enter
    3. Alt+F -> E -> C (Export CSV)
    4. 방향키 아래 2번 (Signal export)
    5. Enter 2번 (완료)

    Returns:
        "success": 성공
        "no_signal": No signal available
        "error": 기타 오류
    """

    folder_name = Path(d_folder_path).name
    print(f"\n  처리 중: {folder_name}")

    try:
        # Step 1: Alt+F (File 메뉴)
        print("    1. File 메뉴 열기...")
        pyautogui.hotkey('alt', 'f')
        time.sleep(0.01)

        # Step 2: Shift+G (Load Signal)
        print("    2. Load Signal...")
        pyautogui.hotkey('shift', 'g')
        time.sleep(0.01)

        # Step 3: 파일 경로 입력
        print("    3. 파일 경로 입력...")
        pyperclip.copy(d_folder_path)
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.01)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.01)

        # Step 4: Enter (파일 열기)
        print("    4. 파일 열기...")
        pyautogui.press('enter')
        time.sleep(0.1)

        # Step 4.5: "No signals available" 대응 - Enter 한번 더
        print("    4.5. 오류 대화상자 닫기 (있을 경우)...")
        pyautogui.press('enter')
        time.sleep(0.8)

        # Step 5: Alt+F (File 메뉴)
        print("    5. File 메뉴 열기...")
        pyautogui.hotkey('alt', 'f')
        time.sleep(0.01)

        # Step 6: E (Export)
        print("    6. Export...")
        pyautogui.press('e')
        time.sleep(0.01)

        # Step 7: C (CSV)
        print("    7. CSV 선택...")
        pyautogui.press('c')
        time.sleep(0.01)

        # Step 8: 방향키 아래 2번 (Signal export로 이동)
        print("    8. Signal export 선택...")
        pyautogui.press('down')
        time.sleep(0.01)
        pyautogui.press('down')
        time.sleep(0.01)

        # Step 9: Enter 2번 (Export 완료)
        print("    9. Export 실행...")
        pyautogui.press('enter')
        time.sleep(0.01)
        pyautogui.press('enter')
        time.sleep(0.01)

        # Step 10: export.csv 복사
        temp_export = r"C:\Chem32\1\TEMP\export.csv"
        old_mtime = None

        # 기존 파일의 수정 시간 확인
        if os.path.exists(temp_export):
            old_mtime = os.path.getmtime(temp_export)

        # 파일 생성 대기 (최대 2초)
        for i in range(20):
            if os.path.exists(temp_export):
                mtime = os.path.getmtime(temp_export)

                # 새로 생성되었거나 최근 2초 이내에 수정됨
                if old_mtime is None or mtime > old_mtime:
                    age = time.time() - mtime
                    if age < 2:  # 최근 2초 이내에 수정됨
                        # 파일 복사
                        shutil.copy(temp_export, output_csv_path)
                        size = os.path.getsize(output_csv_path)
                        print(f"    [성공] {size:,} bytes")
                        return "success"

            time.sleep(0.1)

        print(f"    [실패] No signal available (export 파일 미생성)")
        return "no_signal"

    except Exception as e:
        print(f"    [오류] {e}")
        return "error"


def check_and_cleanup_duplicates(output_dir):
    """
    중복 파일 확인 및 정리

    - 같은 이름의 CSV 파일이 여러 폴더에 있으면 확인
    - 파일 크기, 수정 시간 비교
    - 중복 파일 리스트 생성
    """
    print("\n" + "=" * 80)
    print("  중복 파일 확인 중...")
    print("=" * 80)

    # 모든 CSV 파일 찾기
    csv_files = {}
    for root, dirs, files in os.walk(output_dir):
        for file in files:
            if file.endswith('.csv'):
                full_path = os.path.join(root, file)

                if file not in csv_files:
                    csv_files[file] = []

                # 파일 정보 저장
                size = os.path.getsize(full_path)
                mtime = os.path.getmtime(full_path)
                csv_files[file].append({
                    'path': full_path,
                    'size': size,
                    'mtime': mtime,
                    'rel_path': os.path.relpath(full_path, output_dir)
                })

    # 중복 파일 찾기
    duplicates = {}
    for filename, file_list in csv_files.items():
        if len(file_list) > 1:
            duplicates[filename] = file_list

    if not duplicates:
        print("\n[OK] 중복 파일 없음")
        return

    print(f"\n[WARNING] 중복 파일 발견: {len(duplicates)}개")
    print("\n" + "-" * 80)

    # 중복 파일 상세 정보
    for filename, file_list in sorted(duplicates.items())[:10]:
        print(f"\n📄 {filename} ({len(file_list)}개 중복)")
        for i, info in enumerate(file_list, 1):
            size_kb = info['size'] / 1024
            mtime_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(info['mtime']))
            print(f"  {i}. {info['rel_path']}")
            print(f"     크기: {size_kb:.1f} KB | 수정: {mtime_str}")

    if len(duplicates) > 10:
        print(f"\n... 외 {len(duplicates)-10}개 중복 파일 더")

    # 중복 파일 정리 제안
    print("\n" + "=" * 80)
    print("중복 파일 중 가장 최근 파일만 남기고 나머지를 삭제하시겠습니까?")
    print("(각 파일명마다 수정 시간이 가장 최근인 파일 1개만 유지)")
    print("=" * 80)

    # 자동으로 정리하지 않고 리포트만 생성
    duplicate_report = os.path.join(output_dir, "duplicate_files_report.txt")
    with open(duplicate_report, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("중복 파일 리포트\n")
        f.write("=" * 80 + "\n\n")

        for filename, file_list in sorted(duplicates.items()):
            f.write(f"\n파일명: {filename} ({len(file_list)}개 중복)\n")
            f.write("-" * 80 + "\n")

            for i, info in enumerate(file_list, 1):
                size_kb = info['size'] / 1024
                mtime_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(info['mtime']))
                f.write(f"{i}. {info['rel_path']}\n")
                f.write(f"   크기: {size_kb:.1f} KB | 수정: {mtime_str}\n")

    print(f"\n[OK] 중복 파일 리포트 저장: {duplicate_report}")
    print("   수동으로 확인 후 필요한 파일을 삭제하세요.")


def main():
    """자동 export 실행 - 모든 입력 자동화"""

    print("=" * 80)
    print("  Chemstation 자동 Export - 전체 자동 실행")
    print("=" * 80)

    # 자동 설정
    base_dir = r"C:\Chem32\1\DATA"
    output_dir = os.path.join(os.getcwd(), "exported_signals_all")

    # 기존 exported_signals 폴더와 통합
    old_export_dir = os.path.join(os.getcwd(), "exported_signals")
    if os.path.exists(old_export_dir):
        print(f"\n[INFO] 기존 exported_signals 폴더 발견")
        print(f"   기존: {old_export_dir}")
        print(f"   새로운: {output_dir}")
        print(f"   두 폴더를 확인 후 중복 파일을 정리합니다.")

    print(f"\n[자동 설정]")
    print(f"  입력 디렉토리: {base_dir}")
    print(f"  출력 디렉토리: {output_dir}")

    # 폴더 구조 유지 여부 확인
    print("\n" + "=" * 80)
    print("  폴더 구조 옵션")
    print("=" * 80)
    print("\n  하위 폴더의 폴더 구조를 어떻게 처리할까요?")
    print("\n  1) 폴더 구조 유지 (예: output/프로젝트A/sample1.csv)")
    print("  2) 평평하게 저장 (예: output/sample1.csv)")
    print("\n  선택 (1 또는 2): ", end="")

    preserve_structure = True
    while True:
        choice = input().strip()
        if choice == '1':
            preserve_structure = True
            print("\n  [OK] 폴더 구조를 유지합니다.")
            break
        elif choice == '2':
            preserve_structure = False
            print("\n  [OK] 모든 파일을 한 폴더에 평평하게 저장합니다.")
            break
        else:
            print("  잘못된 입력입니다. 1 또는 2를 입력하세요: ", end="")

    # .D 폴더 찾기
    print(f"\n'{base_dir}' 에서 .D 폴더 검색 중...")
    print("  (하위 폴더 포함 재귀적 검색)")
    d_folders = find_all_d_folders(base_dir, recursive=True)

    if not d_folders:
        print(f"\n[ERROR] .D 폴더를 찾을 수 없습니다.")
        print(f"경로를 확인해주세요: {base_dir}")
        return

    print(f"\n[OK] {len(d_folders)}개 .D 폴더 발견 (하위 폴더 포함)")

    # 프로젝트별 분류
    print("\n" + "=" * 80)
    print("  프로젝트별 파일 분포")
    print("=" * 80)

    folder_groups = {}
    for d_folder in d_folders:
        try:
            rel_path = Path(d_folder).relative_to(base_dir)
            parent_folder = str(rel_path.parent) if rel_path.parent != Path('.') else '(루트)'
        except ValueError:
            parent_folder = '(기타)'

        if parent_folder not in folder_groups:
            folder_groups[parent_folder] = 0
        folder_groups[parent_folder] += 1

    for folder, count in sorted(folder_groups.items(), key=lambda x: x[1], reverse=True):
        print(f"  [DIR] {folder}: {count}개")

    # 전체 파일 목록 표시
    print("\n" + "=" * 80)
    print(f"발견된 전체 파일 목록 ({len(d_folders)}개):")
    print("-" * 80)
    for i, d_folder in enumerate(d_folders, 1):
        rel_path = Path(d_folder).relative_to(base_dir)
        print(f"  {i:3d}. {rel_path}")

    # 디렉토리 생성
    os.makedirs(output_dir, exist_ok=True)
    print(f"\n[OK] 출력 디렉토리 생성 완료: {output_dir}")

    # 준비
    print("\n" + "=" * 80)
    print("  시작 준비")
    print("=" * 80)
    print("\n  주의사항:")
    print("    [!] Chemstation 창이 활성화되어 있어야 합니다")
    print("    [!] 다른 창이 가리지 않도록 해주세요")
    print("    [!] 마우스를 왼쪽 위 모서리로 이동하면 중단됩니다")
    print(f"\n  총 {len(d_folders)}개 파일 처리 예정")
    print(f"  예상 소요 시간: {len(d_folders) * 2 / 60:.1f}분")
    print("\n  10초 후 자동 시작...")

    for i in range(10, 0, -1):
        print(f"    {i}...")
        time.sleep(1)

    print("\n" + "=" * 80)
    print("  Export 시작")
    print("=" * 80)

    # 파일 처리
    success_count = 0
    no_signal_files = []
    failed = []
    skipped_last_blank = 0
    start_time = time.time()

    for i, d_folder in enumerate(d_folders, 1):
        folder_name = Path(d_folder).name.replace('.D', '')

        # "last"나 "blank" 포함된 파일 건너뛰기
        folder_name_lower = folder_name.lower()
        if 'last' in folder_name_lower or 'blank' in folder_name_lower:
            print(f"\n[{i}/{len(d_folders)}] 건너뜀: {folder_name} (last/blank 파일)")
            skipped_last_blank += 1
            continue

        # 폴더 구조 유지 여부에 따라 경로 설정
        if preserve_structure:
            # 프로젝트 폴더 구조 유지
            try:
                # d_folder의 상대 경로 계산
                rel_path = Path(d_folder).relative_to(base_dir)
                # 상위 폴더 구조 생성
                subfolder = rel_path.parent
                output_subfolder = os.path.join(output_dir, subfolder)
                os.makedirs(output_subfolder, exist_ok=True)
                # CSV 파일 경로
                output_csv = os.path.join(output_subfolder, f"{folder_name}.csv")
            except ValueError:
                # 상대 경로 계산 실패 시 기본 경로 사용
                output_csv = os.path.join(output_dir, f"{folder_name}.csv")
        else:
            # 평평하게 저장 (모든 파일을 한 폴더에)
            output_csv = os.path.join(output_dir, f"{folder_name}.csv")

        # 이미 존재하면 건너뛰기
        if os.path.exists(output_csv):
            print(f"\n[{i}/{len(d_folders)}] 건너뜀: {folder_name} (이미 존재)")
            success_count += 1
            continue

        print(f"\n[{i}/{len(d_folders)}] {folder_name}")

        # Export 실행
        result = export_one_file(d_folder, output_csv)
        if result == "success":
            success_count += 1
        elif result == "no_signal":
            no_signal_files.append(folder_name)
        else:  # "error"
            failed.append(folder_name)

        # 진행 상황 (매 10개마다)
        if i % 10 == 0 or i == len(d_folders):
            elapsed = time.time() - start_time
            avg_time = elapsed / i
            remaining = (len(d_folders) - i) * avg_time

            print(f"\n  [PROGRESS] {success_count}/{i} 성공 ({success_count/i*100:.1f}%)")
            print(f"  [TIME] 경과 시간: {elapsed/60:.1f}분")
            print(f"  [ETA] 예상 남은 시간: {remaining/60:.1f}분")

    # 완료
    total_time = time.time() - start_time
    print("\n" + "=" * 80)
    print("  배치 Export 완료")
    print("=" * 80)
    print(f"\n  [SUCCESS] {success_count}/{len(d_folders)} 파일 ({success_count/len(d_folders)*100:.1f}%)")
    print(f"  [TIME] 소요 시간: {total_time/60:.1f}분")
    print(f"  [DIR] 출력 디렉토리: {output_dir}")

    # 폴더별 요약 출력
    print("\n" + "=" * 80)
    print("  프로젝트 폴더별 export 파일 수")
    print("=" * 80)

    exported_summary = {}
    for d_folder in d_folders:
        folder_name = Path(d_folder).name.replace('.D', '')

        # 폴더 구조 유지 여부에 따라 경로 설정
        if preserve_structure:
            try:
                rel_path = Path(d_folder).relative_to(base_dir)
                subfolder = rel_path.parent
                output_csv = os.path.join(output_dir, subfolder, f"{folder_name}.csv")
            except ValueError:
                output_csv = os.path.join(output_dir, f"{folder_name}.csv")
        else:
            output_csv = os.path.join(output_dir, f"{folder_name}.csv")

        if os.path.exists(output_csv):
            if preserve_structure:
                try:
                    rel_path = Path(d_folder).relative_to(base_dir)
                    parent_folder = str(rel_path.parent) if rel_path.parent != Path('.') else '(루트)'
                except ValueError:
                    parent_folder = '(기타)'
            else:
                parent_folder = '(전체 - 평평하게 저장)'

            if parent_folder not in exported_summary:
                exported_summary[parent_folder] = 0
            exported_summary[parent_folder] += 1

    for folder, count in sorted(exported_summary.items(), key=lambda x: x[1], reverse=True):
        print(f"  [OK] {folder}: {count}개")

    # No signal 파일 목록
    if no_signal_files:
        print(f"\n" + "=" * 80)
        print(f"  [NO SIGNAL] No signal available 파일 ({len(no_signal_files)}):")
        print("=" * 80)
        for name in no_signal_files[:20]:
            print(f"    - {name}")
        if len(no_signal_files) > 20:
            print(f"    ... 외 {len(no_signal_files)-20}개")

    # 기타 실패 파일 목록
    if failed:
        print(f"\n" + "=" * 80)
        print(f"  [FAILED] 기타 오류 파일 ({len(failed)}):")
        print("=" * 80)
        for name in failed[:20]:
            print(f"    - {name}")
        if len(failed) > 20:
            print(f"    ... 외 {len(failed)-20}개")

    # Last/Blank 건너뛴 파일
    if skipped_last_blank > 0:
        print(f"\n  [SKIPPED] Last/Blank 파일: {skipped_last_blank}개")

    # 중복 파일 확인 및 정리
    check_and_cleanup_duplicates(output_dir)

    print("\n" + "=" * 80)
    print("\n[DONE] Export 완료! 이제 분석을 시작할 수 있습니다.")
    print(f"[DIR] 출력 디렉토리: {output_dir}")
    print(f"[SUCCESS] 성공: {success_count}개")
    if no_signal_files:
        print(f"[NO SIGNAL] No signal available: {len(no_signal_files)}개")
    if failed:
        print(f"[FAILED] 기타 오류: {len(failed)}개")
    if skipped_last_blank > 0:
        print(f"[SKIPPED] Last/Blank 건너뜀: {skipped_last_blank}개")


if __name__ == '__main__':
    main()
