---
artifact_id: PLAN-20261124-001
work_id: FIX-20261124-AI-FOLLOWUP-WEB-SEARCH
owner: Gemini
status: completed
approval: user-approved-max-searches-5-merge-and-backup-deploy
---

# AI 도우미 다단계 웹 검색 도구 호출 호환·보정·검색 한도 확장 계획

## 1. 장애 현황 및 근본 원인

- **발생 작업:** 백업 서버(`192.168.0.24`, `eqmgmt-backup`) `nekohost`(`UserId=1`)의 대화(`d969a5caabe1710dea611a5cd5d4c470`) 내 작업 `f24fee369adc41b2b992fee39164acfd`(`2026-11-24 08:24:23~08:25:06 KST`)
- **모델 및 설정:** `260Strata` / `gemma-4-26b-a4b-qat-ud-q4_k_xl` (`context_tokens=65,536`, `reasoning_effort=high`, `web_search_mode=auto`, `web_search_allowed=True`)
- **경과:**
  1. Step 0(`planning=True`, 남은 검색 `2/2`)에서 모델이 `plan_web_search(needed=true, query=...)`를 호출해 Yahoo 1차 웹 검색(5건, `1,810`자)이 정상 완료되었고, 문맥 예산(`ctx_chars=18,619`) 문제도 재발하지 않았습니다.
  2. Step 1(`planning=False`, 남은 검색 `1/2`)로 전환되면서 `tools` 목록에서는 `plan_web_search`가 빠지고 `web_search`가 제공되었으나, 모델에 전달된 대화 이력(`messages[-2]`)의 직전 성공 도구명이 여전히 `plan_web_search`였고 `utils/ai_assistant/policy.py`의 `SYSTEM` 전역 문구 역시 모든 단계에 `plan_web_search`가 실제 검색을 실행한다고 안내하고 있었습니다.
  3. 모델이 2차 정밀 검색을 위해 `web_search` 대신 `plan_web_search`를 다시 호출하자 `utils/ai_assistant/__init__.py`의 `if not planning and name=='plan_web_search': raise AssistantError(...)` 검사에서 `INVALID_TOOL_CALL`로 즉시 실패하고(사용자 말풍선 오류 상자에 정상 표출), 답변을 완료하지 못했습니다.

## 2. Claude Opus 5.5 (`xhigh`) 독립 검토 및 반영 사항

Claude Code CLI(`--model opus --effort xhigh`, `canonicalModel: claude-opus-5-5`, 읽기 전용 감사)의 계획 검토에서 도출된 6가지 보완점을 모두 설계에 반영합니다.

1. **`policy.py` 전역 지시 분리:** `SYSTEM`에서 `plan_web_search` 전용 안내 문단을 `PLANNING_INSTRUCTIONS`로 분리해 `build_system_for()`의 `planning_flag=True` 단계에만 포함합니다(Step 1+ `worst_overhead` 약 495 UTF-8B 절감 효과 포함).
2. **`auto` 모드 검색 소진(`0/{MAX_SEARCHES}`) 완충:** Step 1+ 투영 후 모델이 `0/{MAX_SEARCHES}` 단계에서 `web_search` 또는 `plan_web_search(needed=true)`를 모방 재호출할 때 곧바로 `WEB_SEARCH_LIMIT`로 종료하지 않고, **프라이버시/taint(`check_public_query`) 검증을 통과한 경우**에 한해 `CORRECTIONS['search_decided']`로 1회 보정합니다(반복 시 `WEB_SEARCH_LIMIT`, `required` 모드는 기존 계약대로 즉시 `WEB_SEARCH_LIMIT`).
3. **Step 1+ `plan_web_search(needed=false)` 처리:** DB `jobs.context`에 저장하면 `search_permitted()`가 오염되므로 저장하지 않고, 도구를 유지한 신규 보정 단계 `CORRECTIONS['search_decided']`를 1회 제공합니다(장비 도구 포함 후속 처리 가능, `claim()` `worst_overhead`에 반영).
4. **인수 정규화 순서 및 배치 방어:** Raw JSON의 문자열 `"False"`가 Python truthy로 오인되지 않도록 모든 호출에 `normalized_tool_arguments()`를 먼저 적용하고, `not planning` & `search_mode(route)=='auto'` & `search_permitted` & `public_searches>=1` & 순수 검색 호출(`web_search` 또는 `plan_web_search(needed=True)`)일 때만 `needed`를 제거해 `web_search`로 재검증·정규화 저장합니다(혼합 배치·무단 검색·Step 0 `false` 후 `needed=true`는 기존대로 I/O 전 즉시 `INVALID_TOOL_CALL`; 중간 서비스 비가용 전환 시에도 `check_public_query`·1회 `search_decided` 후 반복 시 `WEB_SEARCH_UNAVAILABLE`).
5. **모델 투영(`project_search_messages`)의 비가변·위치 기반 정합성:** DB `jobs.context` 및 `recovery.model_context()`는 불변으로 두고 `claim()`이 모델 전송용 `messages`를 조립할 때만 비가변 복사 투영을 적용하며, 단계 간 `tool_call_id` 재사용 가능성을 고려해 `assistant.tool_calls` 바로 뒤 연속 `tool` 메시지 슬라이스로 위치 매칭한 뒤 `kind=='web_search'` 결과에 대응하는 `plan_web_search`만 `web_search`(`canonical()` 기반 `needed` 제거)로 투영합니다.
6. **`build_system_for()` 프롬프트 모순 제거:** `phase == 'answer'`일 때 활성 검색 도구 안내를 생략하고, 이미 1차 출처를 확보한 뒤 Step 1에서 검색 서비스가 비가용 전환된 경우 기존 출처 기반 답변을 지시하며 추가 검색 시도 시 `search_decided` 1회 보정(반복 시 `WEB_SEARCH_UNAVAILABLE`)을 적용합니다.

## 3. 사용자 추가 지시: 충분한 자료조사용 웹 검색 한도 확장 (`MAX_SEARCHES = 5`)

- **`utils/ai_assistant/web_search.py` (`[EN rev.7]`):** `MAX_SEARCHES = 5`, `SEARCH_RESERVATION = 32000 * MAX_SEARCHES` (`160000`).
- **`utils/ai_assistant/store.py` (`[EN rev.14]`):** `last_step`을 `MAX_SEARCHES + 3`(`8`, 최대 9단계 `0..8`)으로 연동해 5회 검색·장비 도구·보정·최종 답변까지 충분한 단계를 확보합니다.
- **`utils/ai_assistant/context.py` (`[EN rev.5]`):** `build_context()` `public_web_sources` 인계 상한을 `MAX_SEARCHES`(5건)로 동기화합니다.
- **`utils/ai_assistant/__init__.py` (`[EN rev.17]`):** `/api/ai/jobs/<jid>`의 `w` 커서 상한(`-1 <= search_version <= MAX_SEARCHES`) 및 `build_system_for()` 남은 검색 안내(`{rem_searches}/{MAX_SEARCHES}`)를 동기화합니다.
- **`utils/ai_assistant/policy.py` (`[EN rev.14]`) · `domain.py` (`[EN rev.10]`):** `SYSTEM` 및 `web_search_control` 안내 문구에서 `MAX_SEARCHES` 값을 동적으로 반영합니다.
- **`tests/test_ai_web_search.py` (`[EN rev.9]`) · `tests/test_ai_followup_web_search.py` (`[EN rev.2]`):** 5회 한도 및 9단계(`0..8`) `STEP_LIMIT`, `SEARCH_RESERVATION = 160000`, `?w=5` 커서, 5건 다단계 후속 검색 시나리오를 검증합니다.

## 4. Staging 및 루트 병합 · 백업 배포 범위

대상 Staging 폴더: `Staging/20261124-ai-search-followup/` (병합·검증 후 삭제)
1. `utils/ai_assistant/web_search.py`
2. `utils/ai_assistant/policy.py`
3. `utils/ai_assistant/recovery.py`
4. `utils/ai_assistant/domain.py`
5. `utils/ai_assistant/store.py`
6. `utils/ai_assistant/context.py`
7. `utils/ai_assistant/__init__.py`
8. `tests/test_ai_web_search.py`
9. `tests/test_ai_followup_web_search.py`
10. `tests/run_assistant_fixture.py`

## 5. 검증 및 배포 완료 기준

- Staging · 병합 루트 각각 Windows 정적 보안·구문 검사(`test_security_static_review.py`, `-B`): 14/14 통과
- Staging · 병합 루트 각각 백업 서버(`eqmgmt-backup`) Linux `tmpfs` 격리 백엔드 스위트(`run_assistant_fixture.py --host eqmgmt-backup --tmpfs-fixtures --summary-only`): 356/356 전수 통과 (`production_app_imported: false`, `production_database_opened: false`)
- Staging (`/dev/shm` 임시 오버레이) `test_provider_ca.py` + `test_mail_translation.py`: 51/51 통과
- 병합 루트 Linux 실제 Chromium 브라우저 UI 스위트(`--browser-target web-search`, `--browser-target recovery`): 전수 통과
- `governance-tool.mjs validate` 통과(`errors: 0`), 본 작업 대상 13개 파일만 scoped commit/push (`origin/main`)
- 백업 서버(`eqmgmt-backup`, `nkhst-pentium`) `tools/deploy_ai_ux_release.py` (`pause` -> `git pull --ff-only` -> `check-copy` -> `activate`) 무중단 반영 및 라이브 검증 통과
