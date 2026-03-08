# Feature 5: Standard Curve and Quantitative Analysis

## 개요

QuantitativeAnalyzer 모듈은 검량선(Standard Curve)을 생성하고, 피크 면적으로부터 농도를 계산하는 정량 분석 기능을 제공합니다.

## 주요 기능

### 1. 검량선 생성
- **Linear Regression**: 1차 직선 회귀
- **Quadratic Regression**: 2차 곡선 회귀
- **Force Zero**: 원점 통과 옵션
- **R² Calculation**: 결정계수 자동 계산

### 2. 정량 분석
- 피크 면적 → 농도 변환
- Dilution factor 자동 적용
- 배치 정량 분석
- 농도 역계산 (농도 → 면적)

### 3. 검량선 검증
- R² 기반 검증
- LOD/LOQ 계산
- 잔차 분석
- 검량선 저장/불러오기 (JSON)

## QuantitativeAnalyzer 사용법

### 1. 기본 설정

```python
from modules.quantification import QuantitativeAnalyzer

# Analyzer 생성
analyzer = QuantitativeAnalyzer()

# 여러 검량선 관리 가능
analyzer1 = QuantitativeAnalyzer()  # 화합물 A
analyzer2 = QuantitativeAnalyzer()  # 화합물 B
```

### 2. 검량선 생성 (Linear)

가장 일반적인 방법입니다.

```python
# 표준 용액 데이터
concentrations = [0.0, 1.0, 2.5, 5.0, 10.0]  # mg/L
areas = [0.0, 98.5, 248.2, 501.3, 1005.8]     # Peak area

# 검량선 생성
curve = analyzer.create_standard_curve(
    concentrations=concentrations,
    areas=areas,
    curve_name="compound_A",
    method="linear"
)

print(f"Equation: {curve.equation}")
print(f"Slope: {curve.slope:.4f}")
print(f"Intercept: {curve.intercept:.4f}")
print(f"R²: {curve.r_squared:.6f}")
```

**출력 예시:**
```
Equation: y = 100.23x + 1.45
Slope: 100.2300
Intercept: 1.4500
R²: 0.999850
```

**검량선 품질 기준:**
- **R² ≥ 0.995**: 우수
- **R² ≥ 0.990**: 양호
- **R² < 0.990**: 재측정 권장

### 3. 원점 통과 검량선 (Force Zero)

낮은 농도에서 더 정확한 결과를 원할 때 사용합니다.

```python
# 원점을 통과하는 검량선
curve = analyzer.create_standard_curve(
    concentrations=concentrations,
    areas=areas,
    curve_name="compound_A_forced",
    method="linear",
    force_zero=True  # 절편 = 0
)

print(f"Equation: {curve.equation}")
print(f"Slope: {curve.slope:.4f}")
print(f"Intercept: {curve.intercept:.4f}")  # ~0
```

**사용 시기:**
- 검출기 응답이 원점을 지나는 것이 이론적으로 타당할 때
- Blank의 피크 면적이 거의 0일 때
- 낮은 농도 범위에서 정확도 향상

**주의사항:**
- R²가 일반 회귀보다 낮을 수 있음
- 높은 농도에서 정확도가 떨어질 수 있음

### 4. 2차 곡선 검량선 (Quadratic)

넓은 농도 범위에서 비선형성이 있을 때 사용합니다.

```python
# 넓은 농도 범위
concentrations = [0.0, 0.5, 1.0, 5.0, 10.0, 50.0, 100.0]
areas = [0, 48, 95, 450, 850, 3500, 6200]  # 비선형 응답

# 2차 곡선 fitting
curve = analyzer.create_standard_curve(
    concentrations=concentrations,
    areas=areas,
    curve_name="wide_range",
    method="quadratic"
)

print(f"Equation: {curve.equation}")
# 출력: y = 0.012x² + 95.3x + 2.1
print(f"R²: {curve.r_squared:.6f}")
```

**사용 시기:**
- 농도 범위가 넓을 때 (>100배)
- 검출기 응답이 비선형일 때
- Linear R²가 < 0.99일 때

### 5. 농도 계산

검량선으로부터 농도를 계산합니다.

```python
# 검량선 생성
analyzer.create_standard_curve(
    concentrations=[0, 1, 2.5, 5, 10],
    areas=[0, 100, 250, 500, 1000],
    curve_name="my_curve"
)

# 샘플의 피크 면적으로부터 농도 계산
sample_area = 375.5

concentration = analyzer.calculate_concentration(
    area=sample_area,
    curve_name="my_curve",
    dilution_factor=1.0
)

print(f"Peak area: {sample_area}")
print(f"Concentration: {concentration:.4f} mg/L")
```

**출력:**
```
Peak area: 375.5
Concentration: 3.7550 mg/L
```

### 6. Dilution Factor 적용

희석된 샘플의 실제 농도를 계산합니다.

```python
# 샘플을 5배 희석하여 측정
sample_area = 450.0
dilution_factor = 5.0

# 희석 전 농도 계산
original_concentration = analyzer.calculate_concentration(
    area=sample_area,
    curve_name="my_curve",
    dilution_factor=dilution_factor
)

print(f"Measured area: {sample_area}")
print(f"Dilution: {dilution_factor}x")
print(f"Original concentration: {original_concentration:.4f} mg/L")
```

**희석 배수 계산 예:**
```
1 mL 샘플 + 4 mL 용매 = 5배 희석
0.5 mL 샘플 + 4.5 mL 용매 = 10배 희석
```

### 7. 배치 정량 분석

여러 샘플을 한 번에 처리합니다.

```python
# 여러 샘플의 면적 데이터
sample_areas = [125.5, 378.2, 756.8, 234.1, 892.3]
sample_names = ["S1", "S2", "S3", "S4", "S5"]
dilution_factors = [1.0, 5.0, 10.0, 2.0, 10.0]

# 배치 정량
results = analyzer.calculate_batch_concentrations(
    areas=sample_areas,
    dilution_factors=dilution_factors,
    sample_names=sample_names,
    curve_name="my_curve"
)

# 결과 출력
for result in results:
    print(f"{result['sample_name']}: "
          f"{result['concentration']:.4f} mg/L "
          f"(area={result['area']:.1f}, "
          f"dilution={result['dilution_factor']}x)")
```

**출력 예시:**
```
S1: 1.2550 mg/L (area=125.5, dilution=1.0x)
S2: 18.9100 mg/L (area=378.2, dilution=5.0x)
S3: 75.6800 mg/L (area=756.8, dilution=10.0x)
S4: 4.6820 mg/L (area=234.1, dilution=2.0x)
S5: 89.2300 mg/L (area=892.3, dilution=10.0x)
```

### 8. 검량선 검증

```python
# 검량선 생성
analyzer.create_standard_curve(
    concentrations=[0, 1, 2.5, 5, 10],
    areas=[0, 100, 250, 500, 1000],
    curve_name="test_curve"
)

# 검증 (R² 기준)
is_valid, message = analyzer.validate_curve(
    curve_name="test_curve",
    min_r_squared=0.995  # 최소 R² 요구사항
)

print(f"Valid: {is_valid}")
print(f"Message: {message}")
```

**검증 기준 가이드:**
- **0.999**: 매우 엄격 (연구용, 미량 분석)
- **0.995**: 일반적 (일상 분석)
- **0.990**: 완화된 기준 (스크리닝)

### 9. LOD/LOQ 계산

검출한계(LOD)와 정량한계(LOQ)를 계산합니다.

```python
# 검량선 생성
analyzer.create_standard_curve(
    concentrations=[0, 1, 2.5, 5, 10],
    areas=[0, 100, 250, 500, 1000]
)

# LOD 계산 (3.3σ)
lod = analyzer.get_lod_loq(confidence=3.3)

# LOQ 계산 (10σ)
loq = analyzer.get_lod_loq(confidence=10)

print(f"LOD (Limit of Detection): {lod:.6f} mg/L")
print(f"LOQ (Limit of Quantification): {loq:.6f} mg/L")
```

**신뢰 수준:**
- **3.3σ**: LOD (검출한계) - IUPAC 권장
- **10σ**: LOQ (정량한계) - IUPAC 권장
- **3.0σ**: 더 완화된 LOD

**해석:**
- LOD 미만: "검출 안됨" (ND)
- LOD ~ LOQ: "검출되었으나 정량 불가"
- LOQ 이상: 정량 가능

### 10. 검량선 저장 및 불러오기

나중에 재사용하기 위해 검량선을 저장합니다.

```python
# 검량선 생성
analyzer.create_standard_curve(
    concentrations=[0, 1, 2.5, 5, 10],
    areas=[0, 100, 250, 500, 1000],
    curve_name="saved_curve"
)

# JSON 파일로 저장
save_path = "calibration_curves/compound_A.json"
analyzer.save_curve("saved_curve", save_path)

print(f"Curve saved to: {save_path}")

# 나중에 불러오기
analyzer2 = QuantitativeAnalyzer()
loaded_name = analyzer2.load_curve(save_path)

print(f"Curve loaded as: {loaded_name}")

# 불러온 검량선 사용
concentration = analyzer2.calculate_concentration(
    area=350,
    curve_name=loaded_name
)
```

**저장되는 정보:**
- 검량선 이름
- 표준점 데이터 (농도, 면적)
- 회귀 계수 (slope, intercept)
- R² 값
- 생성 일시

## 통합 워크플로우

### 표준 용액 → 검량선 → 샘플 정량

```python
from modules.data_loader import DataLoader
from modules.peak_detector import PeakDetector
from modules.quantification import QuantitativeAnalyzer
from modules.excel_exporter import ExcelExporter

# ===== 1. 표준 용액 측정 =====
print("Step 1: Measuring standards...")

standard_concentrations = [0.0, 1.0, 2.5, 5.0, 10.0]  # mg/L
standard_files = [
    "std_0.csv",
    "std_1.csv",
    "std_2.5.csv",
    "std_5.csv",
    "std_10.csv"
]

loader = DataLoader()
standard_areas = []

for conc, file in zip(standard_concentrations, standard_files):
    # 데이터 로드
    time, intensity = loader.load_file(file)

    # 피크 검출
    detector = PeakDetector(time, intensity, auto_threshold=True)
    peaks = detector.detect_peaks()

    # 타겟 피크 선택 (예: RT=4.5 부근)
    target_peak = detector.get_peak_at_rt(4.5, tolerance=0.2)

    if target_peak:
        standard_areas.append(target_peak.area)
        print(f"  {conc} mg/L → Area: {target_peak.area:.2f}")
    else:
        standard_areas.append(0.0)
        print(f"  {conc} mg/L → No peak detected")

# ===== 2. 검량선 생성 =====
print("\nStep 2: Creating calibration curve...")

analyzer = QuantitativeAnalyzer()
curve = analyzer.create_standard_curve(
    concentrations=standard_concentrations,
    areas=standard_areas,
    curve_name="target_compound"
)

print(f"  Equation: {curve.equation}")
print(f"  R²: {curve.r_squared:.6f}")

# 검증
is_valid, message = analyzer.validate_curve("target_compound", min_r_squared=0.995)
print(f"  Validation: {message}")

# ===== 3. 샘플 측정 =====
print("\nStep 3: Analyzing samples...")

sample_files = ["sample1.csv", "sample2.csv", "sample3.csv"]
dilution_factors = [5.0, 10.0, 5.0]  # 희석 배수

sample_results = []

for sample_file, dilution in zip(sample_files, dilution_factors):
    # 데이터 로드
    time, intensity = loader.load_file(sample_file)

    # 피크 검출
    detector = PeakDetector(time, intensity, auto_threshold=True)
    peaks = detector.detect_peaks()

    # 타겟 피크
    target_peak = detector.get_peak_at_rt(4.5, tolerance=0.2)

    if target_peak:
        # 농도 계산
        concentration = analyzer.calculate_concentration(
            area=target_peak.area,
            curve_name="target_compound",
            dilution_factor=dilution
        )

        sample_results.append({
            'file': sample_file,
            'area': target_peak.area,
            'dilution': dilution,
            'concentration': concentration
        })

        print(f"  {sample_file}: {concentration:.4f} mg/L")

# ===== 4. 결과 출력 =====
print("\nStep 4: Exporting results...")

# Excel 출력
exporter = ExcelExporter(output_dir="quantitative_results")

for result in sample_results:
    metadata = {
        "Dilution Factor": f"{result['dilution']}x",
        "Calibration Curve": curve.equation,
        "R²": curve.r_squared,
        "Concentration": f"{result['concentration']:.4f} mg/L"
    }

    # 결과 저장 (구현 필요)

print("✓ Complete workflow finished!")
```

## 실전 사용 예시

### 예시 1: 식품 중 카페인 정량

```python
# 검량선 (카페인 표준 용액)
caffeine_concs = [0, 10, 25, 50, 100, 200]  # mg/L
caffeine_areas = [0, 245, 612, 1225, 2450, 4900]

analyzer = QuantitativeAnalyzer()
analyzer.create_standard_curve(
    concentrations=caffeine_concs,
    areas=caffeine_areas,
    curve_name="caffeine"
)

# 커피 샘플 (100배 희석)
coffee_area = 1850
coffee_conc = analyzer.calculate_concentration(
    area=coffee_area,
    curve_name="caffeine",
    dilution_factor=100
)

print(f"Coffee caffeine: {coffee_conc:.2f} mg/L")
```

### 예시 2: 환경 시료 중 중금속

```python
# 검량선 (납 표준 용액)
pb_concs = [0, 0.01, 0.05, 0.1, 0.5, 1.0]  # mg/L
pb_areas = [120, 1250, 6230, 12450, 62300, 124500]

analyzer = QuantitativeAnalyzer()
analyzer.create_standard_curve(
    concentrations=pb_concs,
    areas=pb_areas,
    curve_name="lead",
    force_zero=False
)

# LOD/LOQ
lod = analyzer.get_lod_loq(confidence=3.3)
loq = analyzer.get_lod_loq(confidence=10)

print(f"LOD: {lod:.6f} mg/L")
print(f"LOQ: {loq:.6f} mg/L")

# 하천수 샘플
river_area = 8500
river_conc = analyzer.calculate_concentration(area=river_area, curve_name="lead")

if river_conc < lod:
    print("Lead: Not detected")
elif river_conc < loq:
    print(f"Lead: Detected but < LOQ ({loq:.6f} mg/L)")
else:
    print(f"Lead: {river_conc:.6f} mg/L")
```

## 모범 사례

### 검량선 농도 범위 선택

```python
# ✅ 좋은 예: 샘플 농도를 포함하는 범위
expected_sample_range = (2.0, 8.0)  # mg/L
standard_concs = [0, 1, 2, 5, 10, 15]  # 샘플 범위를 충분히 커버

# ❌ 나쁜 예: 샘플이 검량선 범위 밖
expected_sample_range = (15, 25)  # mg/L
standard_concs = [0, 1, 2, 5, 10]  # 최고 농도가 샘플보다 낮음
```

**권장사항:**
- 예상 샘플 농도의 50% ~ 150% 범위
- 최소 5개 농도 점
- 0 농도 포함 (blank)
- 균등한 간격보다 로그 간격 선호 (넓은 범위)

### 반복 측정 및 통계

```python
# 표준 용액 3회 반복 측정
import numpy as np

standard_areas_replicate = {
    0.0: [0, 0, 0],
    1.0: [98, 102, 100],
    2.5: [245, 250, 248],
    5.0: [498, 502, 500],
    10.0: [1000, 1005, 1002]
}

# 평균 면적 사용
concentrations = []
average_areas = []

for conc, areas in standard_areas_replicate.items():
    concentrations.append(conc)
    average_areas.append(np.mean(areas))

    rsd = (np.std(areas) / np.mean(areas)) * 100
    print(f"{conc} mg/L: {np.mean(areas):.1f} ± {np.std(areas):.1f} (RSD: {rsd:.2f}%)")

# 평균으로 검량선 생성
analyzer.create_standard_curve(concentrations, average_areas)
```

### 검량선 재사용

```python
# 검량선을 정기적으로 저장
from datetime import datetime

# 검량선 생성
analyzer.create_standard_curve(concs, areas, curve_name="daily_curve")

# 날짜별 저장
today = datetime.now().strftime("%Y%m%d")
save_path = f"calibration/curve_{today}.json"
analyzer.save_curve("daily_curve", save_path)

# 분석 시 불러오기
analyzer2 = QuantitativeAnalyzer()
analyzer2.load_curve(save_path)
```

## 문제 해결

### R²가 낮은 경우 (<0.99)

```python
# 1. 이상점(outlier) 확인
import matplotlib.pyplot as plt

plt.scatter(concentrations, areas)
plt.xlabel('Concentration (mg/L)')
plt.ylabel('Area')
plt.title('Calibration Points')
plt.show()

# 2. 농도 범위 축소
# 전체 범위: 0-100 (R² = 0.985)
# 축소 범위: 0-10 (R² = 0.998)

# 3. 2차 곡선 시도
curve = analyzer.create_standard_curve(
    concentrations, areas,
    method="quadratic"
)
```

### 음수 농도가 계산되는 경우

```python
# 원인: Intercept가 너무 크거나, 면적이 너무 작음

# 해결 1: Force zero 사용
analyzer.create_standard_curve(
    concentrations, areas,
    force_zero=True
)

# 해결 2: Blank correction
blank_area = 50
corrected_area = sample_area - blank_area
```

### 희석 배수 계산 실수

```python
# ✅ 올바른 계산
# 1 mL 샘플 + 4 mL 용매 = 총 5 mL
dilution_factor = 5  # 5배 희석

# ❌ 흔한 실수
dilution_factor = 4  # 용매의 부피만 사용 (잘못됨)
```

## 테스트 결과

```
✅ Standard Curve Creation: PASSED
✅ Concentration Calculation: PASSED
✅ Batch Quantification: PASSED
✅ Curve Validation: PASSED
✅ Curve Save/Load: PASSED
✅ LOD/LOQ Calculation: PASSED
🎉 All tests passed (6/6)!
```

## API Reference

### QuantitativeAnalyzer 클래스

```python
class QuantitativeAnalyzer:
    def create_standard_curve(
        self,
        concentrations: List[float],
        areas: List[float],
        curve_name: str = "default",
        method: str = "linear",
        force_zero: bool = False
    ) -> CalibrationCurve:
        """검량선 생성

        Args:
            concentrations: 표준 농도 리스트
            areas: 피크 면적 리스트
            curve_name: 검량선 이름
            method: "linear" 또는 "quadratic"
            force_zero: 원점 통과 여부

        Returns:
            CalibrationCurve 객체
        """

    def calculate_concentration(
        self,
        area: float,
        curve_name: str = "default",
        dilution_factor: float = 1.0
    ) -> float:
        """농도 계산

        Args:
            area: 피크 면적
            curve_name: 사용할 검량선 이름
            dilution_factor: 희석 배수

        Returns:
            계산된 농도
        """

    def calculate_batch_concentrations(
        self,
        areas: List[float],
        dilution_factors: List[float] = None,
        sample_names: List[str] = None,
        curve_name: str = "default"
    ) -> List[Dict]:
        """배치 농도 계산

        Returns:
            [{'sample_name', 'area', 'dilution_factor', 'concentration'}, ...]
        """

    def validate_curve(
        self,
        curve_name: str = "default",
        min_r_squared: float = 0.995
    ) -> Tuple[bool, str]:
        """검량선 검증

        Returns:
            (is_valid, message)
        """

    def get_lod_loq(
        self,
        curve_name: str = "default",
        std_dev_blank: float = None,
        confidence: float = 3.3
    ) -> float:
        """LOD/LOQ 계산

        Args:
            confidence: 3.3 (LOD) 또는 10 (LOQ)

        Returns:
            검출/정량 한계
        """

    def save_curve(self, curve_name: str, filepath: str) -> bool:
        """검량선 저장"""

    def load_curve(self, filepath: str) -> str:
        """검량선 불러오기

        Returns:
            불러온 검량선 이름
        """
```

## 관련 문서

- [Feature 2: Peak Detection](FEATURE_2_PEAK_DETECTION.md)
- [Feature 4: Excel Export](FEATURE_4_EXCEL_EXPORT.md)
- [전체 기능 요약](ALL_FEATURES_SUMMARY.md)

## 참고 문헌

- IUPAC Guidelines on Detection Limits
- ICH Q2(R1) Validation of Analytical Procedures
- FDA Guidance for Industry: Bioanalytical Method Validation
