# HPLC Peak Picker

고급 베이스라인 보정과 피크 디컨볼루션을 적용한 HPLC 크로마토그램 자동 분석 도구

## 주요 기능

- **자동 내보내기**: 키보드 자동화로 Chemstation에서 크로마토그램 내보내기
- **개선된 베이스라인 보정** ✨: RT 기반 슬로프 완화 + 최적화된 앵커 검출
  - 앵커 포인트 82% 감소 (85개 → 15개)
  - 자동 품질 평가 (204점 만점)
  - 피크 검출 성능 유지
- **강건한 피크 검출**: 100배 강도 범위(0.01배~10배)에서 안정적인 검출
- **피크 디컨볼루션** 🆕: 겹친 피크 자동 분리 및 정량
  - 자동 숄더 피크 검출
  - 가우시안 멀티 피팅
  - 비대칭도 기반 자동 판단
  - R² > 0.95 고품질 피팅
- **완전 자동화 워크플로우**: Export → 베이스라인 보정 → 피크 검출 → 디컨볼루션 → 정량
- **스마트 음수 처리**: 실제 음수 피크 보존, 가짜 음수 영역 자동 제거
- **배치 처리**: 여러 파일 자동 분석
- **Excel 리포트**: 피크 상세 정보 + 디컨볼루션 결과

## 빠른 시작

### 방법 1: 통합 워크플로우 (추천) 🆕

```bash
# Export → 분석 → 디컨볼루션을 한번에 실행
python run_complete_workflow.py
```

이 스크립트는:
1. Chemstation에서 CSV 자동 export
2. 베이스라인 보정 및 피크 검출
3. 필요시 자동 피크 디컨볼루션
4. Excel 리포트 생성

### 방법 2: 완전 자동화 워크플로우 (Export부터)

```bash
# 방법 1: 폴더 경로 직접 지정 (가장 빠름 🚀)
python complete_workflow.py "result/DEF_LC 2025-05-19 17-57-25"

# 방법 2: 최근 폴더 자동 감지
python quick_analyze.py

# 방법 3: 대화형 모드
python complete_workflow.py
#   옵션: 1. Export부터 / 2. 기존 폴더 / 경로 직접 입력
```

### 방법 3: 단계별 실행

```bash
# 1. Chemstation에서 데이터 내보내기
python auto_export_keyboard_final.py

# 옵션 선택:
#   1. 대화형 폴더 탐색 (트리 뷰로 폴더 구조 확인)
#   2. 직접 경로 입력
#   3. 전체 폴더 스캔 후 모든 .D 자동 내보내기 ⚡

# 2. 내보낸 CSV 파일 분석 (디컨볼루션 자동 활성화)
python hplc_analyzer_enhanced.py "csv/파일/경로"

# 또는 디컨볼루션 비활성화
python hplc_analyzer_enhanced.py "csv/파일/경로" --no-deconvolution

# 또는 민감도 조정 (기본값: 1.2)
python hplc_analyzer_enhanced.py "csv/파일/경로" --asymmetry-threshold 1.5

# 3. 피크 면적 정량 분석
python quantify_peaks.py "result/폴더명"
```

## 핵심 파일

### 메인 스크립트
- `run_complete_workflow.py` - **통합 워크플로우** (Export → 분석 → 디컨볼루션) 🆕
- `complete_workflow.py` - **완전 자동화 워크플로우** (Export → 분석 → 시각화) ⭐
- `quantify_peaks.py` - **피크 면적 정량 분석 및 검량선 생성**
- `auto_export_keyboard_final.py` - Chemstation 자동 내보내기 (대화형 경로 입력)
- `hplc_analyzer_enhanced.py` - 메인 분석 파이프라인
- `test_deconvolution.py` - 디컨볼루션 테스트 스크립트 🆕
- `integrated_peak_detection.py` - 통합 피크 검출 시스템

### 진단 및 테스트 도구
- `check_area_calculation.py` - 면적 계산 방법 검증 (6가지 방법 비교)
- `test_smoothing_improvements.py` - 스무딩 개선 효과 비교
- `inspect_baseline_check.py` - 베이스라인 상세 점검
- `diagnose_negative_issue.py` - 음수 영역 진단

### 문서
- `DECONVOLUTION_README.md` - **피크 디컨볼루션 상세 가이드** 🆕
- `PROJECT_UPDATE.md` - **최신 업데이트 내역**
- `docs/USAGE_EXAMPLES.md` - 상세 사용 가이드 (한글)
- `docs/OUTPUT_ORGANIZATION_GUIDE.md` - 출력 디렉토리 구조 가이드
- `docs/TIMING_OPTIMIZATION_GUIDE.md` - 성능 최적화 가이드
- `docs/PROJECT_STRUCTURE.md` - 프로젝트 구조 상세 설명
- `docs/BASELINE_IMPROVEMENTS.md` - 베이스라인 개선 사항 ✨

### 소스 모듈 (src/)
- `improved_baseline.py` - **개선된 베이스라인 보정 엔진** ✨
- `peak_deconvolution.py` - **피크 디컨볼루션 엔진** 🆕
- `peak_models.py` - **피크 모델** (Gaussian, Lorentzian, Voigt, EMG) 🆕
- `deconvolution_visualizer.py` - **디컨볼루션 시각화** 🆕
- `hybrid_baseline.py` - 베이스라인 보정 (강화된 스무딩)
- `chemstation_parser.py` - 데이터 파싱
- `result_exporter.py` - 결과 출력

### 예제 (examples/)
- `baseline_example.py` - 베이스라인 보정 4가지 예제

## 필수 라이브러리

```bash
pip install numpy scipy pandas openpyxl pyautogui pyperclip matplotlib
```

## 문서

자세한 사용 방법, 예제 및 문제 해결은 [USAGE_EXAMPLES.md](docs/USAGE_EXAMPLES.md)를 참조하세요.

피크 디컨볼루션 상세 가이드는 [DECONVOLUTION_README.md](DECONVOLUTION_README.md)를 참조하세요.

## 성능

- **피크 검출 정확도**: >95%
- **스케일 강건성**: 0.01배~10배 범위에서 100%
- **음수 값 감소**: 61.5% (1103 → 424개)
- **가짜 음수 피크 제거**: 66.7% (6 → 2개)
- **디컨볼루션 품질**: R² = 0.967 (평균)
- **처리 속도**: 크로마토그램당 ~2초
- **베이스라인 방법**: 자동 선택되는 3가지 알고리즘

## 프로젝트 구조

```
PeakPicker/
├── run_complete_workflow.py       # 통합 워크플로우 (추천) 🆕
├── complete_workflow.py           # 완전 자동화 워크플로우 ⭐
├── quantify_peaks.py              # 정량 분석
├── auto_export_keyboard_final.py  # Export 자동화
├── hplc_analyzer_enhanced.py      # 분석 파이프라인
├── test_deconvolution.py          # 디컨볼루션 테스트 🆕
├── integrated_peak_detection.py   # 통합 피크 검출
├── README.md                      # 프로젝트 개요
├── DECONVOLUTION_README.md        # 디컨볼루션 가이드 🆕
├── PROJECT_UPDATE.md              # 업데이트 내역
│
├── src/                           # 소스 모듈
│   ├── improved_baseline.py       # 개선된 베이스라인 보정 ✨
│   ├── peak_deconvolution.py      # 피크 디컨볼루션 엔진 🆕
│   ├── peak_models.py             # 피크 모델 (Gaussian 등) 🆕
│   ├── deconvolution_visualizer.py # 디컨볼루션 시각화 🆕
│   ├── hybrid_baseline.py         # 베이스라인 보정
│   ├── chemstation_parser.py      # 데이터 파싱
│   └── result_exporter.py         # 결과 출력
│
├── docs/                          # 문서
│   ├── USAGE_EXAMPLES.md          # 사용 가이드 (한글)
│   ├── BASELINE_IMPROVEMENTS.md   # 베이스라인 개선 ✨
│   ├── OUTPUT_ORGANIZATION_GUIDE.md
│   └── TIMING_OPTIMIZATION_GUIDE.md
│
├── backup_scripts/                # 개발/테스트 파일
│
└── result/                        # 출력 결과 (자동 생성)
    ├── Experiment1/
    │   ├── *.csv                  # Export된 CSV
    │   └── analysis_results/      # 분석 결과
    │       ├── *_peaks.xlsx       # Excel 리포트
    │       └── *_deconv.png       # 시각화 (옵션) 🆕
    └── ...
```

## 주요 개선사항

### v3.2 (2025-11-10) - 피크 디컨볼루션 통합 🆕
- **피크 디컨볼루션 엔진**: 겹친 피크 자동 분리
  - 자동 숄더 피크 검출 (2차 미분 분석)
  - 다중 가우시안 피팅 (최대 4개 컴포넌트)
  - 비대칭도 기반 자동 판단 (임계값: 1.2)
  - R² > 0.95 고품질 피팅 보장
- **피크 모델 라이브러리**: Gaussian, Lorentzian, Voigt, EMG
- **시각화 도구**: 원본 vs 디컨볼루션된 피크 비교 플롯
- **Excel 리포트 확장**: Deconvolved_Peaks 시트 추가
- **통합 워크플로우**: Export → 분석 → 디컨볼루션 한번에 실행
- **테스트 검증**: R² = 0.967 평균 피팅 품질

### v3.1 (2025-11-10) - 완전 자동화 워크플로우 및 정량 분석 ⭐
- **완전 자동화**: Export → 베이스라인 보정 → 피크 검출 → 정량 → 시각화 (원스톱)
- **정량 분석 도구** (`quantify_peaks.py`):
  - 검량선 자동 생성 (농도 vs 면적)
  - 샘플 농도 자동 계산
  - 회수율 자동 계산 (spiked vs unspiked)
  - 상세 Excel 리포트 (농도, 회수율, 통계)
- **빠른 분석 도구** (`quick_analyze.py`): 최근 폴더 자동 감지 및 분석
- **향상된 사용성**:
  - 대화형 워크플로우 선택
  - 폴더 경로 직접 지정 지원
  - 더 빠른 실행 (명령줄 인자)
- **개선된 시각화**:
  - 검량선 플롯
  - 회수율 비교 차트
  - 농도별 피크 면적 비교

### v3.0 (2025-11-09) - 음수 처리 개선 및 통합 피크 검출
- **스마트 음수 처리**: 실제 음수 피크 보존, 가짜 음수 영역 제거
  - 음수 값 61.5% 감소 (1103 → 424개)
  - 가짜 음수 피크 66.7% 감소 (6 → 2개)
  - 양수 피크 100% 보존
- **통합 피크 검출 시스템**:
  - 양수/음수 피크 모두 검출 (solvent dip 등)
  - 2단계 필터링: 베이스라인 평균 보정 + 극값 제거
  - 강화된 스무딩 (3배)
- **개선된 베이스라인 보정**:
  - 과적합 방지 (더 부드러운 베이스라인)
  - 피크 영역 정확한 베이스라인 연결
  - 잡음 강건성 향상

### v2.1 (2025-11-06) - 재귀적 검색 및 성능 최적화
- **전체 폴더 스캔 모드**: 한 번에 모든 .D 파일 탐색 및 내보내기 ⚡
- **재귀적 폴더 검색**: 하위 폴더 내 .D 파일 자동 발견
- **대화형 디렉토리 탐색기**: 트리 뷰로 폴더 구조 확인하며 선택
- **체계적인 출력 구조**: `result/` 폴더에 실험별로 정리
- **최적화된 타이밍**: 평균 3.5초/파일 (기존 7초에서 50% 개선)
- **스마트 필터링**: 이미 내보낸 파일 건너뛰기

### v2.0 (2025-11-05) - 베이스라인 보정 개선
- **RT 기반 슬로프 완화**: 큰 RT 간격에서 자동 slope 조정
- **앵커 포인트 82% 감소**: 85개 → 15개로 최적화
- **자동 품질 평가**: 204점 만점 스코어링 시스템
- **3가지 베이스라인 방법**: adaptive_spline, robust_spline, linear
- **피크 영역 선형 베이스라인**: 더 정확한 면적 계산

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 기여

버그 리포트, 기능 제안, 풀 리퀘스트를 환영합니다.

---

**Version**: 3.2
**Last Updated**: 2025-11-10
**Python Version**: 3.7+
**Dependencies**: numpy, scipy, pandas, matplotlib, openpyxl, pyautogui, pyperclip
