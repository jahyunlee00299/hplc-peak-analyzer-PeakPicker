# Feature 4: Excel Results Export

## 개요

ExcelExporter 모듈은 피크 분석 결과를 전문적인 형식의 Excel 파일로 출력하는 기능을 제공합니다.

## 주요 기능

### 1. 단일 샘플 출력
- 피크 데이터, 메타데이터, 요약 통계를 포함한 multi-sheet Excel 파일
- 전문적인 formatting (색상, 테두리, 폰트)
- 타임스탬프 자동 추가

### 2. 배치 출력
- 여러 샘플을 한 번에 출력
- 샘플별 시트 자동 생성
- 샘플 간 비교 용이

### 3. 비교 출력
- 타겟 RT에서 샘플 간 피크 비교
- 상대 면적 계산
- RT tolerance 지정 가능

## ExcelExporter 사용법

### 1. 기본 설정

```python
from modules.excel_exporter import ExcelExporter

# Exporter 생성
exporter = ExcelExporter(output_dir="results")

# 커스텀 디렉토리 지정
exporter = ExcelExporter(output_dir="/path/to/output")
```

**출력 디렉토리:**
- 지정하지 않으면 현재 디렉토리 사용
- 디렉토리가 없으면 자동 생성
- 파일명에 타임스탬프 자동 추가

### 2. 단일 샘플 출력

가장 기본적인 사용법입니다.

```python
from modules.data_loader import DataLoader
from modules.peak_detector import PeakDetector
from modules.excel_exporter import ExcelExporter

# 데이터 로드 및 피크 검출
loader = DataLoader()
time, intensity = loader.load_file("sample.csv")

detector = PeakDetector(time, intensity, auto_threshold=True)
peaks = detector.detect_peaks()

# Excel 출력
exporter = ExcelExporter(output_dir="results")
output_file = exporter.export_peaks(
    peaks=peaks,
    filename="my_sample",
    sample_name="Sample 1"
)

print(f"Exported to: {output_file}")
```

**출력 파일 구조:**
- Sheet 1: **Metadata** - 샘플 정보 및 분석 조건
- Sheet 2: **Peak Data** - 모든 피크의 상세 정보
- Sheet 3: **Summary** - 요약 통계

### 3. 메타데이터 추가

분석 조건 등의 추가 정보를 포함할 수 있습니다.

```python
# 메타데이터 정의
metadata = {
    "Instrument": "HPLC-RID",
    "Column": "C18, 4.6x250mm",
    "Mobile Phase": "Water:MeOH (60:40)",
    "Flow Rate": "1.0 mL/min",
    "Temperature": "30°C",
    "Injection Volume": "10 μL",
    "Detection": "RID",
    "Analyst": "John Doe",
    "Date": "2025-01-06"
}

# 메타데이터와 함께 출력
output_file = exporter.export_peaks(
    peaks=peaks,
    filename="sample_with_metadata",
    sample_name="Sample 1",
    metadata=metadata
)
```

**메타데이터 활용:**
- 재현성을 위한 분석 조건 기록
- 추적성(traceability) 확보
- 보고서 작성 시 참고

### 4. 배치 출력

여러 샘플을 한 번에 처리할 때 유용합니다.

```python
from pathlib import Path

# 여러 샘플 처리
sample_files = [
    "sample1.csv",
    "sample2.csv",
    "sample3.csv"
]

batch_results = {}

for sample_file in sample_files:
    # 데이터 로드
    time, intensity = loader.load_file(sample_file)

    # 피크 검출
    detector = PeakDetector(time, intensity, auto_threshold=True)
    peaks = detector.detect_peaks()

    # 결과 저장
    sample_name = Path(sample_file).stem
    batch_results[sample_name] = peaks

# 배치 출력
output_file = exporter.export_batch_results(
    batch_results=batch_results,
    output_filename="batch_analysis"
)

print(f"Batch exported to: {output_file}")
```

**배치 출력 특징:**
- 각 샘플마다 별도의 시트 생성
- 첫 번째 시트에 전체 요약 포함
- 샘플 간 비교가 용이한 구조

### 5. 샘플 비교 출력

특정 RT에서 여러 샘플을 비교할 때 사용합니다.

```python
# 샘플별 피크 데이터
sample_peaks = {
    "Standard": standard_peaks,
    "Sample_1": sample1_peaks,
    "Sample_2": sample2_peaks,
    "Sample_3": sample3_peaks
}

# 타겟 RT 지정
target_rts = [2.5, 4.0, 5.5, 7.2]  # 관심 화합물의 RT

# 비교 출력
output_file = exporter.export_comparison(
    sample_peaks=sample_peaks,
    target_rts=target_rts,
    output_filename="rt_comparison",
    rt_tolerance=0.1  # ±0.1분 이내 피크 매칭
)

print(f"Comparison exported to: {output_file}")
```

**비교 출력 내용:**
- 각 타겟 RT에 대한 샘플별 피크 정보
- 면적의 상대값 (% area)
- RT 편차
- Missing peaks 표시

**RT tolerance 가이드:**
- **0.05**: 매우 정밀한 매칭 (좋은 재현성)
- **0.1**: 일반적인 HPLC 분석 (권장)
- **0.2**: 넓은 매칭 범위 (RT 편차가 큰 경우)

## Excel 출력 구조

### Sheet 1: Metadata

| 항목 | 값 |
|------|-----|
| Sample Name | Sample 1 |
| Analysis Date | 2025-01-06 14:30:00 |
| Number of Peaks | 8 |
| Total Area | 15234.56 |
| Instrument | HPLC-RID |
| ... | ... |

### Sheet 2: Peak Data

| Peak # | RT (min) | Area | Height | Width (min) | % Area | RT Start | RT End |
|--------|----------|------|--------|-------------|--------|----------|--------|
| 1 | 2.45 | 1234.5 | 456.7 | 0.12 | 8.1 | 2.39 | 2.51 |
| 2 | 4.02 | 3456.8 | 890.1 | 0.15 | 22.7 | 3.94 | 4.10 |
| ... | ... | ... | ... | ... | ... | ... | ... |

### Sheet 3: Summary

| 통계 | 값 |
|------|-----|
| Total Peaks | 8 |
| Total Area | 15234.56 |
| Average RT | 4.52 |
| Average Area | 1904.32 |
| Largest Peak RT | 4.02 |
| Largest Peak Area | 3456.8 |

## 통합 워크플로우

### 전체 분석 파이프라인

```python
from modules.data_loader import DataLoader
from modules.baseline_handler import BaselineHandler
from modules.peak_detector import PeakDetector
from modules.excel_exporter import ExcelExporter

# 1. 데이터 로드
loader = DataLoader()
time, intensity = loader.load_file("sample.csv")

# 2. Baseline 보정
handler = BaselineHandler(time, intensity)
baseline = handler.calculate_als_baseline()
corrected = handler.apply_baseline_correction()

# 3. 피크 검출
detector = PeakDetector(time, corrected, auto_threshold=True)
peaks = detector.detect_peaks()

# 4. Excel 출력
exporter = ExcelExporter(output_dir="results")

metadata = {
    "Instrument": "HPLC-RID",
    "Baseline Method": "ALS",
    "Detection": "Auto threshold"
}

output_file = exporter.export_peaks(
    peaks=peaks,
    filename="final_result",
    sample_name="Sample 1",
    metadata=metadata
)

print(f"✓ Analysis complete: {output_file}")
```

### 정량 분석 결과 출력

```python
from modules.quantification import QuantitativeAnalyzer

# 검량선 생성
analyzer = QuantitativeAnalyzer()
analyzer.create_standard_curve(
    concentrations=[0, 1, 2.5, 5, 10],
    areas=[0, 100, 250, 500, 1000]
)

# 피크 검출
peaks = detector.detect_peaks()

# 농도 계산
for peak in peaks:
    peak.concentration = analyzer.calculate_concentration(
        peak.area,
        dilution_factor=5.0
    )

# Excel 출력 (농도 정보 포함)
metadata = {
    "Dilution Factor": "5x",
    "Standard Curve": "Linear, R²=0.9999",
    "Units": "mg/L"
}

output_file = exporter.export_peaks(peaks, "quantitative_result", "Sample 1", metadata)
```

## Formatting 커스터마이징

현재 버전에서는 기본 formatting이 적용됩니다:

**헤더:**
- 배경색: 진한 파랑 (#4472C4)
- 폰트: 흰색, 굵게
- 테두리: 얇은 검정색

**데이터 셀:**
- 교차 행 음영 (밝은 회색)
- 숫자 형식: 소수점 2-4자리
- 자동 열 너비 조정

**요약 시트:**
- 강조 색상: 연한 녹색 (#E2EFDA)
- 키 통계 굵게 표시

## 모범 사례

### 파일명 규칙

```python
# 타임스탬프 자동 추가
output_file = exporter.export_peaks(
    peaks,
    filename="sample1"  # → sample1_20250106_143000.xlsx
)

# 날짜별 정리
from datetime import datetime
date_str = datetime.now().strftime("%Y%m%d")
output_file = exporter.export_peaks(
    peaks,
    filename=f"{date_str}_sample1"
)
```

### 메타데이터 템플릿

```python
# 재사용 가능한 메타데이터 템플릿
metadata_template = {
    "Instrument": "HPLC-RID",
    "Column": "C18, 4.6x250mm",
    "Mobile Phase": "Water:MeOH (60:40)",
    "Flow Rate": "1.0 mL/min"
}

# 샘플별 추가 정보
for sample_id in samples:
    metadata = metadata_template.copy()
    metadata["Sample ID"] = sample_id
    metadata["Injection Time"] = get_injection_time(sample_id)

    exporter.export_peaks(peaks, sample_id, sample_id, metadata)
```

### 배치 처리 최적화

```python
# 대량 샘플 처리
import os

data_dir = "raw_data"
output_dir = "results"

# 모든 CSV 파일 처리
batch_results = {}

for filename in os.listdir(data_dir):
    if filename.endswith(".csv"):
        filepath = os.path.join(data_dir, filename)

        # 분석
        time, intensity = loader.load_file(filepath)
        detector = PeakDetector(time, intensity)
        peaks = detector.detect_peaks()

        # 결과 저장
        sample_name = os.path.splitext(filename)[0]
        batch_results[sample_name] = peaks

# 한 번에 출력
exporter.export_batch_results(batch_results, "batch_analysis")
```

## 문제 해결

### Excel 파일이 열리지 않는 경우

```python
# openpyxl이 설치되어 있는지 확인
import openpyxl
print(openpyxl.__version__)  # 3.0.0 이상 권장

# 파일 경로에 특수문자 확인
output_file = exporter.export_peaks(
    peaks,
    filename="sample_1"  # 공백 대신 밑줄 사용
)
```

### 메모리 부족 (대용량 배치)

```python
# 샘플을 그룹으로 나누어 처리
batch_size = 10

for i in range(0, len(all_samples), batch_size):
    batch = all_samples[i:i+batch_size]

    batch_results = {}
    for sample in batch:
        # 처리...
        batch_results[sample.name] = peaks

    # 배치별 출력
    exporter.export_batch_results(
        batch_results,
        f"batch_{i//batch_size + 1}"
    )
```

### 한글 깨짐 문제

openpyxl은 UTF-8을 기본으로 사용하므로 한글이 정상적으로 표시됩니다.

```python
metadata = {
    "분석자": "홍길동",
    "시료명": "표준물질 1",
    "비고": "반복 측정 3회"
}

# 한글 정상 출력됨
exporter.export_peaks(peaks, "한글파일명", "샘플 1", metadata)
```

## 테스트 결과

```
✅ Peak Export: PASSED
✅ Batch Export: PASSED
✅ Comparison Export: PASSED
🎉 All tests passed (3/3)!
```

## 다음 단계

- Feature 5에서 정량 결과를 Excel에 포함
- 차트 자동 생성 (피크 분포, 농도 그래프)
- PDF 리포트 생성
- 템플릿 커스터마이징 기능

## 예시 코드

전체 예시는 `examples/excel_export_example.py` 참조

## API Reference

### ExcelExporter 클래스

```python
class ExcelExporter:
    def __init__(self, output_dir: str = ".")
        """
        Args:
            output_dir: 출력 디렉토리 경로
        """

    def export_peaks(self, peaks: List[Peak], filename: str,
                    sample_name: str, metadata: Dict = None) -> str:
        """단일 샘플 출력

        Args:
            peaks: Peak 객체 리스트
            filename: 파일명 (확장자 제외)
            sample_name: 샘플 이름
            metadata: 추가 메타데이터

        Returns:
            출력된 파일의 전체 경로
        """

    def export_batch_results(self, batch_results: Dict[str, List[Peak]],
                           output_filename: str) -> str:
        """배치 출력

        Args:
            batch_results: {샘플명: Peak 리스트} 딕셔너리
            output_filename: 출력 파일명

        Returns:
            출력된 파일의 전체 경로
        """

    def export_comparison(self, sample_peaks: Dict[str, List[Peak]],
                         target_rts: List[float],
                         output_filename: str,
                         rt_tolerance: float = 0.1) -> str:
        """샘플 비교 출력

        Args:
            sample_peaks: {샘플명: Peak 리스트} 딕셔너리
            target_rts: 타겟 RT 리스트
            output_filename: 출력 파일명
            rt_tolerance: RT 매칭 허용 오차

        Returns:
            출력된 파일의 전체 경로
        """
```

## 관련 문서

- [Feature 2: Peak Detection](FEATURE_2_PEAK_DETECTION.md)
- [Feature 3: Baseline Correction](FEATURE_3_BASELINE_PEAK_HANDLING.md)
- [Feature 5: Quantitative Analysis](FEATURE_5_QUANTIFICATION.md)
- [전체 기능 요약](ALL_FEATURES_SUMMARY.md)
