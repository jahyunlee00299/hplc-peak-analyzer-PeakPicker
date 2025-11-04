# HPLC Peak Picker - 빠른 참조 가이드

## 🚀 빠른 시작

### 가장 간단한 방법
```bash
python quick_start.py
```
위즈드를 따라가면서 옵션을 선택하세요.

### 즉시 실행 (데이터 경로만 수정)
```bash
python hplc_analyzer.py "C:/Chem32/1/DATA"
```

---

## 📁 주요 파일

| 파일 | 설명 | 용도 |
|------|------|------|
| `quick_start.py` | 대화형 시작 스크립트 | 초보자 추천 |
| `hplc_analyzer.py` | 메인 분석 프로그램 | 커맨드라인 실행 |
| `run_analysis.bat` | Windows 배치 파일 | 더블클릭 실행 |
| `chemstation_parser.py` | Chemstation 파일 파서 | 라이브러리 |
| `peak_detector.py` | Peak 검출 엔진 | 라이브러리 |
| `result_exporter.py` | 결과 내보내기 | 라이브러리 |
| `config.json` | 설정 파일 | 기본값 설정 |
| `README.md` | 전체 문서 | 상세 설명 |
| `USAGE_EXAMPLES.md` | 사용 예제 | 예제 모음 |

---

## 💡 주요 명령어

### 기본 분석
```bash
python hplc_analyzer.py "데이터경로"
```

### Peak가 너무 많을 때
```bash
python hplc_analyzer.py "데이터경로" --prominence 500 --min-height 1000
```

### Peak가 안 잡힐 때
```bash
python hplc_analyzer.py "데이터경로" --prominence 50 --min-height 100
```

### 특정 RT 검색
```bash
python hplc_analyzer.py "데이터경로" --target-rts 2.5 5.8 10.2
```

### 빠른 분석 (그림 없이)
```bash
python hplc_analyzer.py "데이터경로" --no-plots
```

### CSV로 저장
```bash
python hplc_analyzer.py "데이터경로" --format csv
```

---

## 📊 출력 파일

### 개별 샘플 결과
- `{샘플명}_peaks.xlsx` - Peak 데이터 (RT, area, height 등)
- `{샘플명}_chromatogram.png` - 크로마토그램 이미지

### 전체 요약
- `batch_summary_{날짜시간}.xlsx` - 모든 샘플 요약

### Target RT 분석
- `target_peaks_analysis_{날짜시간}.xlsx` - 특정 RT의 peak 비교

---

## ⚙️ 파라미터 설명

| 파라미터 | 설명 | 기본값 | 조정 방법 |
|----------|------|--------|----------|
| `--prominence` | Peak의 두드러진 정도 | 자동 | 높이면 큰 peak만, 낮추면 작은 peak도 |
| `--min-height` | 최소 peak 높이 | 자동 | 높이면 높은 peak만 |
| `--min-width` | 최소 peak 너비 (분) | 0.01 | 높이면 넓은 peak만 |
| `--target-rts` | 검색할 RT 목록 | 없음 | 공백으로 구분 |
| `--rt-tolerance` | RT 매칭 오차 (분) | 0.1 | 넓히면 더 많이 매칭 |

---

## 🔧 문제 해결 체크리스트

- [ ] Python 3.7 이상 설치되어 있는가?
- [ ] 필요한 라이브러리가 설치되어 있는가? (`pip install -r requirements.txt`)
- [ ] 데이터 경로가 올바른가?
- [ ] .ch 파일이 실제로 존재하는가?
- [ ] 파일 접근 권한이 있는가?

---

## 📞 지원

- 📖 상세 문서: `README.md`
- 💻 사용 예제: `USAGE_EXAMPLES.md`
- 🐛 문제 발생 시: GitHub Issues

---

## 🎯 일반적인 워크플로우

1. **데이터 준비**
   - Chemstation .D 폴더들이 있는 디렉토리 확인

2. **분석 실행**
   ```bash
   python quick_start.py
   ```
   또는
   ```bash
   python hplc_analyzer.py "경로"
   ```

3. **결과 확인**
   - `analysis_results` 폴더에서 Excel 파일 확인
   - 크로마토그램 이미지 확인 (생성한 경우)

4. **필요시 재분석**
   - 파라미터 조정 후 다시 실행

---

## 📈 결과 해석

### Excel의 Peak Data 시트
- **RT**: Peak의 retention time
- **Area**: Peak 면적 (정량분석에 사용)
- **Height**: Peak 높이
- **% Area**: 전체 peak 중 비율

### 좋은 Peak의 특징
- Area > 0 (negative area는 역 peak)
- Width가 너무 좁지 않음 (> 0.01 min)
- % Area가 의미있는 값 (노이즈는 보통 < 1%)

---

**Tip:** 처음 사용할 때는 소수의 샘플로 테스트한 후, 파라미터를 조정하고 전체 배치를 실행하세요!
