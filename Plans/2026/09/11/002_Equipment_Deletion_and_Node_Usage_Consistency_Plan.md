---
artifact_id: PLAN-20260911-002
work_id: WORK-20260911-EQUIPMENT-DELETION-NODE-USAGE
created_at: 2026-09-11T09:36:07.846+09:00
updated_at: 2026-09-11T09:39:58.167+09:00
related_artifacts:
  - ../../../../Tasks/2026/09/11/002_Equipment_Deletion_and_Node_Usage_Consistency_Task.md
  - ../../../../Reports/2026/09/11/003_Equipment_Deletion_and_Node_Usage_Consistency_Validation_Report.md
  - ./001_Lineup_Full_Model_Path_Display_Plan.md
  - ./003_Equipment_Audit_FK_and_Proposal013_Backup_Remediation_Plan.md
  - ../../../../Plans/2026/09/10/003_Lineup_Node_Registration_and_Admin_Management_Plan.md
---

# [계획서] 장비 삭제·옵션 관리·노드 사용량 정합성 개선

- 작성일: 2026-09-11
- 작업 ID: WORK-20260911-EQUIPMENT-DELETION-NODE-USAGE
- 상태: 원인 확정 및 통합 계획 완료 / 구현 승인 대기
- 귀속: 제안 047 후속 개선

## 1. 분리 판단

전체 모델 경로 표시는 조회 결과의 표현 문제지만, 이번 증상은 장비 삭제 후 보존되는 옵션의 관리 경로가 없는 문제다. 변경 대상·위험·수용 기준이 다르므로 모델 경로 계획과는 분리한다. 반면 앞서 작성한 장비 삭제·노드 사용량 계획과는 원인과 해결 경로가 동일하므로 이 문서에 병합한다. 두 계획 모두 제안 047 후속 결함이므로 같은 릴리스 검증 묶음으로 수행할 수 있다.

## 2. 현재 소스에서 확인된 사실

- equipments 테이블에는 IsDeleted, DeleteYn, deleted_at 같은 장비 소프트 삭제 컬럼이 정의되어 있지 않다.
- IsDeleted와 DeletedAt은 users 테이블의 계정 삭제용 컬럼이다.
- 사용자 화면의 DELETE /api/equipment/<id>는 감사 로그를 기록한 뒤 DELETE FROM equipments WHERE id = ?를 실행한다.
- 관리자 노드 스냅샷의 equipment_count는 equipments와 equipment_options를 직접 JOIN하여 물리적으로 남은 장비 행을 센다.
- 관리자 화면의 노드 삭제 버튼은 equipment_count가 아니라 child_count 또는 option_count가 1 이상일 때 비활성화된다.

사용자 확인으로 장비 행은 삭제되지만 해당 equipment_options 행이 보존되는 것이 원인으로 확정됐다. 이는 카탈로그 옵션 재사용 관점에서는 정상적인 보존 정책이지만, 관리자 화면에 옵션 조회·수정·삭제 경로가 없어 사용하지 않는 옵션을 정리할 수 없는 기능 공백이다.

현재 API에는 옵션 생성 POST와 관리자 전용 삭제 DELETE가 있으나 관리자 화면에서 이를 사용할 수 없다. 옵션 목록 전용 관리 응답과 수정 API도 없다.

## 3. 해결 범위

기존 라인업 노드 관리 화면을 노드·옵션 통합 관리 화면으로 확장한다. 별도 관리자 메뉴를 늘리지 않고 각 노드 카드에서 소속 옵션을 펼쳐 관리하게 하여 현재 카테고리·제조사·노드 맥락을 유지한다.

- 노드별 옵션 목록, 승인 상태, 스펙, 연결된 정식 장비 수와 임시저장 수를 표시한다.
- 관리자는 옵션을 추가하고 이름·스펙을 수정할 수 있다.
- 연결 장비가 0인 옵션만 명시 확인 후 삭제할 수 있다.
- 옵션 삭제 후 노드 스냅샷을 다시 읽어 option_count와 노드 삭제 가능 상태를 즉시 갱신한다.
- 승인 대기 옵션은 전자결재함에서 처리한다는 상태와 이동 안내를 표시하며 관리자 화면에서 승인 절차를 우회하지 않는다.
- 장비 삭제 시 옵션이나 노드를 자동 연쇄 삭제하지 않는다.

## 4. 기준 동작

### 장비 수

- equipment_count는 현재 유효한 장비 인스턴스만 센다.
- 현재 하드 삭제 정책이 운영과 일치하면 삭제된 행은 물리적으로 없어야 하므로 별도 삭제 조건 없이 0으로 감소해야 한다.
- 임시저장 장비는 실제 옵션을 점유하므로 전체 사용량에는 포함하되, 관리자 화면에서 active_equipment_count와 draft_equipment_count를 분리해 오인을 방지한다.

### 옵션 수와 노드 삭제 가능 여부

- 장비 삭제는 equipment_options를 자동 삭제하지 않는다. 옵션은 여러 장비가 재사용할 수 있는 카탈로그 데이터이기 때문이다.
- 관리자 화면은 장비 0과 옵션 잔존을 명확히 구분해 표시한다.
- 노드 삭제가 막힌 경우 '장비가 남음'이 아니라 '연결된 옵션이 남음'처럼 실제 차단 이유를 표시한다.
- 사용하지 않는 옵션은 참조 장비 0을 서버에서 다시 검증한 뒤 별도 명시 삭제로 처리한다. 장비 삭제에 옵션·노드 연쇄 삭제를 결합하지 않는다.

## 5. 예정 구현

1. utils/lineup_node_service.py의 관리자 스냅샷에 options 배열을 추가한다. 각 옵션은 id, lineup_node_id, option_name, 파싱된 specs, status, requested_by, active_equipment_count, draft_equipment_count를 제공한다.
2. 기존 POST /api/equipment_option을 공통 옵션 서비스로 연결해 노드 존재·승인 상태, 이름 길이, specs 객체 형식, 동일 노드 내 중복 이름을 서버에서 검증한다.
3. 관리자 전용 PUT /api/equipment_option/<id>를 추가해 이름과 specs를 수정한다. lineup_node_id 이동은 이번 범위에서 금지해 잘못된 모델 계층 이동을 막는다.
4. 기존 DELETE /api/equipment_option/<id>를 강화한다. 옵션 존재 여부, 승인 상태, 정식·임시저장 장비 참조 0을 같은 transaction에서 재검증하고 조건부 DELETE rowcount를 확인한다.
5. 옵션 생성·수정·삭제는 기존 audit_logs에 이전값·새값과 대상 ID를 기록하며 실패 시 함께 rollback한다.
6. templates/lineup_management.html의 각 노드 카드에 옵션 펼침 영역과 추가·수정·삭제 동작을 제공한다.
7. 삭제 버튼은 연결 장비가 있으면 비활성화하고 정확한 건수와 차단 이유를 title 및 화면 문구로 표시한다.
8. 옵션 삭제 성공 후 관리자 스냅샷과 sessionStorage의 nodeCache_v2를 무효화한다. 해당 노드의 option_count가 0이고 자식도 없으면 노드 삭제 버튼이 활성화된다.
9. 장비 삭제 API는 기존 하드 삭제 정책을 유지하되 성공 후 option_id를 반환해 향후 UI 안내에 사용할 수 있게 한다. 옵션 자동 삭제는 하지 않는다.

### API 호환성

- 기존 옵션 생성·삭제 URL과 응답의 success/message 필드는 유지한다.
- 관리자 스냅샷의 기존 categories, manufacturers, nodes 필드는 유지하고 options만 추가한다.
- 장비등록 캐시 API의 승인된 옵션 목록 형식은 변경하지 않는다.
- 신규 PUT만 추가하며 DB 스키마 migration은 예상하지 않는다.

## 6. 감사 로그와 외래키 주의사항

현재 CREATE TABLE 정의에는 equipments_audit_log.equipment_id가 equipments.id를 참조하지만, 연결 생성 시 foreign_keys를 명시적으로 활성화하지 않는다. 하드 삭제와 삭제 감사 이력을 동시에 유지하려면 외래키가 활성화된 환경에서도 모순이 없어야 한다.

- 운영 반영 전 실제 PRAGMA foreign_keys 및 외래키 정의를 확인한다.
- 외래키가 활성화되어 하드 삭제를 막는다면 이를 끄는 방식으로 해결하지 않는다.
- 운영 시험에서 실제 고아 외래키 4건과 제안 013 백업 실패가 확인되어 `003_Equipment_Audit_FK_and_Proposal013_Backup_Remediation_Plan.md`로 별도 분리했다.
- 감사 테이블 migration은 옵션 관리 구현에 자동 포함하지 않고 연결된 003 계획과 검증 절차를 따른다.

## 7. 테스트 계획

- 장비 1개가 연결된 노드의 equipment_count가 1인지 확인한다.
- 소유자와 관리자의 정상 삭제 후 equipments 행이 0이고 equipment_count도 0인지 확인한다.
- 권한 없는 사용자의 삭제 실패 후 행과 집계가 그대로인지 확인한다.
- 삭제 transaction 중 감사 기록 또는 DELETE가 실패하면 둘 다 rollback되는지 확인한다.
- 같은 장비를 두 번 삭제했을 때 성공으로 오인하지 않는지 확인한다.
- 장비 0·옵션 1 상태가 '옵션 잔존'으로 표시되고 장비 수로 오인되지 않는지 확인한다.
- 임시저장 장비가 별도 수치로 식별되는지 확인한다.
- 관리자 스냅샷을 재요청했을 때 삭제 직후 최신 값이 반환되는지 확인한다.
- foreign_keys ON/OFF 양쪽에서 정해진 삭제·감사 정책이 일관되는지 확인한다.
- 옵션 생성·수정에서 빈 이름, 과도한 이름, 비객체 specs, 동일 노드 중복 이름이 거부되는지 확인한다.
- 연결 장비 또는 임시저장이 하나라도 생긴 옵션은 동시 삭제 요청에서도 삭제되지 않는지 확인한다.
- 사용하지 않는 옵션 삭제 후 option_count가 감소하고 말단 노드 삭제 버튼 상태가 갱신되는지 확인한다.
- 승인 대기 옵션을 관리자 화면에서 임의 승인 상태로 바꿀 수 없는지 확인한다.
- 모바일에서는 옵션 목록과 버튼이 세로 배치되고, PC에서는 노드 맥락을 잃지 않는지 확인한다.

## 8. 수용 기준

- 성공 응답을 받은 장비 삭제는 DB와 노드 관리자 사용량에 즉시 동일하게 반영된다.
- equipment_count, draft_equipment_count, option_count의 의미가 화면에서 구분된다.
- 옵션이 남아 노드를 삭제할 수 없는 상황을 장비 잔존으로 잘못 설명하지 않는다.
- 권한·감사·rollback이 기존보다 약화되지 않는다.
- 운영 스키마에 없는 삭제 컬럼을 추정해 추가하지 않는다.
- 장비 삭제가 옵션이나 노드의 암묵적 연쇄 삭제를 일으키지 않는다.
- 관리자가 현재 노드 맥락에서 옵션을 조회·추가·수정하고, 미사용 옵션을 안전하게 삭제할 수 있다.
- 옵션 삭제 후 노드의 option_count와 삭제 가능 상태가 새로고침 없이 일치한다.

## 9. 중단 조건과 롤백

- 운영 DB 스키마·DATABASE_PATH·실행 commit이 확인되지 않으면 스키마 및 삭제 의미 변경을 중단한다.
- 기존 외부 클라이언트가 삭제 응답 형식에 의존한다면 신규 필드는 추가만 하고 기존 message를 유지한다.
- 옵션 API·집계·화면 변경은 기존 get_admin_snapshot, route, 템플릿 변경을 함께 되돌려 복구한다. 기존 옵션 데이터는 변경하지 않는다.
- 스키마 변경이 필요해지면 이 계획과 분리된 migration 승인 및 백업이 없이는 진행하지 않는다.
