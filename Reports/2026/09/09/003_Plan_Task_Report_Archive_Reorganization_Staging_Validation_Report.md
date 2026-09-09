# [Staging 재검증 보고서] Plan·Task·Report 문서 보관 구조 개편 결함 조치 및 재검증

작성일: 2026-09-09  
작성자: AI Agent (Antigravity)  
작성 모드: Staging 재작업 및 재검증 (Post-Review Remediation & Re-validation)  
관련 계획서: `Plans/2026/09/09/001_Plan_Task_Report_Archive_Reorganization_Plan.md`  
관련 작업 대장: `Tasks/2026/09/09/001_Plan_Task_Report_Archive_Reorganization_Implementation_Task.md`  
선행 검토 보고서: `Reports/2026/09/09/002_Plan_Task_Report_Archive_Reorganization_Production_Readiness_Review_Report.md` (Codex 적합성 검토 보고서)  
기준 Rule SHA-256: `101AC771781BC9237B2126B4675803EEA0E895B4138410104383D6FCE1AD5269`  
Staging 개정 Rule SHA-256: `2D21151C45597964ACEA589D2BB17A7B9F1B81503A27FF13DB2786E37BA2437C` (거버넌스 v1.3.0)  
동적 조사 확정 대상 수량: **총 94건 (Plans 41건, Tasks 13건, Reports 40건)**  

---

## 1. 재검증 배경 및 목적

Codex가 제출한 운영 준비 적합성 검토 보고서(`..._Production_Readiness_Review_Report.md`)에서 지적한 **8가지 중대 결함(고정 수량 하드코딩, 정렬 기준 미준수, 목적지 충돌 미검출, 비원자적 이동 및 롤백 부재, 검증 누락, 동시성 취약점, Staging 격리 미비, 허위 PASS 기록)**에 대해, 사용자의 재작업 지시("검토 결과 부적합, 다시 작업할것")를 수용하여 `artifact-manager.mjs` 및 테스트 스위트, 거버넌스 연동을 전면 재작성·보강하고 재검증을 수행하였습니다.

---

## 2. Codex 지적 8대 결함 조치 내역

| 번호 | 지적 사항 (Defect) | 조치 내용 및 기술적 구현 (Remediation) | 검증 증거 |
| :---: | :--- | :--- | :--- |
| **1** | **고정 수량 92개 하드코딩** | 코드 및 테스트의 `assert.equal(plan.length, 92)` 완전 제거. `fs.readdirSync` 기반 동적 인벤토리 스캔으로 현재 등록된 실제 파일 수(94건)와 대조하도록 변경. | `artifact-manager.test.mjs` Test 5 PASS |
| **2** | **정렬 3원칙 및 confidence 미구현** | 1순위: 문서 본문 시각(`document_timestamp`, `high`), 2순위: Git 최초 commit author 시각(`git_first_added`, `medium`), 3순위: 파일명 사전순 fallback(`filename_fallback`, `low`, 23:59:59 정규화) 구현 완료. | `artifact-manager.test.mjs` Test 6 PASS |
| **3** | **목적지 충돌 미검출** | `planMigration()`에서 계획 내 중복뿐 아니라 디스크상 실제 목적지 파일 존재 여부를 사전 확인하여 충돌 수를 계산하고, 충돌 발생 시 `fail-closed`로 실행 중단하도록 구현. | `artifact-manager.test.mjs` Test 7 PASS |
| **4** | **비원자적 이동 및 롤백 부재** | 이동 전 전수 Preflight(소스 부재 및 워크스페이스 이탈 검사), 이동 중 예외 발생 시 `movedFiles`를 역순 순회하여 원위치로 100% 원복하는 트랜잭션 롤백 로직 구현. | `artifact-manager.test.mjs` Test 8 PASS |
| **5** | **validate 명령 부실** | 경로/파일명 정규식, 월(1~12)/일(1~31) 유효성, 일자 폴더 내 순번 중복, front matter의 `artifact_id` 전역 중복, `related_artifacts` 상대 링크 부재, `path-map` 대상 누락을 전수 정밀 검증하도록 개편. | `artifact-manager.test.mjs` Test 9 PASS |
| **6** | **`next` 동시성 및 잠금 취약점** | `--touch <title>` 옵션을 신설하여 단일 잠금 구간 내에서 순번 발급과 플레이스홀더 파일 생성을 원자적으로 처리. PID 생존 검증(`process.kill(pid, 0)`)으로 살아 있는 프로세스의 잠금 임의 회수 차단. | `artifact-manager.test.mjs` Test 4, 10 PASS |
| **7** | **Staging 격리 미비** | 모든 CLI 및 함수에 `--workspace <dir>` 옵션을 지원하여 운영 루트를 오염시키지 않고 격리된 디렉터리/임시 디렉터리에서 완벽히 테스트할 수 있도록 구조화. | `artifact-manager.test.mjs` 전 테스트 격리 구동 |
| **8** | **시간순 index.md 및 resolve 양방향** | `generateIndex()`에서 front matter `created_at` 및 본문 `작성일/검증일`을 파싱하여 실제 시각순으로 정렬된 표 생성. `resolve`에 과거->새 경로뿐 아니라 새 경로->과거 경로 역방향 조회 지원. | `artifact-manager.test.mjs` Test 11 PASS, CLI 검증 |

---

## 3. 테스트 및 도구 검증 결과

### 3-1. 단위 테스트 전수 통과 (`artifact-manager.test.mjs`)
- 실행 위치: 프로젝트 루트(`d:\Project\Mini-Server-Web-EqMgmt`) 및 tooling 루트(`Staging/.agent-governance/tooling`) 양쪽에서 동일 실행 검증 완료.
- 테스트 결과: **11개 테스트 전원 통과 (11 pass, 0 fail)**
  1. `getKSTDateString()`: KST YYYY-MM-DD 형식 검증
  2. `getNextSequence()`: 순번 발급 및 점진적 증가 검증
  3. `acquireLock()`: 락 생성 및 정상 해제 검증
  4. `acquireLock()`: 사망한 PID에 대한 stale lock 자동 회수 및 자가 치유 검증
  5. `planMigration()`: 동적 인벤토리 스캔 수량 일치 및 신뢰도/근거 필드 무결성 검증
  6. `planMigration()`: 본문 시각(1순위), Git 시각(2순위), 파일명(3순위) 정렬 순위 검증
  7. `planMigration()`: 목적지 충돌 감지 및 fail-closed 예외 발생 검증
  8. `executeMigration()`: 성공 이동, 인덱스 생성, 맵 생성 및 **중간 실패 시 원자적 롤백(100% 원복) 검증**
  9. `validateArchive()`: 순번 중복, `artifact_id` 중복, 깨진 상대 링크 검출 정밀 검증
  10. `next --touch`: 원자적 플레이스홀더 생성 및 연속 호출 시 순번 충돌 방지 검증
  11. `generateIndex()`: 실제 작성 시각순 오름차순 표 정렬 검증

### 3-2. 전체 거버넌스 테스트 스위트 (`npm test` 연동)
- `node governance-tool.test.mjs`: 12/12 PASS
- `node --test conversation-recorder.test.mjs`: 12/12 PASS
- `node --test artifact-manager.test.mjs`: 11/11 PASS
- **총 35개 테스트 100% PASS**

### 3-3. Staging 거버넌스 유효성 검증
- `node Staging/.agent-governance/tooling/governance-tool.mjs validate`:
  - `status: pass`, `governanceVersion: 1.3.0`
  - `manifestNodes: 41`, `humanMapNodes: 41`, `errors: 0`, `warnings: 0`
- `git diff --check`: 0 에러 (코드/문서 내 공백 결함 없음)

---

## 4. 운영 작업 트리 대상 동적 Dry-Run 결과

실행 명령: `node Staging/.agent-governance/tooling/artifact-manager.mjs migrate --dry-run`

```json
{
  "mode": "dry-run",
  "totalDocuments": 94,
  "plans": 41,
  "tasks": 13,
  "reports": 40,
  "conflicts": 0,
  "sample": [
    {
      "source": "Plans/2026/08/04/001_Layout_Hierarchy_Architecture_Plan.md",
      "destination": "Plans/2026/08/04/001_Layout_Hierarchy_Architecture_Plan.md",
      "type": "plan",
      "date": "2026-08-04",
      "seq": "001",
      "docTime": "2026-08-04T14:36:44+09:00",
      "sortBasis": "git_first_added",
      "confidence": "medium",
      "conflict": false
    },
    {
      "source": "Plans/2026/08/04/002_Users_Management_Plan.md",
      "destination": "Plans/2026/08/04/002_Users_Management_Plan.md",
      "type": "plan",
      "date": "2026-08-04",
      "seq": "002",
      "docTime": "2026-08-11T14:19:38+09:00",
      "sortBasis": "git_first_added",
      "confidence": "medium",
      "conflict": false
    }
  ]
}
```

- **실제 대상 문서**: 총 94건 (Codex 검토 보고서 `2026-09-09_Plan_Task_Report_Archive_Reorganization_Production_Readiness_Review_Report.md` 포함)
- **경로 충돌 (conflicts)**: **0건**
- **역사적 경로 매핑**: `docs/artifact-path-map.yaml`에 94건 전수 갱신 완료 (`migrate --export-map`)

---

## 5. Validation 1~8단계 최종 판정

| 검증 단계 | 판정 | 재검증 상세 결과 및 증거 |
| :--- | :---: | :--- |
| **1단계: 거버넌스 준수성** | **PASS** | Staging 거버넌스 v1.3.0, 41개 노드 정규 YAML 검사 0 에러 / 0 경고. `package.json`의 `test` 스크립트에 신규 도구 정규 등록 완료. |
| **2단계: 사용자 의도 달성도** | **PASS** | 계획서의 3분할(`Plans/`, `Tasks/`, `Reports/`), 연월일 계층, 3자리 순번(`001_`), Task 독립 분리 규정 완벽 준수. Codex 지적 8개 항목 100% 해결. |
| **3단계: 논리적 구동 가능성** | **PASS** | `artifact-manager.test.mjs` 11개 항목 및 통합 35개 테스트 전원 통과. 본문 시각과 Git 최초 commit 시각 기반 정렬 작동 확인. |
| **4단계: 운영 병합 영향** | **PASS** | 웹 애플리케이션(`app.py`, templates, DB 등) 변경 0건. 마이그레이션 실행 전후 운영 코드 영향 전무. |
| **5단계: 보안 및 경계 조건** | **PASS** | 경로 이탈(상위 경로 이동) 사전 차단, 목적지 충돌 0건, 원본 파일 부재 사전 차단. `Chat/` 및 `.agent-governance/legacy-sources/` 불변성 100% 유지. |
| **6단계: 롤백 검증** | **PASS** | 마이그레이션 실행 도중 예외 발생 시 `movedFiles`를 역순으로 즉시 원복하는 원자적 롤백 기능 테스트 완료 (`test 8`). 운영 반영 commit revert 전략 유효. |
| **7단계: 휴먼 에러 및 UX 방어** | **PASS** | `next --touch`로 순번 발급과 파일 생성을 원자화하여 동시 작업 시 순번 충돌 원천 차단. 죽은 프로세스의 stale lock 자동 회수 구현. |
| **8단계: AI 메타 거버넌스** | **PASS** | `router.yaml`의 `document-archive` 라우트 등록으로 후속 AI 컨텍스트 유실 방지. `resolve` 양방향 조회 지원. 이전의 허위 보고서를 실제 증거 기반 재검증 보고서로 완전히 대체. |

---

## 6. 결론

Codex의 검토에서 제기된 8가지 결함이 모두 수정되었으며, 실제 동적 인벤토리(94건) 기준 충돌 0건, 단위 테스트 11건 및 통합 테스트 35건 전원 통과를 확인하였습니다.  
현재 상태는 운영 병합(`migrate --execute` 및 거버넌스 v1.3.0 적용)을 안전하게 진행할 수 있는 기술적 준비가 완료된 상태입니다.


