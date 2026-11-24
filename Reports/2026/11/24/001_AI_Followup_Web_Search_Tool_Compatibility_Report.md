---
artifact_id: REPORT-20261124-001
work_id: FIX-20261124-AI-FOLLOWUP-WEB-SEARCH
owner: Gemini
status: root-merged-and-verified
approval: user-approved-max-searches-5-merge-and-backup-deploy
---

# AI 도우미 다단계 웹 검색 도구 호출 호환·보정·검색 한도 확장 검증 보고서

## 1. 장애 원인 및 해결 요약

- **장애 대상:** 백업 서버(`eqmgmt-backup`) `nekohost`(`UserId=1`) 대화(`d969a5caabe1710dea611a5cd5d4c470`) 내 작업 `f24fee369adc41b2b992fee39164acfd`(`2026-11-24 08:24:23~08:25:06 KST`), 모델 `260Strata` / `gemma-4-26b-a4b-qat-ud-q4_k_xl`(`context_tokens=65,536`, `level=high`, `reasoning_effort=high`, `web_search_mode=auto`, `web_search_allowed=True`).
- **근본 원인:**
  1. Step 0(`planning=True`, 남은 검색 `2/2`)에서 `plan_web_search(needed=true)`로 1차 Yahoo 웹 검색(5건, `1,810`자, `ctx_chars=18,619`)이 정상 완료되었습니다(이전 문맥 한도·오류 UI 표출은 정상 동작).
  2. Step 1(`planning=False`, 남은 검색 `1/2`) 전환 시 `tools`에서는 `web_search`만 제공되었으나, 모델에 전달된 대화 이력의 직전 호출명(`plan_web_search`)과 `utils/ai_assistant/policy.py` `SYSTEM`의 `plan_web_search` 전역 안내가 Step 1에도 남아 있어 모델이 후속 검색으로 `plan_web_search`를 다시 호출했고 `INVALID_TOOL_CALL`로 즉시 실패(`steps=2`)했습니다.
- **최종 병합 구현 범위 (다단계 검색 호환·보정 + `MAX_SEARCHES = 5` 한도 확장):**
  1. `utils/ai_assistant/web_search.py` (`[EN rev.7]`): `MAX_SEARCHES = 5`, `SEARCH_RESERVATION = 32000 * MAX_SEARCHES` (`160000`) 확장.
  2. `utils/ai_assistant/store.py` (`[EN rev.14]`): `last_step = MAX_SEARCHES + 3` (`8`, 최대 9단계 `0..8`) 연동으로 5회 검색·장비 도구·보정·최종 답변 단계 확보.
  3. `utils/ai_assistant/context.py` (`[EN rev.5]`): `build_context()` `public_web_sources` 인계 상한을 `MAX_SEARCHES`(5건)로 동기화.
  4. `utils/ai_assistant/policy.py` (`[EN rev.14]`): `plan_web_search` 전용 지시를 `SYSTEM`에서 `PLANNING_INSTRUCTIONS`로 분리하여 `planning_flag=True` 단계에만 포함하고 `MAX_SEARCHES` 값을 동적으로 반영.
  5. `utils/ai_assistant/recovery.py` (`[EN rev.4]`): 검색 판단·한도·가용성 확정 후 도구를 유지한 채 1회만 보정하는 `CORRECTIONS['search_decided']` 추가.
  6. `utils/ai_assistant/domain.py` (`[EN rev.10]`): `Domain.check_public_query(job, store, query, provider='auto', scope=None)` 추가(배우/세션/taint/민감정보/프로바이더·범위 선검증) 및 `web_search_control` 안내에 `MAX_SEARCHES` 동적 반영.
  7. `utils/ai_assistant/__init__.py` (`[EN rev.17]`): 비가변 위치 기반 `project_search_messages()` 투영, `build_system_for()` `phase == 'answer'` 및 중간 비가용 프롬프트 정합성·`{rem_searches}/{MAX_SEARCHES}` 반영, `claim()` `worst_overhead`에 `search_decided` 반영, `/api/ai/jobs/<jid>` `?w` 커서 상한(`-1 <= search_version <= MAX_SEARCHES`) 동기화, `finish()` `normalized_tool_arguments()` 선적용·Step 1+ `plan_web_search(needed=True)`의 `web_search` 안전 정규화·`plan_web_search(needed=False)`/`0/{MAX_SEARCHES}`/중간 장애/중복 쿼리 1회 `search_decided` 보정 적용.
  8. `tests/test_ai_web_search.py` (`[EN rev.9]`), `tests/test_ai_followup_web_search.py` (`[EN rev.2]`), `tests/run_assistant_fixture.py`: 5회 한도·9단계 `STEP_LIMIT`·`SEARCH_RESERVATION = 160000`·`?w=5`·다단계 후속 검색 17개 시나리오 검증 및 픽스처 러너 등록.

## 2. Claude Opus 5.5 (`xhigh`) 독립 검토 반영

`claude -p --model opus --effort xhigh` 읽기 전용 감사(`thinkingTokens: 41,766`)에서 도출한 6가지 보완 사항(`SYSTEM` 전역 지시 분리, `auto` `0/{MAX_SEARCHES}` 1회 보정, `plan(false)` 미저장 `search_decided` + `worst_overhead` 반영, `"False"` 문자열 선행 정규화 및 혼합 배치 차단, 위치 기반 비가변 `project_search_messages`, `phase=='answer'`·중간 장애 프롬프트 정합성)을 모두 코드와 테스트에 반영했습니다.

## 3. Staging 병합·정리 및 병합 루트 검증 결과

`Staging/20261124-ai-search-followup/`에서 1차 구현 및 `MAX_SEARCHES = 5` 확장 검증(검색 집중 `81/81`, 전체 백엔드 `356/356`, CA+메일 `51/51`)을 통과한 뒤 운영 루트 10개 파일에 병합하고 LF 정규화 SHA-256 일치 확인 후 해당 Staging 폴더를 삭제했습니다(기존 미커밋 작업본 및 다른 `Staging/*` 폴더 무변경).

아래 표는 **운영 루트 병합 완료 이후** 격리 환경(Windows `-B` · `eqmgmt-backup` Linux `tmpfs` / `/dev/shm` / Chromium CDP)에서 실 LLM 호출·운영 DB 접근 없이 수행한 최종 검증 결과입니다.

| 검증 항목 | 실행 환경 | 결과 | 상세 근거 |
| --- | --- | --- | --- |
| 정적 보안·구문 검사 (`tests.test_security_static_review`) | Windows `.venv\Scripts\python.exe -B` (병합 루트) | **통과 (14 / 14)** | 실패 0, 오류 0, `4.952s`. Python 126개 컴파일, JS 18개 `node --check`, Jinja 28개, 인라인 JS 19블록 통과 |
| 전체 백엔드 스위트 (`run_assistant_fixture.py --tmpfs-fixtures --summary-only`) | `eqmgmt-backup` Linux `tmpfs` | **통과 (356 / 356)** | 실패 0, 오류 0, skip 0, `79.805s`, `production_app_imported: false`, `production_database_opened: false` (`fixture_digest=84e367a0baacd46440a0e0d15dc11b036ee37ebc4cbda39f458f27fc368c72af`) |
| 프로바이더 격리 스위트 (`--provider-only --tmpfs-fixtures --summary-only`) | `eqmgmt-backup` Linux `tmpfs` | **통과 (284 / 284)** | 실패 0, 오류 0, skip 0, `64.010s`, `production_app_imported: false`, `production_database_opened: false` (`fixture_digest=a8f629bcca403c21f1586e442820d9f0623c2442b057115385d0bf82aa88067b`) |
| 웹 검색 집중 스위트 (`test_ai_web_search` + `test_ai_followup_web_search`) | `eqmgmt-backup` Linux `tmpfs` (`--focus`) | **통과 (81 / 81)** | 실패 0, 오류 0, skip 0, `23.398s`, `production_app_imported: false`, `production_database_opened: false` (`fixture_digest=18f1800227d16a95f31a597881831a3a708807e99ef4cf1b39e19343fa4b5f4d`) |
| Provider CA + 메일 번역 회귀 (`test_provider_ca`, `test_mail_translation`) | `eqmgmt-backup` `/dev/shm` 격리 실행 | **통과 (51 / 51)** | 실패 0, 오류 0, skip 0, `18.209s`. 실행 후 `/dev/shm/eq-ca-mail-*` 잔여 0건 확인(`SHM_LEFTOVERS: []`) |
| 실제 Chromium `web-search` UI (`--browser-only --browser-target web-search`) | `eqmgmt-backup` Linux Chromium CDP | **통과 (8 / 8)** | `320/390/820/1440px × light/dark` 각 20체크 전수 통과(`fixture_digest=8a719e525941c0936388af671b932230b1a18ec9bcd1c3eecfd96ced1c15c258`) |
| 실제 Chromium `recovery` UI (`--browser-only --browser-target recovery`) | `eqmgmt-backup` Linux Chromium CDP | **통과 (12 / 12)** | `320/390/1440px × light/dark × current/cached-before-recovery` 각 32체크 전수 통과, 잔여 아티팩트 0건(`fixture_digest=d36729554ba18bb935c7da5ed3e72074b9b1199ef7221eb6c19c73b88f7a6462`) |
| 거버넌스 검증 (`node .agent-governance/tooling/governance-tool.mjs validate`) | Windows 프로젝트 루트 | **통과 (`pass`)** | `errors: 0`, `warnings: 1`(기존 `CORRECTIVE_ACTIONS.md` WebMCP stale 경고, 본 작업 무관) |

## 4. 병합 루트 산출물 목록 및 LF 정규화 SHA-256

| 파일 (프로젝트 상대 경로) | LF 바이트 | LF SHA-256 |
| --- | ---: | --- |
| `utils/ai_assistant/web_search.py` | 23,936 | `bdae1c56158fc147d067d903e2e7b1d59ebdba312ee1ae46ddee645c038be20c` |
| `utils/ai_assistant/policy.py` | 27,622 | `cef2e31f77b0bd3d07bced421837dc9ae62c8fb42a28372b66017e82380594f9` |
| `utils/ai_assistant/recovery.py` | 6,409 | `0188346170ff04c654461b95e3ae8f81ffdd1e3a0084a7ac1b664bfd84a9d1aa` |
| `utils/ai_assistant/domain.py` | 33,233 | `297fae8b531edc5866e92c58a6f46dd64c8fcd7914dd97177584ae69dfa73ead` |
| `utils/ai_assistant/context.py` | 19,980 | `9618a48a5a2bf73af550d79648febbb91ee9fa0e7dc46ceb5128bdefa7e179ed` |
| `utils/ai_assistant/store.py` | 59,769 | `e396a0dffb9befc4f4435aff0a6aa4785df080e59c8f2a04c471334217ff015e` |
| `utils/ai_assistant/__init__.py` | 108,240 | `aa8d7df63e2fd1f7204c766f3faadad961e0de3a73374a1ef391e46f3934a829` |
| `tests/test_ai_web_search.py` | 68,631 | `9baf4cbdcb8f7c622158c957270c701d644ebe9144e20c0751b8261d95c1c1d9` |
| `tests/test_ai_followup_web_search.py` | 45,405 | `f88875f53bf5f3e39fe7e48353c2a10078e7bf0850183b1f69bee9cfb54f1b9d` |
| `tests/run_assistant_fixture.py` | 20,660 | `bc64ecc242fa25f1b1e951e8de8dada5a31481d511c54e3dae3cd9af5420529a` |

## 5. Git 반영 및 백업 서버 배포 예정

- 본 작업 대상 13개 파일(위 10개 + `Plan`/`Task`/`Report` 3개)만 scoped commit/push 후 백업 서버(`eqmgmt-backup`, `nkhst-pentium`)에 `tools/deploy_ai_ux_release.py`로 무중단 반영 및 라이브 검증을 진행합니다.
