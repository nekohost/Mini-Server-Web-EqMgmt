# 제안-013 DB 백업·복원 운영 가이드

## 필수 배포 조건

1. Gunicorn은 현재 운영 구성처럼 `--workers 1`을 유지한다. 복원 Lock과 DB 연결 계수는 단일 프로세스 메모리 상태다.
2. 서비스 계정만 접근할 수 있는 DB 작업 디렉터리를 준비한다.

```bash
install -d -m 700 -o nekohost -g nekohost /home/nekohost/.local/share/mini-server-eqmgmt/database-operations
```

3. systemd 환경 변수에 다음 값을 추가한다.

```ini
Environment="DATABASE_PATH=/home/nekohost/services/Mini-Server-Web-EqMgmt/equipment.db"
Environment="DATABASE_OPERATION_ROOT=/home/nekohost/.local/share/mini-server-eqmgmt/database-operations"
```

실제 서비스 경로가 다르면 `DATABASE_PATH`만 실제 절대 경로로 맞춘다. DB 작업 디렉터리는 저장소와 Nginx 정적 경로 밖에 둔다.

## 보존·용량 정책

- 브라우저로 전송한 수동 다운로드 백업은 응답이 끝난 뒤 서버에서 즉시 삭제한다. 중단된 다운로드의 잔여 파일은 다음 작업 때 1시간을 넘기면 정리한다.
- 업로드 후보 DB는 생성 시각 기준 30분 후 삭제한다. 이 정리는 프로세스 재시작 뒤에도 작업 시작 시 다시 수행한다.
- 복원 직전 자동 백업과 외부 작업·감사 저널은 7일 보관한다. 수동 복구가 필요하면 보존 기간 안에 별도 안전 저장소로 옮긴다.
- 업로드·백업·복원 시작 전에는 작업 디렉터리와 운영 DB 파일시스템 모두에 후보·자동 백업·64MiB 여유 공간이 있는지 검사한다. 공간이 부족하면 DB를 변경하지 않고 중단한다.

## 보안 동작

- 백업 생성은 CSRF 토큰이 필요한 `POST /api/admin/database/backup`으로만 요청한다. 화면이 응답 파일을 내려받으므로 외부 사이트가 단순 링크로 백업 파일을 만들 수 없다.
- 복원 상태 토큰은 URL 쿼리가 아닌 `X-Restore-Monitor-Token` 요청 헤더로 전달한다. Gunicorn access log와 브라우저 주소·기록에 토큰이 남지 않게 하기 위함이다.
- 후보와 운영 DB의 테이블·컬럼·외래키·인덱스·트리거·뷰 및 적용 마이그레이션을 비교한다. 비교 화면에는 SHA-256, 수정 시각, 스키마 지문, 적용 마이그레이션 수와 필수 테이블 건수를 표시한다.

## Staging 서버 검증 명령

운영 DB가 아닌 별도 모의 DB를 사용하는 테스트다.

```bash
cd /home/nekohost/services/Mini-Server-Web-EqMgmt
.venv/bin/python -m unittest Staging/tests/test_proposal013_backup_restore.py
```

이 테스트는 정상 복원, 사후 검증 실패 원복, 저널 기록 실패 중 원복 지속, 누락 테이블·인덱스 거부, 요청 종료 연결 정리, 헤더 토큰 전용 상태 조회, 재시작 뒤 만료 후보 파일 정리를 포함한다.

## 복원 중 프로세스가 종료된 경우

자동으로 점검을 해제하지 않는다. `DATABASE_OPERATION_ROOT/jobs/<작업ID>.json`에서 마지막 단계를 확인하고 `backups/before-restore-<작업ID>.db`를 보존한다. 현재 DB와 자동 백업을 각각 복사해 별도 보관한 뒤 수동 복구 여부를 결정한다.
