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
pyautogui.PAUSE = 0.3
pyautogui.FAILSAFE = True

def find_all_d_folders():
    """모든 .D 폴더 찾기"""
    base_dir = r"C:\Chem32\1\DATA\2. D-Xyl cascade HPLC\Ribavirin\Riba pH Main"
    d_folders = []
    for item in Path(base_dir).iterdir():
        if item.is_dir() and item.name.endswith('.D'):
            d_folders.append(str(item))
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
        time.sleep(0.5)

        # Step 2: Shift+G (Load Signal)
        print("    2. Load Signal...")
        pyautogui.hotkey('shift', 'g')
        time.sleep(1)

        # Step 3: 파일 경로 입력
        print("    3. 파일 경로 입력...")
        pyperclip.copy(d_folder_path)
        pyautogui.hotkey('ctrl', 'a')  # 전체 선택
        time.sleep(0.2)
        pyautogui.hotkey('ctrl', 'v')  # 붙여넣기
        time.sleep(0.5)

        # Step 4: Enter (파일 열기)
        print("    4. 파일 열기...")
        pyautogui.press('enter')
        time.sleep(3)  # 파일 로드 대기

        # Step 5: Alt+F (File 메뉴)
        print("    5. File 메뉴 열기...")
        pyautogui.hotkey('alt', 'f')
        time.sleep(0.5)

        # Step 6: E (Export)
        print("    6. Export...")
        pyautogui.press('e')
        time.sleep(0.5)

        # Step 7: C (CSV)
        print("    7. CSV 선택...")
        pyautogui.press('c')
        time.sleep(0.5)

        # Step 8: 방향키 아래 2번 (Signal export로 이동)
        print("    8. Signal export 선택...")
        pyautogui.press('down')
        time.sleep(0.2)
        pyautogui.press('down')
        time.sleep(0.3)

        # Step 9: Enter 2번 (Export 완료)
        print("    9. Export 실행...")
        pyautogui.press('enter')
        time.sleep(0.5)
        pyautogui.press('enter')
        time.sleep(2)  # Export 완료 대기

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

            time.sleep(0.5)

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

    # .D 폴더 찾기
    d_folders = find_all_d_folders()
    print(f"\n[확인] {len(d_folders)}개 .D 폴더 발견")

    # 출력 디렉토리
    output_dir = r"C:\Users\Jahyun\PycharmProjects\PeakPicker\exported_signals"
    os.makedirs(output_dir, exist_ok=True)

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
