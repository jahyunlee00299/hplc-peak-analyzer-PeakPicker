# Peak Deconvolution Feature

## 개요

PeakPicker에 추가된 피크 디컨볼루션(Peak Deconvolution) 기능은 겹쳐있는 HPLC 피크들을 자동으로 분리하고 정량 분석할 수 있도록 해줍니다.

### 주요 기능

✅ **자동 숄더 피크 검출** - 2차 미분 분석으로 숨어있는 피크 자동 발견
✅ **가우시안 피팅** - 겹친 피크들을 다중 가우시안 곡선으로 분리
✅ **비대칭도 분석** - 피크 비대칭도를 계산하여 디컨볼루션 필요 여부 자동 판단
✅ **품질 평가** - R² 및 RMSE로 피팅 품질 평가
✅ **시각화** - 원본 vs 분리된 피크 비교 플롯 자동 생성
✅ **Excel 리포트** - 분리된 각 피크 컴포넌트 정보를 별도 시트에 저장

---

## 설치된 파일

### 새로 추가된 모듈

```
src/
├── peak_models.py              # 피크 모델 함수들 (Gaussian, Lorentzian, Voigt, EMG)
├── peak_deconvolution.py       # 피크 디컨볼루션 핵심 알고리즘
└── deconvolution_visualizer.py # 시각화 도구

test_deconvolution.py           # 테스트 스크립트
```

### 수정된 파일

```
hplc_analyzer_enhanced.py       # 디컨볼루션 기능 통합
```

---

## 사용법

### 1. 기본 사용 (자동 디컨볼루션)

```bash
python hplc_analyzer_enhanced.py "C:\데이터경로"
```

기본적으로 디컨볼루션이 **자동으로 활성화**됩니다. 비대칭도가 1.2 이상인 피크나 숄더 피크가 감지되면 자동으로 디컨볼루션을 수행합니다.

### 2. 디컨볼루션 비활성화

```bash
python hplc_analyzer_enhanced.py "C:\데이터경로" --no-deconvolution
```

### 3. 비대칭도 임계값 조정

```bash
python hplc_analyzer_enhanced.py "C:\데이터경로" --asymmetry-threshold 1.5
```

- **낮은 값 (1.1-1.2)**: 더 많은 피크를 디컨볼루션 (민감함)
- **높은 값 (1.5-2.0)**: 명확하게 비대칭인 피크만 디컨볼루션 (보수적)
- **기본값: 1.2** (권장)

### 4. 전체 옵션 예시

```bash
python hplc_analyzer_enhanced.py "C:\HPLC_Data" ^
    --output "C:\Results" ^
    --asymmetry-threshold 1.3 ^
    --pattern "*.CSV"
```

---

## 출력 결과

### Excel 리포트

분석 결과 Excel 파일에 다음 시트가 추가됩니다:

#### 1. Summary 시트
- 기존 정보에 추가:
  - `Deconvolved Peaks`: 디컨볼루션된 피크 개수
  - `Total Components`: 분리된 총 컴포넌트 개수

#### 2. Peaks 시트
- 기존과 동일 (원본 피크 정보)

#### 3. Deconvolved_Peaks 시트 (새로 추가!)
각 분리된 피크 컴포넌트에 대한 상세 정보:

| 컬럼 | 설명 |
|------|------|
| `Original_Peak_Number` | 원본 피크 번호 |
| `Original_RT` | 원본 피크 RT |
| `Component_Number` | 컴포넌트 번호 (1, 2, 3...) |
| `Component_RT` | 분리된 피크의 RT |
| `Component_Height` | 분리된 피크의 높이 |
| `Component_Area` | 분리된 피크의 면적 |
| `Component_Area_Percent` | 원본 피크 대비 면적 % |
| `Sigma` | 가우시안 폭 파라미터 |
| `Is_Shoulder` | 숄더 피크 여부 (True/False) |
| `Asymmetry` | 비대칭도 |
| `Start_RT` | 피크 시작 RT |
| `End_RT` | 피크 종료 RT |
| `Fit_Quality_R2` | 피팅 품질 (R²) |
| `RMSE` | 피팅 오차 (RMSE) |
| `Method` | 사용된 방법 (예: 2-Gaussian) |

---

## 작동 원리

### 1. 디컨볼루션 필요 여부 자동 판단

다음 조건 중 하나라도 만족하면 디컨볼루션 수행:

- **높은 비대칭도**: Asymmetry Factor > 임계값 (기본 1.2)
- **숄더 피크 검출**: 2차 미분으로 inflection point 감지
- **다중 변곡점**: 3개 이상의 변곡점 존재

### 2. 피크 센터 자동 검출

- Local maxima 검출
- Prominence 기반 우선순위 정렬
- 최대 4개 컴포넌트까지 시도

### 3. 가우시안 피팅 최적화

- Scipy `curve_fit` 사용
- 초기값 자동 추정 (amplitude, center, sigma)
- Bounds 설정으로 물리적으로 타당한 해 보장
- R² > 0.85 이상일 때만 결과 채택

### 4. 품질 평가

- **R² (결정계수)**: 1.0에 가까울수록 완벽한 피팅
- **RMSE**: 낮을수록 좋은 피팅
- 자동으로 최적 컴포넌트 개수 선택

---

## 테스트 실행

합성 데이터로 디컨볼루션 테스트:

```bash
python test_deconvolution.py
```

생성되는 파일:
- `test_scenario_1_deconv.png` - 2개 피크 겹침 테스트
- `test_scenario_2_deconv.png` - 3개 피크 겹침 테스트
- `test_scenario_3_deconv.png` - 비대칭 피크 + 숄더 테스트
- `test_deconvolution_summary.png` - 통계 요약

---

## Python API 사용

### 직접 사용 예제

```python
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path.cwd() / 'src'))

from peak_deconvolution import PeakDeconvolution
from deconvolution_visualizer import DeconvolutionVisualizer

# 데이터 준비 (rt: 시간, signal: 강도)
rt = np.array([...])
signal = np.array([...])

# 디컨볼루션 객체 생성
decon = PeakDeconvolution(
    min_asymmetry=1.2,          # 비대칭도 임계값
    min_shoulder_ratio=0.1,     # 숄더 최소 높이 비율 (10%)
    max_components=4,           # 최대 컴포넌트 개수
    fit_tolerance=0.85          # 최소 R² 값
)

# 피크 분석
result = decon.analyze_peak(
    rt=rt,
    signal=signal,
    peak_start_idx=100,
    peak_end_idx=200,
    force_deconvolution=False   # False면 필요시만 수행
)

# 결과 확인
if result and result.success:
    print(f"Found {result.n_components} components")
    print(f"Fit quality (R²): {result.fit_quality:.4f}")

    for i, comp in enumerate(result.components, 1):
        print(f"Peak {i}:")
        print(f"  RT: {comp.retention_time:.3f} min")
        print(f"  Area: {comp.area:.1f} ({comp.area_percent:.1f}%)")
        print(f"  Shoulder: {comp.is_shoulder}")

    # 시각화
    viz = DeconvolutionVisualizer()
    fig = viz.plot_single_deconvolution(
        rt, signal, result,
        peak_start_idx=100,
        peak_end_idx=200,
        save_path=Path("result.png")
    )
```

---

## 지원하는 피크 모델

### 현재 구현됨
- ✅ **Gaussian** - 대부분의 HPLC 피크에 적합
- ✅ **Lorentzian** - 테일링 피크
- ✅ **Voigt** - Gaussian + Lorentzian 조합
- ✅ **EMG (Exponentially Modified Gaussian)** - 비대칭 피크

### 현재 디컨볼루션에 사용
- **Gaussian 모델만 사용** (가장 일반적이고 안정적)
- 향후 업데이트에서 다른 모델 옵션 추가 예정

---

## 제한사항 및 주의사항

### 현재 제한사항
1. **최대 4개 컴포넌트**: 한 피크당 최대 4개까지 분리 가능
2. **가우시안 모델 전용**: 현재는 가우시안 피팅만 지원
3. **높은 노이즈**: S/N ratio가 낮으면 정확도 감소
4. **심하게 겹친 피크**: 90% 이상 겹치면 분리 어려움

### 권장 사항
- 베이스라인 보정 활성화 (`--no-hybrid-baseline` 사용 안 함)
- 충분한 데이터 포인트 (피크당 최소 20-30 포인트)
- 적절한 비대칭도 임계값 설정 (1.2-1.5 권장)

### 문제 해결
- **너무 많은 피크가 디컨볼루션되는 경우**:
  → `--asymmetry-threshold` 값을 높임 (예: 1.5)

- **분리되어야 할 피크가 안 되는 경우**:
  → `--asymmetry-threshold` 값을 낮춤 (예: 1.1)

- **Excel에 Deconvolved_Peaks 시트가 없는 경우**:
  → 디컨볼루션이 필요한 피크가 없었음 (모두 대칭 피크)

---

## 알고리즘 상세

### 숄더 피크 검출 알고리즘

1. **2차 미분 계산**
   - Savitzky-Golay 필터로 스무딩
   - 노이즈에 강한 미분 계산

2. **Concave-up 영역 찾기**
   - 2차 미분의 local maxima
   - 이 영역들이 잠재적 숄더 피크

3. **유효성 검증**
   - 메인 피크 대비 최소 10% 이상 높이
   - Prominence 기반 필터링

### 피팅 최적화 전략

```
1개 컴포넌트 피팅 시도
  ↓ (R² < 0.95)
2개 컴포넌트 피팅 시도
  ↓ (R² < 0.95)
3개 컴포넌트 피팅 시도
  ↓ (R² < 0.95)
4개 컴포넌트 피팅 시도
  ↓
최고 R² 값 가진 결과 선택
```

---

## 성능

### 테스트 결과 (합성 데이터)

| 시나리오 | 실제 피크 | 검출 피크 | R² | RMSE |
|---------|---------|---------|-----|------|
| 2개 중첩 피크 | 2 | 2 | 0.996 | 2.0 |
| 3개 중첩 피크 | 3 | 1-3 | 0.953 | 9.4 |
| 숄더 피크 | 2 | 1-2 | 0.951 | 6.5 |

**평균 성능**: R² = 0.967, RMSE = 5.96

---

## 향후 개발 계획

### Phase 2 (예정)
- [ ] Voigt/EMG 모델 지원
- [ ] 사용자 정의 initial guess
- [ ] 배치 시각화 개선
- [ ] GPU 가속 (대량 샘플)

### Phase 3 (예정)
- [ ] 머신러닝 기반 피크 분류
- [ ] 자동 파라미터 최적화
- [ ] GUI 통합

---

## 라이선스 & 인용

PeakPicker Peak Deconvolution Module
© 2025 PeakPicker Project

---

## 문의 및 버그 리포트

이슈가 있거나 개선 제안이 있으시면 프로젝트 이슈 트래커에 등록해주세요.

---

**Version**: 1.0.0
**Last Updated**: 2025-11-10
**Python Version**: 3.7+
**Dependencies**: numpy, scipy, matplotlib, pandas, openpyxl
