"""워크플로우 테스트 - 기존 폴더로 분석"""
from complete_workflow import WorkflowManager
from pathlib import Path

# 워크플로우 매니저 생성
workflow = WorkflowManager()

# 기존 폴더 지정
workflow.output_folder = Path(r"C:\Users\Jahyun\PycharmProjects\PeakPicker\result\DEF_LC 2025-05-19 17-57-25")

# 정량 분석 실행
if workflow.run_quantification():
    print("\n정량 분석 성공! 시각화 창을 표시합니다...")
    # 시각화 창 표시
    workflow.show_results_viewer()
else:
    print("\n정량 분석 실패")
