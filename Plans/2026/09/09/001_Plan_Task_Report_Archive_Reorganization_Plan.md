# [개편 계획서] Plan·Task·Report 문서 보관 구조

- 작성일: 2026-09-09
- 상태: 검토 완료, 구현 미수행
- 기준 Rule SHA-256: `101AC771781BC9237B2126B4675803EEA0E895B4138410104383D6FCE1AD5269`
- 조사 기준 대상: 기존 `Plans/` 51개, `Report/` 37개와 관련 Rule·거버넌스·문서 참조
- 구현 시 예상 대상: 본 Plan·Task·검증 보고서를 포함한 Plan 41개, Task 12개, Report 38개, 총 91개

## 1. 최종 권고안

문서 종류별 디렉터리를 `Plans/`, `Tasks/`, `Reports/`로 통일한다. 세 이름 모두 복수형으로 사용한다.

Plan과 Task는 한 문서에 합치지 않는다. Plan은 승인된 목표·범위·설계·수용 기준을 고정하는 기준선이고, Task는 수행 중 상태가 계속 변하는 실행 대장이므로 수정 주기와 역할이 다르다. 서로 별도 파일로 보존하되 공통 `work_id`와 상호 경로로 연결한다.

## 2. 표준 경로와 파일명

모든 문서는 작성 시점의 검증된 KST 날짜를 기준으로 연도·월·일 폴더에 저장한다. 월과 일은 두 자리 숫자로 고정한다.

```text
Plans/YYYY/MM/DD/001_<작업명>_Plan.md
Tasks/YYYY/MM/DD/001_<작업명>_Task.md
Reports/YYYY/MM/DD/001_<작업명>_Report.md
```

예시는 다음과 같다.

```text
Plans/2026/09/09/001_Plan_Task_Report_Archive_Reorganization_Plan.md
Tasks/2026/09/09/001_Plan_Task_Report_Archive_Reorganization_Task.md
Reports/2026/09/09/001_Plan_Task_Report_Archive_Reorganization_Validation_Report.md
```

기존 파일명의 `YYYY-MM-DD_` 접두사는 제거한다. 날짜는 상위 경로로 표현하고 파일명은 순번·주제·문서 종류만 담는다.

## 3. 날짜별 순번 규칙

1. 각 디렉터리의 일자 폴더마다 `001`부터 독립적으로 시작한다.
2. 순번은 문서의 검증된 `created_at` KST 오름차순으로 배정한다.
3. 동일 시각이면 Git 최초 추가 commit 시각, 기존 파일명 사전순을 차례로 tie-breaker로 사용한다.
4. 순번은 항상 세 자리 숫자와 밑줄을 사용한다. `1.`, `2.`처럼 자릿수가 다른 표기는 파일 탐색기에서 `10`이 `2`보다 먼저 정렬될 수 있어 사용하지 않는다.
5. commit된 문서의 순번은 경로 안정성을 위해 재사용하거나 임의로 다시 매기지 않는다.
6. 뒤늦게 발견된 과거 문서는 다음 빈 순번을 받고, 실제 사건 시각은 메타데이터와 일자별 색인에서 정렬한다. 기존 경로를 대량 변경하는 재번호 부여는 하지 않는다.

새 문서는 직접 최대 번호를 추측하지 않고 전용 문서 도구가 일자 폴더의 다음 번호를 잠금 상태에서 배정하도록 한다. 이 도구가 준비되기 전에는 같은 날짜·종류의 문서를 동시에 생성하지 않는다.

기존 문서에 `created_at`이 없거나 정확한 시각을 확정할 수 없을 때는 다음 우선순위를 적용한다.

1. 문서 본문에 명시된 offset 포함 작성 시각
2. 해당 파일을 Git에 최초 추가한 commit의 author 시각
3. 기존 파일명 사전순

각 문서의 정렬 근거를 migration 원장에 `document_timestamp`, `git_first_added`, `filename_fallback` 중 하나로 기록한다. 3번까지 내려간 문서는 추정 순서임을 나타내는 `confidence: low`를 표시하며 확정 시각으로 보고하지 않는다.

## 4. Plan·Task·Report 연결

신규 문서는 다음 최소 메타데이터를 YAML front matter로 가진다.

```yaml
artifact_id: PLAN-20260909-001
work_id: WORK-20260909-001
created_at: 2026-09-09T00:00:00.000+09:00
related_artifacts: []
```

- `artifact_id`는 문서 자체의 불변 식별자다.
- `work_id`는 날짜가 달라져도 같은 작업의 Plan·Task·Report를 연결한다.
- `created_at`은 순번 배정 근거이며 KST offset과 밀리초를 보존한다.
- `related_artifacts`에는 현재 유효한 상대 경로를 기록한다.

개편 활성화 전에 작성된 91개 문서 본문에는 front matter를 일괄 삽입하지 않는다. 원문 보존을 위해 마이그레이션 원장에 기존 경로, 새 경로, 문서 종류, 날짜, 순번, 정렬 근거와 신뢰도를 기록한다.

## 5. 일자별 색인

각 일자 폴더에는 사람이 직접 관리하는 중복 목록을 두지 않는다. 전용 문서 도구가 파일과 메타데이터를 읽어 `index.md`를 결정적으로 생성한다.

색인은 순번, 작성 시각, 제목, `work_id`, 관련 Plan·Task·Report 링크를 보여준다. 뒤늦게 발견된 과거 문서처럼 파일 순번과 실제 사건 시각이 달라질 수 있는 예외는 색인에서 실제 시각순으로 표시한다.

`index.md`, 각 루트의 `README.md`, migration 원장과 경로 map은 일반 Plan·Task·Report가 아니다. 순번 할당, 문서 수량, 다음 번호 계산 대상에서 제외한다.

## 6. 기존 문서 마이그레이션

조사 시점의 기존 88개 파일과 이번 개편 통제 문서 3개는 모두 `YYYY-MM-DD_...` 형식이며 새 경로로 변환했을 때 이름 충돌이 없다. 다음 순서로 이동한다.

1. 구현 시작 직전에 `Plans/`와 `Report/`를 다시 전수 조사한다. 91개는 2026-09-09 계획 확정 시점의 기준선이며 고정 상수가 아니다.
2. 새 문서가 추가됐다면 종류별 수량, migration 원장과 검증 기대값을 실제 조사 결과로 갱신한다. 기존 91개만 이동하고 새 파일을 누락해서는 안 된다.
3. 기존 파일별 목적 경로와 정렬 근거를 담은 마이그레이션 원장을 생성한다.
4. dry-run으로 모든 source 존재, destination 중복 0개, 경로 이탈 0개를 확인한다.
5. 기준선 수량에서 추가가 없다면 `Plans/`의 Plan 41개를 새 `Plans/` 계층으로 이동한다.
6. 기준선 수량에서 추가가 없다면 `Plans/`의 Task 12개를 새 `Tasks/` 계층으로 이동한다.
7. 기준선 수량에서 추가가 없다면 `Report/`의 Report 38개를 `Reports/` 계층으로 이동한다.
8. 이동된 문서·`PROPOSALS.md`·활성 거버넌스의 현재 경로 참조를 새 경로로 갱신한다.
9. 모든 새 경로와 상호 참조를 검사한 뒤 기존 평면 경로가 남지 않았는지 확인한다.

이동은 파일 내용 재작성보다 Git rename으로 인식될 수 있게 수행하고, 전체 변경을 하나의 원자적 migration commit으로 묶는다.

## 7. Chat과 역사 원본 처리

`Chat/`에는 기존 Plan·Report 경로 표현이 302회, 고유 경로 기준 74개 존재한다. 이 가운데 현재 파일로 연결되는 경로는 72개다.

Chat 원문과 `.agent-governance/legacy-sources/`는 수정하지 않는다. 대화 원문을 경로 갱신 목적으로 바꾸면 원문 보존과 provenance 검증이 훼손되기 때문이다.

대신 `docs/artifact-path-map.yaml`에 기존 경로와 새 경로를 기록하고, 문서 검증 도구가 역사적 경로를 이 원장으로 해석하게 한다. 기존 위치에 수십 개의 redirect 파일이나 symlink를 남기는 방식은 평면 폴더 정리 목적과 Windows·Linux 호환성을 해치므로 채택하지 않는다.

## 8. Rule 및 거버넌스 변경

Rule 후보는 먼저 Staging에서 작성하고 다음 조항을 동기화한다.

- `6-1-10-3`: 영구 문서 범위에 `Tasks/`와 `Reports/`를 명시
- `7-2-2`: Plan의 새 날짜 계층·순번·파일명 규칙
- 신규 `7-2-3`: Task 분리 저장과 Plan 연결 규칙
- 신규 `7-2-4`: Report의 새 날짜 계층·순번·파일명 규칙
- `7-3-4`: `Staging_PLAN.md`의 새 아카이빙 경로
- `7-5-3`: 후속 AI가 Plans·Tasks·Reports를 함께 읽는 승계 규칙
- `10-1-1`: Validation Task와 종합 보고서의 저장 위치 및 연결 규칙

실행 노드는 `records.scratch-retention`, `workflow.plans`, `workflow.staging-merge`, `workflow.multi-agent-handoff`, `validation.orchestration`을 갱신한다. router에는 `Plans/**`, `Tasks/**`, `Reports/**` 경로를 등록한다. Rule SHA-256, section baseline, node digest, rule map, human map과 manifest 버전을 같은 변경 단위로 동기화한다.

구현 AI는 계획서에 적힌 현재 Rule hash를 그대로 사용하지 않는다. 작업 시작 시 운영 루트의 `sync-status`로 `currentRuleHash`와 변경 섹션 전체를 다시 확인하고, 그 hash를 `sync-plan`과 최종 `validate --expected-rule-sha`에 전달한다. 계획 작성 뒤 Rule이 달라졌거나 section이 추가·삭제됐다면 이전 결과를 재사용하지 않고 새 동기화 계획을 만든다.

## 9. 전용 문서 도구

`.agent-governance/tooling/artifact-manager.mjs`를 추가해 다음 기능을 제공한다.

- `next`: KST 날짜와 문서 종류에 맞는 다음 3자리 순번을 잠금 상태에서 할당
- `validate`: 경로 형식, 날짜, 중복 순번, ID 중복, 깨진 관련 문서 링크 검사
- `index`: 날짜별 `index.md` 결정적 재생성
- `migrate --dry-run`: 기존 91개 문서의 source·destination·충돌·참조 변경 목록 출력
- `resolve`: `artifact-path-map.yaml`을 통한 역사적 경로 조회

Windows와 Linux에서 동일하게 동작하도록 Node 표준 기능과 프로젝트의 고정된 YAML 파서를 사용한다. 경로는 프로젝트 루트 아래인지 확인하고, 단일 lock과 원자적 파일 교체를 사용한다.

## 10. 추가 제안

1. 세 루트에 각각 `README.md`를 두어 새 경로, 순번, 문서 종류와 검색 방법을 설명한다.
2. 문서 내용 검색은 경로 탐색과 별개이므로 `rg Plans Tasks Reports` 예시를 운영 가이드에 둔다.
3. CI 또는 governance test에서 새 문서 경로와 참조 무결성을 검사해 평면 경로가 다시 생기지 않게 한다.
4. 날짜 폴더가 비어 있으면 Git에 남기지 않는다. 월·일 폴더는 첫 문서 생성 때 만든다.
5. 외부 GitHub 링크는 저장소 안에서 전수 탐지할 수 없으므로 migration commit과 경로 원장을 영구 보존한다.

## 11. 검증 기준

- 구현 직전 재조사한 모든 파일이 누락 없이 각각 한 새 경로에 존재한다.
- 기준선 91개에서 파일이 늘었다면 갱신된 Plan·Task·Report 종류별 기대 수량이 유지된다.
- 목적 경로 충돌, 중복 순번, 경로 이탈이 0건이다.
- 활성 문서의 기존 `Plans/YYYY-MM-DD_...`와 `Report/YYYY-MM-DD_...` 참조가 0건이다.
- Chat과 legacy source의 byte hash는 변경 전과 동일하다.
- migration map으로 Chat의 현재 유효한 역사적 경로 72개를 모두 새 경로로 해석한다.
- Rule·노드·router·map·baseline·manifest가 같은 버전으로 validate와 sync-status를 통과한다.
- `artifact-manager`의 Windows·Linux 경로, 동시 번호 할당, 날짜 전환, rollback 시험이 통과한다.
- `git diff --check`와 링크 검사가 통과한다.

## 12. 롤백

운영 반영은 문서 이동, 참조 갱신, Rule·거버넌스와 도구를 한 commit으로 구성한다. 문제가 생기면 해당 commit을 revert하여 기존 `Plans/`와 `Report/` 평면 구조 및 이전 Rule hash로 함께 되돌린다.

부분 이동 상태에서는 commit하거나 push하지 않는다. 실패한 migration은 원장을 기준으로 이동 전 경로를 복원하고 파일 수·hash를 다시 대조한다.

## 13. 구현 순서

1. Staging에 Rule·거버넌스·artifact-manager 후보 작성
2. 구현 직전 파일 재조사, 기대 수량 확정과 migration 원장·정렬 신뢰도 생성
3. dry-run 및 Validation 1~8 수행
4. 검증 보고서 제출과 사용자 운영 병합 승인 확인
5. 운영 트리에 Rule·도구·문서 이동을 원자적으로 병합
6. 파일 수·hash·경로·링크·거버넌스 재검증
7. Staging 정리
8. 별도 지시가 있으면 commit·push

## 14. 판정

`Plans/`, `Tasks/`, `Reports/` 분리와 `YYYY/MM/DD/NNN_...` 구조는 현재 문서량과 향후 증가를 고려할 때 타당하다. Task를 Plan 본문에 합치지 않고 독립 파일로 관리하는 것이 승인 기준선과 실행 상태를 가장 명확하게 보존한다.

구현은 Rule 동기화, 자동 순번 할당, 역사적 경로 매핑을 포함해야 하며 단순 폴더 이동만으로 완료 처리하지 않는다.
