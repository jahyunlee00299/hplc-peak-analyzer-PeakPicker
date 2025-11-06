"""
Chemstation 자동 Export - 키보드 단축키 버전
사용자 제공 단축키 사용
"""

import pyautogui
import pyperclip
import time
import os
import shutil
from pathlib import Path

# 안전 설정
# PAUSE: 각 PyAutoGUI 명령 후 대기 시간
# 0.3 -> 0.15로 줄이면 속도 2배 향상 (안정성 약간 감소)
# 권장: 0.2 (균형), 빠르게: 0.15, 안전: 0.3
pyautogui.PAUSE = 0.2  # 원래 0.3 -> 0.2로 최적화
pyautogui.FAILSAFE = True


def show_directory_tree(path, max_depth=2, prefix="", current_depth=0, max_items=15):
    """
    디렉토리 트리 구조 표시

    Args:
        path: 현재 경로
        max_depth: 최대 깊이
        prefix: 트리 접두사
        current_depth: 현재 깊이
        max_items: 각 레벨에서 보여줄 최대 항목 수
    """
    if current_depth >= max_depth:
        return

    try:
        items = sorted([d for d in Path(path).iterdir() if d.is_dir()])
    except (PermissionError, OSError):
        return

    for i, item in enumerate(items[:max_items]):
        is_last = (i == len(items[:max_items]) - 1)
        connector = "└── " if is_last else "├── "

        # .D 폴더 표시
        marker = " [.D]" if item.name.endswith('.D') else ""
        print(f"{prefix}{connector}{item.name}{marker}")

        # 재귀적으로 하위 폴더 표시
        if current_depth < max_depth - 1:
            extension = "    " if is_last else "│   "
            show_directory_tree(item, max_depth, prefix + extension, current_depth + 1, max_items)

    if len(items) > max_items:
        connector = "└── " if max_items == 0 else "    "
        print(f"{prefix}{connector}... 외 {len(items) - max_items}개 더")


def browse_directory_interactive(start_path):
    """
    대화형 디렉토리 탐색기 (트리 뷰 포함)

    Args:
        start_path: 시작 경로

    Returns:
        선택된 디렉토리 경로 또는 None
    """
    current_path = Path(start_path)

    while True:
        print("\n" + "=" * 80)
        print(f"현재 위치: {current_path}")
        print("=" * 80)

        # 하위 디렉토리 목록
        try:
            subdirs = [d for d in current_path.iterdir() if d.is_dir()]
            subdirs.sort()
        except PermissionError:
            print("접근 권한이 없습니다.")
            subdirs = []

        # .D 폴더 개수 세기
        d_count = sum(1 for d in subdirs if d.name.endswith('.D'))

        if not subdirs:
            print("\n하위 폴더가 없습니다.")
        else:
            print(f"\n하위 폴더: 총 {len(subdirs)}개 (.D 폴더: {d_count}개)")

            # 트리 구조 미리보기
            print("\n디렉토리 구조 미리보기 (2단계):")
            print(f"{current_path.name}/")
            show_directory_tree(current_path, max_depth=2, max_items=10)

            # 선택 가능한 폴더 목록
            print(f"\n선택 가능한 폴더 ({len(subdirs)}개):")
            display_limit = 20
            for i, subdir in enumerate(subdirs[:display_limit], 1):
                marker = " [.D]" if subdir.name.endswith('.D') else ""
                # 하위 .D 폴더 개수도 표시
                try:
                    sub_d_folders = [d for d in subdir.iterdir() if d.is_dir() and d.name.endswith('.D')]
                    if sub_d_folders:
                        count_info = f" ({len(sub_d_folders)}개 .D)"
                    else:
                        count_info = ""
                except:
                    count_info = ""

                print(f"  {i:2d}. {subdir.name}{marker}{count_info}")

            if len(subdirs) > display_limit:
                print(f"  ... 외 {len(subdirs)-display_limit}개 더")

        # 옵션 표시 (오른쪽 정렬)
        print("\n" + "=" * 80)
        commands = [
            ("[번호]", "해당 폴더로 이동"),
            ("s", "✅ 현재 폴더 선택"),
            ("u", "⬆️  상위 폴더"),
            ("t", "🌲 전체 트리 보기"),
            ("path", "✏️  경로 직접 입력"),
            ("q", "❌ 취소")
        ]

        # 2열로 표시
        for i in range(0, len(commands), 2):
            left_cmd, left_desc = commands[i]
            left_str = f"  {left_cmd:8s} : {left_desc}"

            if i + 1 < len(commands):
                right_cmd, right_desc = commands[i + 1]
                right_str = f"{right_cmd:8s} : {right_desc}"
                print(f"{left_str:40s} │ {right_str}")
            else:
                print(left_str)

        print("=" * 80)
        choice = input("👉 선택: ").strip().lower()

        if choice == 'q':
            return None
        elif choice == 's':
            # 선택 시 하위 .D 폴더 개수 확인
            print("\n검색 중...")
            d_folders = find_all_d_folders(current_path, recursive=True)
            print(f"\n'{current_path.name}' 선택됨")
            print(f"총 {len(d_folders)}개 .D 폴더 발견 (하위 폴더 포함)")
            if len(d_folders) > 0:
                # 몇 개 샘플 표시
                print("\n발견된 .D 폴더 (샘플):")
                for d in d_folders[:5]:
                    rel_path = Path(d).relative_to(current_path)
                    print(f"  - {rel_path}")
                if len(d_folders) > 5:
                    print(f"  ... 외 {len(d_folders)-5}개 더")

                confirm = input("\n계속하시겠습니까? (y/n): ").strip().lower()
                if confirm == 'y':
                    return str(current_path)
                else:
                    continue
            else:
                print("\n경고: .D 폴더가 없습니다. 다른 폴더를 선택해주세요.")
                input("(Enter를 눌러 계속...)")
                continue
        elif choice == 'u':
            current_path = current_path.parent
        elif choice == 't':
            # 전체 트리 보기
            print("\n디렉토리 전체 구조 (3단계):")
            print(f"{current_path.name}/")
            show_directory_tree(current_path, max_depth=3, max_items=20)
            input("\n(Enter를 눌러 계속...)")
        elif choice == 'path':
            new_path = input("경로 입력: ").strip().strip('"').strip("'")
            if os.path.exists(new_path):
                current_path = Path(new_path)
            else:
                print(f"경로가 존재하지 않습니다: {new_path}")
                input("(Enter를 눌러 계속...)")
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(subdirs):
                current_path = subdirs[idx]
            else:
                print("잘못된 번호입니다.")
                input("(Enter를 눌러 계속...)")
        else:
            print("잘못된 입력입니다.")
            input("(Enter를 눌러 계속...)")


def quick_scan_all_d_folders(base_dir):
    """
    전체 폴더를 빠르게 스캔하여 모든 .D 폴더 찾기 및 표시

    Args:
        base_dir: 검색 시작 디렉토리

    Returns:
        선택된 디렉토리 경로 또는 None
    """
    print("\n" + "=" * 80)
    print("  전체 폴더 스캔 중...")
    print("=" * 80)
    print(f"\n검색 경로: {base_dir}")
    print("재귀적으로 모든 하위 폴더 검색 중...\n")

    # 모든 .D 폴더 찾기
    d_folders = find_all_d_folders(base_dir, recursive=True)

    if not d_folders:
        print("❌ .D 폴더를 찾을 수 없습니다.")
        print(f"경로를 확인해주세요: {base_dir}")
        input("\n(Enter를 눌러 계속...)")
        return None

    print(f"✅ 총 {len(d_folders)}개 .D 폴더 발견!\n")

    # 폴더별로 그룹화 (상위 폴더별)
    folder_groups = {}
    for d_folder in d_folders:
        parent = Path(d_folder).parent
        rel_parent = parent.relative_to(base_dir) if parent != Path(base_dir) else Path(".")
        if rel_parent not in folder_groups:
            folder_groups[rel_parent] = []
        folder_groups[rel_parent].append(Path(d_folder).name)

    # 그룹별로 표시
    print("📊 폴더별 분포:")
    print("-" * 80)
    for parent, files in sorted(folder_groups.items())[:10]:
        print(f"\n📁 {parent}/")
        for f in files[:5]:
            print(f"   └─ {f}")
        if len(files) > 5:
            print(f"   └─ ... 외 {len(files)-5}개 더")

    if len(folder_groups) > 10:
        print(f"\n... 외 {len(folder_groups)-10}개 폴더 더")

    # 처음 10개 .D 폴더 표시
    print("\n" + "=" * 80)
    print("발견된 .D 폴더 목록 (처음 10개):")
    print("-" * 80)
    for i, d_folder in enumerate(d_folders[:10], 1):
        rel_path = Path(d_folder).relative_to(base_dir)
        print(f"  {i:2d}. {rel_path}")

    if len(d_folders) > 10:
        print(f"  ... 외 {len(d_folders)-10}개 더")

    # 확인
    print("\n" + "=" * 80)
    print(f"총 {len(d_folders)}개 파일을 모두 내보내시겠습니까?")
    confirm = input("계속하려면 'y', 취소하려면 'n': ").strip().lower()

    if confirm == 'y':
        return base_dir
    else:
        print("\n취소되었습니다.")
        return None


def get_data_directory():
    """사용자로부터 데이터 디렉토리 경로 입력받기"""
    print("\n" + "=" * 80)
    print("  데이터 디렉토리 설정")
    print("=" * 80)

    # 기본 경로 제시
    default_path = r"C:\Chem32\1\DATA"

    print(f"\n기본 경로: {default_path}")
    print("\n옵션:")
    print("  1. 대화형 폴더 탐색 (트리 뷰)")
    print("  2. 직접 경로 입력")
    print("  3. 전체 폴더 스캔 후 모든 .D 내보내기")

    while True:
        choice = input("\n선택 (1, 2, 또는 3): ").strip()

        if choice == '1':
            # 대화형 탐색
            start = default_path if os.path.exists(default_path) else os.getcwd()
            base_dir = browse_directory_interactive(start)
            if base_dir is None:
                print("\n취소되었습니다.")
                return None
            break

        elif choice == '2':
            base_dir = input("\n데이터 디렉토리 경로를 입력하세요: ").strip()
            base_dir = base_dir.strip('"').strip("'")
            break

        elif choice == '3':
            # 전체 폴더 스캔
            scan_path = input(f"\n스캔할 경로 (Enter=기본값 '{default_path}'): ").strip()
            if not scan_path:
                scan_path = default_path

            scan_path = scan_path.strip('"').strip("'")

            if not os.path.exists(scan_path):
                print(f"\n❌ 경로가 존재하지 않습니다: {scan_path}")
                continue

            base_dir = quick_scan_all_d_folders(scan_path)
            if base_dir is None:
                continue
            break

        else:
            print("1, 2, 또는 3을 선택해주세요.")

    # 경로 존재 확인
    if not os.path.exists(base_dir):
        print(f"\n경고: 경로가 존재하지 않습니다: {base_dir}")
        confirm = input("계속하시겠습니까? (y/n): ").strip().lower()
        if confirm != 'y':
            return None

    return base_dir


def find_all_d_folders(base_dir, recursive=True):
    """
    모든 .D 폴더 찾기 (재귀적 검색 지원)

    Args:
        base_dir: 검색 시작 디렉토리
        recursive: True면 하위 폴더도 검색
    """
    d_folders = []

    try:
        if recursive:
            # 재귀적 검색: 모든 하위 폴더 포함
            for root, dirs, files in os.walk(base_dir):
                for dirname in dirs:
                    if dirname.endswith('.D'):
                        full_path = os.path.join(root, dirname)
                        d_folders.append(full_path)
        else:
            # 현재 디렉토리만 검색
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
    """

    folder_name = Path(d_folder_path).name
    print(f"\n  처리 중: {folder_name}")

    try:
        # Step 1: Alt+F (File 메뉴)
        print("    1. File 메뉴 열기...")
        pyautogui.hotkey('alt', 'f')
        time.sleep(0.01)  # 원래 0.5 -> 메뉴 열리는 시간만 필요

        # Step 2: Shift+G (Load Signal)
        print("    2. Load Signal...")
        pyautogui.hotkey('shift', 'g')
        time.sleep(0.01)  # 원래 1.0 -> 대화상자 열리는 시간

        # Step 3: 파일 경로 입력
        print("    3. 파일 경로 입력...")
        pyperclip.copy(d_folder_path)
        pyautogui.hotkey('ctrl', 'a')  # 전체 선택
        time.sleep(0.01)  # 원래 0.2 -> 선택 즉시
        pyautogui.hotkey('ctrl', 'v')  # 붙여넣기
        time.sleep(0.01)  # 원래 0.5 -> 붙여넣기 완료 시간

        # Step 4: Enter (파일 열기)
        print("    4. 파일 열기...")
        pyautogui.press('enter')
        time.sleep(1)  # 원래 3.0 -> 파일 로드 대기 (가장 긴 시간, 필요시 조정)

        # Step 5: Alt+F (File 메뉴)
        print("    5. File 메뉴 열기...")
        pyautogui.hotkey('alt', 'f')
        time.sleep(0.01)  # 원래 0.5 -> 메뉴 열리는 시간

        # Step 6: E (Export)
        print("    6. Export...")
        pyautogui.press('e')
        time.sleep(0.01)  # 원래 0.5 -> 서브메뉴

        # Step 7: C (CSV)
        print("    7. CSV 선택...")
        pyautogui.press('c')
        time.sleep(0.01)  # 원래 0.5 -> 대화상자

        # Step 8: 방향키 아래 2번 (Signal export로 이동)
        print("    8. Signal export 선택...")
        pyautogui.press('down')
        time.sleep(0.01)  # 원래 0.2 -> 키 입력 간격
        pyautogui.press('down')
        time.sleep(0.01)  # 원래 0.3 -> 선택 확인

        # Step 9: Enter 2번 (Export 완료)
        print("    9. Export 실행...")
        pyautogui.press('enter')
        time.sleep(0.01)  # 원래 0.5
        pyautogui.press('enter')
        time.sleep(0.01)  # 원래 2.0 -> Export 완료 대기

        # Step 10: export.csv 복사
        temp_export = r"C:\Chem32\1\TEMP\export.csv"

        # 파일 생성 대기 (최대 10초)
        for i in range(20):
            if os.path.exists(temp_export):
                mtime = os.path.getmtime(temp_export)
                age = time.time() - mtime

                if age < 15:  # 최근 15초 이내에 수정됨
                    # 파일 복사
                    shutil.copy(temp_export, output_csv_path)
                    size = os.path.getsize(output_csv_path)
                    print(f"    [성공] {size:,} bytes")
                    return True

            time.sleep(0.1)

        print(f"    [실패] Export 파일이 생성되지 않음")
        return False

    except Exception as e:
        print(f"    [오류] {e}")
        return False


def main():
    """배치 export 실행"""

    print("=" * 80)
    print("  Chemstation 자동 Export")
    print("  키보드 단축키 버전")
    print("=" * 80)

    # 데이터 디렉토리 입력받기
    base_dir = get_data_directory()

    if base_dir is None:
        print("\n프로그램을 종료합니다.")
        return

    # .D 폴더 찾기 (재귀적 검색 옵션)
    print(f"\n'{base_dir}' 에서 .D 폴더 검색 중...")
    print("  (하위 폴더 포함 재귀적 검색)")
    d_folders = find_all_d_folders(base_dir, recursive=True)

    if not d_folders:
        print(f"\n.D 폴더를 찾을 수 없습니다.")
        print(f"경로를 확인해주세요: {base_dir}")
        return

    print(f"\n[확인] {len(d_folders)}개 .D 폴더 발견 (하위 폴더 포함)")

    # 처음 몇 개 표시
    print("\n발견된 파일:")
    for i, d_folder in enumerate(d_folders[:5], 1):
        print(f"  {i}. {Path(d_folder).name}")
    if len(d_folders) > 5:
        print(f"  ... 외 {len(d_folders)-5}개 더")

    # 사용자 확인
    print("\n" + "=" * 80)
    confirm = input(f"\n{len(d_folders)}개 파일을 처리하시겠습니까? (y/n): ").strip().lower()
    if confirm != 'y':
        print("\n취소되었습니다.")
        return

    # 출력 디렉토리 설정
    print("\n" + "=" * 80)
    print("  출력 디렉토리 설정")
    print("=" * 80)

    # 기본 경로: result/
    default_output = os.path.join(os.getcwd(), "result")

    # 상위 폴더 이름 추출
    base_dir_name = Path(base_dir).name
    suggested_subdir = os.path.join(default_output, base_dir_name)

    print(f"\n기본 출력 경로: {default_output}/")
    print(f"제안된 하위 폴더: {base_dir_name}/")
    print(f"→ 최종 경로: {suggested_subdir}")

    print("\n옵션:")
    print("  1. 제안된 경로 사용 (result/{폴더명}/)")
    print("  2. result/ 폴더에 직접 저장")
    print("  3. 커스텀 경로 입력")

    output_choice = input("\n선택 (1, 2, 또는 3, Enter=1): ").strip()

    if output_choice == '2':
        output_dir = default_output
        print(f"\n선택된 경로: {output_dir}/")
    elif output_choice == '3':
        custom_output = input("\n출력 경로 입력: ").strip().strip('"').strip("'")
        output_dir = custom_output
        print(f"\n선택된 경로: {output_dir}/")
    else:  # 1 또는 Enter
        output_dir = suggested_subdir
        print(f"\n선택된 경로: {output_dir}/")

    # 디렉토리 생성
    os.makedirs(output_dir, exist_ok=True)
    print(f"✅ 출력 디렉토리 생성 완료")

    # 준비
    print("\n" + "=" * 80)
    print("  시작 준비")
    print("=" * 80)
    print("\n  주의사항:")
    print("    - Chemstation 창이 활성화되어 있어야 합니다")
    print("    - 다른 창이 가리지 않도록 해주세요")
    print("    - 마우스를 왼쪽 위 모서리로 이동하면 중단됩니다")
    print("\n  5초 후 시작...")

    for i in range(5, 0, -1):
        print(f"    {i}...")
        time.sleep(1)

    print("\n" + "=" * 80)
    print("  Export 시작")
    print("=" * 80)

    # 파일 처리
    success_count = 0
    failed = []
    start_time = time.time()

    for i, d_folder in enumerate(d_folders, 1):
        folder_name = Path(d_folder).name.replace('.D', '')
        output_csv = os.path.join(output_dir, f"{folder_name}.csv")

        # 이미 존재하면 건너뛰기
        if os.path.exists(output_csv):
            print(f"\n[{i}/{len(d_folders)}] 건너뜀: {folder_name} (이미 존재)")
            success_count += 1
            continue

        print(f"\n[{i}/{len(d_folders)}] {folder_name}")

        # Export 실행
        if export_one_file(d_folder, output_csv):
            success_count += 1
        else:
            failed.append(folder_name)

        # 진행 상황
        if i > 0:
            elapsed = time.time() - start_time
            avg_time = elapsed / i
            remaining = (len(d_folders) - i) * avg_time

            print(f"\n  진행 상황: {success_count}/{i} 성공")
            print(f"  예상 남은 시간: {remaining/60:.1f}분")

    # 완료
    total_time = time.time() - start_time
    print("\n" + "=" * 80)
    print("  배치 Export 완료")
    print("=" * 80)
    print(f"\n  성공: {success_count}/{len(d_folders)} 파일")
    print(f"  소요 시간: {total_time/60:.1f}분")
    print(f"  출력 디렉토리: {output_dir}")

    if failed:
        print(f"\n  실패한 파일 ({len(failed)}):")
        for name in failed[:10]:
            print(f"    - {name}")
        if len(failed) > 10:
            print(f"    ... 외 {len(failed)-10}개")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[중단] 사용자가 중단했습니다.")
    except Exception as e:
        print(f"\n[오류] {e}")
        import traceback
        traceback.print_exc()