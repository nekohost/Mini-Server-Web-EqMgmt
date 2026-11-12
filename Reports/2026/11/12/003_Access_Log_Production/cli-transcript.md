# 운영 배포에 참여한 Codex CLI 지시와 응답

두 작업자에게 보낸 지시와 CLI가 공개한 상태 메시지·최종 답변의 전문이다. 아래 메시지의 임시 파일 경로는 각 작업 당시의 경로다. 파일 지문과 운영 사본 시험 결과는 [배포 보고서](../003_Access_Log_Production_Report.md)에 연결했다.

## 릴리스 검토

### CLI에 보낸 지시

후보 ZIP과 원장의 모든 파일 지문을 독립 대조하고, 배포 시 기존 로그가 유실되거나 구형 대기열이 재생될 수 있는 지점을 확인하십시오. 근거와 배포 전 확인 항목을 한국어로 회신하십시오. 근거는 현재 임시 폴더의 candidate.zip, manifest.json, evidence/, README.md, RESULT.md와 prior_deploy_reference.py입니다. ZIP 전부의 해시, 기존 큐 종료 경계, 현행 Git 배포에 포함할 소스만 독립 기술검토하십시오. 현재 폴더 안에서만 작업하고 SSH·외부 서비스·제품 파일 변경은 총괄이 맡습니다. 원본 데이터나 인증정보는 없습니다. 8문장 이내로 결과를 회신하십시오.

### 공개 응답 1

현재 폴더에서 ZIP 전체와 각 항목의 해시를 직접 계산해 원장과 대조하고, 이전 배포 코드와 후보 소스에서 로그와 대기열의 처리 경계를 확인하겠습니다.

### 공개 응답 2

ZIP의 210개 항목과 변경 파일 15개의 후보 지문이 모두 일치했습니다. 이전 배포 절차는 웹 PID가 사라진 뒤 DB를 백업하므로, 종료 직전 메모리에 있던 로그까지 저장됐는지는 그 백업만으로 확인할 수 없습니다.

### 공개 응답 3

- **파일 지문** — `candidate.zip` 1,140,043바이트에서 직접 계산한 SHA-256은 `e110ce03260d5bbdd5c477e8596a5f5ba89e347b6517386005ad43efd8a90c15`이고, ZIP 안팎의 `source-manifest.json`은 바이트까지 같으며 SHA-256은 `ccc74fdacaafd3af85988fe274a062b79609bd46a1fb58a4de3016a547316357`입니다. 원장 자체를 포함한 210개 항목에서 누락·추가·중복·지문 불일치는 0건이었고, 변경 15개의 `archive_sha256`은 모두 일치했으며 `staging_sha256`도 4개는 그대로, 11개는 줄바꿈을 CRLF로 변환하면 일치했습니다. [전체 파일 원장](C:/Users/nkhst/AppData/Local/Temp/eq-access-release-20261112-release-zvdhmua6/evidence/source-manifest.json) · [변경 파일 원장](C:/Users/nkhst/AppData/Local/Temp/eq-access-release-20261112-release-zvdhmua6/manifest.json)
- **Git 반영 범위** — 실행 소스는 `app.py`, `templates/access_logs.html`, `utils/access_log_cleanup.py`, `utils/http_audit_queue.py`, `utils/ai_assistant/__init__.py`, `utils/ai_assistant/audit.py` 6개이고, Git 변경은 `docs/ai-assistant.md`와 원장에 명시된 테스트 8개를 더한 **15개 경로**입니다. 기준 Git 원본은 이 폴더에 없으므로 배포 전 현행 Git에서 기준 커밋 `75829b30d3584aed02d9f6571f322a09cfa2dbab`의 기존 11개 LF 지문과 신규 4개 경로의 충돌 여부를 확인하십시오. [변경 경로와 기준 지문](C:/Users/nkhst/AppData/Local/Temp/eq-access-release-20261112-release-zvdhmua6/manifest.json:7)
- **로그 유실 지점** — 이전 `pause()`는 AI 작업·실행 가드를 확인하고 워커를 멈춘 뒤 웹 PID에 `SIGTERM`을 보내므로, PID 소멸 후의 DB 스냅샷만으로는 종료 직전 메모리에 있던 접근 로그의 커밋을 증명할 수 없습니다. 후보도 단일 웹 워커에서 처리 중 배치까지 `unfinished_tasks == 0`이 된 뒤 정리 상한 `MAX(LogId)`를 잡지만, 큐 포화 시 로그를 버리고 DB 쓰기 실패에도 `task_done()`을 호출하며 종료 훅은 최대 3초만 기다립니다. [이전 종료 절차](C:/Users/nkhst/AppData/Local/Temp/eq-access-release-20261112-release-zvdhmua6/prior_deploy_reference.py:228) · [후보 ZIP의 app.py 346–444행](C:/Users/nkhst/AppData/Local/Temp/eq-access-release-20261112-release-zvdhmua6/candidate.zip)
- **전환 전 확인** — 실제 웹 워커가 1개인지 확인하고 신규 HTTP 유입을 막아 진행 중 요청을 마친 뒤, 기존 메모리 큐와 처리 중 배치의 최종 커밋·쓰기 오류 유무를 확인하고 구 프로세스를 완전히 종료한 다음, 새 버전 기동 전후 `access_logs`와 `audit_logs`의 모든 기존 행이 그대로 보존됐는지 대조하십시오. [전환 절차](C:/Users/nkhst/AppData/Local/Temp/eq-access-release-20261112-release-zvdhmua6/README.md:32) · [기존 행 대조 방식](C:/Users/nkhst/AppData/Local/Temp/eq-access-release-20261112-release-zvdhmua6/prior_deploy_reference.py:127)
- **구형 큐 재생** — 후보의 합성 재시작 시험에서는 `instance/http-audit/pending.sqlite3`의 지문이 유지되고 재생이 0건이었지만 구버전은 미전송 행을 다시 배출할 수 있으므로, 롤백 전 서비스를 멈춘 상태에서 운영자 승인하에 `-wal`·`-shm` 등 동반 파일까지 함께 격리 보관하거나 재생과 과거 AI 본문 열람을 차단한 복구판을 사용하십시오. [재시작 시험 결과](C:/Users/nkhst/AppData/Local/Temp/eq-access-release-20261112-release-zvdhmua6/RESULT.md:49) · [롤백 절차](C:/Users/nkhst/AppData/Local/Temp/eq-access-release-20261112-release-zvdhmua6/README.md:36)

## 삭제·보존 검증

### CLI에 보낸 지시

운영 서버 안의 전용 사본에서만 실행할 검증기를 작성하십시오. 일반 삭제와 AI 포함 전체 삭제의 대상, 시작 뒤 새 행, 업무 기록 보존을 실제 후보 코드로 판정하고 합성 SQLite로 먼저 시험하십시오. 운영 접속이나 원본 수정은 총괄이 맡습니다. 현재 임시 폴더에서만 작업하고 SSH·외부 서비스 사용은 하지 마십시오. candidate.zip 안의 utils/access_log_cleanup.py의 begin/advance 및 실제 audit_logs 스키마와 동등한 audit 콜백을 사용하십시오. 파일 이름 clone_scope.py. 인터페이스는 python clone_scope.py --snapshot /절대경로/equipment.snapshot.sqlite3 --workdir /절대경로/격리전용디렉터리 --source /절대경로/릴리스소스입니다. snapshot은 mode=ro로만 열고 workdir 아래 새 임시 DB에 가급적 필요한 로그 컬럼과 영수증·업무 보존 지문을 복제하거나 완전한 SQLite 온라인 사본을 생성하십시오. 원본과 검증 DB 경로가 같은 상황을 거부하고, 본문/IP/사용자 식별값은 출력하지 마십시오. 일반 삭제 후 남은 과거 AI 행의 수·내용 일치, 포괄 삭제 후 잔여 0, 새 경계 밖의 표식 행 1개 이상 보존을 검사하고 JSON 집계만 출력하십시오. 신규 감사 행은 원래 업무 감사와 구분하십시오. 업무 행이 0개인 사본에도 적용 가능해야 합니다. 합성 DB의 자체시험을 실제로 수행하십시오. 8문장 이내로 결과 및 대량자료 실행 제약을 회신하십시오.

### 공개 응답 1

임시 폴더에서 후보 ZIP의 `begin`·`advance`와 감사 기록 방식을 확인한 뒤, 같은 경로를 호출하는 `clone_scope.py`를 작성하고 합성 SQLite로 실행하겠습니다.

### 공개 응답 2

후보의 감사 콜백은 삭제와 같은 트랜잭션에서 `audit_logs`에 영수증을 기록합니다. 검증기는 전체 SQLite 사본 한 개에서 두 삭제를 차례로 실행하고, 각 작업을 시작한 직후 일반 경로와 AI 경로 표식을 하나씩 넣어 경계를 확인하도록 작성하고 있습니다.

### 공개 응답 3

합성 DB에서 일반 삭제는 503행을 지우고 기존 AI 257행의 모든 열을 보존했습니다. 추가 시험에서 SQLite가 WAL 형식 사본을 `mode=ro`로 읽을 때도 원본 폴더에 보조 파일을 만들 수 있음을 확인해, 그 파일까지 건드리지 않도록 복사 경로를 보완하고 있습니다.

### 공개 응답 4

[clone_scope.py](C:/Users/nkhst/AppData/Local/Temp/eq-access-release-20261112-preserve-5tip9ojx/clone_scope.py)를 작성하고, 후보 ZIP의 `begin`·`advance`와 실제 `audit_logs` 스키마에 맞춘 감사 콜백으로 합성 SQLite 자체시험을 통과했습니다. 검증기는 지정한 스냅숏을 읽기 전용으로 취급하고 `--workdir` 아래 새 사본에서만 삭제를 실행하며, 본문·IP·사용자 식별값을 제외한 JSON 집계 한 줄을 출력합니다.

일반 삭제는 대상 **503행**을 지웠고, 과거 AI **257행**은 건수와 모든 열의 지문이 일치했습니다. 이어 AI 포함 삭제는 그 257행과 직전 표식 2행을 지워 **경계 안 잔여가 0행**이었고, 두 작업 모두 시작 직후 넣은 일반·AI 표식을 각각 1행씩 보존했습니다. 신규 정리 영수증 7행은 별도로 집계했고, 기존 감사 2행과 업무 2행의 내용 보존 및 업무·기존 감사가 모두 0행인 사본도 확인했습니다.

합성 접근 로그 **10만 행** 시험도 통과했으며, 대량 자료의 실행 시간은 전체 테이블 지문 계산과 최대 250행 단위 삭제 커밋의 영향을 받습니다. 작업 디렉터리에는 전체 DB 사본과 SQLite 저널 공간이 필요하며, 입력에 비어 있지 않은 WAL이나 롤백 저널이 있으면 DB와 해당 저널을 한 벌 더 복사할 공간이 필요합니다.
