# [개선계획 보고서] 제안-046 Gunicorn 로그 운영 및 점검 관리자 화면

작성일: 2026-09-07
상태: 검토 완료, 구현 대기
대상: Gunicorn 실행 방식, `templates/maintenance_admin.html`, `app.py` 점검 상태 변경 API

## 1. 현행 확인

운영 서버는 `app.py`를 직접 실행하지 않고 Gunicorn이 `app:app`을 불러 포트 `127.0.0.1:5000`에서 실행한다. `--access-logfile - --error-logfile - --capture-output` 옵션은 Gunicorn·Flask 로그를 표준 출력과 표준 오류로 보낸다. 전면 실행 때는 SSH 콘솔에 즉시 표시되지만, 백그라운드 실행에서는 로그를 안정적으로 추적할 표준 수단이 없다.

점검 관리자 화면은 현재 `NORMAL`에서도 활성화·해제 양식을 함께 표시한다. 확인 문구는 영문 `MAINTENANCE`와 `NORMAL`이며, 예상 종료 시각은 단일 `datetime-local` 값으로 API에 전달된다.

## 2. 로그 운영 개선

### 목표

Gunicorn을 전면 SSH 세션에 묶지 않고 systemd 서비스로 실행한다. 관리자는 별도 콘솔에서 `journalctl -u mini-server-eqmgmt.service -f`를 실행해 기존 `app.py` 직접 실행 때와 같은 실시간 로그 흐름을 본다.

### 구현 범위

1. 서버 전용 systemd 유닛 `mini-server-eqmgmt.service`를 만든다. `User=nekohost`, 프로젝트 작업 경로, 가상환경 Gunicorn 절대 경로와 현재 검증된 `--workers 1 --bind 127.0.0.1:5000 --access-logfile - --error-logfile - --capture-output app:app` 실행 인자를 명시한다.
2. `StandardOutput=journal`, `StandardError=journal`, `Environment=PYTHONUNBUFFERED=1`, `Restart=on-failure`, `RestartSec=3`, `KillSignal=SIGTERM`, 제한 시간 종료를 설정한다.
3. 운영 절차를 문서화한다. 시작·중지·상태 확인은 `sudo systemctl start|stop|status mini-server-eqmgmt.service`, 실시간 로그는 `sudo journalctl -u mini-server-eqmgmt.service -f`, 최근 로그는 `sudo journalctl -u mini-server-eqmgmt.service -n 100 --no-pager`를 사용한다.
4. systemd가 관리하지 않는 기존 Gunicorn이 남아 있으면 서비스 등록 전에 마스터 PID를 정상 종료하고 포트 5000이 비어 있는지 확인한다. 동시에 두 프로세스를 실행하지 않는다.

### 수용 기준

- SSH를 닫아도 Gunicorn이 유지된다.
- `journalctl -f`에서 접근 로그, Flask 출력, 오류 로그가 실시간으로 보인다.
- 비정상 종료 시에만 자동 재시작하고, `systemctl stop`은 SIGTERM으로 정상 종료한다.
- 포트 5000에 하나의 Gunicorn 마스터와 하나의 워커만 존재한다.

## 3. 점검 관리자 화면 개선

### 상태별 화면

- `NORMAL`: 현재 상태와 점검 활성화 양식만 표시한다.
- `DRAINING`, `RECOVERY`: 현재 상태와 점검 해제 양식만 표시한다.
- `RESTORING`: 현재 상태·안내만 표시한다. DB 복원 보호 구간에서는 해제를 포함한 상태 변경을 허용하지 않는다.

이 구분은 템플릿 조건부 렌더링으로 처리하며, 서버 API의 `RESTORING` 거부 규칙은 유지한다. 따라서 화면 숨김만으로 권한을 판단하지 않는다.

### 확인 문구

- 활성화 확인 문구를 `점검시작`으로 변경한다.
- 해제 확인 문구를 `점검종료`로 변경한다.
- `app.py`와 템플릿의 문구를 상수 또는 같은 명세로 단일화하고, 서버에서는 앞뒤 공백을 제거한 뒤 정확히 비교한다.
- 현재 관리자 비밀번호 재인증, CSRF, 서버 DB 역할 확인, 감사 로그는 변경하지 않는다.

### 예상 종료 일시

1. 날짜는 `<input type="date">`로 분리한다. 브라우저의 달력 선택기를 제공하고 수동 입력도 허용한다.
2. 시간은 `HH:MM` 형식의 텍스트 입력과 `<datalist>` 목록을 조합한다. 관리자는 직접 `14:30`을 입력할 수 있고, 목록에서 30분 단위 후보를 선택할 수 있다.
3. 클라이언트는 두 값이 모두 비어 있으면 기존처럼 예상 종료 시각 없음으로 보낸다. 하나만 입력하면 전송을 막고 오류를 표시한다. 둘 다 있으면 `YYYY-MM-DDTHH:MM`으로 결합한다.
4. 서버는 길이만 검사하던 현재 방식 대신 정규식과 `datetime.strptime`으로 실제 일시를 검증한다. 유효하지 않은 날짜·시간은 400으로 거부한다.
5. 로그인 안내와 점검 안내 화면에는 결합된 시각의 `T`를 공백으로 바꿔 읽기 쉽게 표시한다.

## 4. 변경 대상

| 대상 | 변경 내용 |
| --- | --- |
| 서버 전용 `/etc/systemd/system/mini-server-eqmgmt.service` | Gunicorn 실행, journald 로그, 재시작·종료 정책 |
| 운영 문서 | systemd 시작·중지·상태·로그 확인·복구 절차 |
| `Staging/templates/maintenance_admin.html` | 상태별 양식 렌더링, 한글 확인 문구, 날짜·시간 입력과 클라이언트 검증 |
| `Staging/app.py` | 한글 확인 문구 검증, 날짜·시간 엄격 검증, 표시용 일시 정규화 |
| `Staging/templates/login.html`, `Staging/templates/maintenance.html` | 예상 종료 시각의 표시 형식 정리 |

## 5. 검증 및 복구

Staging에서 JavaScript 구문, 템플릿 조건, API 입력 검증을 확인한다. 서버에서는 systemd 기동·중지·자동 재시작, `journalctl -f` 로그, `NORMAL → DRAINING → NORMAL`, 잘못된 한글 확인 문구, 날짜만 입력, 잘못된 시간 입력을 순서대로 검증한다.

문제 발생 시 systemd 유닛을 `sudo systemctl disable --now mini-server-eqmgmt.service`로 중지하고, 직전 Gunicorn 실행 절차로 복귀한다. 애플리케이션 코드는 이전 Git 커밋으로 되돌릴 수 있으며, 이 개선은 DB 스키마나 점검 상태 파일 형식을 바꾸지 않는다.
