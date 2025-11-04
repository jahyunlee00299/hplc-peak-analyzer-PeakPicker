# HPLC Peak Picker

Agilent Chemstation HPLC 데이터의 자동 peak detection 및 integration 도구

## 기능

- ✅ Chemstation .ch 파일 자동 읽기
- ✅ 자동 peak detection
- ✅ Peak area integration (baseline 보정 포함)
- ✅ Retention time (RT) 기반 분석
- ✅ Excel/CSV 결과 export
- ✅ 크로마토그램 시각화 (peak 표시)
- ✅ 배치 처리 (여러 샘플 동시 분석)
- ✅ 특정 RT 검색 기능

## 설치

필요한 Python 패키지 설치:

```bash
pip install numpy pandas scipy matplotlib openpyxl
```

## 사용 방법

### 1. 기본 사용 (전체 디렉토리 분석)

```bash
python hplc_analyzer.py "C:/Chem32/1/DATA"
```

### 2. 특정 하위 디렉토리 분석

```bash
python hplc_analyzer.py "C:/Chem32/1/DATA/1. DeoxyNucleoside HPLC raw data"
```

### 3. Peak detection 파라미터 조정

```bash
python hplc_analyzer.py "C:/Chem32/1/DATA" --prominence 100 --min-height 50 --min-width 0.02
```

### 4. 특정 RT 검색

```bash
python hplc_analyzer.py "C:/Chem32/1/DATA" --target-rts 2.5 5.8 10.2 --rt-tolerance 0.15
```

### 5. CSV로 export

```bash
python hplc_analyzer.py "C:/Chem32/1/DATA" --format csv
```

### 6. 출력 디렉토리 지정

```bash
python hplc_analyzer.py "C:/Chem32/1/DATA" -o "C:/Results/MyAnalysis"
```

## 설정 파일 사용

`config.json` 파일을 편집하여 기본 설정을 저장할 수 있습니다:

```json
{
  "data_directory": "C:/Chem32/1/DATA",
  "peak_detection": {
    "prominence": 100,
    "min_height": 50,
    "min_width": 0.01
  },
  "target_retention_times": [2.5, 5.8, 10.2],
  "rt_tolerance": 0.1
}
```

## 출력 파일

분석 완료 후 다음 파일들이 생성됩니다:

1. **개별 샘플 결과**
   - `{sample_name}_peaks.xlsx` - Peak 데이터 (RT, area, height 등)
   - `{sample_name}_chromatogram.png` - 크로마토그램 이미지

2. **배치 요약** (여러 샘플 분석 시)
   - `batch_summary_{timestamp}.xlsx` - 전체 샘플 요약

3. **Target RT 분석** (--target-rts 사용 시)
   - `target_peaks_analysis_{timestamp}.xlsx` - 특정 RT의 peak 비교

## Excel 출력 형식

각 Excel 파일은 다음 시트들을 포함합니다:

### Metadata 시트
- Sample Name
- Analysis Date
- Number of Peaks
- Total Area
- 파일 경로 등

### Peak Data 시트
| Peak # | RT (min) | RT Start | RT End | Height | Area | Width | % Area |
|--------|----------|----------|--------|--------|------|-------|--------|
| 1      | 2.45     | 2.30     | 2.60   | 150.2  | 325.5| 0.12  | 35.2   |
| 2      | 5.82     | 5.65     | 6.00   | 220.8  | 598.3| 0.18  | 64.8   |

### Summary 시트
- Total Peaks
- Total Area
- Average Peak Height
- Average Peak Width
- Retention Time Range

## 주요 파라미터 설명

### Peak Detection 파라미터

- **prominence**: Peak가 주변보다 얼마나 두드러져야 하는지 (낮을수록 더 많은 peak 검출)
- **min_height**: Peak의 최소 높이
- **min_width**: Peak의 최소 너비 (분 단위)
- **rel_height**: 너비 계산 시 사용하는 상대적 높이 (0.5 = FWHM)

자동 설정 (None)을 사용하면 데이터 범위의 5-10%를 기준으로 자동 계산됩니다.

## 프로그래밍 방식 사용

Python 스크립트에서 직접 사용:

```python
from hplc_analyzer import HPLCAnalyzer

# Analyzer 생성
analyzer = HPLCAnalyzer(
    data_directory="C:/Chem32/1/DATA",
    output_directory="C:/Results",
    prominence=100,
    min_height=50,
)

# 배치 분석 실행
results = analyzer.analyze_batch(
    recursive=True,
    export_format='excel',
    create_plots=True,
)

# 특정 RT 검색
target_peaks = analyzer.analyze_with_target_peaks(
    target_rts=[2.5, 5.8, 10.2],
    tolerance=0.1,
)
```

## 개별 모듈 사용

### Chemstation 파일 읽기

```python
from chemstation_parser import read_chemstation_file

time, intensity = read_chemstation_file("path/to/file.ch")
```

### Peak Detection

```python
from peak_detector import PeakDetector

detector = PeakDetector(time, intensity, prominence=100)
peaks = detector.detect_peaks()

for peak in peaks:
    print(f"RT: {peak.rt:.2f}, Area: {peak.area:.1f}")
```

### 결과 Export

```python
from result_exporter import ResultExporter

exporter = ResultExporter(output_dir="results")
exporter.export_peaks_to_excel(peaks, "my_sample", "Sample Name")
exporter.export_chromatogram_plot(time, intensity, peaks, "my_plot", "Sample Name")
```

## 문제 해결

### Peak가 너무 많이 검출되는 경우
- `--prominence` 값을 높이기
- `--min-height` 값을 높이기
- `--min-width` 값을 높이기

### Peak가 검출되지 않는 경우
- `--prominence` 값을 낮추기
- `--min-height` 값을 낮추기
- `--min-width` 값을 낮추기

### 파일을 읽을 수 없는 경우
- .ch 파일이 Agilent Chemstation 형식인지 확인
- 파일 경로에 한글이나 특수문자가 있는지 확인
- 파일 접근 권한 확인

## 파일 구조

```
PeakPicker/
├── hplc_analyzer.py          # 메인 실행 파일
├── chemstation_parser.py     # Chemstation 파일 파서
├── peak_detector.py          # Peak detection 및 integration
├── result_exporter.py        # 결과 export
├── config.json               # 설정 파일
└── README.md                 # 이 문서
```

## 라이선스

MIT License

## 문의

문제가 발생하거나 기능 요청이 있으면 이슈를 등록해주세요.
