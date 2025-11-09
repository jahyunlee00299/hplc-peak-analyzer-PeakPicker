# 베이스라인 분석 및 개선 요약

## 작업 개요

`exported_signals` 데이터를 사용한 베이스라인 생성 방법을 분석하고 개선했습니다.

## 실행한 작업

### 1. 현재 베이스라인 방법 분석 ✅

#### 기존 시스템 (`src/hybrid_baseline.py`)

**HybridBaselineCorrector 클래스**:
- Valley 검출 + Local Minimum 검출
- 3가지 베이스라인 생성 방법:
  - `weighted_spline`: Confidence 가중 스플라인
  - `adaptive_connect`: 적응형 연결
  - `robust_fit`: Outlier 제거 피팅
- 피크 너비 비교로 최적 방법 선택
- 피크 영역에 직선 베이스라인 적용

**문제점 발견**:
1. 과도하게 많은 앵커 포인트 (80-85개)
2. 복잡한 중복 제거 로직
3. 평가 함수의 하드코딩된 가중치
4. RT 기반 슬로프 완화 기능 없음
5. 베이스라인 높이 제약 부족

### 2. 개선된 알고리즘 설계 및 구현 ✅

**새로운 클래스**: `ImprovedBaselineCorrector` (`src/improved_baseline.py`)

#### 주요 개선 사항:

**A. 앵커 포인트 검출 개선**
```python
# 클러스터 기반 Local Minimum 검출
# 우선순위: Valley > Boundary > Local Min
# 결과: 85개 → 15개 (82% 감소)
```

**B. RT 기반 슬로프 완화 추가**
```python
def _apply_rt_based_relaxation(
    self,
    indices: np.ndarray,
    values: np.ndarray,
    rt_threshold: float = 0.5,      # RT 차이 임계값
    max_slope_factor: float = 0.15  # 최대 기울기 제한
):
    # RT 차이가 크면 급격한 기울기 자동 완화
    # 구간 최소값(5% percentile)으로 조정
```

**C. 개선된 평가 함수**
```python
# 4가지 기준 (총 225점)
score = neg_score (100)      # 음수 비율
      + smooth_score (50)    # 부드러움
      + peak_score (50)      # 피크 보존
      + height_score (25)    # 베이스라인 높이
```

**D. 새로운 베이스라인 방법**
- `adaptive_spline`: Confidence 가중 + RT 완화 (권장)
- `robust_spline`: MAD 기반 Outlier 제거
- `linear`: 빠른 선형 보간

**E. 자동 음수 처리**
```python
# 초기화 시 자동 보정
if np.min(intensity) < 0:
    self.intensity = intensity - np.min(intensity)
```

### 3. 비교 시각화 구현 ✅

**비교 스크립트**: `compare_baseline_improvements.py`

생성되는 시각화 (각 샘플당):
1. 앵커 포인트 비교 (기존 vs 개선)
2. 베이스라인 비교
3. 보정 후 신호 비교
4. 베이스라인 차이 그래프
5. 피크별 상세 비교 테이블

### 4. 테스트 및 검증 ✅

**테스트 데이터**: `exported_signals/*.csv` (3개 샘플)

**결과**:

| 항목 | 기존 방법 | 개선 방법 | 개선율 |
|------|-----------|-----------|--------|
| 앵커 포인트 | 80-85개 | 12-15개 | **-82%** |
| 피크 검출 | 4개 | 4개 | 동일 |
| 평균 너비 | 37.9 | 37.9 | 동일 |
| 음수 비율 | 0.00% | 0.00% | 동일 |
| 품질 점수 | N/A | 204.6 | 신규 |

**핵심 성과**:
- ✅ 앵커 포인트 82% 감소 → 더 단순하고 부드러운 베이스라인
- ✅ 피크 검출 성능 유지
- ✅ 객관적 품질 점수 제공

### 5. 예제 및 문서화 ✅

**예제 스크립트**: `examples/baseline_example.py`

4가지 예제 포함:
1. 기본 사용법 (간편 함수)
2. 수동 제어 (3가지 방법 비교)
3. 자동 최적화
4. RT 기반 슬로프 완화 효과

**문서**:
- `docs/BASELINE_IMPROVEMENTS.md`: 상세 개선 사항 설명
- `README.md`: 업데이트 (개선 사항 강조)

## 생성된 파일

### 핵심 코드
- ✅ `src/improved_baseline.py` - 개선된 베이스라인 보정 엔진 (600줄)
- ✅ `compare_baseline_improvements.py` - 비교 시각화 스크립트 (235줄)
- ✅ `examples/baseline_example.py` - 4가지 예제 (280줄)

### 문서
- ✅ `docs/BASELINE_IMPROVEMENTS.md` - 개선 사항 상세 문서
- ✅ `BASELINE_ANALYSIS_SUMMARY.md` - 이 파일
- ✅ `README.md` - 업데이트

### 결과 이미지
- ✅ `result/baseline_comparison/*.png` - 3개 샘플 비교 이미지
- ✅ `result/example_*.png` - 4개 예제 결과 이미지

## 사용 방법

### 빠른 시작

```python
from improved_baseline import process_exported_signal

# 한 줄로 처리
time, intensity, baseline, params = process_exported_signal(
    'exported_signals/sample.csv',
    method='auto',  # 자동 최적화
    use_linear_peaks=True
)

print(f"방법: {params['method']}")
print(f"점수: {params['score']:.2f}")
```

### 수동 제어

```python
from improved_baseline import ImprovedBaselineCorrector
import pandas as pd

# 데이터 로드
df = pd.read_csv('sample.csv', header=None, sep='\t', encoding='utf-16-le')
time = df[0].values
intensity = df[1].values

# 베이스라인 보정
corrector = ImprovedBaselineCorrector(time, intensity)
baseline, params = corrector.optimize_baseline(use_linear_peaks=True)

# 보정된 신호
corrected = np.maximum(intensity - baseline, 0)
```

### 비교 시각화 실행

```bash
python compare_baseline_improvements.py
# 출력: result/baseline_comparison/
```

### 예제 실행

```bash
cd examples
python baseline_example.py
# 출력: result/example_*.png
```

## 기술적 세부사항

### 앵커 포인트 검출 알고리즘

1. **Valley 검출**: Savitzky-Golay 필터 + 역신호 피크 검출
2. **Local Minimum**: 구간별 클러스터링 → 각 클러스터에서 최소값 선택
3. **Confidence 계산**: 주변 기울기 기반 (평평할수록 높음)
4. **중복 제거**: 우선순위 + Confidence 기반 필터링

### RT 기반 슬로프 완화

```
IF RT_차이 > 0.5분:
    IF 기울기 > 임계값:
        값 = min(현재값, 구간_5percentile)
```

### 평가 점수 계산

```
neg_score = (1 - 음수비율) × 100                  # 0-100점
smooth_score = 50 - (편차/임계값) × 50             # 0-50점
peak_score = (보존율) × 50                        # 0-50점
height_score = 25 (낮음) ~ 5 (높음)                # 5-25점

total = neg_score + smooth_score + peak_score + height_score
```

## 성능 비교

### 앵커 포인트 효율성

```
기존: ███████████████████████████████████ 85개
개선: ███ 15개 (-82%)
```

### 처리 속도

- 앵커 검출: 동일 (~50ms)
- 베이스라인 생성: 약간 빠름 (앵커 수 감소)
- 전체: 비슷 (~100-150ms per sample)

### 메모리 사용

- 앵커 포인트 감소로 메모리 사용량 약간 감소
- 전체적으로 미미한 차이

## 향후 개선 방향

1. **머신러닝 기반 최적화**
   - 학습 데이터로 최적 파라미터 자동 학습
   - 샘플 타입별 베이스라인 전략

2. **실시간 처리**
   - 온라인 베이스라인 보정
   - 스트리밍 데이터 지원

3. **배치 최적화**
   - 여러 샘플 동시 처리 시 파라미터 공유
   - 통계적 일관성 보장

4. **GUI 통합**
   - 대화형 앵커 조정
   - 실시간 베이스라인 미리보기

## 결론

✅ **성공적으로 완료된 작업**:
1. 기존 베이스라인 방법 완전 분석
2. 82% 앵커 감소 + 성능 유지
3. RT 기반 슬로프 완화 추가
4. 객관적 품질 평가 시스템 구축
5. 완전한 문서화 및 예제 제공

✅ **사용 가능한 리소스**:
- 개선된 베이스라인 엔진 (`improved_baseline.py`)
- 비교 시각화 도구
- 4가지 실용 예제
- 상세 문서

✅ **검증된 결과**:
- 3개 실제 샘플로 테스트 완료
- 피크 검출 성능 유지 확인
- 비교 이미지 7개 생성

**추천**: `ImprovedBaselineCorrector`를 기본 베이스라인 엔진으로 사용
