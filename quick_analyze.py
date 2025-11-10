"""
빠른 분석 래퍼 - 폴더 경로만 입력하면 바로 분석 시작
"""
import sys
from pathlib import Path

# 가장 최근 폴더 자동 감지
def find_latest_result_folder():
    """result 폴더에서 가장 최근 폴더 찾기"""
    result_dir = Path('result')
    if not result_dir.exists():
        return None

    folders = [f for f in result_dir.iterdir() if f.is_dir()]
    if not folders:
        return None

    # 수정 시간 기준 최신 폴더
    latest = max(folders, key=lambda f: f.stat().st_mtime)
    return latest

if __name__ == '__main__':
    if len(sys.argv) > 1:
        # 폴더 경로가 주어진 경우
        folder_path = sys.argv[1]
    else:
        # 최근 폴더 자동 감지
        folder_path = find_latest_result_folder()
        if folder_path is None:
            print("[ERROR] result 폴더에서 분석할 폴더를 찾을 수 없습니다.")
            print("\n사용법:")
            print('  python quick_analyze.py "폴더경로"')
            print('  또는')
            print('  python quick_analyze.py  (최근 폴더 자동)')
            sys.exit(1)

        print(f"최근 폴더 자동 감지: {folder_path}")

    # complete_workflow.py를 폴더 경로와 함께 실행
    import subprocess
    subprocess.run([sys.executable, 'complete_workflow.py', str(folder_path)])
