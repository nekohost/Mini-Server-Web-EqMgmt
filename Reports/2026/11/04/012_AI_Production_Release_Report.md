---
artifact_id: REPORT-20261104-012
work_id: RELEASE-20261104-USER-AI
owner: Codex
created_at: 2026-11-04
status: complete
---

# AI 도우미 운영 배포·실제 검증

## 사전 Validation (순차)

1. **거버넌스:** 사용자가 011 결과 승인 후 서버 반영·실제 테스트·운영 screenshot을 명시했다. recorder 정상, legacy/runtime-session-mismatch, governance 1.8.1/44 nodes/0 errors·warnings. 필수 세 pack의 노드를 읽었다. 대상은 장비관리 프로젝트이며 외부 Strata는 API reference다.
2. **의도:** 검증된 전체 AI 후보를 운영 루트/Git/Linux에 반영하고 실제 결과를 확인한다. Staging 샘플을 운영 screenshot이라고 재사용하지 않는다. 실제 업무 변경 확정은 하지 않으며 기존 사용자/장비/대화와 타 서비스는 보존한다.
3. **논리:** 로컬·서버 HEAD cd93b1a와 app SHA가 일치한다. AI 신규 기능은 비활성 기본이며 현재 운영 환경에는 USER_AI 설정/worker가 없다. crypto 설치·독립 secret·menu/권한과 별도 AI DB 초기화가 필요하다. 사본 import/row 지문과 경로·프로토콜·현재 PID를 조합해 부분 반영을 차단한다.
4. **운영 영향:** 앱 PID 632016은 사용자 소유이며 관련 systemd 앱 unit은 비활성이다. 기존 실제 구동 방식을 확인했고 SIGTERM 후 이전 환경/commit으로 복귀할 수 있게 준비한다. 기존 .env/Flask SECRET_KEY와 Strata Nginx 경로는 유지한다. 전환 중 짧은 서비스 재기동이 필요하다.
5. **보안:** 관리자 로그인은 사용자 직접 입력으로 확인했다. 암호·cookie·키를 원장/명령 인수에 노출하지 않는다. 기존 Strata 키는 root 전용이며 현재 sudo 인증이 없어 보호 연결 단계에는 사용자 직접 인증이 필요하다. 일반 사용자 경계와 미지원 추론은 실제 서버에서 확인한다.
6. **복구:** 온라인 DB snapshot·보호 설정·코드 기준선을 서버와 로컬에 보존한 뒤 업무 DB를 확인한다. AI 이력이 없으면 신규 AI 저장소를 별도 생성하며 있으면 v3/추론 형식 이전을 사본에서 먼저 검증한다. 실패 시 새 접수 닫기→자체 worker/앱 정리→검증한 코드/환경 복귀 순서다. 실제 업무·감사 기록을 삭제하는 롤백은 하지 않는다.
7. **UX:** 실제 로그인/portal에서 새 AI 메뉴·대화·추론/출처·중단 안내 및 관리자 모델 설정, 12px 안내와 dark 글자 대비를 확인한다. desktop/mobile 이미지를 운영 origin에서 캡처한다. 테스트용 확정 장비·카탈로그 데이터는 만들지 않는다.
8. **메타:** 011 합성 112/93 통과를 배포 전 근거로 사용하되 실제 운영 결과와 구분한다. 현재는 백업·병합·배포 전이다. 다른 작업자의 dirty 변경과 과거 009/010/011 기록을 보존하며 성공/실패와 필요한 입력을 정확히 기록한다.

## 진행 기록

일관 백업 `instance/releases/user-ai-20261104T131639Z`를 서버에 만들고 로컬 `instance/release-backups/user-ai-20261104T131639Z`에 수신했다. 업무 DB 사본은 120,000,512 bytes, SHA-256 `d845de35d4d633f13a149ae85d56548249c3f9e9e388dde3e87aa7045bbd2e14`로 서버/로컬이 일치한다. 설정 사본도 보호 영역에 보관했으며 값은 기록하지 않았다. 기존 AI DB는 없었다.

011 최종 원장의 source hash를 검증한 뒤 runtime/test 24개 파일을 구조화 병합했다. 제품 소스는 원본과 텍스트가 일치하며 Git whitespace 검사에 맞춰 app/session_timer의 마지막 빈 줄만 정리했다. 합성 검증 runner는 루트 프로젝트 경로와 제한된 자산 목록을 읽도록 이관했다. 배포 전용 도구를 별도 Staging에서 정적 검사 후 `tools/deploy_user_ai.py`로 병합했다. Python AST와 JavaScript syntax, governance validate가 통과했다. Windows 앱 실행은 없었다.

병합된 루트 소스를 다시 메모리 전송해 Linux Python 3.12.3에서 backend **112/112**, 실패/오류/건너뜀 0, **235.455초**를 확인했다. 브라우저도 사용자 desktop 32/mobile 33, 관리자 desktop 14/mobile 14의 **93/93** 검사가 통과했다. 이 검사는 합성 DB·모델을 사용했고 운영 app import/DB 접근은 없었다. 실제 운영 검증과 구분한다. runtime 소스의 Git whitespace 검사는 통과했다. 과거 003 보고서·010 HTML의 기존 마지막 빈 줄은 원본 보존을 위해 변경하지 않았다.

이번 후보·010/011 화면 재현 harness·배포 도구의 원본 34개는 `012_AI_Production_Verification/reviewed-staging-sources.zip`에 원래 경로 그대로 보존했다. `source-archive-manifest.json`의 파일별 SHA와 ZIP 내용을 모두 대조한 후 해당 Staging 파일만 구조화 삭제했다. 과거 화면 캡처·Plan/Task/Report와 무관한 Staging은 보존했다. 기존 tracked dirty 9개는 선택 commit에서 제외한다.

GitHub main과 서버에 `b9455852d35e4c12d8decda52a93c8985cb85478`을 반영했다. 기존 Flask 3.1.3, requests 2.34.2, python-dotenv 1.2.3은 유지하고 cryptography 50.0.2를 서버 venv에 설치했다. 실제 DB를 새 private 사본으로 복제해 전체 app import·AI v3 초기화를 실행했다. 기존 18개 업무/메타 테이블과 새 AI 메뉴 이외의 기존 메뉴/권한 행이 보존됐고, 실제 계정 3개의 CreatedAt 결손은 0이었다. 익명 `/login` 200, `/assistant`·관리자 AI 설정 302, capabilities 401, worker claim 403을 확인했다. 기존 live 앱 PID 632016은 이 단계에서 계속 운영 중이다.

사용자의 직접 sudo 인증으로 기존 root 전용 Strata 키를 같은 서비스의 0600 환경에 연결했다. 2026-11-04T13:34:46Z에 기존 앱을 정상 종료하고 PID 719360으로 재기동했으며 Flask key와 업무 행 보존을 확인했다. 사용자 unit worker PID 719375는 active/running, 재시작 0회다. Nginx와 공유 Strata 서비스는 재기동·설정 변경하지 않았다.

실제 운영 UI에서 medium 산술 대화 7.575초, 본인 장비 조회 5.429초/2단계(`search_equipment`, 답변 2개), 제조사 신청 확인 카드 12.115초/2단계(`prepare_catalog_request`)를 확인했다. 실제 업무 확정 버튼은 누르지 않았다. 실제 모델 기능 시험은 chat/tools/off/low/medium/xhigh의 6단계로 19.170초에 통과했고, 네 추론 단계의 verified_levels가 기록됐다. 이 시간은 서버 job의 접수~상태 갱신 시간이며 순수 생성 속도/장문 성능 벤치마크가 아니다.

운영 화면 검사에서 제조사 신청 카드의 `name` 항목이 공통 사전 때문에 '장비 이름'으로 표시되는 결함을 발견해 사용자에게 알렸다. 실행·저장 내용의 결함은 아니며, 신청 종류별 '카테고리 이름/제조사 이름/라인업 이름'을 사용하도록 별도 Staging에서 수정·syntax 검증 후 루트에 병합했다. 수정 후 Linux 합성 브라우저 4개 폭/화면의 93 검사는 재통과했다. 실제 운영 재확인은 후속 기록에 남긴다.

## 최종 검증 결과

제품 코드의 최종 수정은 `1fd1a3d35af667eb3f3433f9740e68665b0717e6`이다. Windows와 Linux의 runtime/test/배포 파일 25개 SHA-256이 일치한다. 이후 자료 정리 commit은 제품 실행 코드를 바꾸지 않는다. [실제 캡처 16개](012_AI_Production_Verification/index.html), [최종 서버 상태](012_AI_Production_Verification/final-runtime-check.json), [합성 회귀](012_AI_Production_Verification/merged-regression.json), [실제 모델 측정](012_AI_Production_Verification/real-model-checks.json)을 보존했다.

| 구분 | 대상/방식 | 실제 결과 |
| --- | --- | --- |
| 배포 전/후 DB | 실제 업무 DB 온라인 사본의 전체 app/AI 초기화, integrity/FK, 행 지문 | 초기 18개 테이블 보존. UI 시험 후 17개 동일, `user_settings`의 시험 메타데이터만 변경 |
| 백엔드 합성 회귀 | Linux 실제 소스·합성 DB/모델 | 112/112, 실패/오류/건너뜀 0, 235.455초 |
| 브라우저 합성 회귀 | 사용자 32+33, 관리자 14+14 | 93/93. 카드 항목명 수정 후 93개 재통과 |
| 운영 소스 권한 | 실제 DB의 새 격리 사본·실제 login decorator/메뉴/owner 경계 | 일반 사용자 화면·capabilities 200, 관리자 경로 403, 위조 역할 403, 타인 대화 404, 위조 cookie 401 등 11개 통과 |
| 실제 HTTPS | 정상 인증서/Nginx의 익명 화면/API/worker 경계 | 7개 예상 status 일치. 실제 로그인된 브라우저에서 새 메뉴·대화·관리자 UI 정상 |
| 실제 모델/도구 | 기존 Strata Qwen3.8 Flash Next | 산술 답변·본인 장비 조회·확인 카드·6단계 기능 계약 시험 통과 |
| 실제 화면 | desktop 1440, mobile 430, 초기 기본 폭 및 light/dark | 원본 JPEG 16개, 가로 넘침 없음, 안내문 12px, dark 글자/white control 구분, 표준 추론 전체 표시 |
| 감사 | 운영 AI HTTP 본문 940개 확인 시점 | 질문·추론·제안 내용 보존, 재사용 secret 원문 4종은 미포함 |
| 종료 상태 | 앱/worker·AI DB·시험 기록 | worker active/running·재시작/경고 0, AI v3 integrity/FK 정상, done 3/cancelled 1·대기/실행/복구 잠금/미확정 카드 0 |

실제 취소 이유는 새로고침→모바일 대화 목록→기존 대화에서 다시 보였다. 확인 카드의 실행 버튼은 제거됐고, 다음 추론을 low로 바꾸어 저장한 선택도 재접속 후 복원됐다. 기존 답변의 출처 medium은 유지됐다. 시험 종료 후 다음 추론은 medium, 테마는 원래의 시스템으로 복원했으며 임시 viewport override reset을 호출했다. 실제 운영 탭은 사용자 검토용으로 남겼다.

제조사 신청 카드 수정은 새 `1fd1a3d`를 pull한 뒤 '제조사 이름'으로 재확인했다. 모든 실제 업무 확정은 누르지 않았다. 시험 카드 하나만 정확한 job/owner/account를 검증해 `Store.cancel`로 닫았고, 내용·이력을 삭제하지 않았다. 이는 브라우저의 실행 버튼을 누른 시험이 아니며 사유를 저장한 운영 정리다. 최종 DB에는 기존 장비 2개·제조사 1개·신청 0개, AI 실제 실행 영수증 0개가 유지된다.

## 백업과 복구

초기 백업 외에 전환 직전 `equipment-at-activation.sqlite3`·기존 process environment, 적용 후 `post-check/equipment-after.sqlite3`·`assistant-after.sqlite3`·보호 환경을 서버 private release에 보존했다. 최종 DB 사본 두 개를 로컬 private `instance/release-backups/user-ai-20261104T131639Z/post-check`에도 받았고 SHA를 대조했다. 적용 후 설정/키는 로컬의 별도 ACL 제한 `instance/release-key-backups/user-ai-20261104T131639Z`에 보존했다. 비밀·DB 파일은 Git/화면 자료에 넣지 않았다.

최종 업무 DB 사본은 120,815,616 bytes/SHA `07cd59ae70bc2a39532b3c639251808eef6d2b0c41b0860371a92421b85905bb`, AI DB 사본은 180,224 bytes/SHA `19780aab87214e665ffa072b3ec3f7572d3ff5ac4d688092bd362432a9b20bbd`다. app/worker 환경은 0600, AI 디렉터리는 0700, AI DB는 0600이다.

우선 복구는 v3 코드에서 신규 접수/쓰기 비활성→자체 응답 종료 확인→worker 정상 정리→웹앱 재기동 순서다. 이 경로는 기존 메뉴 필터와 AI 이력·감사를 유지한다. 원래 코드/DB 쌍으로 돌아가는 비상 복구는 post-check 업무·감사 자료를 먼저 보존·대조하며 임의 down/행 삭제로 처리하지 않는다. 암호화 키나 epoch를 임의 재생성해 이력/미종료 요청을 성공으로 바꾸지 않는다. 공유 Strata의 작업/프로세스는 복구 대상이 아니다.

## 검증 범위와 남은 경계

실제 로그인/모델 호출/캡처는 사용자가 로그인한 관리자 계정으로 수행했고 AI 도구는 그 계정에도 일반 사용자 범위만 적용했다. 일반 사용자·타 owner 보안 검사는 실제 DB의 격리 사본에서 했으며 다른 실사용자의 브라우저 로그인이나 암호를 사용하지 않았다. 실제 업무 변경 확정·승인·삭제도 시험하지 않았다.

실제 등록·호출 검증 연결은 기존 Strata 한 개다. 여러 연결/모델 전환·독립 그룹·상호 격리와 오류 스트림 등은 합성 회귀로 검증했다. 다른 LAN 모델을 실제 추가하거나 다른 실모델 사이의 이어가기 시험까지 했다고 주장하지 않는다. 외부 서비스 요청의 큐·load/unload·취소를 조작하지 않았다.

65,536은 관리자에게 설정된 컨텍스트 상한이며 실제 질문과 nonce 시험은 짧다. 위 job 시간은 접수/배차/도구 처리까지 포함한 측정이며 장문 전체 성능·최대 컨텍스트·일반 지능·순수 tokens/s의 검증으로 확대하지 않는다. 고급 연결 설정과 D07 주석 일괄 개선, 기존 전역 감사 손실 정책의 후속 검토는 보류 상태를 유지한다.

## 사후 Validation (순차)

1. **거버넌스:** 승인된 운영 반영 범위와 legacy 경로를 유지했다. recorder 정상과 governance validate를 재확인하고 source/문서만 선택 commit한다. 사전 dirty 9개는 별도 diff로 보존·대조한다.
2. **의도:** 실제 HTTPS/Strata/원본 screenshot을 사용했다. 112/93 합성, 실제 DB 사본 11개, 실제 모델 4개 검증 묶음을 명시적으로 구분했다.
3. **논리:** v3 schema·server/worker 계약·지원 4개 추론·25 source SHA와 도구 호출을 대조했다. 카드 항목명 결함은 Staging→정적 검사→Git→Linux pull→실제 재확인으로 수정했다.
4. **운영 영향:** 웹앱은 기존 사용자 실행을 유지하고 자체 worker만 user systemd로 추가했다. Flask key·기존 업무 행을 보존했고 실제 업무 확정은 없었다. 테마/다음 추론 시험값은 복구했다.
5. **보안:** 기존 root 키는 직접 sudo 인증으로 같은 서비스에 연결했다. 인증 원문은 명령/로그/Git에 노출하지 않았고 private mode·익명/권한/owner/CSRF·감사 보존을 검사했다.
6. **복구:** 전/전환/후 DB와 독립 보호 키를 보존·로컬 수신·해시 검증했다. 신규 접수를 끄는 v3 복구를 우선하며 업무/감사 영수증·이력·잠금을 지우는 강제 복구를 금한다.
7. **UX:** 실제 16개 화면을 검토했다. 제조사 항목명은 수정 완료, 지원 밖 high/max는 보이되 비활성, 안내 12px, 추론 스트리밍/자동 접힘/다시 열기/선택 복원/중단 사유가 동작한다.
8. **메타:** 실제 확인한 단일 Strata와 짧은 입력의 경계를 보고한다. 다른 서비스 제어·실사용 일반 계정 로그인·실제 업무 쓰기·장문 벤치마크는 수행했다고 주장하지 않는다. 과거 원본·다른 작업의 dirty 자료를 보존한다.

운영 primary는 현재 백업서버(nkhst-pentium)이며 `/home/nekohost/services/Mini-Server-Web-EqMgmt`에서 실행 중이다. 소스 HEAD와 app SHA가 Windows 기준선과 일치하고 공유 Strata `/health`는 loaded=true, 모델 qwen3.8-flash-next-iq3_xxs, API key 필요 상태다. 기존 secret key 강도 조건은 충족하며 crypto는 아직 설치되지 않았다. root 전용 key 파일을 읽기 위한 권한을 풀거나 인증을 우회하지 않는다.
