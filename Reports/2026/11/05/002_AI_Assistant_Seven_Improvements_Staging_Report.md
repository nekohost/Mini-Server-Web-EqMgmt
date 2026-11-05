---
artifact_id: REPORT-20261105-002
work_id: STAGING-20261105-AI-UX-TRASH
parent_work_id: REVIEW-20261105-AI-UX-RETIREMENT
owner: Codex
created_at: 2026-11-05
status: complete
---

# AI 도우미 1~7번 Staging 구현·검증

## 구현 전 Validation 1~8

1. **거버넌스:** recorder 정상(PID 11268), profile legacy/runtime-session-mismatch, governance 1.8.1 validate 44 nodes/오류·경고 0. 새 context의 세 pack/30개 고유 노드를 순서대로 읽었다. Staging overlay와 영구 Task/Report만 작업 대상으로 분리한다. Windows 앱 구동·원본 소스 변경·실제 DB 변경은 제외한다.
2. **사용자 의도:** 승인된 001 Plan의 1~7을 유지한다. 표/조회 오류/이름/관리자 메뉴/공통 UX/옛 Strata 회수/대화 휴지통을 모두 구현하고 독립 파일은 요청 모델의 하위 작업자로 분담한다. 이번 권한은 Staging이며 운영 배포로 확대하지 않는다. Fast는 도구에 독립 제어 항목이 없어 보장하지 않는다.
3. **정적 논리:** 삭제 상태와 UTC 서버 기산일/revision을 단일 writer에서 검사하고 종속/원장/점유를 분리한다. 원래 group partial index의 실행 job을 바로 삭제하지 않는다. 정리는 bounded batch, 모델 대기 중 DB writer 금지, 공유 파일의 편집 소유자를 고정한다.
4. **운영 영향:** 기존 v3/신규 v4의 전진 migration과 호환 복귀·timer 활성화 순서를 함께 다룬다. 메뉴 metadata는 멱등 이전, 옛 UI proxy는 차단/폐기 안내 계약으로 바꾸며 새 adapter와 공유 Strata 서비스를 유지한다. 소스 후보·제거 목록·설치 문서를 분리하고 실제 Nginx/서비스는 손대지 않는다.
5. **보안/예외:** actor owner+account, CSRF/Origin, tool 검증, safe DOM, 프로바이더 비밀 경계를 유지한다. 정상 목록/휴지통/만료와 확정/GC/복구/늦은 callback 경합을 검사한다. 장비 삭제 권한이나 AI tool을 통한 대화 삭제는 추가하지 않는다.
6. **복구:** 신규 overlay 삭제로 소스 후보를 되돌릴 수 있으며 원본 dirty 9개/기타 untracked는 보존한다. 실제 v4 적용은 일관 백업·점유 이전·호환 코드와 묶어야 하고 영구삭제가 자동 복구 가능하다고 안내하지 않는다. 독립 감사/업무/백업은 기존 정책을 유지한다.
7. **휴먼 에러:** mobile·light/dark·중복 클릭·결과 불명확·저장 후 GET 실패·명시적 영구삭제 확인·복구 후 30일 재기산·두 탭 stale state를 수용 기준으로 삼는다. 긴 모델 요청에 일괄 timeout이나 공유 모델 중단을 넣지 않는다.
8. **메타:** 각 하위 에이전트는 자기 recorder/profile/context를 확인하고 할당한 후보 파일만 편집한다. 새 결과를 실제 실행과 정적 검토로 구분하며 과거 112/93 수치를 재사용하지 않는다. 최종 통합은 부모가 실제 파일/검사 근거로 판단한다.

## 작업 진행 및 실행 근거

구현 시작 전 기록이다. 새 검증 수치는 아직 없으며 이후 실제 실행 결과를 추가한다.

### 구현·반례 확인

- 요청대로 세 하위 작업을 gpt-6.1-sol/reasoning max로 생성했다. 하위의 profile은 legacy/runtime-thread-id-conflict로 식별되었고 각자 recorder/context/적용 노드를 확인했다. Fast를 별도로 설정·검증하는 tool 인수는 제공되지 않아 보장하지 않는다. 공유 파일 소유권과 API 계약을 부모가 조율했다.
- 표/짧은 모델명·관리자 메뉴/모달·기존 Strata 폐기 후보·v4 휴지통/guard/원장·공통 정규화/진단 분리를 모두 구현했다. API·원장·점유·권한 교차검토는 부모가 수행했다.
- 초기 새 Store 회귀의 malformed ID 400 기대는 기존 `opaque()`의 404 계약과 달랐다. 구현을 완화하지 않고 정확한 기존 404 기대와 배열/대문자 거절 반례로 정정했다. v1/v2 이전의 최종 version 기대도 v4로 갱신했다. foreign cursor는 v4 view-bound 형식을 사용하고 구 형식 400 거절 검사를 추가했다.
- 실제 오류 회귀: guard_finish가 PROCESSING_FAILED/점검 실패까지 cancelled로 분류한 것을 발견했다. 최초 error/error_code와 기존 failed/cancelled 판정을 보존하도록 구현을 고치고 단독 세 반례를 추가했다. worker의 새 사전 허가 검사를 기존 chunk 거절 fixture에도 구분해 반영했다.
- 교차검토 반례: 삭제 후 점검 중 detached lease cleanup, 관리자 강등/메뉴 회수 후 probe 조회/검증, final writer 직전 권한 회수, 도구 사이 휴지통 이동, guard 검사와 lease 읽기 사이 purge, pre-dispatch 준비 오류를 보완·검사했다.
- 실제 화면 반례: native dialog의 닫힘/focus 시점, 이전 close 이벤트의 다음 모달 간섭, body를 focus 대상으로 잘못 고르는 문제, 목록 more와 background refresh 경합, 이전 조작 receipt가 현재 상태를 반환하는 경우를 수정했다. 표 구분행 검사에는 실제 streaming=true를 전달하며 최종 GFM 표 규칙과 혼동하지 않는다.
- 첫 화면 fixture는 차단된 CDN과 수동 preflight로 실제 공통 테마를 충분히 재현하지 못했다. 기존 로컬 Tailwind fallback을 명시적으로 로드하고 실제 사용자 설정 복원·light/dark class·배경 RGB·글자 대비를 검사하도록 보완했다. 제품 배경을 바꾸어 검사를 통과시키지 않았다.
- 초기 fixture가 import된 AssistantTests를 중복 수집한 것은 수집기가 module 소유 TestCase만 집계하도록 고쳤다. 이후 backend 수치는 고유 178개다. 대량 합성 DB의 디스크 journal 대기가 길어 전용 Linux tmpfs의 파일 기반 SQLite로 기능 검증을 실행한다. WAL/FK/synchronous 설정은 바꾸지 않고 디스크 내구성/운영 성능 검증을 주장하지 않는다.

중간 단계에서 backend 178/0/0/0과 화면 16뷰/757 checks 통과를 확인한 뒤, 강화 검증으로 기존 frame/초기 준비 상태의 비동기 경계를 추가 점검했다. 최종 수치와 판정은 아래 최종 검증 절을 기준으로 하며 이 중간 진행 기록과 구별한다.

## 최종 구현 결과

| 번호 | Staging 반영 내용 | 확인 결과 |
| --- | --- | --- |
| 1 | 기존 안전 DOM renderer에 제한적 GFM 표·정렬·빈/누락 셀·이스케이프·코드펜스·상한/원문·가로 스크롤을 추가했다. 스트리밍 중 미완성 줄과 선택/스크롤/추론 펼침을 보존한다. | 기존 표 재열기·XSS·코드·미완성/완성 구분·긴 표와 light/dark/모바일 통과 |
| 2 | HTTP/Domain에서 같은 optional 조회 필터 정규화를 사용한다. probe를 일반 목록/문맥에서 목적별로 분리하고 mixed 사용자 이력을 보존한다. | 원래 빈 status/due 인자가 본인 장비 조회에 도달, invalid/write enum·권한 차단 유지. 진단 권한 회수·final writer도 재검사 |
| 3 | 모델 옵션은 연결/모델 표시 이름으로 줄이고 capability/불가 사유는 별도 영역으로 표시한다. | 비활성 사유·모델 선택/추론/동결 출처/대화 이어가기 유지 |
| 4 | settings seed와 기존 metadata를 admin_center로 멱등 이전하고 현재 실제 관리자/메뉴 권한으로 노출·API를 제한한다. | 기존 사용자 정의 이름/순서/설명/grant 보존·충돌 차단·일반 사용자 거절 통과 |
| 5 | 공통 로딩과 native dialog, 중복/전환 잠금·focus·결과 불명확 조회·ACK/GET 분리·probe 접수/종료 UX를 적용했다. | 모바일 하단·연속 모달·이전 close 이벤트·409·유실 POST/키 비움·외부 모델 제어 없음 통과 |
| 6 | 옛 화면은 폐기 안내, API/proxy/static은 410 차단 후보로 전환했다. 공개 자산 11개 회수 manifest·Nginx deny·bootstrap 보호 키 분리와 보존 절차를 작성했다. | 새 assistant/adapter·공유 서비스/키·license 이력 보존. 실제 운영 파일 회수나 Nginx 변경은 하지 않음 |
| 7 | v4 가산 이전·휴지통/읽기 전용·복구/재이동 30일·명시적 영구삭제·timer 후보·종속/원장 정리·별도 실행 guard·삭제 결정 대조를 추가했다. | UTC 만료/중복/stale·owner/account·확정/GC/worker 경합·후속 작업 중단·롤백·원장·과거 복원 재노출 방지 통과 |

## 최종 Validation 1~8

1. **거버넌스:** 실제 승인 Plan 001을 구현 전에 승계하고 Task/구현 전 검토 뒤 후보를 작성했다. 실행 단계 Plan 002는 공통 work_id 색인이며 과거 승인/작성 시점을 조작하지 않는다. 일반 소스/문서는 structured apply_patch로만 편집했고, PNG는 승인된 검증 도구의 새 합성 산출물이다. legacy 사유와 Fast 제어 한계를 숨기지 않았다. governance 44 nodes/오류·경고 0, 운영 소스보다 Staging 격리를 유지했다.
2. **사용자 의도:** 1~7의 실제 기능과 UX를 구현하고 세 하위 작업자로 분담했다. 대화 삭제를 장비 삭제 권한으로 확대하지 않았다. 사용자 업무 범위·독립 대화 UI·다중 모델 이어가기·자체 요청 큐·기존 추론 선택 계약을 유지한다. 타 서비스 큐·load/unload/취소·새 외부 AI 서비스는 제어하지 않는다.
3. **논리/실패:** 두 writer의 확정/휴지통 직렬화, indexed/bounded 만료 정리, 동일 조작 멱등·현재 receipt·stale GC/revision, 삭제 후 late event/finish, 조회/업무의 단계별 중단과 최초 오류/최종 상태, 정확한 메시지/초안/handoff 원장 차감을 실제 Linux SQLite로 검사했다. 목록은 view별 큐로 more/background 경합을 막고 메시지 hydration과 sidebar 준비를 분리해 composer/진행 stream/draft를 보존한다.
4. **운영 영향:** 코드/worker/schema/점유/timer의 부분 적용은 피하도록 명시했다. 기존 v1/v2/v3 및 새 v4, current schema의 누락/약한 index는 검증하며 불완전 배포를 기동에서 거절한다. 메뉴는 정확한 metadata 행만 이전한다. v4 적용·보호 환경 경로·옛 UI/Nginx/public asset 전환 순서는 후보 설치 문서에 분리했다. 현재 운영 반영은 실행하지 않았다.
5. **보안/예외:** owner+account_key·실제 role/grant·Origin/CSRF·closed schema·opaque/revision·current lease/epoch를 유지한다. 순수 진단 조회·최종 capability 게시에도 권한 회수를 반영한다. 악성 HTML/링크·잘못된 enum/타입·다른 계정·변조 cursor·중복 JSON ledger/oversize·키 경로/권한을 검사했다. 감사 내용과 업무 영수증은 유지하고 재사용 키는 별도 보호한다.
6. **보존/복구:** root 주요 소스 24개 SHA는 baseline과 같고 HEAD는 3d9dacc다. 기존 tracked dirty 9개와 기타 untracked를 보존하고 index는 비어 있다. candidate에 v4 호환 복귀·timer 중지·최신 삭제/만료 ledger 보존/대조·외부 epoch 절차를 문서화했다. 영구삭제를 rollback으로 복구 가능하다고 주장하지 않는다. 대량 backlog는 제한 배치로 순차 정리하며 만료 열람/복구 차단과 물리 정리 시점을 구별한다.
7. **UX/시각:** 실제 Chromium 16개 조합의 803 checks가 모두 통과했다. focus/키보드·모바일 하단·두 탭·응답 유실·기처리 receipt·보관 기산일·readonly·표/가로 스크롤·진행 추론/stream/draft·기존 모델/CSV 흐름을 포함한다. 대표 모바일 표/desktop dark 표/관리자 dark 모달 PNG를 직접 보았다. class=light인데 중간 dark 색이 남는 headless 현상은 최종 실행에서 body 전환 currentTime=0/endTime=200으로 관찰됐고, 유한한 body 색 전환만 finish한 뒤 실제 CSS endpoint를 검사했다. darkMode=class·class 선택자/정확 RGB/대비 기준은 유지했으며 제품 테마 배경은 바꾸지 않았다.
8. **메타/판정:** 같은 고정 runtime snapshot에서 backend 고유 178개와 UI 803 checks가 함께 통과했다. 근거는 아래 JSON/소스 SHA/PNG다. 수정 전 실패·검증 도구의 포맷 오류·fixture 기대 불일치를 성공으로 숨기지 않고 해당 계약/실제 코드와 대조했다. KO 일괄 동기화와 보류된 고급 연결 설정은 수행하지 않았다. 이 결과는 **Staging 구현·검증 완료**이며 운영 배포나 실제 모델 정답률·속도 완료 보고가 아니다.

## 고정 소스 실행 근거

| 검사 | 최종 결과 |
| --- | --- |
| Linux backend | **178개 통과, 실패 0, 오류 0, skip 0. 35.771초.** Python 3.12.3, 임시 파일 기반 Linux tmpfs·기존 SQLite 설정 유지 |
| 기존 사용자 화면 | desktop 1440/모바일 430, 2뷰·65 checks |
| 관리자 화면 | 기본 desktop/430 + 390 light/430 dark/768 light/1440 dark, 6뷰·198 checks |
| 새 표/휴지통/경합 UI | 390/430/820/1440 × light/dark, 8뷰·540 checks |
| 화면 전체 | **16뷰·803 checks, 실패 0**, 각 화면의 PNG 보존. 관리자 모달 글자 대비 약 5.895 |
| 정적 | Python AST 25개, JS node --check 4개, Linux Jinja parse 3개. 5분 OnCalendar를 실제 systemd-analyze calendar로 검증 |
| 보존 | root baseline 24개 동일, HEAD/index/기존 dirty 보존. 실제 업무/AI DB·모델·서비스·키·Nginx·timer 변경 없음 |

최종 fixture digest는 `a6a5fc299f8158c7299fa56289a9125373226bb9c7b02310a348632d517d8e26`이다. 상세 check 이름·테마/전환/CSS/대비·PNG 경로는 [validation.json](002_AI_Assistant_Seven_Improvements_Staging/validation.json), 후보 파일 SHA/크기는 [source-manifest.json](002_AI_Assistant_Seven_Improvements_Staging/source-manifest.json)에 있다. 재현은 `Staging/20261105-ai-ux-trash/INSTALL-AND-VALIDATION.md`를 따른다. Windows Python에 Jinja가 없어 그 구문 검사는 승인된 Linux venv로 수행했으며 의존성을 새로 설치하지 않았다.

대표 화면(합성 데이터와 의도적인 XSS 검사용 문자열 포함):

- [430px 표 화면](002_AI_Assistant_Seven_Improvements_Staging/screenshots-round7/screen-010.png)
- [1440px dark 표 화면](002_AI_Assistant_Seven_Improvements_Staging/screenshots-round7/screen-015.png)
- [430px dark 관리자 완료 모달](002_AI_Assistant_Seven_Improvements_Staging/screenshots-round7/screen-005.png)

## 적용 범위와 남은 운영 단계

제품 후보는 `Staging/20261105-ai-ux-trash/overlay`에 있다. commit/push·운영 소스 병합·실제 DB migration/삭제·서버 배포·옛 공개 파일 회수·Nginx reload·retention timer 설치/활성화는 수행하지 않았다. 실제 LAN 모델 품질/연결·운영 부하·장문 성능·전원 장애 내구성을 이번 합성 시험으로 주장하지 않는다. 운영 시 v4/worker/guard 동시 적용·정확한 private DB/epoch·백업/삭제 ledger·옛 UI deny/회수·timer 검증 순서가 필요하며 상세는 후보 설치 문서에 남겼다.
