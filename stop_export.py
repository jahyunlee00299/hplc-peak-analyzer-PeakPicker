"""
Export 중단 유틸리티

이 스크립트를 실행하면 export_STOP.txt 파일을 생성하여
현재 실행 중인 auto_export_all.py를 중단시킵니다.
"""

import os

STOP_FILE = "export_STOP.txt"

if __name__ == "__main__":
    # STOP 파일 생성
    with open(STOP_FILE, 'w') as f:
        f.write("Export 중단 요청\n")
        f.write("이 파일이 감지되면 현재 파일 처리 완료 후 중단됩니다.\n")

    print("=" * 60)
    print(f"  [STOP FILE CREATED] '{STOP_FILE}' 생성됨")
    print("=" * 60)
    print("\n현재 실행 중인 export 프로세스가 현재 파일을")
    print("완료한 후 자동으로 중단됩니다.")
    print("\n중단까지 최대 수 초가 걸릴 수 있습니다.")
    print("=" * 60)
