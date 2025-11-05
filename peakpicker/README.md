# PeakPicker GUI Application

크로마토그래피 데이터 분석을 위한 웹 기반 GUI 애플리케이션

## 개발 버전

**v0.1.0 - Feature 1: Data Loading & Chromatogram Visualization**

## 현재 구현된 기능

### ✅ Feature 1: 데이터 로드 및 크로마토그램 시각화
- 파일 업로드 기능 (CSV, TXT, Excel)
- 크로마토그램 시각화
- 반응형 웹 UI (Streamlit)
- Time range 필터링
- 데이터 정보 표시 (데이터 포인트 수, 시간 범위, 강도 범위)
- Raw 데이터 테이블 뷰
- 데이터 다운로드 기능
- 플롯 커스터마이징 (색상, 선 굵기, 그리드)

### 🚧 개발 예정 기능

- **Feature 2**: Peak detection 및 integration
- **Feature 3**: Baseline 수동 조정 및 Peak split
- **Feature 4**: Excel 결과 출력
- **Feature 5**: Standard curve 및 정량 분석
- **Feature 6**: GUI 통합 및 최종 완성

## 설치 방법

### 1. 필수 패키지 설치

```bash
cd peakpicker
pip install -r requirements.txt
```

### 2. 애플리케이션 실행

```bash
streamlit run app.py
```

또는 프로젝트 루트에서:

```bash
cd peakpicker
python -m streamlit run app.py
```

브라우저가 자동으로 열리고 `http://localhost:8501`에서 앱이 실행됩니다.

## 사용 방법

### 1. 데이터 파일 준비

지원되는 파일 형식:
- **CSV**: 두 개의 컬럼 (Time, Intensity)
- **TXT**: 공백 또는 탭으로 구분된 두 개의 컬럼
- **Excel**: 첫 번째 시트에 Time과 Intensity 컬럼

예시 CSV 형식:
```csv
Time,Intensity
0.00,12.5
0.02,13.2
0.04,14.1
...
```

### 2. 파일 업로드

1. 좌측 사이드바에서 "Choose a chromatography data file" 클릭
2. 데이터 파일 선택
3. 자동으로 데이터 로드 및 시각화

### 3. 플롯 커스터마이징

사이드바에서 다음 옵션 조정 가능:
- **Line Color**: 크로마토그램 선 색상
- **Line Width**: 선 굵기 (0.5 - 3.0)
- **Show Grid**: 그리드 표시/숨기기

### 4. Time Range 필터링

1. "Enable Time Filter" 체크박스 활성화
2. Start Time과 End Time 입력
3. 선택한 범위만 확대하여 표시

### 5. 데이터 확인 및 다운로드

- "View Raw Data" 확장 메뉴에서 데이터 테이블 확인
- "Download Data as CSV" 버튼으로 처리된 데이터 다운로드

## 예시 데이터

`examples/sample_chromatogram.csv` 파일을 사용하여 앱을 테스트할 수 있습니다.

이 파일은 두 개의 피크를 가진 가상 크로마토그램 데이터입니다:
- Peak 1: ~1.3 min
- Peak 2: ~4.0 min

## 프로젝트 구조

```
peakpicker/
├── app.py                      # Streamlit 메인 애플리케이션
├── requirements.txt            # Python 패키지 의존성
├── README.md                   # 이 문서
├── modules/
│   ├── __init__.py
│   ├── data_loader.py         # 데이터 로딩 모듈
│   └── visualizer.py          # 크로마토그램 시각화 모듈
└── examples/
    └── sample_chromatogram.csv # 예시 데이터 파일
```

## 기술 스택

- **Frontend**: Streamlit (반응형 웹 UI)
- **Data Processing**: pandas, numpy
- **Visualization**: matplotlib
- **File I/O**: openpyxl (Excel 지원)

## 개발 로드맵

### Phase 1: 기본 기능 (현재)
- [x] 데이터 로드
- [x] 크로마토그램 시각화
- [x] 파일 브라우저
- [x] 반응형 UI

### Phase 2: Peak 분석
- [ ] Peak detection
- [ ] Peak integration
- [ ] Peak area 계산

### Phase 3: 고급 기능
- [ ] Baseline 수동 조정
- [ ] Peak split 기능
- [ ] Peak 파라미터 조정

### Phase 4: 출력 및 보고서
- [ ] Excel 결과 출력
- [ ] Peak 정보 테이블
- [ ] 배치 분석

### Phase 5: 정량 분석
- [ ] Standard curve 입력
- [ ] 농도 자동 계산
- [ ] 희석배수 반영

### Phase 6: 통합 및 완성
- [ ] 전체 워크플로우 통합
- [ ] 사용자 가이드
- [ ] 성능 최적화

## 문제 해결

### 앱이 실행되지 않는 경우

1. Python 버전 확인 (3.8 이상 권장):
   ```bash
   python --version
   ```

2. 패키지 재설치:
   ```bash
   pip install -r requirements.txt --upgrade
   ```

3. Streamlit 버전 확인:
   ```bash
   streamlit --version
   ```

### 파일 업로드 오류

- 파일 형식이 지원되는지 확인 (CSV, TXT, Excel)
- 파일에 Time과 Intensity 데이터가 있는지 확인
- 파일 크기가 너무 크지 않은지 확인 (200MB 제한)

## 기여

이 프로젝트는 기능별 브랜치로 개발됩니다:
- `feature/01-data-loading-visualization` (현재)
- `feature/02-peak-detection-integration`
- `feature/03-baseline-peak-handling`
- `feature/04-excel-export`
- `feature/05-quantitative-analysis`
- `feature/06-gui-integration`

## 라이선스

MIT License

## 문의

문제가 발생하거나 기능 요청이 있으면 이슈를 등록해주세요.
