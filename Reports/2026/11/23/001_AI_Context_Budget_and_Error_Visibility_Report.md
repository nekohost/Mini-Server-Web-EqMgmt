---
artifact_id: REPORT-20261123-001
work_id: FIX-20261123-AI-CONTEXT-ERROR-VISIBILITY
owner: Gemini
status: deployed-to-backup-verified
approval: user-approved-merged-and-deployed-to-backup
---

# AI 도우미 문맥 한도·다단계 재압축 및 중단 사유 화면 표출 검증 보고서

## 1. 요약 및 현재 경계

- **대상 문제:** `nekohost`(`UserId=1`)의 대화(`d969a5caabe1710dea611a5cd5d4c470`)에서 `gemma-4-26b-a4b-qat-ud-q4_k_xl`(`context_tokens=65,536`, `web_search_mode=auto`, `USER_AI_WRITE_TOOLS=true`)로 질의한 최근 2건(`f737b3a9e80744beb3caf6d4c1147ea0`, `ad40fb98e8e847cd84aba95a6889c478`)이 Step 0 Yahoo 웹 검색 완료 직후 Step 1(14개 도구 전환 + 검색 결과 2.9KB 추가) pre-dispatch 한도 검사(`70,919B` / `70,746B > 65,536`)에서 `413`으로 중단되었으며, 일반 채팅 UI 말풍선 내 실패 사유·오류 코드가 보이지 않던 결함을 Staging에서 수정·검증했습니다.
- **완료 범위 (Staging 격리 구현 및 Linux 검증 완료):**
  - **항목 1:** Step 0에서 후속 단계 최대 도구/보정 오버헤드를 선반영하고, 도구 모델 일반 대화의 과거 이력에만 멀티스텝 여유분(`search_allowed` 시 `12,288B`, 미사용 시 `8,192B`)을 비워 두되 `current` 질문 수용 검사·`32,768` 토큰 후보 프로브(`history_headroom=0`) 및 `120,000`자 영속 상한을 지킵니다.
  - **항목 2:** `step >= 1`에서 한도 초과 시 `_split_turn_context()`로 `[handoff?, *history, current_user_msg, *current_turn_tail]` 경계를 구조 식별(불변식 위반 시 fail-closed)하고, 인계 데이터·현재 턴 질문·도구 결과(`public_searches`·비공개 장비 taint)·`CORRECTIONS` 마커 및 `jobs.handoff_chars`/`evidence_chars`/`used_chars` 원장은 불변으로 보존한 채 가장 오래된 `history`부터 축약합니다(이력이 비었는데도 초과하면 모델 투영용 인계 복사본만 축소).
  - **항목 3:**
    - **백엔드:** `ERROR_REASONS['CONTEXT_LIMIT']` 신설, `claim()`/`finish()` 413·120,000자 오류 분류(`BeforeSendError` `PROVIDER_CONTEXT` 우선순위 유지), 원문·비밀 없는 수치 메타 로그 기록, `store.cancel()`에서 `queued` 즉시 취소 시 `USER_CANCELLED` 및 사유 기본 채움 보완.
    - **프론트엔드:** `mailStatus()`를 그대로 유지한 채 순수 함수 `formatJobFailure(job)`와 `jobErrorNotice(messageId, job)`를 추가해 일반 채팅 어시스턴트 말풍선(`.ai-message`) 내부에 비민감 중단 사유와 정제된 `오류 코드: ...`를 `textContent`로 렌더링(후속 턴 전송, 새로고침, 과거 메시지 불러오기, 휴지통 읽기 전용 화면에서도 보존). `#ai-progress`에서도 오류 코드 표시 및 `CONNECTION_TIMEOUT`/`CONNECTION_FAILED` 복구 안내 처리를 보완하고 `equipment_ai.css`에 라이트/다크·모바일 스타일을 추가했습니다.
  - **항목 4 (구현 제외 — 계획만 작성):** [Plan 002 (항목 4 보류 계획)](../../../Plans/2026/11/23/002_AI_Context_Token_Calibration_Plan.md)에 선행 실측·토크나이저 벤치마크·롤백 조건을 별도 문서화했고 코드에는 반영하지 않았습니다.
- **배포 및 보류 범위:** 운영 루트 병합·재검증, Staging 정리, Git commit/push(`20802ffddd7ba58f0a97e0ecbe0d9f94ded621a1`), 백업 서버(`nkhst-pentium`, `192.168.0.24`) `deploy_ai_ux_release.py` 배포 및 라이브 검증까지 완료했습니다. 기존 미커밋 작업본·다른 `Staging/*` 폴더는 건드리지 않았으며, 항목 4([Plan 002](../../../Plans/2026/11/23/002_AI_Context_Token_Calibration_Plan.md))는 계획만 유지하고 구현하지 않았습니다.

## 2. 병렬 작업 분배 및 협업 기록

| 역할 | 담당 파일 (모두 `Staging/20261123-ai-context-error/` 내부) | 주요 구현 내용 |
| --- | --- | --- |
| **하위 작업자 A (백엔드)** | `utils/ai_assistant/policy.py`, `context.py`, `__init__.py`, `store.py`, `tests/test_ai_context_budget_and_compaction.py`, `tests/run_assistant_fixture.py` | Step 0 최악 오버헤드·여유분 예약, `compact_persisted_context`·`compact_step_context`, `CONTEXT_LIMIT`·안전 메타 로그, queued 취소 사유, 9개 백엔드·단위 테스트 작성 및 `py_compile` 검증 |
| **하위 작업자 B (프론트엔드)** | `static/js/equipment_ai.js`, `static/css/equipment_ai.css`, `tests/test_ai_error_visibility_ui.js`, `tests/test_ai_recovery_ui.js` | `formatJobFailure`·`jobErrorNotice`·`progress` 오류 코드 표출·CSS 반응형 스타일·Node 단위 테스트(7개)·Chromium 복구/다중 턴/휴지통 UI 검증 추가 및 `node --check` 검증 |
| **코디네이터 (통합·검증)** | `Plans/2026/11/23/{001,002}_*.md`, `Tasks/2026/11/23/001_*.md`, `Staging/.../tests/assistant_ui_browser_fixture.py`, `Reports/2026/11/23/001_*.md` | diff·불변식 교차 검토, `assistant_ui_browser_fixture.py` 선행 `/logout` 라우트 누락 보완, Linux 격리 백엔드·CA·메일·정적보안·Node·실제 Chromium UI 실행, Validation 1~8 완료 |

## 3. 정적·Linux 격리 검증 결과

| 검증 항목 | 실행 환경 | 결과 | 상세 근거 |
| --- | --- | --- | --- |
| 전체 백엔드 + 신규 문맥 예산/재압축 테스트 (`run_assistant_fixture.py --tmpfs-fixtures`) | `eqmgmt-backup` Linux tmpfs (격리 DB) | **통과 (339 / 339)** | 실패 0, 오류 0, skip 0, `112.624s`(Staging) / `71.128s`(병합 루트, `fixture_digest=cf917716eae8234973d9eb2b24d8d97052afc110e383c55b8f8cdee6ff5049b8`), `production_app_imported: false`, `production_database_opened: false`. 신규 [test_ai_context_budget_and_compaction.py](../../../tests/test_ai_context_budget_and_compaction.py) 9건(`nekohost` 65K+42KB+Yahoo 재현, 32K 프로브/대화, 4K `PROVIDER_CONTEXT`, 16K chat-only 답변 보정 예약, Step 1+ 축약 및 중복 질문/원장/taint/보정 마커 보존, 복구 불가 `CONTEXT_LIMIT`·비노출 로그, `finish()` 120K자 축약, queued 취소) 모두 통과 |
| Provider CA + 메일 번역 회귀 (`test_provider_ca.py`, `test_mail_translation.py`) | `eqmgmt-backup` Linux tmpfs (Staging 메모리 오버레이) | **통과 (51 / 51)** | 실패 0, 오류 0, skip 0, `17.731s`. `PROVIDER_CONTEXT` 4K 경계, 32K 컷오버 프로브, 메일 번역 프롬프트·서명·오류 경로 무손상 확인 |
| 정적 보안·구문 검사 (`test_security_static_review.py`, Staging 오버레이 및 병합 루트) | Windows 정적 AST + `node --check` | **통과 (14 / 14)** | 실패 0, 오류 0, `4.689s`(Staging) / `4.701s`(병합 루트). Python 125개 컴파일, JS 18개 `node --check`, Jinja 템플릿 28개 및 인라인 JS 19블록 구문 검사 통과 |
| 순수 Node JS 단위 테스트 (`test_mail_translation_ui.js` + `test_ai_error_visibility_ui.js`) | Windows Node v24 (`node --test`, Flask/DOM 미사용) | **통과 (13 / 13)** | 실패 0, `91.75ms`(Staging) / `86.045ms`(병합 루트). `mailStatus()` 비메일 빈 문자열 계약 및 `formatJobFailure()` 오류 코드 정제·XSS 방어·복구 안내 검증 |
| 실제 Chromium UI (`--browser-target recovery`) | `eqmgmt-backup` Linux Chromium CDP | **통과 (12 / 12 뷰, 384 체크)** | Staging 및 병합 루트(`fixture_digest=e0310d3355496303cd9933863af0c455051bf6bdc79b5c0a8a9490c65d0d9c35`) 모두 320/390/1440px × 라이트/다크 × `current`/`cached-before-recovery` 전수 통과. `.ai-job-error` 메시지 내 오류 사유·`오류 코드: STREAM_INCOMPLETE`/`CONTEXT_LIMIT` 표시 및 후속 완료 턴·휴지통 읽기 전용 보존 확인 |
| 실제 Chromium UI (`--browser-target ui --browser-width 320/390/1440`) | `eqmgmt-backup` Linux Chromium CDP | **통과 (6 / 6 뷰, 980 체크)** | Staging 및 병합 루트(`fixture_digest=dafe0be8993725c15da985ab6c15ff2451ccff3a6959e70d8160eede6d1d6276`) 모두 320/390/1440px × 라이트/다크 전수 통과(`320/390: 163*2`, `1440: 164*2`). 기존 레이아웃·스크롤·테이블·휴지통·오류 배너 회귀 없음 |
| 실제 Chromium UI (`--browser-target status-banner`) | `eqmgmt-backup` Linux Chromium CDP | **선행 불일치 관찰 (0 / 8)** | 실패 지점: `test_ai_status_banner_ui.js:61` (`$('ai-form').previousElementSibling === banner`). 이번 변경 전 커밋 `ba6ec69`가 `templates/equipment_ai.html:53`에 `#ai-first-uncertain`을 `#ai-connection-status`와 `#ai-form` 사이에 추가하면서 이미 발생한 선행 테스트 불일치이며 이번 Staging 변경과 무관함. 또한 Chromium 픽스처 전반이 `1a34211`의 `miniserver_frame.html` `url_for('logout')` 대비 `assistant_ui_browser_fixture.py` `/logout` 부재로 500 타임아웃되던 문제를 Staging 픽스처에 `/logout`을 보완해 해소함 |
| 거버넌스 및 루트 보호 (`governance-tool validate`, `git-readonly status`) | Windows 프로젝트 루트 | **통과 (`pass`)** | `errors: 0`, `warnings: 1`(기존 `CORRECTIVE_ACTIONS.md` WebMCP 항목 `stale` 경고). 운영 루트 파일 수정 0건 |

## 4. Validation 1~8 순차 검증

1. **1단계 — 거버넌스 준수성:**
   - *긍정/근거:* `conversation-recorder ensure` 선행 통과 후 [Plan 001](../../../Plans/2026/11/23/001_AI_Context_Budget_and_Error_Visibility_Plan.md), [Plan 002](../../../Plans/2026/11/23/002_AI_Context_Token_Calibration_Plan.md), [Task 001](../../../Tasks/2026/11/23/001_AI_Context_Budget_and_Error_Visibility_Task.md)을 먼저 작성했고 모든 구현·테스트 변경을 `Staging/20261123-ai-context-error/`에만 격리했습니다. Windows에서 앱/Flask를 실행하지 않았고 외부 라이브러리를 추가하지 않았습니다.
   - *위험/미비:* `context.py`·`policy.py`·`equipment_ai.js`에 신규/보완 함수가 추가되었으나 기존 `[MINI-COMMENT: ...]`의 `[EN rev.N]`/`[KO rev.N]` 계약과 충돌하는 변경은 병합 단계에서 주석 동기화 여부를 최종 확인해야 합니다.
   - *차단 조건:* 없음.
2. **2단계 — 사용자 의도 달성도:**
   - *긍정/근거:* 항목 1·2(65K 도구 모델 + 42KB 이력 + 자동 웹 검색 Step 1 통과 및 대량 도구 결과 시 과거 이력 안전 재압축)와 항목 3(실패/취소/복구대기 비민감 사유 및 정제된 오류 코드를 일반 채팅 말풍선과 진행 표시줄에 상시 노출, 후속 턴·새로고침·휴지통에서도 보존)을 모두 구현·검증했습니다. 항목 4는 사용자 지시대로 계획 문서(`Plan 002`)만 작성하고 구현하지 않았습니다.
   - *위험/미비:* 기존 운영 DB의 이미 실패한 2건(`f737b3a9`, `ad40fb98`)은 `error_code='PROCESSING_FAILED'`로 기록된 과거 이력이므로 그대로 보존되며, 코드 병합 후에는 말풍선 UI에 당시 `error`와 `PROCESSING_FAILED`가 표시됩니다(과거 실패 원문은 재작성하지 않음).
   - *차단 조건:* 없음.
3. **3단계 — 논리적 구동 가능성:**
   - *긍정/근거:* `_split_turn_context()`가 뒤에서부터 현재 턴의 `tool`/`tool_calls`/보정 `system`을 역추적해 과거 이력과 현재 질문 문구가 동일하더라도 오분할하지 않으며, 비정상 구조에서는 fail-closed로 축약을 건너뜁니다. Step 0과 Step 1+ 오버헤드 계산을 공유 헬퍼(`build_tools_for`, `build_system_for`)로 통일해 단계 간 크기 불일치를 제거했습니다.
   - *위험/미비:* 단일 턴의 `tool` 결과 자체가 모델 `context_tokens - output_tokens - step1_overhead`를 초과하는 극단 케이스는 과거 이력을 모두 비워도 모델에 들어가지 않으므로 설계대로 `CONTEXT_LIMIT`로 안전 중단됩니다.
   - *차단 조건:* 없음.
4. **4단계 — 운영 병합 영향:**
   - *긍정/근거:* DB 스키마 변경, API 엔드포인트 경로 변경, `mailStatus()` 계약 변경, `PROVIDER_CONTEXT` 우선순위 변경 없이 기존 339+51=390개 백엔드/CA/메일 테스트와 980개 메인 UI 체크를 모두 통과했습니다. `test_provider_ca.py` 51개 중 포함 확인된 `32,768` 도구 프로브도 정상 통과합니다.
   - *위험/미비:* [assistant_ui_browser_fixture.py](../../../tests/assistant_ui_browser_fixture.py)의 `/logout` 보완은 선행 커밋 `1a34211`과의 호환 결함을 해결하는 테스트 픽스처 수정이며, `test_ai_status_banner_ui.js:61`의 `#ai-first-uncertain` 선행 불일치는 본 작업 범위 밖으로 별도 정리 대상입니다.
   - *차단 조건:* 없음(병합 루트에도 `tests/run_assistant_fixture.py`, `tests/assistant_ui_browser_fixture.py`, `tests/test_ai_recovery_ui.js`를 함께 반영 완료).
5. **5단계 — 보안과 예외 엣지 케이스:**
   - *긍정/근거:* 백엔드 `ERROR_REASONS['CONTEXT_LIMIT']`가 `admin_logs._PRIVATE_TEXT` 필터에 걸리지 않음을 검증했고, 사전 차단 로그에는 수치/열거형 메타데이터만 남기며 프롬프트·추론·API 키·`str(error)`를 기록하지 않음을 단위 테스트로 확인했습니다. 프론트엔드는 `error_code`를 `/^[A-Z0-9_]{2,64}$/`로 정제하고 `textContent`만 사용해 XSS(`innerHTML` 미사용)를 차단합니다. `public_searches`와 비공개 장비 `get_equipment` taint 검사 결과는 압축 대상에서 완전 제외했습니다.
   - *위험/미비:* 없음(정적 보안 검사 14/14 통과).
   - *차단 조건:* 없음.
6. **6단계 — 롤백과 역방향 파급:**
   - *긍정/근거:* DB 스키마·마이그레이션·설정(`.env`) 변경이 전혀 없으며 `jobs.handoff_chars`·`evidence_chars`·`storage_accounts.used_chars` 원장 계산 불변식을 유지하므로, 운영 병합 후 문제가 발견되더라도 이전 commit의 Python/정적 자산 파일만 되돌리면 즉시 롤백 가능하고 기존 대화/감사 DB 호환성이 깨지지 않습니다.
   - *위험/미비:* 신규 저장된 `error_code='CONTEXT_LIMIT'` 행을 구 코드에서 관리자 로그 조회할 경우 `admin_logs.py`가 `ERROR_REASONS` 미등록 코드를 `None`으로 표시할 뿐 예외를 일으키지 않으나, 병합 전 백업 서버 사본 백업 및 `idle` 상태 확인이 필요합니다.
   - *차단 조건:* 없음.
7. **7단계 — 휴먼 에러와 UX 방어:**
   - *긍정/근거:* 일반 채팅에서 응답이 비고 중단된 경우에도 말풍선 내부 `.ai-job-error`에 명확한 한국어 사유와 `오류 코드: ...` 배지가 남아 사용자가 원인을 복사·보고할 수 있으며, 후속 질의나 휴지통 이동 후에도 사라지지 않습니다. `320px/390px/1440px` 라이트/다크 및 구 템플릿 캐시 모드 모두 가로 넘침(`scrollWidth <= innerWidth + 1`)이나 `#ai-scroll < 119px`·버튼 줄바꿈 깨짐이 없음을 Chromium으로 확인했습니다.
   - *위험/미비:* 물리적 스마트폰 터치 스크롤이나 실제 `260Strata` 실모델 종단 호출은 격리 합성 시험에서 대신하지 않았으며 운영 반영 후 실제 `nekohost` 세션 또는 새 테스트 대화에서 최종 확인하는 것이 안전합니다.
   - *차단 조건:* 없음.
8. **8단계 — AI 메타 거버넌스:**
   - *긍정/근거:* 임시 파일이나 `__pycache__` 잔여물 없이 Staging 산출물만 유지했고, 모든 수치와 통과/실패(`status-banner` 선행 불일치 포함)를 관측된 도구 출력 그대로 사실만 기록했으며, 승인을 재촉하지 않고 객관적 판단을 제시했습니다.
   - *위험/미비:* 본 Antigravity 세션의 워크스페이스 루트가 `c:\project`여서 `Mini-Server-Web-EqMgmt/Chat/` 자동 수집 대상과 다르므로 세션 범위를 투명하게 보고합니다.
   - *차단 조건:* 없음.

## 5. Staging 후보 파일 및 SHA-256 목록

| Staging 상대 경로 | 크기 (Bytes) | SHA-256 |
| --- | ---: | --- |
| `Staging/20261123-ai-context-error/utils/ai_assistant/policy.py` | 27,331 | `14e87e65277261575f6443c37ce604b9f432b77e7e8bfd0e1741ddc1d5adf8f5` |
| `Staging/20261123-ai-context-error/utils/ai_assistant/context.py` | 19,955 | `9ab6066b64aae5e9b25e1916939a817c7b0aa5a4df6c39c5c40d363af931a5d9` |
| `Staging/20261123-ai-context-error/utils/ai_assistant/__init__.py` | 101,435 | `f2e85e8037da0aa078c726c5856a50eb1625d293827936307ab7434af0d9648f` |
| `Staging/20261123-ai-context-error/utils/ai_assistant/store.py` | 59,740 | `ef4737d70bf887014c11b5b7b13f5f5c397535704eec32f188f98335bc9deaea` |
| `Staging/20261123-ai-context-error/static/js/equipment_ai.js` | 166,757 | `0f2678414bff5e027d88637520b846a6ede66ca87020ad3805c995961bae206d` |
| `Staging/20261123-ai-context-error/static/css/equipment_ai.css` | 33,785 | `f58ac43bab06f5ab2fb89a41340c36b85ea40cab1e642da9a9b49b3db1c383fe` |
| `Staging/20261123-ai-context-error/tests/test_ai_context_budget_and_compaction.py` | 37,246 | `a0b71275845bf84cb273a9df216cfd52499707b70c5b26eca320cb845c9331cd` |
| `Staging/20261123-ai-context-error/tests/test_ai_error_visibility_ui.js` | 9,000 | `66a51766a1b618b103bab9cc31b33db22e958f104a53877b8add41542e32ca32` |
| `Staging/20261123-ai-context-error/tests/test_ai_recovery_ui.js` | 18,972 | `fae51f72362fc84195967d9c0593dd1fb15b45e3bf581f202c0b71687789c9d2` |
| `Staging/20261123-ai-context-error/tests/assistant_ui_browser_fixture.py` | 8,567 | `5fb0e3963a8ac67a2940b81d9b5519971cd0e7d63495c15ee6829905f756b256` |
| `Staging/20261123-ai-context-error/tests/run_assistant_fixture.py` | 20,627 | `3c2cd37114ca8b05838ceb43a40baaea877ad1526f99360ed3ca41f6e7a972c3` |

## 6. 운영 루트 병합·재검증 및 Staging 정리 기록

- **루트 병합 및 동일성 검증:** 사용자 승인(`"네, 백업 서버까지 반영을 진행하십시오."`) 후 위 11개 Staging 후보 파일을 운영 루트에 병합했고, LF 정규화 기준 `SHA-256` 11/11 전수 일치 및 `git diff --no-index --ignore-cr-at-eol` 0건을 확인했습니다.
- **병합 루트 재검증 (모두 통과):**
  - `tests.test_security_static_review`: `14 / 14` 통과 (`4.701s`, Python 125 / JS 18 / Jinja 28 / inline JS 19).
  - `node --test tests/test_mail_translation_ui.js tests/test_ai_error_visibility_ui.js`: `13 / 13` 통과 (`86.045ms`).
  - `governance-tool validate`: `pass` (`errors: 0`, `warnings: 1` 기존 `CORRECTIVE_ACTIONS.md` WebMCP 항목).
  - `tests/run_assistant_fixture.py --host eqmgmt-backup --tmpfs-fixtures --summary-only`: `339 / 339` 통과 (`71.128s`, `production_app_imported: false`, `production_database_opened: false`).
  - `tests/run_assistant_fixture.py --host eqmgmt-backup --browser-only --browser-target recovery --summary-only`: `12 / 12` 뷰(`384` 체크) 통과.
  - `tests/run_assistant_fixture.py --host eqmgmt-backup --browser-only --browser-target ui --browser-width 320 --browser-width 390 --browser-width 1440 --summary-only`: `6 / 6` 뷰(`980` 체크) 통과.
- **Staging 정리:** `Plans/2026/11/23/{001,002}_*.md` 보존 확인 후 본 작업 폴더 `Staging/20261123-ai-context-error/`만 삭제했습니다(기존 다른 `Staging/*` 폴더 및 선행 미커밋 작업본 무변경).
- **문서 후속 안내:** 기존 작업본에 이미 수정되어 있던 `docs/ai-assistant.md` 및 `FEATURES.md`는 이번 범위에서 건드리지 않았습니다.

## 7. Git 반영·백업 서버 배포 및 라이브 검증 결과

- **Git 반영 (코드 릴리스):** `fix(ai): 문맥 예산 선반영·다단계 재압축 및 오류 사유 화면 표출 반영` (`20802ffddd7ba58f0a97e0ecbe0d9f94ded621a1`, 정확히 15개 파일) 커밋 및 `origin/main` push 완료.
- **백업 서버(`nkhst-pentium`, `192.168.0.24`) 단계별 배포 (`tools/deploy_ai_ux_release.py`):**
  - 릴리스 디렉터리: `/home/nekohost/services/Mini-Server-Web-EqMgmt/instance/releases/20261105-ai-ux-context-error-20261123T0759Z` (권한 `0700`)
  - **`pause`:** 사전 `HEAD=9331707d7bdfedfaf4182837baef79fb85035476`, `active_jobs={}` 확인 후 기존 웹(`PID 2787990`)과 워커(`PID 1653197`) 정지 및 일치 스냅샷(`equipment-quiesced.sqlite3`, `assistant-quiesced.sqlite3`) 확보 (`{"status": "quiesced", "old_pid": 2787990, "active_jobs": 0}`).
  - **Fast-forward pull 및 해시 일치 확인:** `git pull --ff-only origin main` 후 서버 `HEAD == 20802ffddd7ba58f0a97e0ecbe0d9f94ded621a1` 확인, 반영된 런타임 6개 파일(`policy.py`, `context.py`, `__init__.py`, `store.py`, `equipment_ai.js`, `equipment_ai.css`)의 Linux `sha256sum`이 위 Staging 검증 해시와 6/6 바이트 단위 일치함을 확인.
  - **`check-copy`:** 실 DB 사본(`copy-c24e7bf4233e`) 기동 시험 통과(`"status": "pass"`, 업무 테이블 18개·AI 테이블 21개·수명주기 행 11개·감사 행 보존, `ai_version=4`, `/login=200`, `/assistant=302`, `/api/ai/capabilities=401`, `/internal/ai/claim=403`, `real_model_called=false`, `production_databases_modified=false`).
  - **`activate`:** `{"status": "active", "app_pid": 2970581, "worker": "active", "ai_version": 4, "old_business_rows_preserved": true, "old_ai_rows_preserved": true, "secrets_preserved": true, "retention_timer_enabled": true}` (`2026-11-23T08:00:05.387911+00:00`).
- **백업 서버 라이브 비파괴 검증 (`2026-11-23 17:00 KST`):**
  - 유지보수 상태: `NORMAL` (`revision: 64`).
  - 프로세스/유닛: 웹 `app.py` (`PID 2970581`), `equipment-ai-worker.service` `active` (`MainPID 2970591`, 워커 `/internal/ai/claim` HTTP 200 정상 폴링), `equipment-ai-retention.timer` `active`. 워커 journal 및 `app-start.log`에 예외·Traceback 0건.
  - 로컬 HTTP 엔드포인트 및 정적 자산 해시(`http://127.0.0.1:5000`): `/login -> 200`, `/assistant -> 302`, `/api/ai/capabilities -> 401`, `/static/js/equipment_ai.js -> 200` (`0f2678414bff5e027d88637520b846a6ede66ca87020ad3805c995961bae206d`), `/static/css/equipment_ai.css -> 200` (`f58ac43bab06f5ab2fb89a41340c36b85ea40cab1e642da9a9b49b3db1c383fe`).
  - 읽기 전용 모듈·DB 검증(`?mode=ro`): `ERROR_REASONS['CONTEXT_LIMIT']` 및 `compact_step_context` 로드 정상, `equipment.db`·`assistant.sqlite3` 모두 `PRAGMA integrity_check == ok`, `conversations=30`, `messages=150`, `jobs=75`, 대상 대화 `d969a5caabe1710dea611a5cd5d4c470` 및 기존 실패 작업(`f737b3a9...`, `ad40fb98...`) 무손상 보존 확인.
- **Validation 1~8 최종 사후 확인:** 거버넌스(`validate` `errors: 0`), 의도 달성(항목 1~3 반영·항목 4 보류), 논리 정합성, 백업 서버 무중단·무비밀 이식 및 DB 무결성, 롤백 가능성, UX 가독성, 실측 기반 보고 기준 모두 충족.
