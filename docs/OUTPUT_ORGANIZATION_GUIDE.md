# 출력 디렉토리 구조 가이드

## 개요
v2.1부터 출력 파일이 `result/` 폴더에 체계적으로 정리됩니다.

## 출력 디렉토리 옵션

### 옵션 1: 제안된 경로 사용 (기본값) ✅
선택한 데이터 폴더 이름으로 하위 폴더를 자동 생성합니다.

**예시:**
```
데이터 폴더: C:\Chem32\1\DATA\Ribavirin\

출력 구조:
PeakPicker/
  └── result/
      └── Ribavirin/           ← 자동 생성
          ├── Sample1.csv
          ├── Sample2.csv
          └── Sample3.csv
```

**장점:**
- 여러 실험 데이터를 체계적으로 분리
- 폴더 이름으로 실험 구분 가능
- 재실행 시 자동으로 같은 폴더에 저장

---

### 옵션 2: result/ 폴더에 직접 저장
모든 CSV 파일을 `result/` 폴더에 직접 저장합니다.

**예시:**
```
PeakPicker/
  └── result/
      ├── Sample1.csv
      ├── Sample2.csv
      ├── Sample3.csv
      ├── Exp1_Sample1.csv
      └── Exp2_Sample1.csv
```

**사용 시나리오:**
- 소량의 데이터만 처리할 때
- 하위 폴더가 필요 없을 때

---

### 옵션 3: 커스텀 경로
원하는 경로를 직접 지정합니다.

**예시:**
```
입력: D:\HPLC_Results\2025-11-Experiment\

출력 구조:
D:/HPLC_Results/
  └── 2025-11-Experiment/
      ├── Sample1.csv
      ├── Sample2.csv
      └── Sample3.csv
```

**사용 시나리오:**
- 특정 프로젝트 폴더에 저장하고 싶을 때
- 외부 드라이브에 저장하고 싶을 때

---

## 실행 예시

### 예시 1: 단일 실험 폴더 처리

```bash
python auto_export_keyboard_final.py

# 데이터 폴더 선택
선택: C:\Chem32\1\DATA\Ribavirin\

# 출력 디렉토리 설정
제안된 경로: result/Ribavirin/
선택 (1, 2, 또는 3, Enter=1): [Enter]

✅ 출력 디렉토리 생성 완료
→ result/Ribavirin/
```

**결과:**
```
PeakPicker/
  └── result/
      └── Ribavirin/
          ├── Sample1.csv
          ├── Sample2.csv
          └── Sample3.csv
```

---

### 예시 2: 여러 실험 폴더 순차 처리

**첫 번째 실행:**
```bash
python auto_export_keyboard_final.py

# 데이터: C:\Chem32\1\DATA\Experiment_A\
# 출력: result/Experiment_A/
```

**두 번째 실행:**
```bash
python auto_export_keyboard_final.py

# 데이터: C:\Chem32\1\DATA\Experiment_B\
# 출력: result/Experiment_B/
```

**결과:**
```
PeakPicker/
  └── result/
      ├── Experiment_A/
      │   ├── Sample1.csv
      │   └── Sample2.csv
      └── Experiment_B/
          ├── Sample1.csv
          └── Sample2.csv
```

---

### 예시 3: 전체 스캔 모드 (옵션 3)

```bash
python auto_export_keyboard_final.py

# 옵션 3 선택: 전체 폴더 스캔
스캔 경로: C:\Chem32\1\DATA\

총 125개 .D 폴더 발견!

# 출력 디렉토리 설정
제안된 경로: result/DATA/
선택: 1

→ result/DATA/ 에 모든 CSV 저장
```

**결과:**
```
PeakPicker/
  └── result/
      └── DATA/
          ├── Experiment_A_Sample1.csv
          ├── Experiment_A_Sample2.csv
          ├── Experiment_B_Sample1.csv
          └── ... (125개 파일)
```

---

## 폴더 이름 규칙

### 자동 생성되는 하위 폴더 이름

선택한 데이터 폴더의 **마지막 폴더명**이 사용됩니다:

| 데이터 폴더 경로 | 생성되는 하위 폴더 |
|------------------|-------------------|
| `C:\Chem32\1\DATA\Ribavirin\` | `result/Ribavirin/` |
| `C:\Chem32\1\DATA\2. D-Xyl cascade HPLC\` | `result/2. D-Xyl cascade HPLC/` |
| `C:\Chem32\1\DATA\` | `result/DATA/` |
| `D:\Experiments\2025-11-06\` | `result/2025-11-06/` |

---

## 파일 덮어쓰기

같은 경로에 이미 파일이 있는 경우:
- ✅ **자동으로 건너뜀** (이미 존재하는 파일)
- 진행 상황에 `[건너뜀]` 표시

**예시:**
```
[1/10] 건너뜀: Sample1 (이미 존재)
[2/10] Sample2
  처리 중: Sample2.D
  [성공] 45,231 bytes
```

---

## 권장 워크플로우

### 실험별로 분리 저장 (권장) ⭐
```bash
# 각 실험마다 별도로 실행
1. Ribavirin 실험 → result/Ribavirin/
2. D-Xylose 실험 → result/D-Xylose/
3. Control 실험 → result/Control/
```

### 날짜별로 분리 저장
```bash
# 폴더 이름에 날짜 포함
1. DATA/2025-11-06_Exp1/ → result/2025-11-06_Exp1/
2. DATA/2025-11-07_Exp2/ → result/2025-11-07_Exp2/
```

### 프로젝트별로 커스텀 경로
```bash
# 옵션 3 사용
1. Project_A → D:/Projects/ProjectA/HPLC_Data/
2. Project_B → D:/Projects/ProjectB/HPLC_Data/
```

---

## 분석 단계 연동

Export 후 자동으로 분석 실행:

```bash
# 1. Export
python auto_export_keyboard_final.py
# → result/Ribavirin/ 에 CSV 저장

# 2. 분석
python hplc_analyzer_enhanced.py "result/Ribavirin"
# → result/Ribavirin/analysis_results/ 에 Excel 저장
```

**최종 구조:**
```
PeakPicker/
  └── result/
      └── Ribavirin/
          ├── Sample1.csv
          ├── Sample2.csv
          └── analysis_results/
              ├── Sample1_peaks.xlsx
              └── Sample2_peaks.xlsx
```

---

## 요약

| 옵션 | 경로 | 사용 시나리오 |
|------|------|--------------|
| **1** | `result/{폴더명}/` | ⭐ 기본값, 실험별 분리 |
| **2** | `result/` | 단순한 구조, 소량 데이터 |
| **3** | 사용자 지정 | 특정 프로젝트 경로 |

**기본 권장사항:** 옵션 1 (Enter) 사용
