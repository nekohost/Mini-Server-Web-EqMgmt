# 장비관리 AI 도우미 운영 안내

AI 대화는 `/assistant`를 제공한다. AI 연결 관리는 메인 메뉴 대신 관리자 센터에서 `/admin/ai/providers`로 진입하며 연결·자동 모델 목록·선택형 수동 등록·공개 모델·지원 추론 단계를 관리한다. 기존 `/ai`·`/ai/console`은 폐기 안내와 새 AI 링크만 제공하고 옛 API/browser proxy는 upstream에 연결하지 않는다. 공유 Strata 서비스와 새 AI adapter·키는 보존한다. 2026-11-05 기존 Staging 전체와 공간 절약 배치를 현재 운영 백업서버에 적용했다. [이번 실제 배포·검증](../Reports/2026/11/05/005_AI_Assistant_Production_Release_Report.md)과 [최초 운영 검증](../Reports/2026/11/04/012_AI_Production_Release_Report.md)을 구분한다.

대화·추론·정규화 업무 초안·요청별 연결과 모델 출처를 사용자별 별도 AI DB에 저장한다. 같은 대화에서 모델을 바꾸면 다음 요청부터 적용하고 접수된 요청의 연결·설정·인증 revision은 유지한다. off/low/medium/high/xhigh/max가 모두 보이며 지원되지 않거나 관리자가 허용하지 않은 단계는 비활성이다. 현재 Strata Qwen3.8 Flash Next의 사전 설정은 off/low/medium/xhigh, 기본 medium이다.

답변의 지원되는 Markdown 표는 실제 표로 표시하며 모바일에서는 표 영역 안에서 가로 스크롤한다. 모델 HTML은 삽입하지 않는다. 긴 표는 표시 상한과 전체 원문을 안내하며 기존 메시지를 다시 쓸 필요가 없다. 모델 선택 이름은 연결/모델명으로 짧게 표시하고 업무 가능 여부·사용 불가 사유는 별도 상태로 안내한다. 장비 조회의 선택 status/due 빈 문자열은 필터 없음으로 정규화하며 쓰기 상태값의 검증은 유지한다. 기능시험 기록은 관리자 진단으로 분리하고 혼합된 과거 대화의 실제 사용자 기록은 보존한다.

관리자 연결 화면의 저장·폐기·모델 설정·목록 조회는 공통 로딩과 결과 modal을 사용한다. 저장 ACK 뒤 목록 조회가 실패하면 저장 완료와 갱신 실패를 구분한다. 응답 유실 시 결과 확인을 안내하고 POST를 자동 반복하지 않는다. 기능시험은 접수·대기·진행·종료를 분리하고 자체 client_key로 ACK 유실을 조회한다. 정상 모델 요청에 총시간 기준 취소를 추가하지 않는다.

AI가 할 수 있는 업무는 일반 사용자 범위로 제한한다. 본인 장비 조회·등록·수정·상태 변경, 공개 장비·카탈로그 조회, 카테고리·제조사·라인업·옵션 신청과 개인 설정 등을 고정 도구로 제공한다. 관리자 로그인도 AI 업무에서는 일반 사용자 범위를 유지한다. 삭제·폐기·소유자 이전·관리자 승인·사용자 관리·임의 SQL/코드/주소 실행은 제공하지 않는다. 업무 변경은 모델의 제안 뒤 사용자가 화면의 확인 카드를 확정해야 실행된다.

서명 cookie와 현재 계정 SessionToken/CreatedAt·권한·유지보수 세대를 서버에서 재확인한다. Origin/CSRF와 불변 제안의 HMAC·hash·현재 revision을 검사하며 업무 변경·기존 감사·실행 영수증을 같은 DB transaction으로 기록한다. 추론은 표시 데이터이며 다음 모델 요청의 명령으로 재주입하지 않는다.

장비관리 내부 요청만 물리 자원 그룹별 한 개씩 처리한다. 같은 PC/자원에 여러 모델이 있으면 같은 그룹에 둔다. 외부 서비스의 Strata 요청이나 전역 큐·모델 load/unload/취소는 제어하지 않는다. 완료되지 않은 스트림이나 연결 유실은 사유를 남기고 후속 도구를 중단한다. upstream 종료가 불명확하면 자체 그룹 잠금을 유지한다. 해당 자체 요청의 실제 종료를 확인한 뒤에만 worker의 `--acknowledge-finished OWN_JOB_ID`를 사용한다.

AI DB v4는 대화 내용과 별도의 최소 실행 점유 원장을 사용한다. 휴지통 이동은 queued/미확정 업무를 취소하고 자기 실행 요청의 후속 작업·출력 저장을 막는다. 대화를 영구삭제해도 미종료 그룹 점유는 보존하며 늦은 chunk/finish는 내용을 되살리지 않는다. 복구가 취소 요청이나 확인 카드를 자동 실행하는 동작은 아니다. 이미 확정된 장비 업무/영수증은 유지한다.

대화 삭제는 먼저 휴지통으로 이동한다. `is_deleted/deleted_at/purge_after/lifecycle_revision`을 서버에서 관리하고 이동 시각부터 30×24시간 뒤 만료된다. 복구하면 삭제 예약이 해제되고, 다시 휴지통에 넣을 때만 새 30일을 계산한다. 같은 조작의 재전송·목록 확인은 기간을 연장하지 않는다. 휴지통은 읽기 전용이며 복구 또는 별도 확인 후 즉시 영구삭제할 수 있다. 만료 정각부터 복구·열람을 차단하고 5분 정리 timer/기동 따라잡기가 종속 대화 데이터를 제거한다. 소량 정상 배치의 물리 정리는 한 주기 정도 늦을 수 있으며 대량 backlog·중단·오류는 제한된 배치로 순차 처리한다.

정상+휴지통이 기존 200개 대화/문자 한도를 함께 사용한다. 영구삭제 때만 메시지·초안·인계 자료의 사용량을 정확히 차감한다. 업무 DB·장비 파일·감사 로그·AI_EXECUTE 영수증·보호 CSV 감사 원본·프로바이더 설정은 대화 삭제 대상이 아니다. 앱의 대화 복구는 불가능해져도 기존 별도 감사/백업 정책에 따른 사본은 남을 수 있다.

대화 보관 기준선은 계정별 32,000,000자이며 기본 추가 완료 예산도 32,000,000자다. 한 턴에 458,912자를 예약한다. 예산 부족 시 새 접수를 제한하고 기존 생성 결과를 지우지 않는다. 추론/답변/업무/오류는 감사 로그에 남기고, 재사용 가능한 인증 원문만 HMAC 지문으로 보호한다. CSV 감사 원문은 별도 보호 파일로 보관하며 기본 물리 예산은 2GiB다. 문자 예산과 DB·WAL·감사·백업 디스크 예산은 다르다.

운영 설정은 기존 Flask SECRET_KEY와 분리된 worker token·Fernet key·DB epoch를 사용한다. 서버의 `.env`, `~/.config/eqmgmt/assistant-worker.env`는 0600, AI/백업 디렉터리는 0700으로 보호한다. 비밀·업무 DB·실제 감사 원문은 Git에 넣지 않는다. 기본 연결은 기존 `http://192.168.0.14:8080`이며 배포 허용 목록도 이 주소로 제한한다. 새 LAN 서버를 추가하려면 운영자가 app·worker의 동일 허용 목록을 먼저 갱신해야 한다. 이 제한은 관리자 브라우저 입력으로 우회할 수 없다.

웹앱은 기존 사용자 Python 구동 방식을 유지한다. AI worker는 `systemd/equipment-ai-worker.service`를 사용자 단위로 설치하며 `systemctl --user status equipment-ai-worker`로 확인한다. 네트워크 읽기 제한은 1800초이고 총 생성 시간 제한은 아니다. worker가 중단되면 신규 요청 처리를 재개하기 전에 종료 불명확 작업의 상태를 확인한다.

초기 설치용 `tools/deploy_user_ai.py`는 정확한 commit과 고정 호스트/경로를 검사한다. `check-copy`는 업무 DB의 새 private 사본에서 전체 앱/AI v4 초기화와 업무 행·기존 메뉴 metadata·계정 식별자·익명 HTTP 경계를 검증한다. `prepare-key`는 기존 USER_AI 설정이 있으면 그 바이트를 보존하며, 신규 설정에는 명시적인 owner-only key-file을 요구한다. 옛 root Nginx key include를 읽는 의존성은 제거한다. 보호 키 값은 인수나 출력에 넣지 않는다. 이미 설치된 환경의 이번 업그레이드는 `tools/deploy_ai_ux_release.py`의 pause/check-copy/activate를 사용했다. 정확한 idle 웹 PID/cwd/argv를 확인해 자체 접수를 닫고 worker/web을 정상 종료한 뒤, quiesced 백업과 실제 사본 검증·기존 행/비밀 보존을 확인하고 같은 코드로 재개한다. 옛 gateway의 root Nginx 단계는 `tools/retire_equipment_strata_nginx.py`로 전용 include만 백업·검사·적용한다.

v4 적용은 신규 접수 차단·자기 요청 실제 종료 확인·worker/앱 정리·일관 백업 뒤 호환 코드/전진 migration/worker를 함께 적용한다. retention timer는 모든 점유·권한·삭제 검증 후에만 설치/활성화한다. 정리 CLI는 기존 v4 DB·명시적인 USER_AI_DATABASE/USER_AI_DATABASE_EPOCH를 요구하고 v3를 자동 이전하지 않는다. 기존 worker.env에 DB 경로가 없으면 정확한 private 경로를 먼저 지정한다.

AI DB 복구/교체 전에는 최신 삭제 원장을 `tools/ai_retention_cleanup.py --export-deletions`로 private 경로에 보존한다. 복원 DB를 v4로 검증한 후 같은 CLI의 `--reconcile-deletions`로 삭제 결정을 재적용하고 대화/원장/점유 정합을 확인한 다음 서비스한다. 이 내용 없는 원장은 이미 영구삭제된 대화와 아직 GC되지 않은 만료 대화의 재노출을 방지한다. 접수 차단·자체 요청 종료·worker/앱 정리와 외부 epoch 갱신을 생략하지 않는다. 영구삭제를 코드 rollback으로 되살릴 수 있다고 안내하지 않으며 v4를 모르는 v3 코드로 단독 복귀하지 않는다. 업무/감사 영수증을 지우는 되감기도 하지 않는다. 암호화 키 교체는 이전 키를 보호 키 배열에 보존해 과거 revision/백업을 복호화할 수 있게 한다.

합성 회귀는 Windows에서 앱을 실행하지 않고 `tests/run_assistant_fixture.py --browser`로 승인된 Linux 서버에서 수행한다. 011 원본 후보와 화면 재현 harness는 012 증거의 `reviewed-staging-sources.zip`과 `source-archive-manifest.json`에 원래 경로·SHA-256을 보존한다. 이는 운영 실모델 검증 자료와 구분한다. 고급 연결 설정과 D07 주석 일괄 개선은 기존 보류 상태를 유지한다.

