# 장비관리 AI 도우미 운영 안내

기존 관리자 Strata 시험 화면 `/ai`와 별개인 `/assistant`를 제공한다. 관리자는 `/admin/ai/providers`에서 연결·자동 모델 목록·선택형 수동 등록·공개 모델·지원 추론 단계를 관리한다. 실제 배포와 운영 화면 검증의 결과는 [012 보고서](../Reports/2026/11/04/012_AI_Production_Release_Report.md)에 구분해 기록한다.

대화·추론·정규화 업무 초안·요청별 연결과 모델 출처를 사용자별 별도 AI DB에 저장한다. 같은 대화에서 모델을 바꾸면 다음 요청부터 적용하고 접수된 요청의 연결·설정·인증 revision은 유지한다. off/low/medium/high/xhigh/max가 모두 보이며 지원되지 않거나 관리자가 허용하지 않은 단계는 비활성이다. 현재 Strata Qwen3.8 Flash Next의 사전 설정은 off/low/medium/xhigh, 기본 medium이다.

AI가 할 수 있는 업무는 일반 사용자 범위로 제한한다. 본인 장비 조회·등록·수정·상태 변경, 공개 장비·카탈로그 조회, 카테고리·제조사·라인업·옵션 신청과 개인 설정 등을 고정 도구로 제공한다. 관리자 로그인도 AI 업무에서는 일반 사용자 범위를 유지한다. 삭제·폐기·소유자 이전·관리자 승인·사용자 관리·임의 SQL/코드/주소 실행은 제공하지 않는다. 업무 변경은 모델의 제안 뒤 사용자가 화면의 확인 카드를 확정해야 실행된다.

서명 cookie와 현재 계정 SessionToken/CreatedAt·권한·유지보수 세대를 서버에서 재확인한다. Origin/CSRF와 불변 제안의 HMAC·hash·현재 revision을 검사하며 업무 변경·기존 감사·실행 영수증을 같은 DB transaction으로 기록한다. 추론은 표시 데이터이며 다음 모델 요청의 명령으로 재주입하지 않는다.

장비관리 내부 요청만 물리 자원 그룹별 한 개씩 처리한다. 같은 PC/자원에 여러 모델이 있으면 같은 그룹에 둔다. 외부 서비스의 Strata 요청이나 전역 큐·모델 load/unload/취소는 제어하지 않는다. 완료되지 않은 스트림이나 연결 유실은 사유를 남기고 후속 도구를 중단한다. upstream 종료가 불명확하면 자체 그룹 잠금을 유지한다. 해당 자체 요청의 실제 종료를 확인한 뒤에만 worker의 `--acknowledge-finished OWN_JOB_ID`를 사용한다.

대화 보관 기준선은 계정별 32,000,000자이며 기본 추가 완료 예산도 32,000,000자다. 한 턴에 458,912자를 예약한다. 예산 부족 시 새 접수를 제한하고 기존 생성 결과를 지우지 않는다. 추론/답변/업무/오류는 감사 로그에 남기고, 재사용 가능한 인증 원문만 HMAC 지문으로 보호한다. CSV 감사 원문은 별도 보호 파일로 보관하며 기본 물리 예산은 2GiB다. 문자 예산과 DB·WAL·감사·백업 디스크 예산은 다르다.

운영 설정은 기존 Flask SECRET_KEY와 분리된 worker token·Fernet key·DB epoch를 사용한다. 서버의 `.env`, `~/.config/eqmgmt/assistant-worker.env`는 0600, AI/백업 디렉터리는 0700으로 보호한다. 비밀·업무 DB·실제 감사 원문은 Git에 넣지 않는다. 기본 연결은 기존 `http://192.168.0.14:8080`이며 배포 허용 목록도 이 주소로 제한한다. 새 LAN 서버를 추가하려면 운영자가 app·worker의 동일 허용 목록을 먼저 갱신해야 한다. 이 제한은 관리자 브라우저 입력으로 우회할 수 없다.

웹앱은 기존 사용자 Python 구동 방식을 유지한다. AI worker는 `systemd/equipment-ai-worker.service`를 사용자 단위로 설치하며 `systemctl --user status equipment-ai-worker`로 확인한다. 네트워크 읽기 제한은 1800초이고 총 생성 시간 제한은 아니다. worker가 중단되면 신규 요청 처리를 재개하기 전에 종료 불명확 작업의 상태를 확인한다.

배포 도구 `tools/deploy_user_ai.py`는 정확한 commit과 고정 호스트/경로를 검사한다. `check-copy`는 실제 업무 DB를 새 private 사본으로 복제하여 전체 앱과 AI v3 초기화, 기존 업무 행·기존 메뉴 보존, 계정 식별자와 익명 HTTP 경계를 검증한다. `prepare-key`는 사용자가 직접 sudo 인증한 경우에만 기존 root 전용 Nginx 키를 같은 서비스의 private 환경에 연결한다. `activate`는 현재 PID/cwd/명령을 대조하고 SIGTERM·일관 백업 후 앱과 자체 worker를 시작한다. 보호 키를 명령 인수나 출력에 넣지 않는다.

복구 시 신규 AI 접수를 닫고 자체 요청 종료를 확인한 뒤 worker·앱을 정리한다. 배포 release 디렉터리에 보존한 코드 기준선·환경·DB 쌍을 대조한다. 기존 업무/감사 영수증을 지우는 되감기와 AI v3→v2 강제 down은 하지 않는다. AI DB를 교체하면 DB 외부 epoch도 바꾸어 옛 lease를 차단한다. 암호화 키 교체는 이전 키를 보호 키 배열에 보존해 과거 revision/백업을 복호화할 수 있게 한다.

합성 회귀는 Windows에서 앱을 실행하지 않고 `tests/run_assistant_fixture.py --browser`로 승인된 Linux 서버에서 수행한다. 011 원본 후보와 화면 재현 harness는 012 증거의 `reviewed-staging-sources.zip`과 `source-archive-manifest.json`에 원래 경로·SHA-256을 보존한다. 이는 운영 실모델 검증 자료와 구분한다. 고급 연결 설정과 D07 주석 일괄 개선은 기존 보류 상태를 유지한다.
