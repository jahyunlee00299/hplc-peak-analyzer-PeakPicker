# 완전 자동화 워크플로우 가이드

## 개요

`complete_workflow.py`는 HPLC 데이터 분석의 전체 과정을 자동화합니다:

```
Export (Chemstation) → 베이스라인 보정 → 피크 검출 → 정량 분석 → 시각화
```

## 빠른 시작

### 방법 1: Export부터 시작

Chemstation에서 직접 데이터를 추출하여 분석합니다.

```bash
python complete_workflow.py
```

1. 모드 선택에서 `1` 입력 (Export부터 시작)
2. Chemstation이 실행 중인지 확인 후 Enter
3. 폴더 탐색 모드 선택 (대화형/직접 경로/전체 스캔)
4. 자동으로 분석 및 시각화 완료

### 방법 2: 기존 폴더 분석

이미 export된 CSV 파일이 있는 경우:

```bash
python complete_workflow.py
```

1. 모드 선택에서 `2` 입력 (기존 폴더 분석)
2. 폴더 경로 입력: `result/DEF_LC 2025-05-19 17-57-25`
3. 자동으로 분석 및 시각화 완료

### 방법 3: 프로그래밍 방식

Python 코드에서 직접 호출:

```python
from complete_workflow import WorkflowManager
from pathlib import Path

workflow = WorkflowManager()
workflow.output_folder = Path("result/your_folder_name")

if workflow.run_quantification():
    workflow.show_results_viewer()
```

## 시각화 창 기능

분석이 완료되면 대화형 결과 뷰어가 표시됩니다:

### 탭 1: 검량선 (Calibration Curve)

- 농도별 피크 면적 그래프
- 선형 회귀선 (실측값 vs 참조값)
- R² 값 및 회귀식
- 반복 측정 분포

### 탭 2: 농도별 요약

- 농도별 통계 (평균, 표준편차, 샘플 수)
- RT, 높이, 면적 정보
- CSV 형식으로 정리된 표

### 탭 3: 전체 상세 데이터

- 모든 피크의 상세 정보
- 샘플명, 농도, RT, 높이, 면적, 폭 등
- 최대 500개 행 표시

### 하단 버튼

- **폴더 열기**: 결과가 저장된 폴더를 탐색기에서 열기
- **닫기**: 시각화 창 닫기

## 출력 결과

분석 결과는 `result/폴더명/quantification/`에 저장됩니다:

```
quantification/
├── calibration_curve.png       # 검량선 그래프
├── peak_area_summary.csv       # 농도별 요약 통계
└── all_peaks_detailed.csv      # 전체 피크 상세 정보
```

## 분석 파라미터

### 면적 계산 방법

- **경계 검출**: 베이스라인 복귀 지점 (noise_level * 2)
- **적분 방법**: Trapezoidal integration
- **시간 단위**: 초 (분 → 초 변환)
- **정확도**: 97% (참조값 대비)

### 검량선 비교

참조값 (Chemstation 또는 다른 기준):
- y0 (절편): 2173.0209
- a (기울기): 52004.0462

실측값과 자동 비교하여 차이를 % 단위로 표시합니다.

## 문제 해결

### Export 실패

- Chemstation이 실행 중인지 확인
- 올바른 데이터 폴더가 선택되었는지 확인
- 키보드 자동화 타이밍 조정 필요 시 `auto_export_keyboard_final.py` 수정

### 분석 실패

- CSV 파일이 올바른 형식인지 확인 (UTF-16 LE, tab-separated)
- 폴더 경로에 한글이 포함되어 있는지 확인
- 피크가 검출되지 않는 경우 신호 강도 확인

### 시각화 창이 뜨지 않음

- Tkinter가 설치되어 있는지 확인
- Pillow 라이브러리 설치: `pip install Pillow`
- matplotlib 버전 확인: `pip install --upgrade matplotlib`

## 고급 사용법

### 사용자 정의 파라미터

`quantify_peaks.py`의 `PeakQuantifier` 클래스에서 파라미터 조정:

```python
# 베이스라인 방법 선택
baseline_method = 'robust_fit'  # 또는 'weighted_spline'

# 피크 검출 민감도 조정
min_prominence = signal_range * 0.005
min_height = noise_level * 2

# 베이스라인 복귀 임계값
baseline_threshold = noise_level * 2
```

### 배치 분석

여러 폴더를 한 번에 분석:

```python
from complete_workflow import WorkflowManager
from pathlib import Path

folders = [
    "result/Experiment1",
    "result/Experiment2",
    "result/Experiment3"
]

for folder in folders:
    workflow = WorkflowManager()
    workflow.output_folder = Path(folder)
    workflow.run_quantification()
    # 시각화는 마지막에만 표시

# 마지막 결과 시각화
workflow.show_results_viewer()
```

## 참고

- 전체 프로세스는 일반적으로 1-2분 소요 (샘플 수에 따라 다름)
- 시각화 창을 닫으면 프로그램이 종료됩니다
- 분석 중 생성된 모든 CSV 파일은 Excel에서 열 수 있습니다
- 검량선 이미지는 PNG 형식으로 저장되어 보고서에 바로 삽입 가능합니다
