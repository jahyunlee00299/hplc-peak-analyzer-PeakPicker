# 베이스라인 알고리즘 개선 사항

## 개요

`exported_signals` 데이터에 대한 베이스라인 보정 알고리즘을 분석하고 개선했습니다.

## 주요 개선 사항

### 1. 앵커 포인트 검출 개선

#### 기존 방법 (HybridBaselineCorrector)
- **문제점**: 과도하게 많은 앵커 포인트 생성 (80-85개)
- Valley와 Local Minimum을 모두 찾지만 중복 제거 로직이 비효율적
- 불필요한 앵커가 많아 베이스라인이 복잡해짐

#### 개선 방법 (ImprovedBaselineCorrector)
- **결과**: 최적화된 앵커 포인트 (12-15개)
- 클러스터 기반 Local Minimum 검출
- 우선순위 기반 중복 제거 (Valley > Boundary > Local Min)
- Confidence 기반 품질 평가

```python
# 개선된 앵커 검출
corrector = ImprovedBaselineCorrector(time, intensity)
anchors = corrector.find_anchors(
    valley_prominence_factor=0.01,
    local_min_percentile=10,
    min_anchor_distance=15
)
```

### 2. RT 기반 슬로프 완화

#### 새로운 기능
인접 앵커 간 RT 차이가 클 때 급격한 기울기를 자동으로 완화합니다.

```python
# RT 차이가 0.5분 이상이면 기울기 완화
baseline = corrector.generate_baseline(
    method='adaptive_spline',
    apply_rt_relaxation=True  # RT 기반 완화 활성화
)
```

**작동 원리**:
- RT 차이 > 0.5분: 기울기 검사
- 기울기가 너무 크면: 구간 최소값(5% percentile)으로 조정
- 결과: 더 부드럽고 안정적인 베이스라인

### 3. 개선된 평가 함수

#### 기존 방법
```python
score = (1 - neg_ratio) * 100 + peak_preservation * 50 - smoothness
```
- 단순한 가중치
- 베이스라인 높이 고려 안함

#### 개선 방법
```python
# 4가지 기준으로 평가 (총 225점 만점)
score = neg_score (100점)      # 음수 비율
      + smooth_score (50점)    # 부드러움
      + peak_score (50점)      # 피크 보존
      + height_score (25점)    # 베이스라인 높이
```

- 더 세밀한 평가
- 베이스라인이 너무 높으면 감점
- 각 기준별 적절한 가중치 적용

### 4. 효율적인 베이스라인 생성

#### 방법 종류

**adaptive_spline** (권장):
- Confidence 가중치 + RT 기반 완화
- 적응형 스플라인 피팅
- 가장 균형잡힌 결과

**robust_spline**:
- Outlier 자동 제거 (MAD 기반)
- 강건한 피팅
- 노이즈가 많은 데이터에 효과적

**linear**:
- 단순 선형 보간
- 빠른 처리 속도

### 5. 자동 음수 처리

```python
# 초기화 시 자동으로 음수 처리
corrector = ImprovedBaselineCorrector(time, intensity)
# 내부적으로 음수 값 자동 보정
```

## 성능 비교

### 테스트 결과 (3개 샘플)

| 지표 | 기존 방법 | 개선 방법 | 개선율 |
|------|-----------|-----------|--------|
| 앵커 포인트 | 80-85개 | 12-15개 | **-82%** |
| 피크 검출 | 4개 | 4개 | 동일 |
| 평균 피크 너비 | 37.9 | 37.9 | 동일 |
| 음수 비율 | 0.00% | 0.00% | 동일 |
| 품질 점수 | N/A | 204.6 | N/A |

### 주요 장점

1. **단순성**: 앵커 포인트 82% 감소 → 더 부드러운 베이스라인
2. **정확성**: 피크 검출 성능 유지
3. **안정성**: RT 기반 슬로프 완화로 급격한 변화 방지
4. **품질**: 객관적 평가 점수 제공

## 사용 방법

### 기본 사용

```python
from improved_baseline import ImprovedBaselineCorrector
import pandas as pd

# 데이터 로드
df = pd.read_csv('exported_signals/sample.csv',
                 header=None, sep='\t', encoding='utf-16-le')
time = df[0].values
intensity = df[1].values

# 베이스라인 보정
corrector = ImprovedBaselineCorrector(time, intensity)
baseline, params = corrector.optimize_baseline(use_linear_peaks=True)

# 보정된 신호
corrected = np.maximum(intensity - baseline, 0)

print(f"방법: {params['method']}")
print(f"앵커: {params['num_anchors']}개")
print(f"점수: {params['score']:.2f}")
```

### 고급 사용

```python
# 수동 설정
corrector.find_anchors(
    valley_prominence_factor=0.01,  # Valley 민감도
    local_min_percentile=10,        # Local min 임계값
    min_anchor_distance=15          # 최소 거리
)

baseline = corrector.generate_baseline(
    method='adaptive_spline',       # 방법 선택
    smooth_factor=1.0,              # 스무딩 강도
    apply_rt_relaxation=True        # RT 완화
)

# 피크에 직선 베이스라인 적용
baseline = corrector.apply_linear_to_peaks(baseline)
```

### 간편 함수

```python
from improved_baseline import process_exported_signal

# 한 줄로 처리
time, intensity, baseline, params = process_exported_signal(
    'exported_signals/sample.csv',
    method='auto',  # 자동 최적화
    use_linear_peaks=True,
    apply_rt_relaxation=True
)
```

## 비교 시각화

```bash
# 기존 vs 개선 방법 비교
python compare_baseline_improvements.py
```

생성되는 이미지:
- 앵커 포인트 비교
- 베이스라인 비교
- 보정 후 신호 비교
- 베이스라인 차이
- 피크별 상세 비교 테이블

결과 위치: `result/baseline_comparison/`

## 파일 구조

```
src/
├── hybrid_baseline.py          # 기존 방법
└── improved_baseline.py        # 개선된 방법 ✨

compare_baseline_improvements.py  # 비교 스크립트
```

## 주요 클래스 및 메서드

### ImprovedBaselineCorrector

**주요 메서드**:
- `find_anchors()`: 앵커 포인트 검출
- `generate_baseline()`: 베이스라인 생성
- `apply_linear_to_peaks()`: 피크에 직선 베이스라인 적용
- `optimize_baseline()`: 자동 최적화
- `_apply_rt_based_relaxation()`: RT 기반 슬로프 완화
- `_evaluate_baseline()`: 베이스라인 품질 평가

### BaselineAnchor (dataclass)

```python
@dataclass
class BaselineAnchor:
    index: int          # 데이터 인덱스
    rt: float           # Retention Time
    value: float        # 강도 값
    type: str           # 'valley', 'local_min', 'boundary'
    confidence: float   # 신뢰도 (0-1)
```

## 향후 개선 방향

1. **머신러닝 기반 앵커 선택**: 학습 데이터로 최적 앵커 패턴 학습
2. **피크 타입별 베이스라인**: Sharp vs Broad 피크에 따른 적응형 베이스라인
3. **배치 최적화**: 여러 샘플 동시 처리 시 파라미터 자동 조정
4. **실시간 처리**: 온라인 베이스라인 보정 알고리즘

## 참고 자료

- 기존 방법: `src/hybrid_baseline.py`
- 개선 방법: `src/improved_baseline.py`
- 비교 스크립트: `compare_baseline_improvements.py`
- 테스트 결과: `result/baseline_comparison/`

## 라이선스

프로젝트 라이선스를 따릅니다.
