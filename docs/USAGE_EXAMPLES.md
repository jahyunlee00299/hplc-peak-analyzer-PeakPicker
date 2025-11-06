# HPLC Peak Picker - 사용 가이드

하이브리드 베이스라인 보정을 적용한 HPLC 데이터 자동 분석 완전 가이드

## 목차
1. [빠른 시작](#빠른-시작)
2. [1단계: Chemstation에서 데이터 내보내기](#1단계-chemstation에서-데이터-내보내기)
3. [2단계: 내보낸 데이터 분석](#2단계-내보낸-데이터-분석)
4. [고급 사용법](#고급-사용법)

---

## 빠른 시작

### 전체 작업 흐름
```bash
# 1단계: Chemstation에서 모든 .D 파일 내보내기 (자동화)
python auto_export_keyboard_final.py

# 2단계: 내보낸 CSV 파일 분석
python hplc_analyzer_enhanced.py "C:\경로\to\exported\csv\files"
```

---

## 1단계: Chemstation에서 데이터 내보내기

### 키보드 자동화 방식으로 내보내기

`auto_export_keyboard_final.py` 스크립트는 키보드 단축키를 사용하여 내보내기 과정을 자동화합니다.

#### 실행 전 준비사항
- Chemstation이 열려 있고 준비된 상태여야 합니다
- 스크립트 실행 전 Chemstation 창에 커서를 두세요

#### 사용 방법
```python
python auto_export_keyboard_final.py
```

#### 실행 화면 예시
```
================================================================================
  Chemstation 자동 Export
  키보드 단축키 버전
================================================================================

================================================================================
  데이터 디렉토리 설정
================================================================================

현재 기본 경로: C:\Chem32\1\DATA

옵션:
  1. 기본 경로 사용
  2. 직접 경로 입력

선택 (1 또는 2): 1

'C:\Chem32\1\DATA' 하위 폴더 목록:
  1. Experiment_A
  2. Experiment_B
  3. Test_Samples
  4. Standard_Curves

전체 경로를 입력하거나 위 번호를 선택하세요.
경로 또는 번호: 2

'C:\Chem32\1\DATA\Experiment_B' 에서 .D 폴더 검색 중...

[확인] 15개 .D 폴더 발견

발견된 파일:
  1. SAMPLE_001.D
  2. SAMPLE_002.D
  3. SAMPLE_003.D
  4. SAMPLE_004.D
  5. SAMPLE_005.D
  ... 외 10개 더

================================================================================

15개 파일을 처리하시겠습니까? (y/n): y

출력 디렉토리 기본값: C:\Users\Jahyun\PycharmProjects\PeakPicker\exported_signals
다른 경로를 사용하시겠습니까? (Enter=기본값 사용):

출력 디렉토리: C:\Users\Jahyun\PycharmProjects\PeakPicker\exported_signals
```

#### 스크립트가 수행하는 작업:
1. 지정된 디렉토리에서 모든 `.D` 폴더를 찾습니다
2. 각 폴더에 대해:
   - `Alt+F` → `Shift+G`로 신호 파일을 불러옵니다
   - `Alt+F` → `E` → `C`로 CSV로 내보냅니다
   - 자동으로 이름을 지정하여 저장합니다

#### 경로 설정 방법

##### 옵션 1: 기본 경로에서 하위 폴더 선택
```
선택 (1 또는 2): 1

하위 폴더 목록에서 번호 선택:
경로 또는 번호: 2
```

##### 옵션 2: 직접 경로 입력
```
선택 (1 또는 2): 2

데이터 디렉토리 경로를 입력하세요: C:\Chem32\1\DATA\MyExperiment
```

#### 예상 출력
```
[1/15] SAMPLE_001

  처리 중: SAMPLE_001.D
    1. File 메뉴 열기...
    2. Load Signal...
    3. 파일 경로 입력...
    4. 파일 열기...
    5. File 메뉴 열기...
    6. Export...
    7. CSV 선택...
    8. Signal export 선택...
    9. Export 실행...
    [성공] 156,482 bytes

  진행 상황: 1/1 성공
  예상 남은 시간: 2.3분

...

================================================================================
  배치 Export 완료
================================================================================

  성공: 15/15 파일
  소요 시간: 3.2분
  출력 디렉토리: C:\Users\Jahyun\PycharmProjects\PeakPicker\exported_signals
```

---

## 2단계: 내보낸 데이터 분석

### 하이브리드 베이스라인 보정을 통한 향상된 분석

`hplc_analyzer_enhanced.py` 스크립트는 자동 베이스라인 보정과 함께 고급 피크 검출을 제공합니다.

#### 기본 사용법
```bash
python hplc_analyzer_enhanced.py "C:\경로\to\csv\files"
```

#### 사용자 지정 출력 디렉토리 지정
```bash
python hplc_analyzer_enhanced.py "C:\경로\to\csv\files" -o "C:\경로\to\results"
```

#### 하이브리드 베이스라인 비활성화 (원본 데이터 사용)
```bash
python hplc_analyzer_enhanced.py "C:\경로\to\csv\files" --no-hybrid-baseline
```

#### 사용자 지정 파일 패턴
```bash
python hplc_analyzer_enhanced.py "C:\경로\to\csv\files" --pattern "EXPORT*.CSV"
```

### 분석 결과물

각 CSV 파일에 대해 다음 내용을 포함한 Excel 파일이 생성됩니다:

1. **Summary (요약) 시트**
   - 샘플 이름
   - 분석 날짜
   - 검출된 피크 개수
   - 총 피크 면적
   - 시간 범위

2. **Peaks (피크 상세) 시트**
   - 피크 번호
   - 체류 시간 (RT)
   - 피크 높이
   - 피크 면적
   - 피크 너비
   - Prominence (돌출도)
   - 신호 대 잡음비 (SNR)
   - 면적 백분율

### 출력 예시
```
Analyzing: EXPORT_SAMPLE_001.CSV
  Data points: 3472
  Time range: 0.00 - 24.99 min
  Intensity range: 0.00 - 21678.97
  Applying hybrid baseline correction...
  Best baseline method: weighted_spline
  Detecting peaks...
  Peaks detected: 7
  Results saved: EXPORT_SAMPLE_001_peaks.xlsx

배치 분석 완료
Total files processed: 15
Successfully analyzed: 15/15 files
Results saved to: C:\경로\to\csv\files\analysis_results
```

---

## 고급 사용법

### 하이브리드 베이스라인 보정

향상된 분석기는 다음을 결합한 정교한 베이스라인 보정 알고리즘을 사용합니다:
- **Valley Detection (골짜기 감지)**: 피크 사이의 계곡을 찾습니다
- **Local Minimum Search (지역 최소값 검색)**: 각 구간에서 베이스라인 포인트를 식별합니다
- **Weighted Spline Fitting (가중 스플라인 피팅)**: 신뢰도 기반 가중 보간을 수행합니다
- **Adaptive Methods (적응형 방법)**: 최적 접근법을 자동으로 선택합니다

#### 베이스라인 방법
세 가지 방법이 자동으로 테스트되며 최적의 방법이 선택됩니다:
1. **Weighted Spline**: 신뢰도 가중 스플라인 보간 (가장 효과적)
2. **Adaptive Connect**: 구간별 적응형 연결
3. **Robust Fit**: 이상값에 강한 피팅

### 스케일 강건성

하이브리드 베이스라인 방법은 광범위한 신호 강도에서 안정적으로 작동합니다:
- **테스트 범위**: 0.01배 ~ 10배 (100배 변동)
- **성공률**: 모든 스케일에서 100%
- **일관된 검출**: 모든 조건에서 주요 피크 검출

### 프로그래밍 방식 사용

```python
from hplc_analyzer_enhanced import EnhancedHPLCAnalyzer

# 분석기 생성
analyzer = EnhancedHPLCAnalyzer(
    data_directory="C:/경로/to/csv/files",
    output_directory="C:/경로/to/results",
    use_hybrid_baseline=True
)

# 단일 파일 분석
result = analyzer.analyze_csv_file(Path("EXPORT_001.CSV"))

# 모든 CSV 파일 일괄 분석
results = analyzer.batch_analyze(file_pattern="*.CSV")

# 결과 접근
for result in results:
    if 'error' not in result:
        print(f"파일: {result['file']}")
        print(f"피크 수: {len(result['peaks'])}")
        for peak in result['peak_data']:
            print(f"  RT {peak['retention_time']:.2f}: 면적 {peak['area']:.2f}")
```

### 기존 코드와 통합

```python
# 하이브리드 베이스라인 보정기를 독립적으로 사용
from hybrid_baseline import HybridBaselineCorrector
import pandas as pd
import numpy as np

# 데이터 로드
df = pd.read_csv('your_data.csv', header=None, sep='\t', encoding='utf-16-le')
time = df[0].values
intensity = df[1].values

# 베이스라인 보정 적용
corrector = HybridBaselineCorrector(time, intensity)

# 앵커 포인트 찾기 (골짜기 + 지역 최소값)
anchor_points = corrector.find_baseline_anchor_points(
    valley_prominence=0.01,
    percentile=10,
    min_distance=10
)

print(f"발견된 앵커 포인트: {len(anchor_points)}개")
for point in anchor_points[:5]:
    print(f"  {point.type}: RT {time[point.index]:.2f}, 신뢰도 {point.confidence:.2f}")

# 베이스라인 생성
baseline = corrector.generate_hybrid_baseline(method='weighted_spline')

# 또는 자동 최적화
baseline, best_params = corrector.optimize_baseline()
print(f"최적 방법: {best_params['method']}")

# 보정 적용
corrected = intensity - baseline
corrected = np.maximum(corrected, 0)
```

---

## 문제 해결

### 자동 내보내기 문제

**문제**: 내보내기 스크립트가 작동하지 않음
- **해결책**: 스크립트 실행 전 Chemstation 창이 활성화되어 있는지 확인
- **해결책**: 키보드 단축키가 Chemstation 버전과 일치하는지 확인
- **해결책**: 타이밍 문제가 있으면 `pyautogui.PAUSE` 값을 증가

**문제**: 잘못된 파일이 내보내짐
- **해결책**: 스크립트의 `base_dir` 경로 확인
- **해결책**: 지정된 디렉토리에 `.D` 폴더가 있는지 확인

**문제**: 경로 입력 시 에러 발생
- **해결책**: 경로를 드래그 앤 드롭하면 따옴표가 자동으로 포함됨 (스크립트가 자동 제거)
- **해결책**: 경로에 한글이나 특수문자가 포함되어 있는지 확인

### 분석 문제

**문제**: 피크가 검출되지 않음
- **해결책**: CSV 파일 형식이 올바른지 확인 (탭 구분, UTF-16-LE 인코딩)
- **해결책**: `--no-hybrid-baseline`으로 원본 데이터 확인
- **해결책**: 신호가 너무 노이즈가 많을 수 있음 - 원본 크로마토그램 확인

**문제**: 너무 많은 거짓 피크가 검출됨
- **해결책**: 하이브리드 베이스라인이 자동으로 처리해야 함
- **해결책**: 노이즈 레벨이 올바르게 추정되었는지 확인
- **해결책**: 필요시 코드에서 임계값을 수동으로 조정

**문제**: 베이스라인 보정이 제대로 작동하지 않음
- **해결책**: 하이브리드 베이스라인은 여러 방법 보유 - 최적화기가 최적을 선택해야 함
- **해결책**: 다른 prominence factor로 분석 시도
- **해결책**: 데이터에 특이한 특성이 있는지 확인 (드리프트, 아티팩트)

---

## 성능 벤치마크

### 내보내기 속도
- **단일 파일**: ~5-10초 (Chemstation GUI 작업 포함)
- **배치 (100개 파일)**: ~8-15분

### 분석 속도
- **단일 크로마토그램**: 1-3초
- **배치 (100개 파일)**: 2-5분
- **하이브리드 베이스라인**: 파일당 +0.5초 (가치 있음!)

### 정확도
- **피크 검출**: 잘 분리된 피크에 대해 >95% 정확도
- **스케일 강건성**: 0.01배-10배 범위에서 100% 주요 피크 검출
- **베이스라인 품질**: 자동 최적화로 최적 방법 선택 보장

---

## 파일 구조

```
PeakPicker/
├── auto_export_keyboard_final.py   # 1단계: Chemstation에서 내보내기
├── hplc_analyzer_enhanced.py       # 2단계: CSV 파일 분석
├── hybrid_baseline.py              # 베이스라인 보정 엔진
├── chemstation_parser.py           # Chemstation 형식 파싱
├── result_exporter.py              # 결과 내보내기
├── USAGE_EXAMPLES.md               # 이 파일
└── backup_scripts/                 # 구 버전/테스트 스크립트
    ├── test_*.py
    ├── demonstrate_*.py
    └── *.png
```

---

## 팁과 모범 사례

1. **항상 첫 번째 파일 확인**: 첫 번째 분석 결과를 수동으로 확인하여 올바른 피크 검출 확인

2. **배치 처리**: 대용량 데이터셋의 경우 야간에 분석 실행

3. **백업 유지**: 원본 CSV 파일은 수정되지 않음 - 재분석 가능

4. **파라미터 조정**: 필요시 분석기 코드에서 검출 파라미터 조정

5. **품질 관리**: 출력의 SNR 값 확인 - SNR < 3인 피크는 노이즈일 수 있음

6. **베이스라인 검사**: 의심스러운 결과의 경우 베이스라인 플롯 확인 (출력에 추가 가능)

---

## 지원 및 문서

문제나 질문이 있는 경우:
1. 이 사용 가이드 확인
2. 스크립트의 코드 주석 검토
3. backup_scripts/에서 예제 및 테스트 확인
4. CSV 파일 형식이 예상 형식과 일치하는지 확인

---

## 버전 히스토리

- **v2.0** (현재): 하이브리드 베이스라인 보정, 향상된 분석, 대화형 경로 입력
- **v1.0**: 자동 내보내기가 포함된 기본 피크 검출

---

마지막 업데이트: 2025-11-06