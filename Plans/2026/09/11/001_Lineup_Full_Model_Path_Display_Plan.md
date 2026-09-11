---
artifact_id: PLAN-20260911-001
work_id: WORK-20260911-LINEUP-MODEL-PATH-DISPLAY
created_at: 2026-09-11T09:30:08.650+09:00
related_artifacts:
  - ../../../../Tasks/2026/09/11/001_Lineup_Full_Model_Path_Display_Task.md
  - ../../../../Reports/2026/09/11/002_Lineup_Full_Model_Path_Display_Validation_Report.md
  - ./002_Equipment_Deletion_and_Node_Usage_Consistency_Plan.md
  - ../../../../Plans/2026/09/10/003_Lineup_Node_Registration_and_Admin_Management_Plan.md
---

# [계획서] 라인업 전체 모델 경로 표시 개선

- 작성일: 2026-09-11
- 작업 ID: WORK-20260911-LINEUP-MODEL-PATH-DISPLAY
- 상태: 계획 및 사전 검토 완료 / 구현 승인 대기
- 귀속: 제안 047의 후속 개선

## 1. 현상과 원인

나의 장비와 공개 장비 목록은 장비가 연결된 최하위 lineup_nodes 행의 name만 ModelName으로 반환한다. templates/index.html도 이 값을 그대로 출력하므로, 예를 들어 노드가 Mini PC → SER → SER8 순서라면 목록에는 SER8만 보인다.

직접 원인은 app.py의 /api/equipment 조회가 equipment_options.lineup_node_id로 최하위 노드 하나만 JOIN하고 node.name AS ModelName을 선택하는 구조다. 같은 축약은 /api/equipments_v2 및 대시보드 복합 검색 목록에도 존재한다.

## 2. 목표와 표시 계약

- 모델의 완성명은 선택된 노드에서 parent_id를 따라 루트까지 올라간 뒤 루트 → 자식 → 최하위 노드 순서로 나열한다.
- 표준 구분자는 화면의 기존 표기와 읽기 쉬운 ' / '를 사용한다.
- 예: 제조사 표시가 Beelink이고 노드 경로가 Mini PC → SER → SER8이면 화면은 Beelink / Mini PC / SER / SER8로 표시한다.
- 카테고리와 제조사 이름은 노드 경로에 중복 포함하지 않는다. 기존 화면이 별도 컬럼과 접두 표시를 담당한다.
- 기존 ModelName은 최하위 노드명 의미로 유지한다.
- 신규 FullModelName 필드에 완성된 노드 경로 문자열을 제공하고, 화면은 FullModelName이 있으면 우선 사용하며 없으면 ModelName으로 후퇴한다.

## 3. 구현 설계

### 3.1 공통 경로 조립기

utils/lineup_node_service.py에 전체 lineup_nodes를 한 번 조회해 ID별 경로를 만드는 공통 함수를 추가한다.

- parent_id 연결을 실제 순서의 기준으로 사용하고 저장된 depth 값은 표시 순서의 근거로 사용하지 않는다.
- 메모이제이션으로 공통 조상 경로를 재사용해 노드 수에 대해 선형에 가까운 비용으로 처리한다.
- 한 요청에서 노드 조회 1회만 수행하고 장비 행마다 SQL을 실행하는 N+1 조회를 만들지 않는다.
- 기존 최대 깊이 50을 동일하게 적용한다.
- 순환 참조, 유실된 부모, 존재하지 않는 노드가 발견되면 요청 전체를 500으로 만들지 않고 해당 장비의 최하위 ModelName으로 안전하게 후퇴한다.

### 3.2 API 적용 범위

다음 조회 결과에 FullModelName을 추가한다.

1. /api/equipment: 나의 장비, 공개 장비, 임시저장 목록
2. /api/equipments_v2: 공통 장비 조회
3. /api/dashboard/stats: 카테고리·제조사 복합 검색의 equipment_list

장비 등록·수정 payload, option_id, lineup_node_id, DB 스키마는 변경하지 않는다.

### 3.3 화면 적용 범위

- templates/index.html의 모델 셀은 FullModelName || ModelName || '-' 순서로 표시한다.
- templates/dashboard.html의 복합 검색 결과도 같은 후퇴 규칙을 사용한다.
- 모든 문자열은 기존 escapeHtml 경로를 통과시켜 노드 이름의 HTML이 실행되지 않게 한다.
- 긴 다단계 이름은 데이터 자체를 생략하지 않는다. 셀의 가로 넘침은 현재 테이블 스크롤 정책을 유지하고, 필요하면 구현 검증에서 줄바꿈 또는 title 보조 표시를 결정한다.

## 4. 테스트 계획

### 서비스 단위 테스트

- 1단계 노드는 자기 이름만 반환한다.
- 2단계와 3단계 이상 노드는 루트부터 순서대로 결합된다.
- 형제 노드의 경로가 섞이지 않는다.
- 잘못된 depth 값이 있어도 parent_id 순서가 우선한다.
- 유실 부모, 순환 참조, 50단계 초과는 최하위 이름으로 후퇴한다.
- 이름에 HTML 특수문자나 구분자 문자가 있어도 원문 보존 및 프론트엔드 이스케이프 계약을 지킨다.

### API 및 화면 계약 테스트

- 나의 장비와 공개 장비가 동일한 FullModelName을 받는다.
- 기존 ModelName과 LineupNodeId는 변경되지 않는다.
- FullModelName 부재 시 기존 ModelName 표시가 유지된다.
- 대시보드 복합 검색도 전체 경로를 표시한다.
- 빈 목록, 삭제된 옵션 연결 등 기존 LEFT JOIN 예외 동작이 깨지지 않는다.

## 5. 단계별 수행 순서

1. Staging에 공통 경로 조립기와 단위 테스트 후보를 작성한다.
2. 메모리 SQLite 데이터로 정상·손상 계층·최대 깊이 경계를 검증한다.
3. Staging API 결과와 화면 계약 후보를 검토한다.
4. 별도 운영 반영 승인 후 app.py, utils, templates, tests에 병합한다.
5. Python 테스트, JavaScript 구문/계약 검사, 기존 제안 047 회귀 테스트를 실행한다.
6. Linux 서비스 재시작 후 나의 장비와 공개 장비에서 실제 표시를 확인한다.

## 6. 수용 기준

- 각 목록의 모델명이 루트부터 최하위 노드까지 빠짐없이 같은 순서로 표시된다.
- 제조사명과 노드명이 불필요하게 중복되지 않는다.
- 기존 API 소비자를 위해 ModelName의 최하위 노드명 의미가 유지된다.
- DB migration 없이 기존 데이터에 즉시 적용된다.
- 계층 손상 한 건이 전체 장비 목록 장애로 확대되지 않는다.
- 장비 행 수에 비례한 추가 DB 쿼리가 발생하지 않는다.

## 7. 비범위

- 노드 DB 스키마 변경 및 경로 문자열 영구 저장
- 노드 이름 자동 정규화 또는 구분자 입력 금지
- 카테고리·제조사 관리 재설계
- 장비 등록 화면의 노드 선택 UX 추가 변경
- 제안 013 시험 및 DB 복원 기능 변경

## 7.1 병렬 후속 계획

장비 삭제 후 옵션이 남아 노드 정리가 막히는 문제는 표시 경로 조립과 원인이 다르므로 별도 [장비 삭제·옵션 관리·노드 사용량 정합성 계획](./002_Equipment_Deletion_and_Node_Usage_Consistency_Plan.md)으로 분리한다. 두 계획은 제안 047 후속 개선으로 함께 검증할 수 있지만 각각 독립적으로 구현·롤백 가능해야 한다.

## 8. 롤백

신규 FullModelName 생성과 두 템플릿의 우선 표시만 제거하면 기존 최하위 ModelName 표시로 복귀한다. DB 변경이 없으므로 데이터 롤백은 필요하지 않다.
