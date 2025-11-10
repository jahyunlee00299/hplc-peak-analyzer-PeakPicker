"""일반 샘플 (비-STD) 워크플로우 테스트"""
from complete_workflow import WorkflowManager
from pathlib import Path
import shutil

# 테스트용 폴더 생성 (NV 샘플만 복사)
source_folder = Path(r"C:\Users\Jahyun\PycharmProjects\PeakPicker\result\DEF_LC 2025-05-19 17-57-25")
test_folder = Path(r"C:\Users\Jahyun\PycharmProjects\PeakPicker\result\TEST_NON_STD")

# 폴더 생성
test_folder.mkdir(parents=True, exist_ok=True)

# NV 샘플만 복사
for csv_file in source_folder.glob("NV*.csv"):
    shutil.copy(csv_file, test_folder / csv_file.name)
    print(f"복사: {csv_file.name}")

print(f"\n테스트 폴더 생성: {test_folder}")
print(f"NV 샘플 파일 수: {len(list(test_folder.glob('*.csv')))}")

# 워크플로우 실행
workflow = WorkflowManager()
workflow.output_folder = test_folder

if workflow.run_quantification():
    print("\n정량 분석 성공! 시각화 창을 표시합니다...")
    workflow.show_results_viewer()
else:
    print("\n정량 분석 실패")
