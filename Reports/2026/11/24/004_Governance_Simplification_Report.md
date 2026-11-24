# 거버넌스 경량화 전환 보고서 (v2.0 단일 진입점 체제)

- **작업 일자:** 2026-11-24
- **기준 커밋:** `0a7505ed94e3d14b0145102bc4e351275ce99e31`
- **전환 방향:** 구 `.agent-governance/` 트리·노드 라우터·고정 `Staging/` 복제·자동 대화 기록기·이중언어 주석 동기화를 폐기하고, 단일 규약 문서(`AGENTS.md`) + 코드 기반 자동 검증·배포 도구 체제로 전환

## 1. 변경 범위

- **단일 정본 및 포인터 진입점 재작성 (4개):**
  - `AGENTS.md`: 프로젝트 토폴로지, 절대 안전 불변식, 코드 기반 검증·배포 도구, 경량 기록 원칙을 62줄 단일 정본으로 통합 (테스트 러너 4종의 루트 마커 유지).
  - `GEMINI.md`, `CLAUDE.md`, `CHATGPT.md`: 각 7줄 포인터로 단순화해 `AGENTS.md`만 참조하도록 통일.
- **유용 도구 이관 및 의존성 정리 (3개):**
  - `.agent-governance/tooling/git-readonly.mjs` → `tools/git-readonly.mjs` 이관.
  - `tools/validate-corrective-actions.mjs`(비추적 상태 유지): `.agent-governance/tooling/package.json`의 `yaml` 패키지 의존성을 제거하고 무의존 자체 파서로 분리.
  - `.vscode/tasks.json`: 폴더 열기 시 미존재 기록기를 호출하던 태스크 제거(`"tasks": []`).
- **레거시 거버넌스 제거 (Git 추적 109개 + 로컬 `node_modules`/`.state`):**
  - `.agent-governance/` 전체, `Rule.md`, `VALIDATION_METHODOLOGY.md`, `tests/test_recipient_tracking.mjs`, Git 추적 구 `Staging/` 9개 파일 제거.
- **보존 대상 (무변경):**
  - 미추적 `Staging/` 50개 폴더(`Staging/20261124-ai-stream-autoscroll/` 포함), 기존 `Plans/`·`Tasks/`·`Reports/`·`Chat/` 이력, 기존 미커밋 작업본(WebMCP, `app.py`, `.gitignore` 등) 전부 무변경 유지.

## 2. 무손실 아카이브 및 롤백 방법

- **로컬 아카이브:** `Backups/2026-11-24_legacy_governance_archive.zip` (비추적, 119개 파일, `466,362`B, CRC 검증 통과, SHA-256 `10fc667049f15d12e7e4400a11455317f667a03669d778c42feef48d2bfed4d2`) — 제거 전 미커밋 구 거버넌스 12개 파일 포함 보존.
- **롤백 절차:** Git 전환 커밋을 `git revert`하거나 위 ZIP 아카이브를 프로젝트 루트에 복원하면 구 거버넌스 상태(미커밋 수정본 포함)로 복귀 가능.

## 3. 제거 후 검증 결과

| 검증 항목 | 환경 | 결과 | 근거 |
| --- | --- | --- | --- |
| 정적 보안·구문 검사 (`tests.test_security_static_review`) | Windows `-B` | **통과 (14 / 14)** | `4.806s`, Python 126 / JS 18 / Jinja 28 / inline JS 19 |
| AI 도우미 전체 백엔드 스위트 (`run_assistant_fixture.py --tmpfs-fixtures`) | `eqmgmt-backup` Linux `tmpfs` | **통과 (356 / 356)** | `79.752s`, `production_app_imported: false`, `production_database_opened: false` (`fixture_digest=adb178756928045653176e6b587dc0d22b8ffa3dee15c26d2fdb1078bde63d0f`) |
| 배포 가드 단위 테스트 (`tests.test_ai_release_guard`) | Windows `-B` | **통과 (10 / 10)** | `0.210s` |
| 순수 Node UI 테스트 (`test_mail_translation_ui.js`, `test_ai_error_visibility_ui.js`) | Windows Node | **통과 (13 / 13)** | `88.1ms` |
| 이관·무의존 도구 (`tools/git-readonly.mjs`, `tools/validate-corrective-actions.mjs`) | Windows Node | **통과** | `node --check` 통과, `git-readonly` 정상, `validate-corrective-actions --self-test` 5/5 통과 및 일반 검사 `registered: 9, errors: 0` |
| `General` 교차 범위 탐색 (`owner-discovery.mjs inspect`) | Windows Node | **통과** | `decision: "no-governed-owner"` (반쪽 마커 오류 없음) |
