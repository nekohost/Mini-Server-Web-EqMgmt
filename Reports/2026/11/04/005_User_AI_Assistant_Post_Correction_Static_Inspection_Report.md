---
doc_type: report
doc_id: REPORT-20261104-005
work_id: REVIEW-20261104-USER-AI-POST-CORRECTION-STATIC
plan_ref: PLAN-20261104-005
task_ref: TASK-20261104-005
title: User AI Assistant Post-Correction Static Inspection Report (Staging 20261104-user-ai-assistant)
created_at: 2026-11-04
updated_at: 2026-11-04
status: completed
mode: static-review
platform: gemini-antigravity
target_staging: Staging/20261104-user-ai-assistant
reviewed_reports:
  - Reports/2026/11/04/002_User_AI_Assistant_Static_Review_Report.md
  - Reports/2026/11/04/003_User_AI_Assistant_Followup_Plan_Review_Report.md
  - Reports/2026/11/04/004_User_AI_Assistant_Corrections_Report.md
  - Reports/2026/11/04/user-ai-assistant-corrections-validation.json
---

# 사용자용 AI 비서 보완 후 Staging 정적 검사 보고서 (`REPORT-20261104-005`)

## 1. 종합 판정 요약 (Executive Summary)

- **검사 대상**: `Staging/20261104-user-ai-assistant/overlay/` 후보 코드 16개 파일, 백로그 문서 3개 파일(`Staging/20261104-user-ai-assistant/README.md`, `ROADMAP.md`, `UNIMPLEMENTED_ROADMAP.md`), 그리고 `Reports/2026/11/04/004_User_AI_Assistant_Corrections_Report.md` 및 `Reports/2026/11/04/user-ai-assistant-corrections-validation.json`
- **검사 방식**: Windows 워크스페이스 거버넌스(`operations.staging`)에 따른 **순수 정적 코드 검사(`static-review`)** 수행 (운영 앱 기동 없음, 루트 DB 접근 없음, Strata 실추론 호출 없음, 후보 및 루트 코드 변경 없음)
- **무결성 및 구문 검증 결과**:
  - `user-ai-assistant-corrections-validation.json`에 기록된 후보 파일 16개(`candidate_manifest`), 기록 문서 3개(`record_manifest`), 루트 보존 대상 15개(`preservation.results`)의 SHA-256 해시 대조 결과 **불일치 0건(`0 mismatch`)** 확인
  - Staging 오버레이 내 Python 파일 10개 AST 파싱(`ast.parse`) 및 JavaScript 파일 2개(`equipment_ai.js`, `session_timer.js`) `node --check` 구문 검증 **전수 통과**
- **사용자 결정사항(`D01~D07`) 반영 여부**:
  - 이전 정적 검토(`002`, `003`)에서 지적되었던 핵심 결함 7건(`D01~D07`)은 모두 사용자 결정 방향에 맞게 **구현·반영되었음**을 정적 코드 대조로 확인함
- **최종 도달 수준 판정**: **조건부 도달 (Conditional Pass — 핵심 기능·품질 목표 달성, 병합/실서버 검증 전 보완 권장 엣지 케이스 4건 및 기술부채 백로그 1건 존재)**
  - **P0 / P1 (Critical / High) 결함**: **0건**
  - **P2 (Medium — 예외·경계 조건 보완 필요)**: **3건 (`S01`, `S02`, `S03`)**
  - **P3 (Low — 오류 메시지 보존 및 기술부채 백로그 참고)**: **2건 (`S04`, `S05`)**

---

## 2. 8단계 순차 검증 요약표 (Validation Phases 1–8)

| 단계 | 검증 영역 | 판정 | 핵심 근거 및 정적 검증 결과 |
| :--- | :--- | :---: | :--- |
| **Phase 1** | 아키텍처·영향도·요구사항 대조 | **PASS** | `app.py` 최소 훅 연결 + `utils/ai_assistant/`(`__init__.py`, `domain.py`, `store.py`, `policy.py`, `audit.py`, `worker.py`) 모듈 분리 유지, 사용자 결정 1~7 전수 반영 확인 |
| **Phase 2** | 문법·구문·전역 심볼 무결성 | **PASS** | Python 10개 파일 AST 구문 검사 통과, JS 2개 파일 `node --check` 통과, 중복 라우트·순환 참조·전역 심볼 충돌 없음 |
| **Phase 3** | 런타임 데이터 흐름·타입·예외 안전성 | **WARN** | `finish()`의 알려진 실패 종결(`D02`) 및 다단계 추론 오프셋 병합(`D03`) 정상 구현. 단, `maintenance_request_gate`의 `/internal/ai/*` 선차단(`S02`), `claim()` 비-`AssistantError` 예외 시 `running` 고착(`S03`), `store.cancel` `COALESCE` 순서(`S04`) 보완 권장 |
| **Phase 4** | 보안·인증·감사·세션 경계 | **WARN** | RBAC, `session_rev`, CSRF, 승인 토큰 HMAC(`proposal_token`), 워커 토큰 상수 시간 비교, 루프백 URL 검증, `audit.py` 자격증명 전용 HMAC 지문화(`D01`) 정상. 단, `app.py:1343`에서 `/api/ai/equipment/.../files` 및 `/api/ai/csv/*`가 바이너리/대용량 본문 캡처 제외 목록에서 누락됨(`S01`) |
| **Phase 5** | DB·트랜잭션·점검 게이트·정합성 | **WARN** | `assistant.sqlite3` 분리(`WAL`, `busy_timeout=5000`, `foreign_keys=ON`), `BEGIN IMMEDIATE` 트랜잭션, 장비 정규화 반환값(`payload`) 공통 사용(`D06`) 확인. 단, `job_actor()`가 점검 상태 확인 전에 `equipment.db` 연결을 여는 순서(`S02`) 보완 필요 |
| **Phase 6** | 프론트엔드·UI·스트리밍·페이지네이션 | **PASS** | `mergeStream` 오프셋 병합, `message_steps` 렌더링, 턴 단위 추론 접기/펼치기(`answer_started`), 대화 50건 단위 커서·메시지 60건 단위 `before` 페이지네이션(`D04`), 폴링 세션 비연장(`X-Session-Touch: 0`), 터미널 실패 시 입력 잠금 해제 확인 |
| **Phase 7** | 성능·용량 예산·쿼리·리소스 상한 | **PASS** | 32MB 기본 + 32MB 기본 확장(`STORAGE_CAP = 64MB`), 출력 예약 `426,144`자(`D05`), `storage_meta` 문자 원장, 대화 최대 200개, 도구 라운드 최대 4회, 전역 단일 작업 큐(`one_application_request`) 확인 |
| **Phase 8** | AI 메타 검증·주석 동기화·보존성 | **PASS (유예 포함)** | 후보 16개·문서 3개·보존 15개 SHA-256 100% 일치. 오버레이 내 24개 `[MINI-COMMENT:...]` 블록 포맷/EN 메타 검증 통과(`0 FORMAT-ERROR`). KO 감사 및 함수별 독스트링은 사용자 결정 7(`AI-TECHDEBT-001`, `S05`)에 따라 백로그 등록 확인 |

---

## 3. 사용자 결정사항(`D01~D07`) 반영 검증 결과

| 항목 | 이전 결함 및 사용자 결정 요약 | 반영 위치 (Staging Overlay) | 정적 검증 판정 |
| :---: | :--- | :--- | :---: |
| **D01**<br>(결정 1) | AI 감사 로그에서 프롬프트·추론·답변·제안·영수증을 마스킹하지 않고 보존하되, 재사용 가능한 인증·보안 자격증명만 상관분석 가능한 일방향 HMAC 지문(`[보호된 인증값:<24-hex>]`)으로 치환 | `utils/ai_assistant/audit.py:1-130` (`audit_body`, `SENSITIVE_KEYS`, `known_secrets`), `app.py:1365-1371`, `utils/ai_assistant/policy.py:111-132` | **반영 완료**<br>(단, 파일/CSV 엔드포인트 제외 조건 `S01` 보완 필요) |
| **D02**<br>(결정 2) | 도구 호출 스키마 불일치·중복 ID·크기 초과 등 원인이 확인된 실패는 `failed`/`cancelled`로 종결하여 예약 용량과 단일 큐 잠금을 즉시 해제하고, 업스트림 실행 여부가 불확실한 경우만 `recovery_required` 유지 | `utils/ai_assistant/__init__.py:429-524` (`finish`), `utils/ai_assistant/store.py:460-483`, `utils/ai_assistant/worker.py:150-228`, `static/js/equipment_ai.js:107,234-245` | **반영 완료**<br>(단, 점검 게이트 503 충돌 `S02` 및 `claim` 예외 처리 `S03` 보완 권장) |
| **D03**<br>(결정 3) | 다단계 도구 루프의 추론 요약을 단계별(`message_steps`)로 누적 보존하고, 오프셋 기반 멱등 스트리밍 병합(`mergeStream`) 및 답변 본문 시작 시점(`answer_started`) 기준 1회 자동 접기 적용 | `utils/ai_assistant/store.py:37,334,372-424`, `utils/ai_assistant/worker.py:120,131-137`, `static/js/equipment_ai.js:14-22,126-163,319-340` | **반영 완료**<br>(단, 취소 시 오류 메시지 보존 `S04` 참고) |
| **D04**<br>(결정 4) | 최대 200개 대화(50개 단위 커서 페이지네이션) 및 60개 초과 메시지(`before` 커서 페이지네이션) 이력 탐색 UI/API 제공 | `utils/ai_assistant/store.py:126-152,309-338`, `utils/ai_assistant/__init__.py:211-225`, `templates/equipment_ai.html:19,40`, `static/js/equipment_ai.js:251-289` | **반영 완료** |
| **D05**<br>(결정 5) | 32,000,000자 기본 예산 + 32,000,000자 기본 자동 확장(총 64,000,000자) 및 426,144자(`OUTPUT_RESERVATION`) 사전 예약·문자 원장(`storage_meta`) 관리 | `utils/ai_assistant/policy.py:15-19`, `utils/ai_assistant/store.py:38,44-93,168-278`, `static/js/equipment_ai.js:84-89` | **반영 완료** |
| **D06**<br>(결정 6) | 장비 생성·수정 제안 생성 시점과 승인 후 실제 DB 반영 시점 모두 `shared_normalize_equipment_mutation_payload`의 반환값(`payload`)을 동일하게 사용 | `utils/ai_assistant/domain.py:164-166,194-216,301` | **반영 완료** |
| **D07**<br>(결정 7) | 주석/독스트링 메타데이터 전수 보강 및 한국어 감사 동기화는 기능 검증 완료 후 후속 기술부채(`AI-TECHDEBT-001`)로 분리 관리 | `ROADMAP.md:366`, `UNIMPLEMENTED_ROADMAP.md:23-29`, `Staging/20261104-user-ai-assistant/README.md:59-64` | **반영 완료**<br>(`S05` 참고) |

---

## 4. 정적 검사에서 확인된 추가 조치 필요 사항 상세 (`S01 ~ S05`)

### `S01` [P2 / Medium] `/api/ai/equipment/<eid>/files` 및 `/api/ai/csv/*` 엔드포인트의 `after_request_func` 본문 캡처 예외 누락
- **관련 기준**: `Q05` (감사 로그 보존), `F07` (첨부파일·CSV 경계), `D01` (감사 정책 보완 후속)
- **위치**:
  - `Staging/20261104-user-ai-assistant/overlay/app.py:1343-1406` (`after_request_func`)
  - `Staging/20261104-user-ai-assistant/overlay/utils/ai_assistant/__init__.py:300-318`
- **원인 분석**:
  - `app.py:1343-1345`의 `is_sensitive_database_operation` 판정식은 기존 장비 경로인 `/api/equipment/csv/`와 `/api/equipment/.../files`만 원문 캡처 대상에서 제외하고, lines 1380–1406의 별도 분기에서 파일명·크기·Content-Type 등 메타데이터만 `access_logs`에 기록하도록 작성되어 있습니다.
  - 그러나 신규 추가된 AI 비서 파일·CSV 경로(`/api/ai/equipment/<int:eid>/files`, `/api/ai/equipment/<int:eid>/files/<int:fid>/download`, `/api/ai/csv/preview`, `/api/ai/csv/export`)는 `/api/ai/`로 시작하므로 `is_sensitive_database_operation == True`가 됩니다.
- **영향**:
  1. **바이너리 멀티파트 요청이 뷰 함수 진입 전후에 소비되지 않고 거절될 때 감사 로그 누락**: `POST /api/ai/equipment/<eid>/files` 요청이 `request.files` 파싱 전에 `401`(세션 만료), `403`(CSRF 불일치), `413`(`MAX_CONTENT_LENGTH` 초과), `503`(점검 게이트) 등으로 반환될 때 업로드 파일이 PNG/JPEG/PDF/XLSX 등 바이너리이면, `app.py:1347`의 `request.get_data(as_text=True)`가 원시 멀티파트 바이트에 대해 UTF-8 디코딩을 시도하다 `UnicodeDecodeError`를 발생시키고 `except Exception:`(line 1409)으로 빠져 **`access_logs` 기록 자체가 유실**됩니다. 또한 대용량 텍스트/CSV 업로드가 `413`으로 거절된 경우에도 소비되지 않은 스트림 전체를 메모리에 읽어들입니다.
  2. **CSV 내보내기 응답 전체가 `access_logs`에 중복 저장됨**: `GET /api/ai/csv/export` 성공 시 `response.get_data(as_text=True)`(line 1363)가 최대 10,000행의 CSV 본문 전체를 `access_logs.ResponsePayload`에 기록합니다(기존 `/api/equipment/csv/export`는 메타데이터만 기록).
- **권장 조치**:
  - `app.py:1343-1345`의 제외 조건에 `not request.path.startswith('/api/ai/csv/')` 및 `not (request.path.startswith('/api/ai/equipment/') and '/files' in request.path)`를 추가하고, lines 1380–1406의 CSV/파일 메타데이터 전용 감사 분기 조건에도 동일하게 포함시킵니다.

---

### `S02` [P2 / Medium] 전역 점검 게이트(`maintenance_request_gate`)가 `/internal/ai/*` 워커 콜백을 HTTP 503으로 선차단하여 실행 중 작업이 `running` 상태로 고착될 수 있음
- **관련 기준**: `F10` (점검·복구 게이트 및 위임 무효화), `Q11` (무응답·중단 없는 실패 종결), `D02` (큐 해제 보완 후속)
- **위치**:
  - `Staging/20261104-user-ai-assistant/overlay/app.py:1266-1297` (`maintenance_request_gate`)
  - `Staging/20261104-user-ai-assistant/overlay/utils/ai_assistant/__init__.py:169-174` (`job_actor`), `385-524` (`claim`, `event`, `finish`)
  - `Staging/20261104-user-ai-assistant/overlay/tests/test_equipment_ai.py:57-115,424-434`
- **원인 분석**:
  - `utils/ai_assistant/__init__.py`의 `/internal/ai/jobs/claim`(line 390), `/internal/ai/jobs/<id>/event`(line 416), `/internal/ai/jobs/<id>/finish`(line 464)는 `job_actor(job)`에서 발생하는 `AssistantError(..., 503)`(점검 상태 전환 또는 `maint_rev` 변경)를 포착하여 `assistant.sqlite3`의 작업을 `cancelled`/`failed`로 깔끔하게 종결하고 예약 용량과 큐 잠금을 해제하도록 설계되었습니다.
  - 그러나 `app.py:1266-1297`의 전역 `@app.before_request` 훅인 `maintenance_request_gate()`는 `DRAINING`/`RESTORING`/`RECOVERY` 상태에서 `get_server_session_role() != 'Admin'`인 모든 요청을 HTTP 503으로 즉시 차단합니다. 내부 워커(`worker.py`)는 브라우저 세션 없이 `X-AI-Worker-Token` 헤더만 사용하므로 `get_server_session_role()`이 항상 `None`입니다.
  - 또한 `job_actor(job)`(`__init__.py:169-174`)는 `with connect() as db:`로 `equipment.db`를 먼저 연 뒤 `domain.actor()` 내부에서 점검 상태를 확인하므로, 만약 `/internal/ai/`를 단순 통과시키면 `RESTORING` 중에도 `equipment.db` 연결을 여는 문제가 생깁니다.
  - 참고로 단위 테스트 `test_maintenance_revision_invalidates_old_delegation`(`test_equipment_ai.py:424`)은 `app.py`에서 `after_request_func`만 추출하고 `maintenance_request_gate`는 추출하지 않았으며, `state['state'] = 'NORMAL'` 상태에서 `revision = 2`만 변경하여 테스트했기 때문에 이 경로가 노출되지 않았습니다.
- **영향**:
  - 작업 실행 도중 관리자가 점검/백업/복구 모드(`DRAINING`/`RESTORING`/`RECOVERY`)에 진입하면, 워커의 `/internal/ai/jobs/<id>/finish` 전송이 3회 재시도(`1s + 2s` 대기, `worker.py:216-226`) 모두 `maintenance_request_gate`의 503에 막혀 실패합니다. 그 결과 점검 모드가 `NORMAL`로 복귀한 뒤에도 해당 작업이 `assistant.sqlite3`에서 영구히 `state='running'`으로 남아 전역 단일 큐(`one_application_request`)가 잠기게 됩니다.
- **권장 조치**:
  1. `app.py:1272`의 `maintenance_request_gate()`에서 `request.path.startswith('/internal/ai/')`를 전역 세션 Role 차단에서 제외하여 내부 콜백 핸들러(`claim`, `event`, `finish`)가 자체 워커 토큰 인증 및 작업 종결 로직을 수행할 수 있게 합니다.
  2. `utils/ai_assistant/__init__.py:169-174`의 `job_actor(job)`에서 `with connect() as db:`로 `equipment.db`를 열기 **전에** `maintenance_state()`를 먼저 확인하여, `maintenance['state'] != 'NORMAL'`이거나 `maint_rev`가 변경된 경우 `equipment.db`를 열지 않고 즉시 `AssistantError('점검 또는 복구 작업 중에는 AI 비서를 사용할 수 없습니다.', 503, 'MAINTENANCE_ACTIVE')`를 발생시켜 `assistant.sqlite3`에서만 작업을 안전하게 취소·종결합니다.
  3. `tests/test_equipment_ai.py` 픽스처에 `maintenance_request_gate`도 함께 연결하여 점검 진행 중(`DRAINING`/`RESTORING`) 워커 `finish` 콜백이 도착하는 시나리오를 회귀 테스트에 포함합니다.

---

### `S03` [P2 / Medium] `/internal/ai/jobs/claim`에서 작업 상태를 `running`으로 전환한 직후 비-`AssistantError` 예외 발생 시 작업 고착 가능성
- **관련 기준**: `Q11` (실패 시 확정적 종결 및 큐 해제), `L03` (앱 전역 단일 요청 큐), `D02` (큐 해제 보완 후속)
- **위치**: `Staging/20261104-user-ai-assistant/overlay/utils/ai_assistant/__init__.py:384-398` (`claim`)
- **원인 분석**:
  - `claim()` 핸들러는 `job = store.claim()`으로 `assistant.sqlite3`의 작업 상태를 먼저 `running`으로 커밋한 후, `job_actor(job)` 호출 시 `except AssistantError as exc:`만 잡아 `store.finish(..., state='cancelled')`를 호출합니다.
  - 반면 `finish()` 핸들러(`__init__.py:517`)에는 예상치 못한 예외에 대비한 `except Exception:` 안전망이 구현되어 있으나, `claim()`(lines 389–397)에는 `except Exception:` 안전망이 없습니다.
- **영향**:
  - `store.claim()` 직후 `job_actor(job)`나 `domain.tools(actor)` 수행 중 일시적인 `sqlite3.OperationalError`(`equipment.db` 잠금 등)나 기타 런타임 예외가 발생하면, 워커는 `job['id']`와 `job['lease']`를 받지 못한 채 HTTP 500을 받게 되고(Strata 호출도 시작되지 않음), DB의 작업은 `state='running'`으로 남아 전역 큐가 잠깁니다.
- **권장 조치**:
  - `claim()`(`__init__.py:389-397`)에도 `finish()`와 동일하게 `except Exception:` 블록을 추가하여 `store.finish(job['id'], job['lease'], state='failed', error='작업 준비 중 내부 오류가 발생했습니다.', error_code='INTERNAL_ERROR')`를 호출한 뒤 응답하도록 보강합니다.

---

### `S04` [P3 / Low] 스트리밍 중 크기 초과 등으로 취소(`store.cancel`)될 때 후속 드레인 플러시가 최초 오류 메시지를 덮어쓸 수 있음
- **관련 기준**: `Q11` (명확한 실패 사유 표시), `Q12` (다단계 스트리밍 스냅샷), `D03` (스트리밍 오프셋 보완 후속)
- **위치**:
  - `Staging/20261104-user-ai-assistant/overlay/utils/ai_assistant/store.py:430-443` (`AssistantStore.cancel`)
  - `Staging/20261104-user-ai-assistant/overlay/utils/ai_assistant/__init__.py:421-427` (`event`)
  - `Staging/20261104-user-ai-assistant/overlay/utils/ai_assistant/worker.py:131-137,165-169`
- **원인 분석**:
  - `store.py:435`의 `cancel()` SQL문은 `error=COALESCE(?,error), error_code=COALESCE(?,error_code)`로 작성되어 있어, 새 인자 `?`가 `NULL`이 아니면 기존에 기록된 `error`와 `error_code`를 덮어씁니다(반면 `__init__.py:539`는 `COALESCE(error, ?)`로 기존 오류를 보존함).
  - `event()`(`__init__.py:421-427`)에서 `store.append()`가 `AssistantError`(예: 다단계 추론 누적 크기가 `MAX_REASONING` 초과)를 발생시키면 `store.cancel(jid, reason=exc.message, error_code='INVALID_RESPONSE')`를 호출한 뒤 워커에 `success=True, cancel=True`를 반환합니다.
  - 이때 `worker.py:135-136`은 `res.get('success')`가 참이므로 DB 롤백에도 불구하고 로컬 `reasoning_offset`을 증가시킵니다. 이후 `worker.py:168`에서 루프 종료 직후 호출되는 `flush(True)`가 남은 조각을 전송하면 오프셋 불일치(`응답 조각의 순서가 올바르지 않습니다.`)가 발생하며, 두 번째 `store.cancel()` 호출이 최초 원인 메시지(`AI 추론 요약이 허용 크기를 초과했습니다.`)를 덮어쓸 수 있습니다.
- **권장 조치**:
  - `store.py:435`의 `COALESCE(?,error), COALESCE(?,error_code)`를 `COALESCE(error,?), COALESCE(error_code,?)`로 수정하여 최초 취소 사유가 보존되도록 하고, `worker.py:135-136`에서 `res.get('cancel')`이 참일 때는 오프셋 갱신 또는 추가 `flush(True)`를 생략하도록 정리합니다.

---

### `S05` [P3 / Low] 주석·독스트링 메타데이터 동기화 백로그(`AI-TECHDEBT-001`) 및 병합 시 루트 기존 파일(`utils/lineup_node_service.py`) 주석 포맷 유의사항
- **관련 기준**: `Q15` (주석/문서화 규칙), `D07` (사용자 결정 7 — 기술부채 백로그 분리)
- **위치**:
  - `ROADMAP.md:366`, `UNIMPLEMENTED_ROADMAP.md:23-29` (`AI-TECHDEBT-001`)
  - `Staging/20261104-user-ai-assistant/overlay/` (추적 주석 24개 블록 및 신규·보완 함수 독스트링)
  - 루트 참고: `utils/lineup_node_service.py:14-28` (`[MINI-COMMENT:LINEUP.NODE.REQUIRED_INT]`)
- **원인 분석 및 검증 결과**:
  - 사용자 결정 7(`D07`)에 따라 AI 비서 기능의 한국어 감사 주석(`[KO rev=N]`) 동기화 및 세부 함수 독스트링(`[Role]`/`[Dependencies]`/`[Impact]`) 전수 보강은 기능 검증 완료 후 `AI-TECHDEBT-001` 백로그로 수행하도록 합의되어 있습니다.
  - Staging 오버레이만을 대상으로 `node .agent-governance/tooling/comment-sync.mjs check --root=Staging/20261104-user-ai-assistant/overlay --config=../../../.agent-governance/comment-sync/config.json --state=../../../.agent-governance/comment-sync/state.json`를 실행한 결과, 오버레이 내 24개 `[MINI-COMMENT:...]` 블록 모두 **형식 오류 0건(`0 FORMAT-ERROR`), 영문 필수 메타 누락 0건(`0 META-FIELD-MISSING`)**으로 작성되어 있으며, 정책대로 `TRANSLATION-PENDING` / `NEW-UNBASELINED` 인계 상태임을 확인했습니다.
  - **추가 참고 사항 (루트 기존 코드)**: 후보 코드 밖인 루트 워크스페이스의 `utils/lineup_node_service.py:14-28`(`LINEUP.NODE.REQUIRED_INT`)에서 `[EN rev=1]`은 독스트링(`"""`) 내부에, `[KO rev=1]`은 함수 본문 `#` 주석에 분리되어 있어 루트 전체에 대해 `comment-sync.mjs check`를 실행할 때 `FORMAT-ERROR: expected one ID, EN, optional KO in order` 예외가 발생합니다. 향후 `AI-TECHDEBT-001`을 통해 루트 병합본 전체에 `comment-sync.mjs baseline`을 수행할 때 해당 블록도 단일 주석 블록으로 함께 정리하는 것이 안전합니다.

---

## 5. 35개 기능·품질·한계 기준(`F01~F12`, `Q01~Q15`, `L01~L08`) 전수 대조표

### 5.1 기능 기준 (`F01 ~ F12`)

| ID | 기준 항목 | 정적 판정 | 근거 위치 및 검증 요약 |
| :---: | :--- | :---: | :--- |
| **F01** | 전용 화면·진입점 및 RBAC 세션 연동 | **PASS** | `utils/ai_assistant/__init__.py:187-197` (`/equipment/ai`), `templates/miniserver_frame.html`, `templates/root_frame.html` 네비게이션 연결 확인 |
| **F02** | 장비·카탈로그·라인업·파일·이력 조회 도구 | **PASS** | `utils/ai_assistant/domain.py:345-610` (`search_equipment`, `get_equipment_detail`, `list_equipment_files`, `get_equipment_history`, `search_catalog`, `get_lineup_tree` 등) 구현 확인 |
| **F03** | 대화 목록(최대 200개, 50개 페이지네이션) 및 메시지(60개 페이지네이션) 관리 | **PASS** | `utils/ai_assistant/store.py:126-152,309-338`, `static/js/equipment_ai.js:251-289` (`D04` 반영 확인) |
| **F04** | 쓰기 작업 제안(Proposal) 생성 및 사용자 명시적 승인(Confirmation) 구조 | **PASS** | `utils/ai_assistant/domain.py:137-238` (`prepare`), `240-342` (`confirm`), `policy.py:72-97` (`proposal_token` HMAC 검증) 확인 |
| **F05** | 장비 등록·수정·삭제 제안과 실제 반영 간 정규화 일관성 | **PASS** | `utils/ai_assistant/domain.py:164-166,194-216,301`에서 `shared_normalize_equipment_mutation_payload` 반환값(`payload`) 공통 사용 확인 (`D06`) |
| **F06** | 카탈로그 요청·승인·반려 및 라인업 노드 변경 제안·승인 연동 | **PASS** | `utils/ai_assistant/domain.py:173-193,267-335`에서 `catalog_request_service` 및 `lineup_node_service` 검증·실행 연동 확인 |
| **F07** | 첨부파일 업로드·다운로드·삭제 및 CSV 미리보기·내보내기 연동 | **PASS (조건부)** | `utils/ai_assistant/__init__.py:300-318`, `domain.py:555-610` 구현 완료. 단, `app.py:1343` 감사 로그 제외 분기 보완 필요 (`S01`) |
| **F08** | 다단계 도구 호출 루프(최대 4라운드) 및 단계별 추론 요약 보존 | **PASS** | `utils/ai_assistant/worker.py:150-198`, `store.py:37,372-424` (`message_steps`), `equipment_ai.js:126-151` 확인 (`D03`) |
| **F09** | 실시간 스트리밍(추론·답변 오프셋 병합) 및 추론 요약 자동/수동 접기 | **PASS** | `utils/ai_assistant/store.py:334,372-424` (`answer_started`), `static/js/equipment_ai.js:14-22,126-163,319-340` 확인 (`D03`) |
| **F10** | 시스템 점검/백업/복구 게이트 연동 및 구 위임 무효화 | **WARN** | `domain.py:30-60`에서 `maint_rev`·`session_rev` 검증은 구현되었으나, `app.py:1266`의 `maintenance_request_gate`가 `/internal/ai/*`를 503으로 선차단하는 엣지 케이스 보완 필요 (`S02`) |
| **F11** | 작업 취소(Cancel) 및 실행 중 상태 표시 | **PASS (조건부)** | `utils/ai_assistant/__init__.py:282-298`, `store.py:430-458`, `worker.py:165-169` 구현 확인 (`S04`의 `COALESCE` 순서 보완 권장) |
| **F12** | 저장소 용량 현황 표시(32MB 기본 + 32MB 확장) 및 대화 정리 | **PASS** | `utils/ai_assistant/store.py:168-228`, `static/js/equipment_ai.js:84-89` 확인 (`D05`) |

### 5.2 품질 기준 (`Q01 ~ Q15`)

| ID | 기준 항목 | 정적 판정 | 근거 위치 및 검증 요약 |
| :---: | :--- | :---: | :--- |
| **Q01** | 역할 기반 접근 제어(RBAC) 및 소유자 격리(Owner Isolation) | **PASS** | `store.py`의 모든 대화·메시지·제안 쿼리에 `owner=?` 조건 강제 및 `domain.py`의 역할별 권한 검사 확인 |
| **Q02** | 세션 버전(`session_rev`) 검증을 통한 권한 변경·로그아웃 즉시 반영 | **PASS** | `utils/ai_assistant/__init__.py:125-174`, `domain.py:30-60`에서 브라우저 및 워커 위임 시 `session_rev` 대조 확인 |
| **Q03** | 모든 상태 변경 요청의 CSRF 방어 및 승인 토큰 무결성 | **PASS** | `utils/ai_assistant/__init__.py:153-156` (`require_csrf`), `policy.py:72-97` (`proposal_token` HMAC) 확인 |
| **Q04** | 내부 워커 인증(`X-AI-Worker-Token`) 및 루프백 전용 통신 경계 | **PASS** | `utils/ai_assistant/__init__.py:176-184` (`hmac.compare_digest`), `policy.py:55-70` (`check_url` 루프백 검증) 확인 |
| **Q05** | `access_logs` 감사 추적성 보존 및 재사용 가능 자격증명 일방향 지문화 | **PASS (조건부)** | `utils/ai_assistant/audit.py` 및 `app.py:1365-1371`로 `D01` 완벽 반영. 단, `/api/ai/` 파일·CSV 경로 제외 조건 보완 필요 (`S01`) |
| **Q06** | 민감 환경변수·비밀키·세션 토큰의 모델 컨텍스트 및 UI 노출 차단 | **PASS** | `utils/ai_assistant/policy.py:111-132` (`redact`), `domain.py` 허용 필드 화이트리스트 확인 |
| **Q07** | 운영 `equipment.db`와 AI 전용 `assistant.sqlite3` 물리적 분리 및 트랜잭션 안전성 | **PASS** | `utils/ai_assistant/store.py:21-33` (`WAL`, `busy_timeout=5000`, `BEGIN IMMEDIATE`) 확인 |
| **Q08** | 제안 승인 시 대상 레코드 버전(`expected_updated_at` 등) 낙관적 잠금 검증 | **PASS** | `utils/ai_assistant/domain.py:203-238,295-320`에서 승인 시점 재검증 및 충돌 시 `409 CONFLICT` 반환 확인 |
| **Q09** | 폴링 요청의 유휴 세션 타이머 비연장(`X-Session-Touch: 0`) | **PASS** | `static/js/session_timer.js:135-156`, `static/js/equipment_ai.js:55-58`, `app.py:1244-1264` 확인 |
| **Q10** | 입력 크기·도구 인자·응답 크기 상한 검증 | **PASS** | `utils/ai_assistant/policy.py:13-33,134-184` (`MAX_PROMPT`, `MAX_CONTENT`, `MAX_REASONING`, `validate_tool_args`) 확인 |
| **Q11** | 원인이 확인된 실패의 확정적 종결(`failed`/`cancelled`)과 불확실 상태(`recovery_required`) 구분 | **WARN** | `finish()`(`__init__.py:429-524`)에서 `D02` 반영 완료. 단, 점검 게이트 503 차단(`S02`) 및 `claim()` 비-`AssistantError` 예외(`S03`) 보완 권장 |
| **Q12** | 스트리밍 델타 순서 보장(오프셋 검증) 및 다단계 추론 유실 방지 | **PASS** | `store.py:372-424` (`reasoning_offset`, `content_offset`, `message_steps`) 및 `equipment_ai.js:14-22` 확인 (`D03`, `S04` 참고) |
| **Q13** | 기존 장비관리 라우트·템플릿·정적 자산과의 비간섭성 | **PASS** | `app.py` 최소 변경 및 보존 대상 15개 루트 파일 SHA-256 100% 일치 확인 |
| **Q14** | 결정론적 오프라인 테스트 픽스처 및 회귀 테스트 구성 | **PASS** | `tests/test_equipment_ai.py` (13개 시나리오), `scripts/run_assistant_fixture.py`, `scripts/assistant_browser_fixture.py` 확인 |
| **Q15** | 코드 주석 및 문서화 거버넌스 준수 | **PASS (유예 포함)** | 오버레이 내 24개 `[MINI-COMMENT:...]` 블록 EN 메타/포맷 정상, KO 동기화 및 함수 독스트링은 `AI-TECHDEBT-001`로 백로그 관리 확인 (`D07`, `S05`) |

### 5.3 운영 한계 기준 (`L01 ~ L08`)

| ID | 기준 항목 | 정적 판정 | 근거 위치 및 검증 요약 |
| :---: | :--- | :---: | :--- |
| **L01** | 로컬 CPU 추론 서버(`127.0.0.1:8081`, Qwen3-4B Q4_K_M) 경계 준수 | **PASS** | `policy.py:11-12,55-70`, `deploy/systemd/equipment-ai-worker.service` 확인 |
| **L02** | 컨텍스트 예산(12,288 토큰) 및 프롬프트·이력·출력 예약(`426,144`자) 상한 | **PASS** | `policy.py:13-25` (`OUTPUT_RESERVATION = 426144`), `store.py:230-278` 확인 (`D05`) |
| **L03** | 애플리케이션 전역 단일 활성 추론 요청(`one_application_request`) 큐 제한 | **PASS** | `store.py:39,230-278` (`UNIQUE(singleton_lock) WHERE state IN ('queued','running')`) 확인 |
| **L04** | 사용자당 저장소 용량 예산(32MB 기본 + 32MB 기본 확장, 최대 64MB) | **PASS** | `policy.py:15-18`, `store.py:168-228` (`storage_meta` 원장) 확인 (`D05`) |
| **L05** | 대화당 도구 호출 라운드 상한(`TOOL_ROUND_LIMIT = 4`) 및 라운드당 호출 수 제한 | **PASS** | `policy.py:21-22`, `worker.py:150-198` 확인 |
| **L06** | 외부 인터넷/클라우드 API 호출 차단(폐쇄망·루프백 전용) | **PASS** | `policy.py:55-70` (`check_url`에서 `127.0.0.1`/`::1`/`localhost` 외 차단), 외부 CDN 미사용 확인 |
| **L07** | 쓰기 도구의 직접 실행 금지(반드시 사용자 승인 거침) | **PASS** | `worker.py:175-188` 및 `domain.py:137-238`에서 쓰기 도구는 제안(`pending`)만 생성하고 `/confirm`에서만 실행됨을 확인 |
| **L08** | Windows 개발 환경과 Linux(Ubuntu 24.04) 실서버 실행 경계 분리 | **PASS** | `Staging/20261104-user-ai-assistant/README.md` 및 `deploy/systemd/equipment-ai-worker.service` 확인 |

---

## 6. 조치 필요 사항 정리표 (Action Items Summary Table)

| 조치 ID | 우선순위 | 구분 | 대상 파일 및 라인 | 문제 요약 | 권장 조치 내용 | 권장 시점 |
| :---: | :---: | :--- | :--- | :--- | :--- | :--- |
| **S01** | **P2**<br>(Medium) | 감사 로그 / 파일·CSV 경계 (`Q05`, `F07`) | `Staging/20261104-user-ai-assistant/overlay/app.py:1343-1406` | `after_request_func`의 `is_sensitive_database_operation` 제외 조건에 `/api/ai/csv/` 및 `/api/ai/equipment/<eid>/files`가 누락되어, 바이너리 멀티파트 요청이 `request.files` 소비 전 거절(401/403/413/503)될 때 `request.get_data(as_text=True)`에서 `UnicodeDecodeError`가 발생하여 `access_logs` 기록이 누락되고, `/api/ai/csv/export` 응답의 전체 CSV 본문이 `access_logs`에 저장됨 | `app.py:1343-1345`의 제외 조건 및 `app.py:1380-1406`의 파일·CSV 메타데이터 전용 감사 분기에 `/api/ai/csv/`와 `/api/ai/equipment/.../files` 경로를 추가 | **루트 병합 전 보완 권장** |
| **S02** | **P2**<br>(Medium) | 점검 게이트 / 큐 종결 (`F10`, `Q11`) | `Staging/20261104-user-ai-assistant/overlay/app.py:1266-1297`,<br>`utils/ai_assistant/__init__.py:169-174` | 전역 `maintenance_request_gate()`가 브라우저 세션이 없는 `/internal/ai/*` 워커 요청을 HTTP 503으로 선차단하여, 작업 실행 중 점검 모드(`DRAINING`/`RESTORING`/`RECOVERY`) 진입 시 `/internal/ai/jobs/<id>/finish`가 실행되지 못하고 작업이 `running` 상태로 고착될 수 있음. 또한 `job_actor()`가 점검 상태 확인 전에 `equipment.db`를 먼저 엶 | 1) `maintenance_request_gate()`에서 `/internal/ai/` 경로를 예외 처리하여 내부 핸들러가 워커 토큰 검증 후 자체 종결 로직을 타게 수정<br>2) `job_actor()`에서 `connect()`(`equipment.db`) 호출 **전에** `maintenance_state()`를 먼저 확인하여 비정상 상태면 `equipment.db`를 열지 않고 즉시 503 `AssistantError`를 발생시켜 `assistant.sqlite3`에서 작업을 취소·종결 | **루트 병합 전 보완 권장** |
| **S03** | **P2**<br>(Medium) | 내부 클레임 예외 안전성 (`Q11`, `L03`) | `Staging/20261104-user-ai-assistant/overlay/utils/ai_assistant/__init__.py:384-398` | `/internal/ai/jobs/claim`에서 `store.claim()`으로 작업을 `running`으로 커밋한 직후 `job_actor(job)`나 `domain.tools(actor)`에서 `AssistantError` 외의 예외(예: 일시적 `sqlite3.OperationalError`)가 발생하면 `store.finish()`가 호출되지 않아 작업이 `running` 상태로 고착될 수 있음 | `claim()`의 `try` 블록(lines 389–397)에 `finish()`(line 517)와 동일한 `except Exception:` 안전망을 추가하여 `store.finish(..., state='failed', error_code='INTERNAL_ERROR')`로 큐 잠금과 예약 용량을 해제 | **루트 병합 전 보완 권장** |
| **S04** | **P3**<br>(Low) | 스트리밍 취소 사유 보존 (`Q11`, `Q12`) | `Staging/20261104-user-ai-assistant/overlay/utils/ai_assistant/store.py:435`,<br>`worker.py:131-137,168` | `store.cancel()`의 `error=COALESCE(?,error)`가 새 오류를 우선시하여, 스트리밍 중 크기 초과(`MAX_REASONING` 등)로 취소된 직후 워커 드레인 플러시(`flush(True)`)에서 발생한 오프셋 불일치 오류가 최초 취소 사유를 덮어쓸 수 있음 | `store.py:435`를 `COALESCE(error, ?), COALESCE(error_code, ?)`로 변경하여 최초 취소 사유를 보존하고, `worker.py`에서 `cancel=True` 수신 시 추가 플러시를 생략 | **루트 병합 전 또는 병합 시 함께 정리 권장** |
| **S05** | **P3**<br>(Low) | 주석·독스트링 기술부채 (`Q15`, `D07`) | `Staging/20261104-user-ai-assistant/overlay/*`,<br>`UNIMPLEMENTED_ROADMAP.md:23-29`,<br>`utils/lineup_node_service.py:14-28` | 오버레이 내 24개 `[MINI-COMMENT:...]` 블록의 한국어 감사본(`[KO rev=N]`) 및 세부 함수 독스트링이 `AI-TECHDEBT-001` 백로그로 유예되어 있으며, 루트 기존 파일인 `utils/lineup_node_service.py:14-28`의 `LINEUP.NODE.REQUIRED_INT` 블록이 독스트링과 `#` 주석으로 나뉘어 있어 전체 `comment-sync.mjs` 실행 시 `FORMAT-ERROR`를 유발함 | 사용자 결정 7(`D07`)에 따라 기능 최종 검증 후 `AI-TECHDEBT-001` 수행 시 오버레이 KO 감사·독스트링 보강과 함께 `utils/lineup_node_service.py:14-28`의 EN/KO 블록도 단일 주석 블록으로 통합 | **기능 최종 검증 완료 후 (`AI-TECHDEBT-001`)** |
