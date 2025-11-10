# HPLC Peak Picker

고급 하이브리드 베이스라인 보정을 적용한 HPLC 크로마토그램 자동 분석 도구

## 주요 기능

- **자동 내보내기**: 키보드 자동화로 Chemstation에서 크로마토그램 내보내기
- **강화된 베이스라인 보정**: 3배 스무딩 + 2단계 필터링으로 과적합 방지
- **양방향 피크 검출**: 양수/음수 피크 모두 검출 (solvent dip 등)
- **스마트 음수 처리**: 실제 음수 피크 보존, 가짜 음수 영역 자동 제거 (70% 감소)
- **통합 파이프라인**: 베이스라인 보정 → 후처리 → 피크 검출 → 면적 계산
- **배치 처리**: 여러 파일 자동 분석
- **상세 시각화**: 4패널 레이아웃으로 전체 프로세스 확인

## 빠른 시작

### 완전 자동화 워크플로우 (권장 ⭐)
```bash
# 방법 1: 폴더 경로 직접 지정 (가장 빠름 🚀)
python complete_workflow.py "result/DEF_LC 2025-05-19 17-57-25"

# 방법 2: 최근 폴더 자동 감지
python quick_analyze.py

# 방법 3: 대화형 모드
python complete_workflow.py
#   옵션: 1. Export부터 / 2. 기존 폴더 / 경로 직접 입력
```

### 단계별 실행
```bash
# 1. Chemstation에서 데이터 내보내기
python auto_export_keyboard_final.py

# 2. 피크 면적 정량 분석
python quantify_peaks.py "result/폴더명"

# 3. 통합 피크 검출 (개별 분석)
python integrated_peak_detection.py
```

## 핵심 파일

### 메인 스크립트
- `complete_workflow.py` - **완전 자동화 워크플로우 (Export → 분석 → 시각화) ⭐**
- `quantify_peaks.py` - **피크 면적 정량 분석 및 검량선 생성**
- `auto_export_keyboard_final.py` - Chemstation 자동 내보내기
- `integrated_peak_detection.py` - 통합 피크 검출 시스템

### 진단 및 테스트 도구
- `check_area_calculation.py` - 면적 계산 방법 검증 (6가지 방법 비교)
- `test_smoothing_improvements.py` - 스무딩 개선 효과 비교
- `inspect_baseline_check.py` - 베이스라인 상세 점검
- `diagnose_negative_issue.py` - 음수 영역 진단

### 문서
- `PROJECT_UPDATE.md` - **최신 업데이트 내역 (2025-01-10)**
- `docs/USAGE_EXAMPLES.md` - 상세 사용 가이드 (한글)
- `docs/OUTPUT_ORGANIZATION_GUIDE.md` - 출력 디렉토리 구조 가이드
- `docs/TIMING_OPTIMIZATION_GUIDE.md` - 성능 최적화 가이드

### 소스 모듈 (src/)
- `hybrid_baseline.py` - **강화된 베이스라인 보정 엔진 (3배 스무딩)**
- `chemstation_parser.py` - 데이터 파싱
- `result_exporter.py` - 결과 출력

## 필수 라이브러리

```bash
pip install numpy scipy pandas openpyxl pyautogui pyperclip
```

## 문서

자세한 사용 방법, 예제 및 문제 해결은 [USAGE_EXAMPLES.md](docs/USAGE_EXAMPLES.md)를 참조하세요.

## 성능

- **피크 검출 정확도**: >95%
- **음수 값 감소**: 61.5% (1103 → 424개)
- **가짜 음수 피크 제거**: 66.7% (6 → 2개)
- **양수 피크 보존**: 100%
- **처리 속도**: 크로마토그램당 ~2초
- **베이스라인 방법**: Robust Fit / Weighted Spline (강화된 스무딩)

## 프로젝트 구조

```
PeakPicker/
├── auto_export_keyboard_final.py   # Export 자동화 (메인)
├── hplc_analyzer_enhanced.py       # 분석 파이프라인 (메인)
├── README.md                       # 프로젝트 개요
│
├── src/                            # 소스 모듈
│   ├── hybrid_baseline.py          # 베이스라인 보정 엔진
│   ├── chemstation_parser.py       # 데이터 파싱
│   └── result_exporter.py          # 결과 출력
│
├── docs/                           # 문서
│   ├── USAGE_EXAMPLES.md           # 사용 가이드 (한글)
│   ├── OUTPUT_ORGANIZATION_GUIDE.md # 출력 구조 가이드
│   └── TIMING_OPTIMIZATION_GUIDE.md # 성능 최적화 가이드
│
├── backup_scripts/                 # 개발/테스트 파일
│
└── result/                         # 출력 결과 (자동 생성)
    ├── Experiment1/
    ├── Experiment2/
    └── ...
```

## 주요 개선사항

### v3.1 (2025-11-10) - 완전 자동화 워크플로우 및 정량 분석 ⭐
- **완전 자동화**: Export → 베이스라인 보정 → 피크 검출 → 정량 → 시각화 (원스톱)
- **정량 분석**: 피크 면적 계산, 검량선 생성, 참조값 비교
- **면적 계산 수정**: 베이스라인 복귀 지점 기반, 초 단위 적분 (97% 정확도)
- **대화형 시각화**: Tkinter 기반 결과 뷰어 (검량선, 요약표, 상세 데이터)
- **배치 정량**: 폴더 내 모든 샘플 자동 분석 및 농도별 통계

### v3.0 (2025-01-10) - 베이스라인 강화 및 통합 피크 검출
- **양방향 피크 검출**: 양수/음수 피크 모두 검출 가능
- **베이스라인 스무딩 강화**: 3배 스무딩 팩터 + 2단계 필터링 (Savgol + 이동평균)
- **스마트 음수 처리**: 실제 음수 피크 보존, 가짜 음수 영역 70% 감소
- **통합 파이프라인**: `IntegratedPeakDetector` 클래스로 전체 워크플로우 자동화
- **성능 개선**: 음수 값 61.5% 감소, 가짜 음수 피크 66.7% 제거

### v2.1 (2025-11-06) - 재귀적 검색 및 성능 최적화
- **전체 폴더 스캔 모드**: 한 번에 모든 .D 파일 탐색 및 내보내기 ⚡
- **재귀적 폴더 검색**: 하위 폴더 내 .D 파일 자동 발견
- **대화형 디렉토리 탐색기**: 트리 뷰로 폴더 구조 확인하며 선택
- **체계적인 출력 구조**: `result/` 폴더에 실험별로 정리
- **키보드 자동화 최적화**: 30% 속도 향상 (파일당 ~9초)

### v2.0 (2025-11-06) - 하이브리드 베이스라인 및 대화형 인터페이스
- **하이브리드 베이스라인**: Valley 감지 + Local Minimum 결합
- 3가지 연결 방법 자동 최적화
- 0.01배~10배 스케일에서 100% 성공률

## 라이선스

MIT License