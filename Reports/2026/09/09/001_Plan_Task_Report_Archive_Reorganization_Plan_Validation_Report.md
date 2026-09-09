# [검증 보고서] Plan·Task·Report 문서 보관 구조 개편 계획

- 검증일: 2026-09-09
- 대상 계획: `Plans/2026/09/09/001_Plan_Task_Report_Archive_Reorganization_Plan.md`
- 기준 Rule SHA-256: `101AC771781BC9237B2126B4675803EEA0E895B4138410104383D6FCE1AD5269`
- 검증 범위: 계획 및 정적 분석, 구현 미수행
- 종합 판정: **계획 적합, 구현 전 별도 승인 필요**

## 1. 조사 결과

계획 수립 전 기준으로 `Plans/`에는 Plan 40개와 Task 11개, `Report/`에는 Report 37개가 있었다. 이번 계획·Task·검증 보고서를 포함하면 실제 구현 시 이전 대상은 Plan 41개, Task 12개, Report 38개로 총 91개다.

기존 88개는 모두 `YYYY-MM-DD_...` 형식이었으며 날짜 접두사를 제거하고 `YYYY/MM/DD/`로 이동했을 때 이름 충돌은 없었다. 날짜별 최대 문서 수는 12개이므로 세 자리 순번은 충분하다.

저장소의 활성 문서와 거버넌스에는 기존 Plans·Report 경로 참조가 57회, 31개 파일에 있다. Chat에는 관련 표현이 302회, 고유 경로 74개 있으며 현재 문서로 연결되는 경로는 72개다.

## 2. Validation 1~8

1. **거버넌스**: 현재 거버넌스 `1.2.0`은 41개 노드, 오류 0건, 경고 0건이며 Rule baseline과 manifest가 일치한다. 구현 시 Rule 7-2·7-3-4·7-5-3·10-1-1과 관련 노드·map·router·manifest 동기화가 필요하다.
2. **사용자 의도**: 날짜 접두사를 제거하고 연·월·일 계층과 시간순 번호를 적용한다. Task 저장 위치의 모호성은 독립 `Tasks/`로 분리해 해결한다.
3. **정적 논리**: `001_` 형식은 문자열 정렬과 시간순을 일치시킨다. Plan·Task·Report가 다른 날 생성될 수 있으므로 경로 번호로 관계를 추정하지 않고 공통 `work_id`를 사용한다.
4. **운영 영향**: 애플리케이션, DB와 Linux 서비스에는 영향이 없다. 문서 91개 이동과 내부 참조 갱신이 주요 변경이며 Git history는 rename으로 보존한다.
5. **보안·경계**: migration 도구는 프로젝트 루트 이탈, 중복 destination과 비정상 날짜를 거부해야 한다. 문서 본문에 비밀값을 새로 수집하지 않는다.
6. **롤백**: 문서 이동, 참조, Rule·거버넌스와 도구를 단일 commit으로 구성하면 한 번의 revert로 이전 구조를 복원할 수 있다. 부분 이동 상태에서는 commit하지 않는다.
7. **사람 실수**: 가변 자릿수 번호, 수동 최대값 추측, 동시 생성, 기존 번호 재사용과 뒤늦은 재번호가 주요 위험이다. 3자리 고정 번호, 단일 allocator와 불변 번호 정책으로 통제한다.
8. **AI 메타**: router에 `Plans/**`, `Tasks/**`, `Reports/**`가 없으면 경로 기반 규칙 선택이 실패할 수 있다. 세 경로를 정식 등록하고 다음 AI의 승계 범위에도 포함해야 한다.

## 3. Task 분리 판정

Task를 Plan 본문에 포함하는 방안은 채택하지 않는다. Plan은 승인 뒤 기준선으로 안정되어야 하지만 Task 체크 상태는 구현 과정에서 반복적으로 바뀐다. 둘을 합치면 계획 변경과 진행 상태 변경을 구분하기 어려워지고 검토 diff가 불필요하게 커진다.

Task는 `Tasks/YYYY/MM/DD/NNN_<작업명>_Task.md`에 별도 보존하고 Plan과 같은 `work_id`로 연결한다. Plan이 필요 없는 단순 작업도 독립 Task를 가질 수 있으며, 이 경우 `related_artifacts`의 Plan 항목을 비워 둔다.

## 4. 추가 제안 판정

- 고정 3자리 순번과 자동 allocator: 채택
- Plan·Task·Report 공통 `work_id`: 채택
- 신규 문서의 KST `created_at` 메타데이터: 채택
- 자동 생성 일자별 `index.md`: 채택
- 역사적 경로 migration map과 resolver: 채택
- 경로·링크 검사 CI: 채택
- 기존 위치 redirect 파일 72개 이상 유지: 폴더 정리 목적을 훼손하므로 기각
- Windows·Linux symlink 호환 계층: checkout 설정 차이로 기각
- Chat과 legacy source의 경로 문자열 일괄 수정: 원문 무결성을 훼손하므로 기각

## 5. 구현 전 차단 조건

- Rule 변경 섹션 전체에 대한 `sync-plan`이 작성되지 않은 경우
- 91개 source와 destination의 일대일 migration 원장이 없는 경우
- 일자 내 정렬 근거와 신뢰도가 기록되지 않은 경우
- Chat 및 legacy source의 변경 전 hash가 확보되지 않은 경우
- migration dry-run에서 누락·충돌·경로 이탈이 한 건이라도 발견된 경우

위 조건을 충족하고 사용자 구현 승인을 받은 뒤 Staging 후보 작성에 착수할 수 있다.

## 6. 타 AI 승계 보강

다른 AI가 계획 작성 시점의 환경을 고정값으로 오인하지 않도록 다음 조건을 계획서에 추가했다.

1. 91개는 현재 기준선이며 구현 직전에 전체 파일 수와 종류별 수량을 다시 확정한다.
2. 과거 문서는 본문 확정 시각, Git 최초 추가 시각, 파일명 순으로 정렬 근거를 선택하고 migration 원장에 신뢰도를 기록한다.
3. `index.md`, 루트 `README.md`, migration 원장과 경로 map은 번호 할당과 문서 수 집계에서 제외한다.
4. 구현 시작 시 `sync-status`의 최신 `currentRuleHash`를 사용해 `sync-plan`과 `validate`를 새로 실행한다.

이 보강 뒤에는 구현 AI가 수량 증가, 불확실한 과거 시각, 보조 문서의 순번 오염과 오래된 Rule hash를 스스로 탐지하고 fail-closed할 수 있다.
