---
artifact_id: REPORT-20260912-005
work_id: WORK-20260912-GOVERNANCE-CONTEXT-CLARITY
created_at: 2026-09-12T17:41:35.779+09:00
related_artifacts:
  - ../../../../Plans/2026/09/12/002_Governance_Context_Clarity_Plan.md
  - ../../../../Tasks/2026/09/12/004_Governance_Context_Clarity_Task.md
---

# 거버넌스 Context 명확성 개선 검증

## 변경 전 Validation 1~8

1. 거버넌스: ensure/validate 통과, Rule/map 전체 및 적용 노드 확인. 이전 진단 문서는 보존한다. 활성 정책 수정 전에 Staging 후보를 만든다.
2. 의도: 안전 조건 완화가 아니라 이해 가능한 입력·오류·재개 계약을 구현한다. 사용자 승인에는 운영 거버넌스와 push가 포함되지만 앱/DB 변경은 포함하지 않는다.
3. 논리: 필수 규칙 선택과 경로 유효성 검사를 분리한다. generic intent로 unknown path가 통과하는 기존 동작도 방지한다. 반복/복합 옵션·Windows 경로·외부 참조·Staging-only·작은 pack을 검사한다.
4. 영향: 기존 --path/--intent 의미를 유지하고 --reference-path와 구조화 diagnostics를 추가한다. 기존 error 문자열 키를 유지한다. 미분류 경로는 명시 오류가 될 수 있어 catalog/설명/회귀를 동시 갱신한다.
5. 보안: 알려진 intent라고 미등록 경로를 허용하지 않는다. 경로 이동/절대 경로/scope 판정을 정규화 후 검사한다. Rule/해시 불일치와 필수 section 누락은 계속 차단한다.
6. 복구: 원본 Git 기준선 116a4bf, 검증된 변경 묶음만 반영하고 전체 묶음 revert를 복구 단위로 한다. 앱 데이터·키·방화벽은 수정하지 않는다.
7. 사용성: 미등록과 미매칭을 분리하고 실제 편집 대상/참고 대상, 안전 진단/일반 구현 중단을 명확하게 설명한다. 편의를 위한 노드 축소나 허위 경로 추가를 금지한다.
8. AI 메타: 이전 오진을 숨기지 않고 기존 진단 보고서를 유지한다. 자동 테스트 성공과 실제 모델명 기능 구현을 혼동하지 않는다. Rule 변경을 이유로 외부 독립 프로젝트를 수정하지 않는다.

## 구현·검증 결과

### Staging 검증 완료

- 후보: `Staging/Governance_Context_20260912`. 기존 추적 파일의 검증용 사본에서 구현하고 동일한 잠금 의존성 yaml 2.9.0을 사용했다.
- 거버넌스 1.6.0, 노드 43개. Rule 변경 섹션은 9-1·9-3이며 `sync-status`의 전체 섹션과 관측 hash로 `sync-plan`을 수행했다.
- 최종 Rule SHA-256: `37257C4FB401B88093CBA604A68C5C5E67616B4EF98A2EF97C29E547CE53901D`.
- `sync-status`: inSync=true, 미동기 섹션 없음. `validate --expected-rule-sha <위 hash>`: 오류 0·경고 0.
- `npm.cmd test --prefix Staging/Governance_Context_20260912/.agent-governance/tooling`: 총 75건 통과. 기존 거버넌스 14, 신규 Context 21, recorder 17, routed ingest 5, cross-scope 3, artifact manager 12, Git read-only 3. 실패·건너뜀 0.
- 초기 회귀에서 작은 Rule context pack 예산 초과를 발견했다. 예산을 늘리거나 규칙을 삭제하지 않고, 공통 노드의 반복 설명은 짧은 참조로 바꾸고 상세 계약을 모든 context가 선택하는 별도 노드로 분리했다. 최종 작은 pack 검사도 통과했다.
- 병합 대상 20개 파일은 모두 원본 기준선과 일치하거나 이번 신규 파일이다. 기존 사용자 변경을 덮어쓰지 않는다.

### 변경 후 Validation 1~8

1. 거버넌스: Rule·노드 의미·양방향 map·섹션 기준선·manifest를 같은 묶음으로 동기화했다. 네 플랫폼 진입점과 두 README·CLI catalog를 맞췄다.
2. 의도: 입력의 오해를 줄이는 수정이다. 실제 미등록 작업·권한 부족·규칙 충돌을 임의로 허용하지 않는다.
3. 논리: migration/UI intent가 필수 노드를 결정하고 모든 경로는 별도로 검증된다. Staging-only, utils, 복합 intent, 대상/참고 역할, 작은 pack을 실제 CLI로 확인했다.
4. 영향: 기존 error 문자열 키와 context 키는 유지하고 diagnostics·referencePaths·pathRoles를 추가했다. 미분류 경로는 generic intent가 있어도 명시 오류가 된다. 앱/DB/서비스 런타임은 변경하지 않는다.
5. 보안: unknown intent/path, 외부 scope 누락, 경로 이동·기존 symlink 조상, 참고만 지정한 변경, 필수 section 누락, stale Rule hash를 모두 실패로 확인했다. context 성공은 수정 승인이 아니다.
6. 복구: 원본 기준선 116a4bf를 보존하고 변경 묶음 전체의 Git revert를 복구 단위로 한다. Staging→운영 동일성 및 운영 재검증 후에만 후보를 정리한다.
7. 사용성: 미등록과 경로 조건 불일치를 구분한다. 실패 중 읽기 전용 진단 및 근거 있는 입력 정정, validate·새 context·모든 pack 읽기·기존 승인 확인을 거친 재개 조건을 설명한다.
8. AI 메타: 이전 오진과 초기 예산 실패를 함께 기록했다. 입력 정정과 정책 완화를 혼동하지 않으며, 이 결과를 공식 모델명 기능의 구현 완료로 보고하지 않는다.

### 운영 반영

- 운영 루트에 검증된 20개 파일을 반영했다. Rule·노드·도구·bootstrap·FEATURES의 Staging/운영 SHA-256 비교는 20개 모두 일치했다. 비교 중 발견한 두 bootstrap의 마지막 빈 줄 차이도 정규화하고 다시 확인했다.
- 운영 `npm.cmd test --prefix .agent-governance/tooling`도 총 75건 통과, 실패·건너뜀 0. 운영 validate 오류·경고 0, sync-status inSync=true.
- 최초 실패의 여섯 Staging/문서 경로와 implement·migration·plan 및 ui intent를 함께 재검사했다. 운영 경로를 허위 추가하지 않고 schema-change·frontend-change·staging-work와 필요한 DB/UI/Validation 노드를 모두 포함한 8개 작은 pack이 통과했다. 이는 라우팅 검증이며 모델명 기능 구현이 아니다. 해당 과거 문서 경로는 재현 입력으로만 사용했으며 현재 문서 순번을 예약하거나 새 파일을 만들지 않았다.
- 이번 Staging 검증 사본만 `scratch/governance-context-20260912-recovery`로 이동했다. 삭제하지 않았으며 복구 가능하다. 이동 전 원본·목적지의 절대 경계와 reparse point 부재를 확인했다. 다른 Staging/기존 scratch는 변경하지 않았다. 이 사본은 영구 기록이 아니므로 장기 복구 기준은 Git 커밋이다.
- 앱 소스, 실제 DB, SSH 설정, Linux 서비스·주 서버·백업 서버는 변경하지 않았다. 이번 운영 반영 대상은 이 저장소의 활성 거버넌스다.
- 구현 커밋: `2e5334888b8d1f4cef88f5a724903b9d49d1cec5` (`fix(governance): clarify context routing and safe retry contract`). 28개 거버넌스·이력 파일이 포함됐다.
- `git push origin main` 성공: `116a4bf..2e53348`. 직후 `git ls-remote --exit-code origin refs/heads/main`이 위 전체 SHA와 일치하고 작업 트리가 깨끗함을 확인했다. 이 확인 이후 완료 기록만 별도 문서 커밋으로 보존한다.
- 영구 문서 검사: `artifact-manager validate --workspace .` 오류 0. Git diff 공백 검사 통과. recorder ensure 재조정 오류 없음.

## 잔여 범위와 재개 시 유의점

공식 모델명 기능은 이번 작업에 포함하지 않았다. 후속 작업은 catalog로 모든 실제 intent·대상·참고를 선언하고 정상 context의 전체 pack을 읽어 기존 Staging 승인 범위에서 진행해야 한다. path registry에 없는 새 경로나 실제 권한·정책 충돌은 자동으로 허용하지 않는다. Rule 변경은 일부 파일만 되돌리지 말고 이번 릴리스 전체 묶음으로 복구한다.
