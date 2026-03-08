# Feature 3: Baseline Correction and Peak Splitting

## 개요

Baseline Correction과 Peak Splitting 모듈은 크로마토그램의 베이스라인을 보정하고, 겹친 피크를 분리하는 기능을 제공합니다.

## 주요 기능

### 1. Baseline Correction
- **Linear Baseline**: 시작과 끝점을 이은 직선
- **Polynomial Baseline**: 다항식 fitting (조정 가능한 차수)
- **ALS Baseline**: Asymmetric Least Squares (고급 알고리즘)
- **Manual Baseline**: 사용자 지정 anchor points

### 2. Peak Splitting
- **자동 분할**: Local minimum에서 피크 분할
- **수동 분할**: 지정된 RT에서 분할
- **Overlap 탐지**: 겹친 피크 자동 감지

## BaselineHandler 사용법

### 1. Linear Baseline

가장 간단한 방법으로, 시작점과 끝점을 잇는 직선입니다.

```python
from modules.baseline_handler import BaselineHandler
import numpy as np

# 데이터 로드
time = np.array([...])
intensity = np.array([...])

# Baseline handler 생성
handler = BaselineHandler(time, intensity)

# Linear baseline 계산
baseline = handler.calculate_linear_baseline()

# 특정 시간 범위 지정
baseline = handler.calculate_linear_baseline(
    start_time=1.0,  # 시작 시간
    end_time=5.0     # 끝 시간
)

# Baseline correction 적용
corrected = handler.apply_baseline_correction()

print(f"Original range: {intensity.min():.2f} - {intensity.max():.2f}")
print(f"Corrected range: {corrected.min():.2f} - {corrected.max():.2f}")
```

### 2. Polynomial Baseline

곡선 형태의 baseline에 적합합니다.

```python
# Polynomial baseline (degree 조정 가능)
baseline = handler.calculate_polynomial_baseline(degree=3)

# 다양한 차수 시도
for degree in [2, 3, 5]:
    baseline = handler.calculate_polynomial_baseline(degree=degree)
    corrected = handler.apply_baseline_correction()
    print(f"Degree {degree}: corrected range {corrected.min():.2f} - {corrected.max():.2f}")
```

**차수 선택 가이드:**
- **degree=2**: 완만한 곡선, 단순한 drift
- **degree=3**: 일반적인 경우에 적합
- **degree=5**: 복잡한 baseline 패턴

### 3. ALS (Asymmetric Least Squares) Baseline

가장 정교한 baseline 보정 방법입니다.

```python
# ALS baseline 계산
baseline = handler.calculate_als_baseline(
    lam=1e6,   # Smoothness parameter (높을수록 smooth)
    p=0.01,    # Asymmetry parameter (0-1)
    niter=10   # 반복 횟수
)

corrected = handler.apply_baseline_correction()
```

**파라미터 가이드:**
- **lam**:
  - 1e4: 약한 smoothing, baseline이 데이터를 따라감
  - 1e6: 중간 (기본값, 권장)
  - 1e8: 강한 smoothing, 매우 smooth한 baseline

- **p**:
  - 0.001: 피크 위쪽을 더 무시 (피크가 많을 때)
  - 0.01: 균형잡힌 설정 (기본값)
  - 0.1: 피크 아래쪽을 더 무시

### 4. Manual Baseline

사용자가 직접 지정한 점들을 연결하여 baseline을 만듭니다.

```python
# Anchor points 정의 (time, intensity)
anchor_points = [
    (0.0, 10.0),    # 시작점
    (2.0, 50.0),    # 중간점 1
    (5.0, 30.0),    # 중간점 2
    (8.0, 15.0)     # 끝점
]

# Manual baseline 생성
baseline = handler.manual_baseline(anchor_points)

# Correction 적용
corrected = handler.apply_baseline_correction()
```

**사용 시나리오:**
- 자동 방법으로 만족스럽지 않은 결과
- 특정 영역에 대한 정밀한 제어 필요
- 알려진 baseline drift 패턴

## PeakSplitter 사용법

### 1. 자동 Peak Splitting

겹친 피크를 local minimum에서 자동으로 분할합니다.

```python
from modules.peak_splitter import PeakSplitter
from modules.peak_detector import PeakDetector

# 피크 검출
detector = PeakDetector(time, intensity)
peaks = detector.detect_peaks()

# Peak splitter 생성
splitter = PeakSplitter(time, intensity)

# 첫 번째 피크 분할
peak1, peak2 = splitter.split_peak_at_minimum(peaks[0])

print(f"Peak 1: RT={peak1.rt:.3f}, Area={peak1.area:.2f}")
print(f"Peak 2: RT={peak2.rt:.3f}, Area={peak2.area:.2f}")
```

### 2. 수동 Peak Splitting

지정된 RT에서 피크를 분할합니다.

```python
# 특정 RT에서 분할
split_rt = 3.5  # 분할 지점의 retention time

peak1, peak2 = splitter.split_peak_at_minimum(
    peaks[0],
    split_rt=split_rt
)

print(f"Split at RT={split_rt}")
print(f"Peak 1: {peak1.rt_start:.3f} - {peak1.rt:.3f} - {peak1.rt_end:.3f}")
print(f"Peak 2: {peak2.rt_start:.3f} - {peak2.rt:.3f} - {peak2.rt_end:.3f}")
```

### 3. Overlap Detection

겹친 피크를 자동으로 감지합니다.

```python
# 피크들 검출
detector = PeakDetector(time, intensity)
peaks = detector.detect_peaks()

# Overlap 감지
splitter = PeakSplitter(time, intensity)
overlapping_pairs = splitter.detect_overlapping_peaks(
    peaks,
    overlap_threshold=0.5  # 50% 이상 겹치면 탐지
)

print(f"Found {len(overlapping_pairs)} overlapping peak pairs")

for peak1_idx, peak2_idx in overlapping_pairs:
    print(f"Peak {peak1_idx+1} overlaps with Peak {peak2_idx+1}")

    # 필요시 분할
    peak1_split, peak2_split = splitter.split_peak_at_minimum(peaks[peak1_idx])
```

## 통합 워크플로우

### Baseline Correction → Peak Detection

```python
from modules.baseline_handler import BaselineHandler
from modules.peak_detector import PeakDetector

# 1. Baseline correction
handler = BaselineHandler(time, intensity)
baseline = handler.calculate_als_baseline()
corrected_intensity = handler.apply_baseline_correction()

# 2. Peak detection on corrected data
detector = PeakDetector(time, corrected_intensity)
peaks = detector.detect_peaks()

print(f"Detected {len(peaks)} peaks after baseline correction")
```

### Peak Detection → Overlap Check → Splitting

```python
from modules.peak_detector import PeakDetector
from modules.baseline_handler import PeakSplitter

# 1. Peak detection
detector = PeakDetector(time, intensity)
peaks = detector.detect_peaks()

# 2. Check for overlaps
splitter = PeakSplitter(time, intensity)
overlaps = splitter.detect_overlapping_peaks(peaks)

# 3. Split overlapping peaks
all_peaks = []
processed_indices = set()

for peak_idx, (i, j) in enumerate(overlaps):
    if i not in processed_indices:
        # Split the overlapping peak
        peak1, peak2 = splitter.split_peak_at_minimum(peaks[i])
        all_peaks.extend([peak1, peak2])
        processed_indices.add(i)
        processed_indices.add(j)

# Add non-overlapping peaks
for i, peak in enumerate(peaks):
    if i not in processed_indices:
        all_peaks.append(peak)

print(f"Total peaks after splitting: {len(all_peaks)}")
```

## 시각화

### Baseline과 함께 표시

```python
from modules.visualizer import ChromatogramVisualizer
import matplotlib.pyplot as plt

# Baseline 계산
handler = BaselineHandler(time, intensity)
baseline = handler.calculate_als_baseline()
corrected = handler.apply_baseline_correction()

# 시각화
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

# Original with baseline
ax1.plot(time, intensity, 'b-', label='Original')
ax1.plot(time, baseline, 'r--', label='Baseline')
ax1.set_title('Original Chromatogram with Baseline')
ax1.legend()
ax1.grid(True, alpha=0.3)

# Corrected
ax2.plot(time, corrected, 'g-', label='Corrected')
ax2.set_title('Baseline-Corrected Chromatogram')
ax2.set_xlabel('Retention Time (min)')
ax2.set_ylabel('Intensity')
ax2.legend()
ax2.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('baseline_correction.png', dpi=300)
```

## 테스트 결과

```
✅ Linear Baseline: PASSED
✅ Polynomial Baseline: PASSED
✅ ALS Baseline: PASSED
✅ Manual Baseline: PASSED
✅ Peak Splitting: PASSED
✅ Overlap Detection: PASSED
🎉 All tests passed (6/6)!
```

## 모범 사례

### Baseline 방법 선택

1. **Linear**:
   - 짧은 시간 범위
   - Baseline이 거의 평평한 경우
   - 빠른 처리 필요

2. **Polynomial**:
   - 중간 정도의 drift
   - Baseline이 곡선 형태
   - 제어 가능한 파라미터 원할 때

3. **ALS**:
   - 복잡한 baseline 패턴
   - 최고 품질의 correction 필요
   - 처리 시간이 충분할 때

4. **Manual**:
   - 자동 방법으로 불가능한 경우
   - 특정 영역에 정밀한 제어 필요
   - Baseline 패턴을 알고 있을 때

### Peak Splitting 시기

- **자동 splitting 사용**:
  - Shoulder peaks
  - 명확한 local minimum 존재
  - 대량의 샘플 처리

- **수동 splitting 사용**:
  - 알려진 화합물의 RT
  - 자동 방법이 실패할 때
  - 정밀한 제어 필요

## 문제 해결

### Baseline이 피크를 너무 따라가는 경우
```python
# ALS의 lam 값을 높이기
baseline = handler.calculate_als_baseline(lam=1e8)  # 더 smooth
```

### Baseline이 너무 평평한 경우
```python
# lam 값을 낮추기
baseline = handler.calculate_als_baseline(lam=1e4)  # 더 flexible
```

### Peak splitting이 잘못된 위치에서 발생
```python
# 수동으로 split 지점 지정
peak1, peak2 = splitter.split_peak_at_minimum(
    peak,
    split_rt=정확한_RT값
)
```

## 다음 단계

- Feature 4에서 결과를 Excel로 출력
- Feature 5에서 정량 분석 수행
- Streamlit UI에서 인터랙티브 baseline 조정

## 예시 코드

전체 예시는 `examples/baseline_example.py` 참조
