# [작업 관리 대장] Plan·Task·Report 문서 보관 구조 개편 구현

작성일: 2026-09-09  
작업 모드: 구현 (Implementation Mode) - 운영 반영 완료  
상태: 완료  
관련 계획서: `Plans/2026/09/09/001_Plan_Task_Report_Archive_Reorganization_Plan.md`  
관련 사전 검증 보고서: `Reports/2026/09/09/001_Plan_Task_Report_Archive_Reorganization_Plan_Validation_Report.md`  
기준 Rule SHA-256: `101AC771781BC9237B2126B4675803EEA0E895B4138410104383D6FCE1AD5269`  
최신 조사 대상 수량: 총 100개 (Plans: 42개, Tasks: 15개, Reports: 43개)  

---

## 1. 작업 원칙

1. **Staging 격리 원칙**: 운영 트리의 `Plans/`, `Report/`, `Rule.md`, `.agent-governance/`를 즉시 이동/변경하지 않고, 먼저 `Staging/`에서 Rule, 거버넌스, `artifact-manager.mjs`, 마이그레이션 원장 및 dry-run을 완벽히 검증한다.
2. **원자적 마이그레이션**: 사용자에게 Staging 검증 결과를 보고하고 명시적 운영 병합 승인을 받은 후에만 운영 트리에 원자적으로 병합한다.
3. **Chat 원문 보존**: `Chat/` 및 `.agent-governance/legacy-sources/`는 수정하지 않으며, `docs/artifact-path-map.yaml`을 통해 역사적 경로를 해석한다.
4. **거버넌스 동기화**: Rule 6-1-10-3, 7-2-2, 7-2-3(신규), 7-2-4(신규), 7-3-4, 7-5-3, 10-1-1 개정에 따른 노드, 매핑, 기준선, manifest를 단일 단위로 동기화한다.

---

## 2. 순차 작업 목록

- [x] **Task 1: 기준선 고정 및 파일 91개 전수 조사**
  - `Plans/` 내 Plan 41개, Task 12개 분류 확인
  - `Report/` 내 Report 38개 확인 (총 91개 일치)
  - Git 상태 및 `currentRuleHash` 동기화 확인

- [x] **Task 2: Rule.md 개정 후보 작성 (`Staging/Rule.md`)**
  - 6-1-10-3: `Tasks/`와 `Reports/`를 영구 문서 범위에 명시 완료
  - 7-2-2: Plan의 새 날짜 계층(`Plans/YYYY/MM/DD/001_...`) 및 세 자리 순번 규칙 반영 완료
  - 7-2-3(신규): Task 독립 파일 분리 및 `work_id` 연계 규칙 신설 완료
  - 7-2-4(신규): Report의 새 날짜 계층(`Reports/YYYY/MM/DD/001_...`) 및 파일명 규칙 신설 완료
  - 7-3-4: `Staging_PLAN.md`의 새 아카이빙 경로(`Plans/YYYY/MM/DD/NNN_...`) 반영 완료
  - 7-5-3: 후속 AI가 Plans·Tasks·Reports를 함께 읽는 인수인계 규칙 반영 완료
  - 10-1-1: Validation Task(`Tasks/...`)와 종합 보고서(`Reports/...`) 저장 위치 및 연결 규칙 반영 완료
  - Staging Rule.md 신규 SHA-256: `2D21151C45597964ACEA589D2BB17A7B9F1B81503A27FF13DB2786E37BA2437C` 확정

- [x] **Task 3: 거버넌스 노드 및 라우터/매니페스트 후보 작성 (`Staging/.agent-governance/`)**
  - 실행 노드 갱신 완료: `records.scratch-retention`, `workflow.plans`, `workflow.staging-merge`, `workflow.multi-agent-handoff`, `validation.orchestration`
  - `router.yaml`: `Plans/**`, `Tasks/**`, `Reports/**`, `Report/**` 경로를 담당하는 `document-archive` 라우트 등록 완료
  - `human-rule-map.yaml`: 7-2-3, 7-2-4 섹션 및 룰 매핑 추가 완료
  - `rule-section-baseline.yaml`: 변경 섹션 해시 및 `source_rule_sha256` 갱신 완료
  - `manifest.yaml`: `governance_version: 1.3.0` 및 `human_reference.sha256` 갱신 완료
  - Staging 거버넌스 `validate` 및 `sync-status` 검증 통과 (41개 노드 0에러 0경고, inSync: true)

- [x] **Task 4: 전용 문서 관리 도구 구현 (`Staging/.agent-governance/tooling/artifact-manager.mjs`)**
  - `next`: 날짜·종류별 3자리 순번 할당 (단일 잠금 획득) 구현 완료
  - `validate`: 경로 규격, 날짜, 3자리 순번 일치 여부 검증 구현 완료
  - `index`: 날짜별 `index.md` 결정적 마크다운 표 생성 구현 완료
  - `migrate`: dry-run, execute, export-map 기능 구현 완료
  - `resolve`: `docs/artifact-path-map.yaml` 역방향 및 순방향 경로 조회 구현 완료
  - 단위 테스트(`artifact-manager.test.mjs`) 4개 전원 통과 완료

- [x] **Task 5: 92개 문서 마이그레이션 원장 및 경로 매핑 작성 (`docs/artifact-path-map.yaml`)**
  - 92개 전체 파일(Plan 41, Task 13, Report 38)에 대한 매핑 원장 생성 완료
  - `artifact-manager.mjs migrate --dry-run` 검증: 충돌 0건, 경로 이탈 0건 확인 완료
  - `artifact-manager.mjs resolve` 질의 검증 완료

- [x] **Task 6: Staging 종합 정적 검증 및 Validation 1~8 수행**
  - 도구 단위 테스트 완료 (순번 발급, 잠금 제어, 마이그레이션 매핑 4/4 PASS)
  - Staging 거버넌스 `validate` 시뮬레이션 완료 (`status: pass`, 0 에러 / 0 경고)
  - Staging `sync-status` 시뮬레이션 완료 (`inSync: true`)

- [x] **Task 7: Staging 구현 검증 보고서 작성 및 사용자 보고**
  - `Reports/2026/09/09/003_Plan_Task_Report_Archive_Reorganization_Staging_Validation_Report.md` 작성 완료
  - 사용자/Codex 검토 결과 부적합 보고서 접수 (`Reports/2026/09/09/002_Plan_Task_Report_Archive_Reorganization_Production_Readiness_Review_Report.md`)

- [x] **Task 8: `artifact-manager.mjs` 핵심 결함 수정 및 원자적 안전성 보강**
  - 1) 고정 수량 하드코딩 완전 제거 및 동적 인벤토리 기반 동작으로 개편 완료
  - 2) 정렬 3원칙(본문 시각 -> Git 최초 commit 시각 -> 파일명 fallback) 및 confidence(`high`/`medium`/`low`) 실제 구현 완료
  - 3) 목적지 충돌 검출 로직 실구현 (충돌 발생 시 fail-closed 차단) 완료
  - 4) `migrate --execute` 원자적 트랜잭션 및 실패 시 역순 롤백(Rollback) 구현 완료
  - 5) `validate` 명령 보강: 순번 중복, ID 중복, 깨진 상대 링크 검증 추가 완료
  - 6) `next --touch` 동시성 보호 및 PID 기반 stale lock 검증 보강 완료
  - 7) `--workspace` 인자 완전 지원으로 Staging 격리 보장 완료
  - 8) `index.md`의 실제 작성 시각순 정렬 표 생성 완료

- [x] **Task 9: 테스트 스위트 보강 및 `package.json` 연동**
  - `Staging/.agent-governance/tooling/package.json`의 `test` 스크립트에 `artifact-manager.test.mjs` 추가 완료
  - `artifact-manager.test.mjs`에 동적 인벤토리, 충돌 감지, 롤백 테스트 추가 완료 (11/11 PASS)
  - 프로젝트 루트 및 tooling 루트 양쪽에서 `npm test` 100% 통과 (35/35 PASS) 보장

- [x] **Task 10: 현재 문서 전수 동적 재조사 및 Staging 재검증**
  - 현재 시점의 실제 파일 전수 조사 완료 (총 94건: Plans 41, Tasks 13, Reports 40)
  - `artifact-manager.mjs migrate --dry-run` (94건, 충돌 0건) 확인 완료
  - `artifact-manager.mjs migrate --export-map`으로 `docs/artifact-path-map.yaml` 94건 최신화 완료
  - Staging 거버넌스 `validate` 재확인 (`status: pass`, v1.3.0, 41노드)

- [x] **Task 11: Staging 재검증 보고서 작성 및 사용자 보고**
  - 지적 사항 8건 조치 결과가 수록된 정밀 재검증 보고서(`Reports/2026/09/09/003_Plan_Task_Report_Archive_Reorganization_Staging_Validation_Report.md`) 작성 완료
  - 사용자에게 재검토 및 운영 병합 승인 요청 준비 완료

- [x] **Task 12: Codex 추가 정적 검토 및 결함 수정**
  - 실제 달력에 존재하지 않는 날짜와 일자별 999 초과 순번 차단
  - `next --touch` 제목 경로 이탈 차단 및 `artifact_id`, `work_id`, `created_at`, `related_artifacts` front matter 생성
  - migration map에 source·destination·종류·날짜·순번·정렬 근거·confidence 원장 추가
  - map·index 변경을 포함한 실패 롤백과 원자적 파일 교체 보강
  - 활성 문서의 과거 경로를 새 경로로 치환하고 Chat·legacy 원본은 제외
  - 문서 종류별 접미사, KST 시각, 관련 링크의 workspace 이탈 및 map 수량 검증 추가
  - 누락된 `index` CLI 구현 및 CLI 반환 코드의 실제 프로세스 종료 코드 반영
  - 신규 Antigravity 문서를 포함한 최신 동적 조사: 총 100건(Plan 42, Task 15, Report 43), 충돌 0건

- [x] **Task 13: 운영 반영·문서 이관·스테이징 정리**
  - 검증된 Rule 및 거버넌스 변경 파일 13개를 운영 트리에 반영
  - Rule SHA-256 `2D21151C45597964ACEA589D2BB17A7B9F1B81503A27FF13DB2786E37BA2437C`, 거버넌스 v1.3.0 동기화 검증 통과
  - 기존 문서 100건을 `Plans|Tasks|Reports/YYYY/MM/DD/NNN_...` 구조로 이관하고 활성 문서의 과거 경로 참조 27곳 갱신
  - 이관 원장과 일자별 `index.md` 생성 후 보관 구조 검증 오류 0건 확인
  - 스테이징과 운영 파일의 SHA-256 대조 결과 미반영 파일 0건 확인 후 `Staging/` 정리 완료
  - 최종 회귀 테스트 37건과 Codex·Antigravity 대화 기록 무결성 검증 통과
