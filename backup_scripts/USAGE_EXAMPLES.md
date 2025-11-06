# HPLC Peak Picker - 사용 예제

## 목차
1. [기본 사용법](#기본-사용법)
2. [고급 옵션](#고급-옵션)
3. [Python 스크립트에서 사용](#python-스크립트에서-사용)
4. [결과 해석](#결과-해석)
5. [문제 해결](#문제-해결)

---

## 기본 사용법

### 방법 1: 간단한 실행 (추천)

```bash
python quick_start.py
```

위즈드 형식으로 옵션을 선택하면서 분석을 실행합니다.

### 방법 2: 배치 파일 실행

1. `run_analysis.bat` 파일을 텍스트 에디터로 열기
2. `DATA_DIR` 변수를 본인의 데이터 경로로 수정
3. 배치 파일 더블클릭하여 실행

### 방법 3: 커맨드 라인 직접 실행

```bash
python hplc_analyzer.py "C:/Chem32/1/DATA"
```

---

## 고급 옵션

### 1. 특정 하위 폴더만 분석

```bash
python hplc_analyzer.py "C:/Chem32/1/DATA/1. DeoxyNucleoside HPLC raw data"
```

### 2. Peak Detection 파라미터 조정

**Peak가 너무 많이 검출되는 경우:**
```bash
python hplc_analyzer.py "C:/Chem32/1/DATA" --prominence 500 --min-height 1000
```

**Peak가 검출되지 않는 경우:**
```bash
python hplc_analyzer.py "C:/Chem32/1/DATA" --prominence 50 --min-height 100
```

**작은 Peak도 검출:**
```bash
python hplc_analyzer.py "C:/Chem32/1/DATA" --min-width 0.005
```

### 3. 특정 Retention Time 검색

예를 들어, RT 2.5분, 5.8분, 10.2분의 peak를 찾고 싶을 때:

```bash
python hplc_analyzer.py "C:/Chem32/1/DATA" --target-rts 2.5 5.8 10.2
```

검색 범위를 더 넓게 하려면 (±0.2분):
```bash
python hplc_analyzer.py "C:/Chem32/1/DATA" --target-rts 2.5 5.8 10.2 --rt-tolerance 0.2
```

### 4. 출력 형식 선택

**CSV로 저장:**
```bash
python hplc_analyzer.py "C:/Chem32/1/DATA" --format csv
```

**Excel과 CSV 둘 다:**
```bash
python hplc_analyzer.py "C:/Chem32/1/DATA" --format both
```

### 5. 크로마토그램 그림 생성

```bash
python hplc_analyzer.py "C:/Chem32/1/DATA"
```
(기본값으로 그림이 생성됩니다)

**그림 생성 안 함 (빠른 분석):**
```bash
python hplc_analyzer.py "C:/Chem32/1/DATA" --no-plots
```

### 6. 출력 디렉토리 지정

```bash
python hplc_analyzer.py "C:/Chem32/1/DATA" -o "C:/Results/MyAnalysis_2025"
```

---

## Python 스크립트에서 사용

### 예제 1: 기본 배치 분석

```python
from hplc_analyzer import HPLCAnalyzer

# Analyzer 생성
analyzer = HPLCAnalyzer(
    data_directory="C:/Chem32/1/DATA",
    output_directory="C:/Results",
)

# 전체 분석 실행
results = analyzer.analyze_batch(
    recursive=True,
    export_format='excel',
    create_plots=True,
)

print(f"Successfully analyzed {len(results)} samples")
```

### 예제 2: 특정 RT의 Peak 비교

```python
from hplc_analyzer import HPLCAnalyzer

analyzer = HPLCAnalyzer("C:/Chem32/1/DATA")

# 전체 샘플에서 RT 5.8 ± 0.1분의 peak 찾기
target_peaks = analyzer.analyze_with_target_peaks(
    target_rts=[5.8],
    tolerance=0.1
)

# 결과 확인
for rt, peak_list in target_peaks.items():
    print(f"\nRT {rt} 근처의 peak:")
    for item in peak_list:
        peak = item['peak']
        print(f"  {item['sample']}: Area={peak.area:.1f}, Height={peak.height:.1f}")
```

### 예제 3: 단일 파일 분석

```python
from chemstation_parser import read_chemstation_file
from peak_detector import PeakDetector
import matplotlib.pyplot as plt

# 파일 읽기
time, intensity = read_chemstation_file("path/to/file.ch")

# Peak detection
detector = PeakDetector(time, intensity, prominence=100)
peaks = detector.detect_peaks()

# 결과 출력
for i, peak in enumerate(peaks, 1):
    print(f"Peak {i}: RT={peak.rt:.2f} min, Area={peak.area:.1f}")

# 시각화
plt.figure(figsize=(12, 5))
plt.plot(time, intensity, 'b-', linewidth=0.5)
for peak in peaks:
    plt.plot(peak.rt, intensity[peak.index], 'ro', markersize=8)
plt.xlabel('Time (min)')
plt.ylabel('Intensity')
plt.title('Chromatogram')
plt.savefig('my_chromatogram.png', dpi=300)
```

### 예제 4: 커스텀 Peak Detection

```python
from chemstation_parser import read_chemstation_file
from peak_detector import PeakDetector

time, intensity = read_chemstation_file("path/to/file.ch")

# 매우 민감한 검출 (작은 peak도 검출)
detector_sensitive = PeakDetector(
    time, intensity,
    prominence=50,      # 낮은 prominence
    min_height=100,     # 낮은 최소 높이
    min_width=0.005,    # 좁은 peak도 검출
)
peaks = detector_sensitive.detect_peaks()

print(f"Detected {len(peaks)} peaks (sensitive mode)")
```

### 예제 5: 특정 범위 적분

```python
from chemstation_parser import read_chemstation_file
from peak_detector import PeakDetector

time, intensity = read_chemstation_file("path/to/file.ch")
detector = PeakDetector(time, intensity)

# 5.0 ~ 6.0분 범위 적분
area = detector.integrate_range(
    rt_start=5.0,
    rt_end=6.0,
    baseline_correct=True
)

print(f"Area between 5.0-6.0 min: {area:.2f}")
```

---

## 결과 해석

### Excel 파일 구조

#### Sheet 1: Metadata
- Sample Name: 샘플 이름 (.D 폴더명)
- Analysis Date: 분석 수행 날짜/시간
- Number of Peaks: 검출된 peak 개수
- Total Area: 모든 peak의 area 합계

#### Sheet 2: Peak Data
- **Peak #**: Peak 번호 (RT 순서)
- **RT (min)**: Peak 최고점의 retention time
- **RT Start**: Peak 시작 시간
- **RT End**: Peak 끝 시간
- **Height**: Peak 높이 (baseline 보정 후)
- **Area**: Peak area (적분값)
- **Width (min)**: Peak 너비 (FWHM)
- **% Area**: 전체 area 대비 비율

#### Sheet 3: Summary
- Total Peaks: 총 peak 수
- Total Area: 총 area
- Average Peak Height: 평균 peak 높이
- Average Peak Width: 평균 peak 너비
- Retention Time Range: RT 범위

### Batch Summary 파일

여러 샘플을 분석하면 생성되는 `batch_summary_*.xlsx` 파일:
- **Summary 시트**: 모든 샘플의 요약
- **All Peaks 시트**: 모든 샘플의 모든 peak 데이터

### Target RT Analysis 파일

특정 RT를 검색하면 생성되는 `target_peaks_analysis_*.xlsx` 파일:
- 각 target RT마다 별도 시트 생성
- 모든 샘플에서 해당 RT의 peak 비교

---

## 문제 해결

### 문제 1: "File not found" 에러

**원인:** 경로가 잘못되었거나 파일이 없음

**해결:**
```bash
# 경로를 확인하고 / 또는 \\ 사용
python hplc_analyzer.py "C:/Chem32/1/DATA"
# 또는
python hplc_analyzer.py "C:\\Chem32\\1\\DATA"
```

### 문제 2: Peak가 전혀 검출되지 않음

**원인:** Peak detection 파라미터가 너무 엄격함

**해결:**
```bash
# 모든 자동 설정 사용
python hplc_analyzer.py "C:/Chem32/1/DATA"

# 또는 낮은 임계값 설정
python hplc_analyzer.py "C:/Chem32/1/DATA" --prominence 10 --min-height 10
```

### 문제 3: 너무 많은 peak가 검출됨 (노이즈도 peak로 인식)

**원인:** Peak detection 파라미터가 너무 관대함

**해결:**
```bash
# 더 높은 임계값 설정
python hplc_analyzer.py "C:/Chem32/1/DATA" --prominence 1000 --min-height 500 --min-width 0.02
```

### 문제 4: Negative area가 나타남

**원인:** Baseline이 peak보다 높은 경우 (역 peak)

**해결:**
- 이는 정상적인 경우도 있음 (용매 피크 등)
- 무시하거나, min-height를 높여서 필터링

### 문제 5: 실행이 너무 느림

**원인:** 크로마토그램 그림 생성에 시간이 많이 걸림

**해결:**
```bash
# 그림 생성 생략
python hplc_analyzer.py "C:/Chem32/1/DATA" --no-plots
```

### 문제 6: 특정 파일만 분석하고 싶음

**해결:**
```bash
# 특정 하위 폴더만 지정
python hplc_analyzer.py "C:/Chem32/1/DATA/specific_folder"
```

또는 Python에서:
```python
from pathlib import Path
from hplc_analyzer import HPLCAnalyzer

analyzer = HPLCAnalyzer("C:/Chem32/1/DATA")
result = analyzer.analyze_file(Path("path/to/specific/file.ch"))
```

### 문제 7: "Invalid time range" 경고

**원인:** 파일 메타데이터에 시간 정보가 없음

**영향:** 시간축이 추정값으로 대체됨 (보통 문제없음)

**해결:** 무시해도 되며, 데이터는 정상적으로 처리됨

---

## 추가 팁

### 1. 여러 프로젝트를 동시에 분석

```bash
# 프로젝트별로 다른 출력 폴더 사용
python hplc_analyzer.py "C:/Chem32/1/DATA/Project1" -o "Results/Project1"
python hplc_analyzer.py "C:/Chem32/1/DATA/Project2" -o "Results/Project2"
```

### 2. 분석 결과 백업

출력 폴더를 정기적으로 백업하는 것을 추천합니다:
```
analysis_results/
├── batch_summary_20250104_143022.xlsx  # 날짜/시간 포함
├── sample1_peaks.xlsx
└── sample1_chromatogram.png
```

### 3. 재현 가능한 분석

파라미터를 기록해두면 나중에 동일한 조건으로 재분석 가능:
```bash
# 파라미터를 파일에 저장
echo "python hplc_analyzer.py 'C:/Chem32/1/DATA' --prominence 200 --min-height 300" > my_analysis.sh
```

### 4. 대용량 데이터 처리

수백 개 이상의 파일을 처리할 때는 `--no-plots` 사용을 권장:
```bash
python hplc_analyzer.py "C:/Chem32/1/DATA" --no-plots --format csv
```

---

## 도움말

더 많은 옵션을 보려면:
```bash
python hplc_analyzer.py --help
```

문제가 계속되면 README.md 파일을 참조하거나 이슈를 등록하세요.
