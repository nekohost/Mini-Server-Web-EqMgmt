# [운영 가이드] Gunicorn systemd 서비스 운영 및 로그 모니터링 절차

- **대상 서비스**: `mini-server-eqmgmt.service`
- **대상 파일**: `/etc/systemd/system/mini-server-eqmgmt.service`
- **운영 기준 경로**: `/home/nekohost/services/Mini-Server-Web-EqMgmt`
- **작성일**: 2026-09-07

---

## 1. 사전 준비 및 기존 Gunicorn 정리

systemd 서비스를 등록하기 전에, 백그라운드 또는 SSH 세션에서 실행 중인 기존 Gunicorn 프로세스를 정상 종료하여 포트 충돌(5000번 포트 중복 바인딩)을 방지합니다.

```bash
# 이 경로가 서비스 유닛과 모든 운영 명령의 기준입니다.
SERVICE_ROOT=/home/nekohost/services/Mini-Server-Web-EqMgmt

# 1) 현재 포트 5000 점유 프로세스 확인
sudo lsof -i :5000
# 또는
sudo ss -tulpn | grep :5000

# 2) 이 서비스 경로에서 실행된 Gunicorn만 확인
pgrep -af -- "$SERVICE_ROOT/.venv/bin/gunicorn"

# 3) 출력에서 이 서비스의 마스터 PID를 확인한 뒤에만 정상 종료
# kill -TERM <확인한-마스터-PID>

# 4) 포트 5000이 완전히 반환되었는지 확인
sudo lsof -i :5000
```

---

## 2. systemd 서비스 유닛 등록 및 활성화

Staging에 준비된 유닛 파일(`mini-server-eqmgmt.service`)을 운영 시스템 경로에 복사하고 systemd 데몬에 등록합니다.

```bash
# 현재 서버의 실제 서비스 루트를 매번 먼저 확인합니다.
SERVICE_ROOT=/home/nekohost/services/Mini-Server-Web-EqMgmt
test -f "$SERVICE_ROOT/app.py"
test -x "$SERVICE_ROOT/.venv/bin/gunicorn"

# 1) 유닛 파일 복사 (소유권 root)
sudo cp "$SERVICE_ROOT/Staging/systemd/mini-server-eqmgmt.service" /etc/systemd/system/mini-server-eqmgmt.service
sudo chown root:root /etc/systemd/system/mini-server-eqmgmt.service
sudo chmod 644 /etc/systemd/system/mini-server-eqmgmt.service

# 2) 복사본에도 실제 경로와 가상환경이 반영되었는지 확인
sudo grep -F "$SERVICE_ROOT" /etc/systemd/system/mini-server-eqmgmt.service
sudo grep -F "$SERVICE_ROOT/.venv/bin/gunicorn" /etc/systemd/system/mini-server-eqmgmt.service

# 3) systemd 데몬 리로드
sudo systemctl daemon-reload

# 4) 부팅 시 자동 시작 등록
sudo systemctl enable mini-server-eqmgmt.service

# 5) 서비스 시작
sudo systemctl start mini-server-eqmgmt.service

# 6) 구동 상태 확인
sudo systemctl status mini-server-eqmgmt.service
```

---

## 3. 서비스 관리 명령어

| 작업 | 명령어 |
| :--- | :--- |
| **서비스 시작** | `sudo systemctl start mini-server-eqmgmt.service` |
| **서비스 중지** | `sudo systemctl stop mini-server-eqmgmt.service` |
| **서비스 재시작** | `sudo systemctl restart mini-server-eqmgmt.service` |
| **서비스 상태 확인** | `sudo systemctl status mini-server-eqmgmt.service` |
| **자동 실행 활성화** | `sudo systemctl enable mini-server-eqmgmt.service` |
| **자동 실행 비활성화** | `sudo systemctl disable mini-server-eqmgmt.service` |

---

## 4. 로그 모니터링 (`journalctl`)

SSH 세션 종료와 무관하게 systemd journal에 Gunicorn 및 Flask 로그가 영구 보관되며, 실시간 스트리밍이 가능합니다.

```bash
# 1) 실시간 로그 스트리밍 (app.py 직접 실행 콘솔과 동일 효과)
sudo journalctl -u mini-server-eqmgmt.service -f

# 2) 최근 로그 100줄 즉시 확인 (페이저 없이 출력)
sudo journalctl -u mini-server-eqmgmt.service -n 100 --no-pager

# 3) 오늘 발생한 에러 레벨 로그만 확인
sudo journalctl -u mini-server-eqmgmt.service -p err --since today
```

---

## 5. 장애 대응 및 롤백 절차

서비스 구동 중 예기치 않은 오류가 발생하여 기존 수동 Gunicorn 실행 방식으로 복귀해야 하는 경우:

```bash
# 1) systemd 서비스 즉시 중지 및 비활성화
sudo systemctl disable --now mini-server-eqmgmt.service

# 2) 서비스 파일 제거 및 데몬 리로드
sudo rm /etc/systemd/system/mini-server-eqmgmt.service
sudo systemctl daemon-reload

# 3) 이전 수동 Gunicorn 실행 방식으로 복귀
SERVICE_ROOT=/home/nekohost/services/Mini-Server-Web-EqMgmt
cd "$SERVICE_ROOT"
"$SERVICE_ROOT/.venv/bin/gunicorn" --workers 1 --bind 127.0.0.1:5000 --access-logfile - --error-logfile - --capture-output app:app
```
