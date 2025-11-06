# Feature 2: Peak Detection and Integration

## 개요

Peak Detection 모듈은 크로마토그램 데이터에서 피크를 자동으로 검출하고 적분하는 기능을 제공합니다.

## 주요 기능

### 1. 자동 Peak Detection
- **scipy 기반 알고리즘**: 신뢰할 수 있는 과학 라이브러리 사용
- **자동 threshold 계산**: 데이터 통계 기반으로 자동 설정
- **수동 파라미터 조정**: 세밀한 제어 가능

### 2. Peak Integration
- **Baseline correction**: 선형 baseline 자동 보정
- **Trapezoidal integration**: 정확한 면적 계산
- **Peak 경계 자동 탐지**: 시작점/끝점 자동 결정

### 3. Peak 정보
각 검출된 피크에 대해 다음 정보 제공:
- **RT (Retention Time)**: 피크 최대값의 retention time
- **RT Start/End**: 피크 시작/끝 시간
- **Height**: 피크 높이 (baseline 보정 후)
- **Area**: 피크 면적 (적분값)
- **Width**: 피크 너비 (FWHM 또는 지정된 높이에서)
- **% Area**: 전체 피크 면적 대비 비율

## 사용 방법

### 기본 사용

```python
from modules.peak_detector import PeakDetector, detect_and_integrate_peaks
import numpy as np

# 데이터 로드
time = np.array([...])
intensity = np.array([...])

# 방법 1: PeakDetector 클래스 사용
detector = PeakDetector(time, intensity, auto_threshold=True)
peaks = detector.detect_peaks()

for i, peak in enumerate(peaks, 1):
    print(f"Peak {i}:")
    print(f"  RT: {peak.rt:.3f} min")
    print(f"  Area: {peak.area:.2f}")
    print(f"  Height: {peak.height:.2f}")
    print(f"  Width: {peak.width:.3f} min")
    print(f"  % Area: {peak.percent_area:.2f}%")

# 방법 2: 편리한 함수 사용
peaks, summary = detect_and_integrate_peaks(time, intensity)
print(f"Detected {summary['num_peaks']} peaks")
print(f"Total area: {summary['total_area']:.2f}")
```

### 파라미터 조정

```python
# 수동 파라미터 설정
detector = PeakDetector(
    time,
    intensity,
    prominence=100,      # 피크 prominence (두드러진 정도)
    min_height=50,       # 최소 높이
    min_width=0.01,      # 최소 너비 (분)
    rel_height=0.5,      # 상대 높이 (0.5 = FWHM)
    auto_threshold=False # 자동 계산 비활성화
)
peaks = detector.detect_peaks()
```

### 특정 RT 검색

```python
# 특정 retention time 주변의 피크 찾기
target_peak = detector.get_peak_at_rt(
    target_rt=5.5,     # 목표 RT
    tolerance=0.1      # 허용 오차 (분)
)

if target_peak:
    print(f"Found peak at RT={target_peak.rt:.3f}")
else:
    print("No peak found")
```

### RT 범위 내 피크 검색

```python
# 특정 시간 범위의 모든 피크
peaks_in_range = detector.get_peaks_in_range(
    rt_start=3.0,
    rt_end=7.0
)
print(f"Found {len(peaks_in_range)} peaks between 3-7 min")
```

### 통계 정보

```python
summary = detector.get_summary()

print(f"Number of peaks: {summary['num_peaks']}")
print(f"Total area: {summary['total_area']:.2f}")
print(f"Average width: {summary['avg_peak_width']:.3f} min")
print(f"Average height: {summary['avg_peak_height']:.2f}")
print(f"Retention times: {summary['retention_times']}")
print(f"Peak areas: {summary['areas']}")
```

## 시각화

### 크로마토그램에 피크 표시

```python
from modules.visualizer import ChromatogramVisualizer

# 시각화 객체 생성
visualizer = ChromatogramVisualizer(figsize=(14, 6))

# 피크가 표시된 크로마토그램 플롯
fig = visualizer.plot_with_peaks(
    time,
    intensity,
    peaks,
    title="Chromatogram with Detected Peaks",
    show_baseline=True,      # baseline 표시
    annotate_peaks=True,     # 피크 번호 및 RT 표시
)

# 그림 저장
visualizer.save_figure("peaks_detected.png", dpi=300)
```

## 파라미터 가이드

### Prominence
- **의미**: 피크가 주변보다 얼마나 두드러져야 하는가
- **낮은 값**: 더 많은 피크 검출 (노이즈 포함 가능)
- **높은 값**: 주요 피크만 검출
- **권장**: 자동 계산 사용 또는 데이터 범위의 5-10%

### Min Height
- **의미**: 검출할 피크의 최소 높이
- **낮은 값**: 작은 피크도 검출
- **높은 값**: 큰 피크만 검출
- **권장**: 평균 + 1×표준편차

### Min Width
- **의미**: 피크의 최소 너비 (분 단위)
- **낮은 값**: 좁은 피크도 검출
- **높은 값**: 넓은 피크만 검출
- **권장**: 0.01 - 0.05 분 (데이터 해상도에 따라)

### Rel Height
- **의미**: 너비 계산 시 사용할 상대 높이
- **0.5**: FWHM (Full Width at Half Maximum)
- **0.1**: 피크 베이스 근처에서 너비 측정
- **0.9**: 피크 상단 근처에서 너비 측정

## 자동 Threshold 계산

`auto_threshold=True`로 설정하면:

```python
# Prominence 계산
prominence = max(
    intensity_range * 0.05,  # 전체 범위의 5%
    2 * std_deviation        # 또는 표준편차의 2배
)

# Min Height 계산
min_height = mean + std_deviation
```

## 테스트 결과

```
✅ Peak Detection: PASSED
✅ Convenience Function: PASSED
🎉 All tests passed!

Example output:
- Detected 1 peaks
- Peak 1: RT=4.040 min, Area=4044.76, Height=1754.31, Width=2.019 min
- Total area: 4044.76
```

## 문제 해결

### 피크가 너무 많이 검출되는 경우
```python
# prominence와 min_height를 높이기
detector = PeakDetector(
    time, intensity,
    prominence=200,  # 증가
    min_height=100,  # 증가
    auto_threshold=False
)
```

### 피크가 검출되지 않는 경우
```python
# prominence와 min_height를 낮추기
detector = PeakDetector(
    time, intensity,
    prominence=10,   # 감소
    min_height=5,    # 감소
    auto_threshold=False
)
```

### 노이즈 때문에 잘못된 피크 검출
```python
# min_width를 높여서 노이즈 필터링
detector = PeakDetector(
    time, intensity,
    min_width=0.05,  # 더 넓은 피크만 검출
    auto_threshold=True
)
```

## 예시 코드

전체 예시는 `examples/peak_detection_example.py` 참조

## API Reference

### PeakDetector 클래스

**생성자**
```python
PeakDetector(
    time: np.ndarray,
    intensity: np.ndarray,
    prominence: Optional[float] = None,
    min_height: Optional[float] = None,
    min_width: float = 0.01,
    rel_height: float = 0.5,
    auto_threshold: bool = True
)
```

**메서드**
- `detect_peaks() -> List[Peak]`: 피크 검출
- `get_peak_at_rt(target_rt, tolerance) -> Optional[Peak]`: 특정 RT의 피크 찾기
- `get_peaks_in_range(rt_start, rt_end) -> List[Peak]`: 범위 내 피크 찾기
- `get_summary() -> Dict`: 통계 정보 반환
- `integrate_range(rt_start, rt_end, baseline_correct) -> float`: 범위 적분

### Peak 데이터클래스

**속성**
- `rt: float` - Retention time (min)
- `rt_start: float` - 피크 시작 시간
- `rt_end: float` - 피크 끝 시간
- `height: float` - 피크 높이
- `area: float` - 피크 면적
- `width: float` - 피크 너비 (min)
- `percent_area: float` - 전체 대비 비율 (%)
- `index: int` - 데이터 배열 인덱스
- `index_start: int` - 시작 인덱스
- `index_end: int` - 끝 인덱스

## 다음 단계

- Feature 3에서 Baseline 수동 조정
- Feature 4에서 결과를 Excel로 출력
- Feature 5에서 정량 분석 수행
