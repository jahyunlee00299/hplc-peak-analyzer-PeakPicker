# 프로젝트 구조

## 개요
PeakPicker는 깔끔하고 체계적인 구조로 정리되어 있습니다.

## 디렉토리 구조

```
PeakPicker/
│
├── 📜 메인 스크립트
│   ├── auto_export_keyboard_final.py   # Chemstation 자동 Export
│   └── hplc_analyzer_enhanced.py       # HPLC 데이터 분석
│
├── 📚 docs/                            # 문서 폴더
│   ├── USAGE_EXAMPLES.md               # 상세 사용 가이드 (한글)
│   ├── OUTPUT_ORGANIZATION_GUIDE.md    # 출력 구조 가이드
│   └── TIMING_OPTIMIZATION_GUIDE.md    # 성능 최적화 가이드
│
├── 🔧 src/                             # 소스 모듈
│   ├── hybrid_baseline.py              # 베이스라인 보정 엔진
│   ├── chemstation_parser.py           # Chemstation 데이터 파싱
│   └── result_exporter.py              # 결과 Excel 출력
│
├── 💾 backup_scripts/                  # 백업/개발 스크립트
│   └── (테스트 및 개발 중 파일들)
│
├── 📊 result/                          # 출력 결과 (자동 생성)
│   ├── Experiment1/
│   │   ├── Sample1.csv
│   │   ├── Sample2.csv
│   │   └── analysis_results/
│   │       ├── Sample1_peaks.xlsx
│   │       └── Sample2_peaks.xlsx
│   ├── Experiment2/
│   └── ...
│
├── 📄 README.md                        # 프로젝트 개요
├── 📋 requirements.txt                 # Python 패키지 의존성
└── 🚫 .gitignore                       # Git 제외 설정
```

## 파일 설명

### 메인 스크립트

#### `auto_export_keyboard_final.py`
- **용도**: Chemstation에서 .D 폴더 → CSV 자동 내보내기
- **실행**: `python auto_export_keyboard_final.py`
- **기능**:
  - 대화형 디렉토리 탐색 (트리 뷰)
  - 전체 폴더 스캔 모드
  - 재귀적 .D 폴더 검색
  - 키보드 자동화 (PyAutoGUI)

#### `hplc_analyzer_enhanced.py`
- **용도**: CSV 파일 분석 및 피크 검출
- **실행**: `python hplc_analyzer_enhanced.py "경로/to/csv"`
- **기능**:
  - 하이브리드 베이스라인 보정
  - 적응형 피크 검출
  - Excel 결과 리포트 생성

### 소스 모듈 (src/)

#### `hybrid_baseline.py`
- Valley 감지 + Local Minimum 하이브리드 베이스라인
- 3가지 연결 방법 (weighted_spline, adaptive_connect, robust_fit)
- 0.01배~10배 스케일에서 강건한 성능

#### `chemstation_parser.py`
- Chemstation CSV 파일 파싱
- 데이터 검증 및 전처리

#### `result_exporter.py`
- Excel 리포트 생성 (openpyxl)
- Summary 및 Peak 상세 정보 시트

### 문서 (docs/)

#### `USAGE_EXAMPLES.md`
- 한글 사용 가이드
- 단계별 실행 방법
- 문제 해결 팁

#### `OUTPUT_ORGANIZATION_GUIDE.md`
- 출력 디렉토리 구조 설명
- 3가지 출력 옵션
- 실험별 폴더 정리 방법

#### `TIMING_OPTIMIZATION_GUIDE.md`
- 키보드 자동화 타이밍 최적화
- 단계별 시간 설정
- 성능 튜닝 가이드

## 워크플로우

### 1단계: Export (Chemstation → CSV)
```bash
python auto_export_keyboard_final.py
```
- 옵션 선택 (대화형 탐색 / 직접 입력 / 전체 스캔)
- 출력 경로 설정 (result/{폴더명}/)
- 자동 Export 실행

**결과**: `result/{폴더명}/*.csv`

### 2단계: 분석 (CSV → Excel)
```bash
python hplc_analyzer_enhanced.py "result/{폴더명}"
```
- 베이스라인 보정
- 피크 검출
- Excel 리포트 생성

**결과**: `result/{폴더명}/analysis_results/*_peaks.xlsx`

## 데이터 흐름

```
Chemstation .D 폴더
    ↓
[auto_export_keyboard_final.py]
    ↓
result/{실험명}/Sample*.csv
    ↓
[hplc_analyzer_enhanced.py]
    ↓
result/{실험명}/analysis_results/Sample*_peaks.xlsx
```

## 폴더 관리

### 자동 생성 폴더
- `result/` - 모든 출력 결과
- `result/{실험명}/` - 실험별 CSV 파일
- `result/{실험명}/analysis_results/` - 분석 결과 Excel

### 제외되는 폴더 (.gitignore)
- `__pycache__/`
- `result/`
- `exported_signals/`
- `analysis_results/`
- `*.csv`, `*.xlsx` (결과 파일)
- `*.png`, `*.jpg` (그래프)

### 백업 폴더
- `backup_scripts/` - 개발/테스트 스크립트 보관

## 의존성

### Python 패키지
```bash
pip install numpy scipy pandas openpyxl pyautogui pyperclip
```

### 시스템 요구사항
- Python 3.8+
- Windows OS (Chemstation 호환)
- Chemstation 설치 (auto_export 사용 시)

## 개발 히스토리

### v2.1 (2025-11-06)
- ✅ 프로젝트 구조 개선 (docs/, src/, result/)
- ✅ 전체 폴더 스캔 모드
- ✅ 대화형 트리 뷰
- ✅ 출력 구조 체계화

### v2.0 (2025-11-06)
- ✅ 하이브리드 베이스라인
- ✅ 대화형 경로 입력
- ✅ 한글 문서화

## 참고 문서

- [README.md](../README.md) - 프로젝트 개요
- [USAGE_EXAMPLES.md](USAGE_EXAMPLES.md) - 상세 사용법
- [OUTPUT_ORGANIZATION_GUIDE.md](OUTPUT_ORGANIZATION_GUIDE.md) - 출력 구조
- [TIMING_OPTIMIZATION_GUIDE.md](TIMING_OPTIMIZATION_GUIDE.md) - 성능 최적화
