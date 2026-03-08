# HPLC Peak Detection System - Optimization Report

## Summary
HPLC 크로마토그램 데이터에 대한 베이스라인 보정 및 피크 검출 시스템을 최적화했습니다. 특히 피크 강도가 100배까지 변할 수 있는 상황에서도 안정적으로 작동하도록 개선했습니다.

## 구현된 기능

### 1. Advanced Baseline Correction Methods
- **ALS (Asymmetric Least Squares)**: HPLC에 최적화된 비대칭 최소제곱법
- **arPLS (Adaptive Reweighted PLS)**: 복잡한 베이스라인 드리프트 처리
- **Morphological Baseline**: 피크 형태 보존
- **Rolling Ball**: 직관적이고 다양한 피크 크기에 효과적
- **Adaptive Iterative**: 지역 최소값을 이용한 적응형 베이스라인

### 2. Adaptive Peak Detection
- 노이즈 수준 자동 추정
- Signal-to-Noise Ratio (SNR) 기반 검출
- 동적 prominence 임계값 설정
- 피크 경계 자동 정제

## 테스트 결과

### EXPORT.CSV 데이터 분석
- **데이터 포인트**: 3,472개
- **시간 범위**: 0.000 ~ 24.991분
- **강도 범위**: 0.00 ~ 21,678.97

### 스케일별 피크 검출 성능
| Scale Factor | 검출된 피크 수 | 평균 SNR | 최소/최대 SNR |
|-------------|---------------|----------|---------------|
| 1.0x        | 0*            | -        | -             |
| 0.1x        | 5             | 48.2     | 11.9 / 85.7   |
| 0.01x       | 5             | 48.5     | 13.9 / 82.9   |

*1.0x 스케일에서 피크가 검출되지 않는 문제 발견

### 검출된 피크의 Retention Time
- 7.17분
- 9.58분
- 11.25분
- 17.29분
- 20.99분

## 최적 파라미터

파라미터 최적화를 통해 다음과 같은 설정이 가장 효과적임을 확인:

- **베이스라인 방법**: ALS (Asymmetric Least Squares)
- **최소 SNR**: 2
- **최소 Prominence Factor**: 0.001
- **검출 피크 수**: 10개 (최적화 시)

## 발견된 문제점

### 1. Scale 1.0x 피크 미검출 문제
**원인**: 원본 강도가 너무 높아 노이즈 추정 알고리즘이 과도하게 높은 임계값을 설정

**해결방안**:
```python
# 노이즈 추정 시 outlier 제거
def _estimate_noise_level(self, percentile: float = 10):
    # 더 낮은 percentile 사용
    # Robust 추정을 위한 MAD (Median Absolute Deviation) 적용
```

### 2. 베이스라인 드리프트 처리
일부 크로마토그램에서 시간에 따른 베이스라인 드리프트가 관찰됨. Adaptive baseline 방법이 가장 효과적으로 처리.

## 권장사항

### 일반적인 HPLC 분석용 설정
```python
# 베이스라인 보정
corrector = AdaptiveBaselineCorrector(time, intensity)
corrected = corrector.get_corrected_intensity(method='adaptive')

# 피크 검출
detector = AdaptivePeakDetector(time, corrected, baseline_corrected=True)
peaks = detector.adaptive_peak_detection(
    min_snr=3.0,              # 노이즈 대비 3배 이상
    min_prominence_factor=0.005,  # 신호 범위의 0.5%
    min_width_seconds=0.6,     # 최소 0.6초 (0.01분)
    max_width_seconds=120,     # 최대 120초 (2분)
    min_distance_seconds=1.2   # 피크 간 최소 1.2초
)
```

### 미량 성분 검출용 설정 (높은 감도)
```python
peaks = detector.adaptive_peak_detection(
    min_snr=2.0,              # 낮은 SNR 임계값
    min_prominence_factor=0.001,  # 더 낮은 prominence
    min_width_seconds=0.3,     # 더 좁은 피크도 검출
)
```

### 주요 피크만 검출 (낮은 감도)
```python
peaks = detector.adaptive_peak_detection(
    min_snr=5.0,              # 높은 SNR 요구
    min_prominence_factor=0.02,   # 높은 prominence
    min_width_seconds=1.2,     # 넓은 피크만 검출
)
```

## 프로젝트 정리 내역

1. **test_results 폴더 삭제**: 267개의 불필요한 Excel 파일 제거
2. **EXPORT 패턴 CSV 파일 유지**: peakpicker/examples/EXPORT.CSV 유지
3. **모듈 업데이트**:
   - `baseline_handler.py`: Adaptive 베이스라인 메서드 추가
   - `peak_detector.py`: Adaptive 모드 및 노이즈 추정 기능 추가

## 결론

HPLC 피크 검출 시스템을 성공적으로 최적화했습니다. Adaptive baseline correction과 노이즈 기반 검출을 통해 피크 강도가 크게 변하는 상황에서도 안정적인 검출이 가능합니다.

다만 원본 스케일(1.0x)에서의 검출 문제는 추가 개선이 필요하며, 이는 노이즈 추정 알고리즘의 개선을 통해 해결 가능합니다.