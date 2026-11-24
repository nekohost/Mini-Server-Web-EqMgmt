# Mini-Server-Web-EqMgmt 작업 지침

이 문서는 `Mini-Server-Web-EqMgmt` 저장소의 **단일 활성 작업 규약**이다. 모든 AI 에이전트(Codex, Gemini/Antigravity, Claude, ChatGPT/Remote MCP)는 이 문서를 기준으로 작업한다.

> 구 `.agent-governance/` 트리·라우터·`Rule.md`·`VALIDATION_METHODOLOGY.md`·고정 `Staging/` 복제·이중언어 주석 동기화·자동 대화 기록기 preflight는 2026-11-24부로 폐기되었다. 원문은 Git 이력과 `Backups/2026-11-24_legacy_governance_archive.zip`에 보존된다.

---

## 1. 프로젝트 개요 및 운영 토폴로지

- **성격:** 개인 보유 장비·자산을 등록·관리하고 내장 AI 도우미를 제공하는 Python Flask + SQLite 웹 애플리케이션(`app.py`, `utils/`, `templates/`, `static/`, `tests/`).
- **Windows 개발 PC (`C:\project\Mini-Server-Web-EqMgmt`):** 소스 편집, 정적 분석, Linux 격리 테스트 호출, Git Commit/Push 용도.
- **Linux 서버:**
  - **백업/검증 서버 (`eqmgmt-backup` / `nkhst-pentium`, `192.168.0.24`, 포트 `5000`):** SSH 격리 테스트 및 현재 주요 배포 대상(`/home/nekohost/services/Mini-Server-Web-EqMgmt`).
  - **미니서버 (`192.168.0.166`, 포트 `5000`):** 사용자가 명시적으로 지시한 경우에만 반영한다.
- 내부 서버 주소와 운영 환경 정보는 외부 공개 문서나 로그에 불필요하게 노출하지 않는다.

---

## 2. 절대 안전 불변식 (Hard Guardrails)

1. **모드 구분과 승인 범위:** 질문·조사·검토·계획 요청을 승인 없는 구현이나 배포로 확대하지 않는다. 질문에는 답변부터 하고, 객관적 근거를 제시하며 승인을 재촉하지 않는다. 파괴적 조치(파일·DB 삭제, 덮어쓰기, 백업 복원, 프로세스 강제 종료, 서버 배포)는 대상과 복구 절차를 확인한 뒤 명시적 승인을 받아 실행한다.
2. **기존 자산·미커밋 작업본 보존:** 기존 DB 데이터, `.env`·비밀 파일, 다른 에이전트 세션이 작업 중인 미커밋·미추적 파일(`Staging/*` 등)을 임의로 삭제하거나 덮어쓰지 않는다. **`git add .` / `git add -A`를 금지**하며, 커밋 전 `git diff --cached --name-only`로 이번 작업 대상 파일만 포함되었는지 확인하는 Scoped Commit을 지킨다.
3. **실행·수정 환경 분리:**
   - **Windows에서 Flask 앱을 직접 구동하거나 로컬 동작 테스트를 수행하지 않는다.** (정적 구문·AST 검사 및 `eqmgmt-backup` SSH 격리 러너 호출은 허용)
   - **Linux 서버에서 운영 소스를 즉석 수정하지 않는다.** 모든 코드 반영은 `Windows 수정 → 격리 검증 → Scoped Commit/Push → Linux git pull --ff-only → 배포` 순서를 따른다.
4. **DB 무결성 및 스키마 진화:** 스키마 변경을 이유로 기존 테이블을 `DROP`하거나 초기화하지 않는다. `sqlite3.Row` 호환과 `ALTER TABLE` 전진 마이그레이션을 우선하며, 컬럼·데이터 계약 변경 시 `app.py`·`db_migration.py`·`utils/`·`templates/`·`static/js/` 연관 체인을 한 단위로 점검하고 백업·복구 경로를 확인한다.
5. **보안 및 프론트엔드 기본선:** 인터넷 공개를 전제로 한다. 비밀번호·`SECRET_KEY`·API 토큰·인증서 개인키를 소스·Git·문서·로그에 평문 기록하지 않는다. `debug=True` 하드코딩 금지, 서버 세션 기준 권한 검증, CSRF·XSS·SQLi·내부 오류 원문 비노출 원칙을 지킨다. 프론트엔드는 Vanilla JS + 경량 Tailwind CSS(반응형 `grid-cols-1` / `sm:grid-cols-2` / `lg:grid-cols-3 xl:grid-cols-4`)를 우선한다.

---

## 3. 표준 검증 및 배포 도구 (코드 기반 강제)

반복 안전 검증은 프롬프트 체크리스트 대신 프로젝트의 실제 스크립트로 수행한다.

- **Windows 정적 보안·구문 검사 (앱·DB 미접근):**
  ```powershell
  .venv\Scripts\python.exe -B -m unittest tests.test_security_static_review
  ```
- **AI 도우미 Linux 격리 테스트 (`eqmgmt-backup` `tmpfs` / Chromium, 운영 DB·실모델 미접근):**
  ```powershell
  .venv\Scripts\python.exe -B tests\run_assistant_fixture.py --host eqmgmt-backup --tmpfs-fixtures --summary-only
  .venv\Scripts\python.exe -B tests\run_assistant_fixture.py --host eqmgmt-backup --browser-only --browser-target <target> --summary-only
  ```
- **백업 서버 무중단 배포 (`eqmgmt-backup`):**
  - `tools/deploy_ai_ux_release.py`로 `pause` → `git pull --ff-only origin main` → `check-copy` → `activate` 순서대로 반영한다.
  - 활성화 후 비파괴 라이브 검증(`instance/maintenance-state.json` `NORMAL`, 웹 PID·`equipment-ai-worker.service`·`equipment-ai-retention.timer` `active`, 로컬 HTTP 스모크, `?mode=ro` SQLite `PRAGMA integrity_check == ok`)을 확인한다.
- **읽기 전용 Git 조회 (index 잠금 충돌 방지):**
  ```powershell
  node tools/git-readonly.mjs -- status -sb
  ```
- **미종결 보안 지적 추적:** `CORRECTIVE_ACTIONS.md`와 `docs/corrective-actions/` 대상 영역을 수정·검증할 때는 `node tools/validate-corrective-actions.mjs`로 정합성을 확인한다.

---

## 4. 작업 방식과 경량 기록 원칙

- **작업 규모에 맞는 격리:** 고정 `Staging/` 전체 복제·병합 절차는 의무가 아니다. 소규모·명확한 수정은 운영 루트에서 Diff/복구가 가능한 구조화 편집 후 격리 테스트로 검증하고, 대규모·고위험 변경은 Git 브랜치·worktree 또는 필요 시 임시 격리를 선택한다.
- **선별적 문서화:** 모든 작업마다 `Plans/`·`Tasks/`·`Reports/` 3종 문서를 의무 생성하지 않는다. **운영 배포, 장애 원인 분석·복구, 멀티 세션·대형 구조 변경**에만 `Reports/YYYY/MM/DD/`에 변경 범위·검증 근거·롤백 방법을 담은 단일 보고서 1건을 남긴다. 기존 `Plans/`, `Tasks/`, `Reports/`, `Chat/`은 과거 이력으로 보존한다.
- **주석과 커밋:** 한국어 유지보수자가 의도와 의존성을 빠르게 파악할 수 있도록 비자명한 함수·계약에 간결한 설명을 남긴다(매 행 설명이나 `[EN/KO rev.N]` 이중언어 동기화는 요구하지 않는다). 커밋은 Conventional Commit 형식(`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`)으로 작성한다.
- **사실 기반 보고:** 실제 수행해 통과한 검증과 미확인 제한사항·실패 원인을 명확히 구분해 보고한다. 변경이나 우려가 없는데 통과한 검사를 불필요하게 반복하지 않는다.
- **타 워크스페이스 경계:** 이 프로젝트의 외부 참고나 부수 명령으로 작업 대상을 임의 변경하지 않으며, 다른 프로젝트 디렉터리의 수정은 해당 프로젝트 지침과 사용자 지시를 따른다.
