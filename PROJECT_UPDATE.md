# PeakPicker 프로젝트 업데이트

## 최근 업데이트 (2025-01-10)

### 베이스라인 개선 및 음수 피크 처리

#### 주요 개선사항

1. **양방향 피크 검출 시스템**
   - 양수 피크와 음수 피크를 모두 검출 가능
   - 기존: 양수 피크만 검출
   - 개선: 신호 반전을 통한 음수 피크 검출 추가
   - 각 피크에 `polarity` 필드 추가 ('positive' / 'negative')

2. **베이스라인 제약 제거**
   - 기존: 베이스라인이 항상 신호보다 아래에 있도록 강제 (`np.minimum`)
   - 개선: 제약 제거로 음수 영역 피크 검출 가능
   - 음수 값 자동 변환 제거 (원본 데이터 보존)

3. **베이스라인 스무딩 강화**
   - 스플라인 스무딩 팩터 **3배 증가**
   - **2단계 필터링**: Savitzky-Golay 필터 + 이동평균
   - 베이스라인 과적합 방지 → 잘못된 음수 영역 생성 방지

4. **음수 영역 후처리**
   - 작고 얕은 음수 영역: 0으로 클리핑 (베이스라인 과보정 제거)
     - 조건: 크기 < 100점, 최소값 > -50
   - 크고 깊은 음수 영역: 실제 음수 피크로 보존
     - 조건: 크기 >= 100점 또는 최소값 <= -50

#### 성능 개선 결과

테스트 샘플: `251014_RIBA_PH_MAIN_GN10_1_6H`

| 항목 | 이전 | 개선 | 개선율 |
|------|------|------|--------|
| 음수 값 개수 | 1,103개 (31.78%) | 424개 (12.22%) | **-61.5%** |
| 잘못된 음수 피크 | 6개 | 2개 | **-66.7%** |
| 양수 피크 | 9개 | 9개 | **100% 유지** |

#### 코드 변경사항

**src/hybrid_baseline.py**
- `generate_hybrid_baseline()`:
  - `enhanced_smoothing` 파라미터 추가 (기본값: True)
  - `weighted_spline` 및 `robust_fit`에 3배 스무딩 적용
  - 2단계 필터링 (savgol + 이동평균)

- `post_process_corrected_signal()` 새로 추가:
  ```python
  def post_process_corrected_signal(
      self,
      corrected: np.ndarray,
      clip_negative: bool = True,
      negative_threshold: float = -50.0
  ) -> np.ndarray
  ```
  - 음수 영역 분석 및 선택적 클리핑
  - 실제 음수 피크와 베이스라인 과보정 구분

**iterative_peak_recovery.py**
- `detect_peaks()`: 양방향 피크 검출 구현
  - 양수 피크: 기존 방식
  - 음수 피크: 신호 반전 후 검출
  - `polarity` 필드 추가

#### 새로운 진단 도구

1. **test_negative_peaks.py**
   - 합성 데이터 및 실제 데이터로 음수 피크 검출 테스트
   - 양수/음수 영역 시각화

2. **diagnose_negative_issue.py**
   - 음수 영역 상세 진단
   - 실제 음수 피크 vs 베이스라인 과보정 구분
   - 곡률 분석 (2차 미분)

3. **inspect_baseline_check.py**
   - 10개 샘플 베이스라인 점검
   - Robust Fit vs Weighted Spline 비교
   - 베이스라인이 신호 위로 가는 영역 분석

4. **test_smoothing_improvements.py**
   - 이전 방식 vs 개선 방식 비교
   - 4x3 그리드 시각화
   - 정량적 개선 효과 측정

---

## 다음 단계: 피크 디텍션 통합

### 목표
베이스라인 개선사항을 실제 피크 검출 워크플로우에 통합

### 통합 계획
1. 기존 피크 검출 파이프라인 확인
2. 양방향 피크 검출 적용
3. 스무딩 강화 및 후처리 기본값 설정
4. 전체 샘플 재분석
5. 성능 비교 및 검증

### 예상 개선
- 잘못된 음수 피크 대폭 감소
- 베이스라인 안정성 향상
- 실제 음수 피크 (solvent dip 등) 검출 가능

---

## 기술 스택

- Python 3.x
- NumPy, SciPy (신호 처리)
- Pandas (데이터 처리)
- Matplotlib (시각화)
- Savitzky-Golay 필터
- UnivariateSpline (베이스라인 피팅)

---

## 참고 문헌

### 베이스라인 보정 방법
- **Hybrid Baseline**: Valley points + Local minima
- **Robust Fit**: MAD 기반 outlier 제거
- **Weighted Spline**: Confidence 가중 스플라인

### 피크 검출
- `scipy.signal.find_peaks`
- Prominence 및 Height 기반 필터링
- 양방향 검출 (positive/negative)

---

## 버전 히스토리

### v0.3.0 (2025-01-10) - Baseline Enhancement
- 양방향 피크 검출 추가
- 베이스라인 스무딩 강화 (3배)
- 음수 영역 후처리 구현
- 진단 도구 4종 추가

### v0.2.0 (이전)
- Hybrid baseline correction
- Peak width 기반 방법 선택
- RT 기반 slope relaxation

### v0.1.0 (초기)
- 기본 베이스라인 보정
- 피크 검출
