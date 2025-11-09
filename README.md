# HPLC Peak Picker

고급 하이브리드 베이스라인 보정을 적용한 HPLC 데이터 자동 분석 도구

## 주요 기능

- **자동 내보내기**: 키보드 자동화로 Chemstation에서 크로마토그램 내보내기
- **개선된 베이스라인 보정** ✨: RT 기반 슬로프 완화 + 최적화된 앵커 검출
  - 앵커 포인트 82% 감소 (85개 → 15개)
  - 자동 품질 평가 (204점 만점)
  - 피크 검출 성능 유지
- **강건한 피크 검출**: 100배 강도 범위(0.01배~10배)에서 안정적인 검출
- **배치 처리**: 여러 파일 자동 분석
- **Excel 리포트**: 피크 상세 정보가 포함된 전문 분석 리포트

## 빠른 시작

```bash
# 1. Chemstation에서 데이터 내보내기
python auto_export_keyboard_final.py

# 옵션 선택:
#   1. 대화형 폴더 탐색 (트리 뷰로 폴더 구조 확인)
#   2. 직접 경로 입력
#   3. 전체 폴더 스캔 후 모든 .D 자동 내보내기 ⚡

# 2. 내보낸 CSV 파일 분석
python hplc_analyzer_enhanced.py "csv/파일/경로"
```

## 핵심 파일

### 메인 스크립트
- `auto_export_keyboard_final.py` - Chemstation 자동 내보내기 (대화형 경로 입력)
- `hplc_analyzer_enhanced.py` - 메인 분석 파이프라인

### 문서 (docs/)
- `USAGE_EXAMPLES.md` - 상세 사용 가이드 (한글)
- `OUTPUT_ORGANIZATION_GUIDE.md` - 출력 디렉토리 구조 가이드
- `TIMING_OPTIMIZATION_GUIDE.md` - 성능 최적화 가이드
- `PROJECT_STRUCTURE.md` - 프로젝트 구조 상세 설명
- `BASELINE_IMPROVEMENTS.md` - 베이스라인 개선 사항 ✨

### 소스 모듈 (src/)
- `improved_baseline.py` - **개선된 베이스라인 보정 엔진** ✨
- `hybrid_baseline.py` - 기존 베이스라인 보정 (레거시)
- `chemstation_parser.py` - 데이터 파싱
- `result_exporter.py` - 결과 출력

### 예제 (examples/)
- `baseline_example.py` - 베이스라인 보정 4가지 예제

## 필수 라이브러리

```bash
pip install numpy scipy pandas openpyxl pyautogui pyperclip
```

## 문서

자세한 사용 방법, 예제 및 문제 해결은 [USAGE_EXAMPLES.md](docs/USAGE_EXAMPLES.md)를 참조하세요.

## 성능

- **피크 검출 정확도**: >95%
- **스케일 강건성**: 0.01배~10배 범위에서 100%
- **처리 속도**: 크로마토그램당 ~2초
- **베이스라인 방법**: 자동 선택되는 3가지 알고리즘

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

### v2.1 (2025-11-06) - 재귀적 검색 및 성능 최적화
- **전체 폴더 스캔 모드**: 한 번에 모든 .D 파일 탐색 및 내보내기 ⚡
- **재귀적 폴더 검색**: 하위 폴더 내 .D 파일 자동 발견
- **대화형 디렉토리 탐색기**: 트리 뷰로 폴더 구조 확인하며 선택 (2열 명령어 표시)
- **체계적인 출력 구조**: `result/` 폴더에 실험별로 정리 ([OUTPUT_ORGANIZATION_GUIDE.md](docs/OUTPUT_ORGANIZATION_GUIDE.md))
- **키보드 자동화 최적화**: 30% 속도 향상 (파일당 ~9초)
- **프로젝트 구조 개선**: 문서(`docs/`), 소스(`src/`), 결과(`result/`) 폴더로 체계화
- 상세 가이드: [성능 최적화](docs/TIMING_OPTIMIZATION_GUIDE.md) | [사용법](docs/USAGE_EXAMPLES.md)

### v2.0 (2025-11-06) - 하이브리드 베이스라인 및 대화형 인터페이스
- **하이브리드 베이스라인**: Valley 감지 + Local Minimum 결합
- 3가지 연결 방법 자동 최적화
- 0.01배~10배 스케일에서 100% 성공률
- 대화형 경로 입력 및 한글 메시지
- 진행 상황 실시간 표시

## 라이선스

MIT License