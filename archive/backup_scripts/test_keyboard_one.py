"""
키보드 단축키 테스트 - 1개 파일만
"""

import pyautogui
import pyperclip
import time
import os
import shutil

# 안전 설정
pyautogui.PAUSE = 0.3
pyautogui.FAILSAFE = True

def test_export_one():
    """1개 파일만 테스트"""

    print("=" * 80)
    print("  키보드 단축키 테스트 (1개 파일)")
    print("=" * 80)

    # 테스트 파일
    test_file = r"C:\Chem32\1\DATA\2. D-Xyl cascade HPLC\Ribavirin\Riba pH Main\251014_RIBA_PH_MAIN_GN9_3_6H.D"
    output_file = r"C:\Users\Jahyun\PycharmProjects\PeakPicker\test_keyboard_result.csv"

    print(f"\n테스트 파일: {test_file}")
    print(f"출력 파일: {output_file}")

    print("\n주의: Chemstation 창이 활성화되어 있어야 합니다!")
    print("5초 후 시작...")

    for i in range(5, 0, -1):
        print(f"  {i}...")
        time.sleep(1)

    print("\n단계별 실행:")

    # Step 1: Alt+F
    print("  1. Alt+F (File 메뉴)")
    pyautogui.hotkey('alt', 'f')
    time.sleep(0.5)

    # Step 2: Shift+G
    print("  2. Shift+G (Load Signal)")
    pyautogui.hotkey('shift', 'g')
    time.sleep(1)

    # Step 3: 파일 경로
    print("  3. 파일 경로 입력")
    pyperclip.copy(test_file)
    pyautogui.hotkey('ctrl', 'a')
    time.sleep(0.2)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.5)

    # Step 4: Enter
    print("  4. Enter (파일 열기)")
    pyautogui.press('enter')
    time.sleep(3)

    # Step 5: Alt+F
    print("  5. Alt+F (File 메뉴)")
    pyautogui.hotkey('alt', 'f')
    time.sleep(0.5)

    # Step 6: E
    print("  6. E (Export)")
    pyautogui.press('e')
    time.sleep(0.5)

    # Step 7: C
    print("  7. C (CSV)")
    pyautogui.press('c')
    time.sleep(0.5)

    # Step 8: 방향키 아래 2번
    print("  8. 방향키 아래 2번 (Signal export)")
    pyautogui.press('down')
    time.sleep(0.2)
    pyautogui.press('down')
    time.sleep(0.3)

    # Step 9: Enter 2번
    print("  9. Enter 2번 (Export 완료)")
    pyautogui.press('enter')
    time.sleep(0.5)
    pyautogui.press('enter')
    time.sleep(2)

    # Step 10: 파일 확인
    print("\n  10. Export 파일 확인 중...")
    temp_export = r"C:\Chem32\1\TEMP\export.csv"

    for i in range(20):
        if os.path.exists(temp_export):
            mtime = os.path.getmtime(temp_export)
            age = time.time() - mtime

            if age < 15:
                shutil.copy(temp_export, output_file)
                size = os.path.getsize(output_file)

                print(f"\n[성공] Export 완료!")
                print(f"  크기: {size:,} bytes")

                # 내용 확인
                import pandas as pd
                try:
                    df = pd.read_csv(output_file, sep='\t', encoding='utf-16-le', header=None)
                    print(f"  행 수: {len(df)}")
                    print(f"  값 범위: {df.iloc[:, 1].min():.2f} ~ {df.iloc[:, 1].max():.2f}")
                except:
                    print("  (파일 읽기 시도)")

                return True

        time.sleep(0.5)
        print(f"    대기 중... ({i+1}/20)")

    print("\n[실패] Export 파일이 생성되지 않음")
    return False

if __name__ == "__main__":
    try:
        test_export_one()
    except Exception as e:
        print(f"\n[오류] {e}")
        import traceback
        traceback.print_exc()
