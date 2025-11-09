# Export 세션 제어 가이드

## 개요

`auto_export_all.py`는 4,500개 이상의 HPLC 데이터 파일을 자동으로 export하는 스크립트입니다.
긴 시간이 걸리는 작업이므로 안전하게 중단할 수 있는 기능이 제공됩니다.

## 중단 방법

### 1. Ctrl+C 사용 (권장)

터미널에서 **Ctrl+C**를 누르면 현재 처리 중인 파일을 완료한 후 안전하게 중단됩니다.

```
[INTERRUPT] Ctrl+C 감지! 현재 파일 완료 후 중단합니다...
```

### 2. STOP 파일 생성

다른 터미널이나 스크립트에서 중단하려면:

```bash
# 방법 A: Python 스크립트 실행
python stop_export.py

# 방법 B: 수동으로 파일 생성
echo "STOP" > export_STOP.txt
```

스크립트가 STOP 파일을 감지하면 현재 파일 완료 후 중단됩니다:

```
[STOP FILE] 'export_STOP.txt' 감지! 현재 파일 완료 후 중단합니다...
```

## 중단 후 재시작

Export는 **이미 완료된 파일을 자동으로 건너뛰므로**, 중단 후 다시 실행하면 중단된 지점부터 계속됩니다.

```bash
# 중단된 export 재시작
python auto_export_all.py
```

스크립트가 자동으로:
- ✅ 이미 export된 파일 건너뜀
- ✅ 중단된 지점부터 계속 진행
- ✅ 진행 상황과 ETA 표시

## 예제 시나리오

### 시나리오 1: 점심시간에 중단

```bash
# Export 시작 (오전)
python auto_export_all.py

# Ctrl+C로 중단 (점심시간)
# [PROGRESS] 150/4549 파일 처리 중 중단됨

# 재시작 (오후)
python auto_export_all.py
# [건너뜀: 이미 존재] x 150
# [151/4549] 새 파일부터 계속...
```

### 시나리오 2: 백그라운드에서 중단

```bash
# Terminal 1: Export 실행 중
python auto_export_all.py &

# Terminal 2: 중단 명령
python stop_export.py
```

## 기술 세부사항

### 안전한 중단 보장

- 현재 처리 중인 파일은 **반드시 완료**됨
- 부분적으로 손상된 CSV 파일이 생성되지 않음
- 중단 시점의 통계 정보 제공

### 중단 확인 주기

스크립트는 **각 파일 처리 전**에 중단 요청을 확인합니다:

```python
for i, d_folder in enumerate(d_folders):
    if check_stop_requested():  # 매 파일마다 확인
        break
    # 파일 처리...
```

### STOP 파일 자동 정리

스크립트 종료 시 `export_STOP.txt` 파일이 자동으로 삭제됩니다.

## 주의사항

⚠️ **즉시 중단되지 않습니다**
- 현재 파일 처리가 완료되어야 중단됩니다
- 파일당 처리 시간: 평균 2초

⚠️ **강제 종료 금지**
- `Ctrl+Z` (suspend) 사용하지 마세요
- `kill -9` (강제 종료) 사용하지 마세요
- 부분 파일이나 손상된 데이터가 생성될 수 있습니다

✅ **안전한 방법**
- `Ctrl+C` 사용
- `python stop_export.py` 실행
- 중단 메시지 확인 후 대기

## 문제 해결

### STOP 파일이 삭제되지 않는 경우

```bash
# 수동으로 삭제
rm export_STOP.txt
# 또는
del export_STOP.txt
```

### 중단이 작동하지 않는 경우

1. 파일 처리 완료 대기 (최대 2초)
2. 터미널 확인 (메시지 출력 확인)
3. 마지막 수단: 터미널 창 닫기 (권장하지 않음)

## 관련 파일

- `auto_export_all.py` - 메인 export 스크립트
- `stop_export.py` - 중단 유틸리티
- `export_STOP.txt` - 중단 신호 파일 (임시)
