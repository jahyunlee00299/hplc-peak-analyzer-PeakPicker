"""개별 크로마토그램 포함 워크플로우 테스트"""
from complete_workflow import WorkflowManager
from pathlib import Path

# 워크플로우 매니저 생성
workflow = WorkflowManager()

# 테스트 폴더 지정
workflow.output_folder = Path(r"C:\Users\Jahyun\PycharmProjects\PeakPicker\result\TEST_NON_STD")

# 정량 분석 실행
if workflow.run_quantification():
    print("\n정량 분석 성공! 시각화 창을 표시합니다...")
    # 시각화 창 표시
    workflow.show_results_viewer()
else:
    print("\n정량 분석 실패")
