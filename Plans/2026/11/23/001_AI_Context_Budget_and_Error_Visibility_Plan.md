---
artifact_id: PLAN-20261123-001
work_id: FIX-20261123-AI-CONTEXT-ERROR-VISIBILITY
owner: Gemini
status: approved-staging
approval: user-approved-staging-1-2-3-and-plan-4
---

# AI 도우미 문맥 한도·다단계 재압축 및 중단 사유 화면 표출 계획

## 1. 배경 및 규명된 원인

- **대상 계정 및 세션:** `nekohost` (`UserId=1`) / 대화 `d969a5caabe1710dea611a5cd5d4c470` (`260Strata / gemma-4-26b-a4b-qat-ud-q4_k_xl`, `context_tokens=65,536`, `web_search_mode=auto`, `USER_AI_WRITE_TOOLS=true`)
- **재현된 장애 2건:** `job=f737b3a9e80744beb3caf6d4c1147ea0` (`2026-11-23 15:37:06~15:37:33 KST`) 및 `job=ad40fb98e8e847cd84aba95a6889c478` (`15:50:29~15:50:52 KST`)
- **직접 원인:**
  1. **Step 0 vs Step 1+ 도구 오버헤드 불일치:** `web_search_mode=auto`의 Step 0에서는 `plan_web_search` 1개(`1,261B`, `overhead=10,002B`)만으로 `build_context()` 예산(`47,342B`)을 산정해 누적 대화 40건(`42,054B`/`41,816B`)을 채웠으나, Step 1 진입 시 14개 전체 도구(`9,588B`, `overhead=18,329B`)로 전환되면서 고정 오버헤드가 `+8,327B` 급증했습니다.
  2. **도구 결과 증가분 미예약 및 Step 1+ 재압축 부재:** Step 0의 `plan_web_search` 호출+Yahoo 검색 결과(`+2,855B`/`+2,920B`)가 `jobs.context`에 추가된 상태에서 `step >= 1`이 과거 이력을 재압축하지 않아 `claim()` Line 991 검사(`70,919B` / `70,746B > 65,536`)에서 HTTP 413으로 중단되었습니다.
  3. **오류 코드/화면 표출 결함 (항목 3):**
     - 413 문맥 한도 오류가 `PROCESSING_FAILED`로 저장되고, 일반 채팅 말풍선(`.ai-message`) 내부에는 실패 사유·오류 코드가 전혀 렌더링되지 않습니다(`mailStatus`는 메일 번역 전용).
     - 실패 사유가 하단 `#ai-progress` 1곳(11px 회색 안내문)에만 의존하여 후속 질의 시 즉시 덮어쓰여 사라지고, 휴지통/읽기 전용 화면에서는 아예 숨겨지며, `error_code`가 사용자 화면에 전혀 표출되지 않았습니다.
     - 큐 대기(`queued`) 상태 취소 시 `store.cancel()`이 `error=None, error_code=None`을 남겨 사유가 `NULL`이 되며, `CONNECTION_TIMEOUT`/`CONNECTION_FAILED`는 복구 완료 후에도 `equipment_ai.js`가 종료 안내 문구를 제거하지 못하는 버그가 있었습니다.

## 2. 작업 범위 및 병렬 작업 분배

### 구현 대상 (항목 1·2·3 — Staging 격리 개발)
- **항목 1 (Step 0 최악 오버헤드 & 멀티스텝 여유분 예약):**
  - Step 0 `build_context()` 예산 산정 시 `plan_web_search` 단독 기준이 아니라 후속 단계의 최대 도구 집합(`planning=False` 전체 도구 + `DRAFT_TOOL` + `TASK_DRAFT_TOOL`) 및 `CORRECTIONS`를 반영한 최악 고정 오버헤드(`worst_overhead`)를 차감합니다.
  - 도구 지원 모델의 일반 대화(`purpose=='chat'`)에서는 `build_context(..., history_headroom=...)`로 과거 이력 적재에만 멀티스텝 여유분(`search_allowed` 시 `12,288B`, 미사용 시 `8,192B`)을 적용하되, 현재 질문(`current`) 수용 검사와 `32,768` 토큰 후보 기능 시험(`test_provider_ca.py`)은 깨지지 않도록 `current`와 `candidate_generation` probe에서는 `history_headroom=0`을 유지합니다.
  - `effective_budget = min(byte_budget, MAX_PERSISTED_CONTEXT - 2048)`로 `120,000`자 영속 상한을 Step 0에서 자가 초과하지 않게 방어합니다.
- **항목 2 (Step 1+ 안전 과거 이력 재압축):**
  - `context.py`에 `compact_persisted_context()` 및 `compact_step_context()`를 추가해 `[handoff?, *history, current_user_msg, *current_turn_tail]` 경계를 구조적으로 식별(뒤에서부터 `tool`/보정 `system`/`tool_calls`를 역추적하여 동일 문구의 과거 메시지와 혼동 방지, 불변식 불일치 시 fail-closed)합니다.
  - `step >= 1`에서 한도(`route['context_tokens']` 또는 `120,000`자) 초과 시, **인계 헤더·현재 턴 질문·현재 턴 도구 호출/결과(`public_searches`, 장비 비공개 조회 오염 검사 대상)·보정 마커(`CORRECTIONS`)는 절대 보존**한 채 오래된 과거 `history`부터 제거합니다.
  - `handoff` 축소는 모델 전송용 투영 복사본에만 적용하고 DB의 `jobs.handoff_chars`와 `evidence_chars`, `storage_accounts.used_chars` 원장은 변경하지 않습니다.
- **항목 3 (비민감 중단 사유·오류 코드 화면 표출 및 안전 진단 로그):**
  - **백엔드:** `policy.py`의 `ERROR_REASONS`에 `CONTEXT_LIMIT` 추가(기존 `BeforeSendError(..., 'PROVIDER_CONTEXT')` 우선순위 유지), `claim()`/`finish()`의 413/120,000자 오류를 `CONTEXT_LIMIT`로 분류하고 원문·비밀 없는 수치 메타 로그(`job`, `step`, `purpose`, `code`, `status`, `context_tokens`, `payload_bytes`) 기록. `store.cancel()`에서 `queued` 취소 시 `USER_CANCELLED`와 기본 사유를 저장하도록 보완.
  - **프론트엔드:** `equipment_ai.js`에 순수 함수 `formatJobFailure(job)`(기존 `mailStatus(job)` 계약 100% 보존)와 `jobErrorNotice(messageId, job)`를 추가해 실패/취소/종료확인 대기 중인 일반 채팅 어시스턴트 말풍선(`.ai-message`) 내부에 비민감 중단 사유와 정제된 `오류 코드: ...`를 `textContent`로 안전 렌더링합니다(후속 질문 전송, 새로고침, 과거 메시지 불러오기, 휴지통/읽기 전용에서도 보존). `#ai-progress`에서도 오류 코드 표시 및 `CONNECTION_TIMEOUT`/`CONNECTION_FAILED` 복구 문구 정리를 보완하고, `equipment_ai.css`에 라이트/다크/모바일 대응 스타일을 추가합니다.
- **항목 4 (별도 계획서만 작성 — 이번 구현 제외):**
  - 실제 모델 토큰 비율 보정 및 `context_tokens` 상향은 [002_AI_Context_Token_Calibration_Plan.md](002_AI_Context_Token_Calibration_Plan.md)로 계획만 분리 작성하며 코드에는 반영하지 않습니다.

### 병렬 작업 분배
파일 소유권이 완전히 분리된 두 영역을 병렬 하위 작업자(`staging-coder`)에게 위임하고, 통합 검증과 Validation 1~8은 코디네이터가 수행합니다.
- **하위 작업자 A (백엔드 문맥·오류 코드):** `Staging/20261123-ai-context-error/utils/ai_assistant/{policy.py,context.py,__init__.py,store.py}`, `Staging/20261123-ai-context-error/tests/{test_ai_context_budget_and_compaction.py,run_assistant_fixture.py}`
- **하위 작업자 B (프론트엔드 오류 표출):** `Staging/20261123-ai-context-error/static/{js/equipment_ai.js,css/equipment_ai.css}`, `Staging/20261123-ai-context-error/tests/{test_ai_error_visibility_ui.js,test_ai_recovery_ui.js}`

## 3. 검증 계획 (Linux 격리 검증 + Validation 1~8)
1. Windows에서 구문 정적 검사(`py_compile`, `node --check`)만 수행하고 앱/테스트는 실행하지 않습니다.
2. `eqmgmt-backup` Linux 격리 환경에서 `Staging/20261123-ai-context-error/tests/run_assistant_fixture.py --tmpfs-fixtures`로 기존 백엔드 회귀 + 신규 문맥 예산/재압축 단위·통합 테스트 + `test_provider_ca.py` + `test_mail_translation.py` + `test_security_static_review.py`를 검증합니다.
3. `eqmgmt-backup`에서 Node `node --test`(신규 `test_ai_error_visibility_ui.js` + `test_mail_translation_ui.js`) 및 실제 Chromium 브라우저 UI 테스트(`recovery`, `status-banner`, `ui` 320/390/1440px 라이트·다크)를 실행합니다.
4. 산출물 SHA-256과 Validation 1~8 결과를 [001_AI_Context_Budget_and_Error_Visibility_Report.md](../../../Reports/2026/11/23/001_AI_Context_Budget_and_Error_Visibility_Report.md)에 기록한 뒤 사용자에게 운영 루트 병합 승인을 요청합니다.
