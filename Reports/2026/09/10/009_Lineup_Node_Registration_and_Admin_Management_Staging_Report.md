---
artifact_id: REPORT-20260910-009
work_id: WORK-20260910-LINEUP-NODE-MANAGEMENT
created_at: 2026-09-10T17:24:20.609+09:00
related_artifacts:
  - ../../../../Plans/2026/09/10/003_Lineup_Node_Registration_and_Admin_Management_Plan.md
  - ../../../../Tasks/2026/09/10/003_Lineup_Node_Registration_and_Admin_Management_Task.md
  - ../../../../Reports/2026/09/10/008_Lineup_Node_Registration_and_Admin_Management_Validation_Report.md
---
# [Staging 결과 보고서] 장비등록 라인업 노드 추가 및 관리자 노드 관리

> 2026-09-10 귀속 검토: **[제안-047]**로 별도 등록. 이 문서의 완료 표기는 Staging 구성요소 후보 작성과 단위·정적 검증에 한정한다. 기존 LineupApp 연결·생성 경로 재선택·메뉴 및 route 통합과 화면 전체 시험은 남아 있으며 운영 병합 준비 완료를 뜻하지 않는다. [검토 근거](../../../../Reports/2026/09/10/010_Lineup_Node_Proposal_Classification_Report.md).

- 작성일: 2026-09-10
- `work_id`: `WORK-20260910-LINEUP-NODE-MANAGEMENT`
- 판정: **Staging 후보 구현 및 격리 검증 완료**
- 운영 반영: **미수행**

## 1. 결론

장비등록 중 노드를 추가할 수 없는 직접 원인은 데이터 모델이나 API 부재가 아니라 `templates/index.html`의 UI 연결 누락이다. 기존 `POST /api/lineup_node`는 구현되어 있으나 장비등록 JavaScript가 한 번도 호출하지 않으며, 루트 노드가 없으면 관리자 문의 문구만 출력한다.

관리자 센터에는 카테고리·제조사 마스터 관리만 있고 라인업 노드 관리 메뉴·페이지·전체 상태 조회 API가 없다. 또한 기존 노드 API에는 계층 무결성을 훼손할 수 있는 검증 공백이 있어 UI만 연결하면 안 된다. 이 결론에 따라 UI와 서버 불변식을 함께 다루는 후보를 Staging에 완성했다.

## 2. 현행 구조와 확인된 결함

| 영역 | 현행 | 영향 | Staging 조치 |
| --- | --- | --- | --- |
| 데이터 모델 | `categories → lineup_nodes → equipment_options → equipments` | 요구사항을 수용 가능 | 스키마 변경 없음 |
| 장비등록 UI | 기존 노드 선택만 가능, 빈 트리는 중단 | 새 모델 등록 불가 | 루트·하위 노드 추가 모듈 |
| 사용자 승인 | 생성 API는 admin=APPROVED, user=PENDING | 정책 재사용 가능 | 승인 상태별 즉시 선택/대기 분기 |
| 관리자 관리 | 노드 전용 메뉴·화면·전체 조회 없음 | 운영자가 트리를 관리할 수 없음 | 관리자 트리 화면·snapshot API 후보 |
| 생성 무결성 | 부모와 요청 category/manufacturer 불일치 허용 | 교차 루트 오염 가능 | 부모 조합·승인 상태 재검증 |
| 이동 무결성 | 이동 루트만 depth 갱신 | 자손 depth 불일치 | 서브트리 전체 depth 보정 |
| 중복·최대 깊이 | 이동 대상 중복과 서브트리 전체 깊이 검사 부족 | 충돌·50단계 초과 가능 | 대소문자 무시 중복·최심부 검사 |
| 삭제·오류 | 없는 노드도 성공 가능, 내부 예외 문자열 노출 | 오인·정보 노출 | 404와 일반화된 500 응답 |

## 3. Staging 산출물

- `Staging/Lineup_Node_Management/lineup_node_service.py`
  - Flask와 분리된 생성·이동·삭제·관리자 snapshot 서비스
  - 실제 부모 경로 기반 깊이 계산, 순환·교차 루트·중복·최대 깊이 방어
- `Staging/Lineup_Node_Management/flask_routes_candidate.py`
  - 로그인·관리자·CSRF·transaction rollback을 포함한 route adapter
- `Staging/Lineup_Node_Management/static/lineup_registration.js`
  - 장비등록의 루트/하위 노드 생성 패널, 중복 요청 잠금, APPROVED/PENDING 분기
- `Staging/Lineup_Node_Management/templates/lineup_management.html`
  - 카테고리·제조사 필터, 상태 요약, 반응형 트리, 추가·수정·이동·삭제 UI
  - API 문자열은 `textContent`/DOM API로 표시해 동적 `innerHTML` 주입을 사용하지 않음
- `Staging/Lineup_Node_Management/INTEGRATION.md`
  - 메뉴 migration, 페이지 route, 기존 `LineupApp` 연결, 운영 통합 후 시험 항목
- `Staging/Lineup_Node_Management/tests/`
  - 메모리 SQLite 단위 테스트와 정적 UI/API 계약 테스트

## 4. 검증 결과

운영 앱을 실행하지 않고 운영 DB를 열지 않은 상태에서 다음을 확인했다.

- Python 서비스 단위 테스트: **9/9 통과**
  - 관리자 즉시 승인
  - 일반 사용자 PENDING 및 approval request
  - 부모 조합 불일치 차단
  - 대소문자 변형 루트 중복 차단
  - 서브트리 이동 시 전 자손 depth 보정
  - 순환·교차 루트 이동 차단
  - 51단계 생성 차단
  - 자식·옵션·미존재 삭제 차단
  - 관리자 snapshot 사용량 집계
- Node 정적 계약 테스트: **3/3 통과**
- Python `py_compile`: **통과**
- 장비등록 JavaScript `node --check`: **통과**
- 관리자 템플릿 내 script `new Function` 구문 검사: **통과**
- governance validate v1.4.0: **errors 0, warnings 0**
- `git diff --check`: 공백 오류 없음. 기존 Antigravity 3개 파일의 CRLF 안내만 유지됨.

## 5. UX 결정

- 빈 카테고리·제조사 조합에는 막힌 안내 대신 “최상위 노드 추가” 패널을 표시한다.
- 기존 각 단계에서는 “새 노드” 진입점을 제공한다.
- 관리자가 만든 APPROVED 노드는 캐시를 갱신하고 생성 경로를 다시 선택해 옵션 입력으로 이어간다.
- 일반 사용자가 만든 PENDING 노드는 승인 전 정식 장비의 옵션 부모로 사용하지 않고 승인 대기임을 명시한다.
- 관리자 화면 삭제 버튼은 자식이나 옵션이 있으면 비활성화하되 서버에서 동일 조건을 다시 검사한다.

## 6. 범위 밖에서 추가 발견한 데이터 무결성 위험

이번 Staging에 섞지 않고 후속 작업으로 분리할 항목이다.

1. `add_equipment()`와 `update_equipment()`의 신규 옵션은 일반 사용자도 APPROVED로 생성되어 `/api/equipment_option`의 PENDING 정책과 일치하지 않는다.
2. 임시저장 fallback은 첫 번째 임의 옵션 또는 존재하지 않을 수 있는 `option_id = 1`을 사용할 수 있다.
3. 마스터 일괄 삭제는 NOT NULL인 `lineup_nodes.category_id/manufacturer_id`를 NULL로 갱신하려 한다.

운영 병합 전에 위 항목을 별도 데이터 무결성 계획으로 검토하는 것이 안전하다.

## 7. 상태 경계

- Proposal 046 점검 모드는 사용자 시험 결과에 따라 구현 완료로 취급한다.
- Proposal 013 DB 백업·복원은 사용자 시험 전이므로 미검증 상태를 유지한다.
- 이번 변경은 Staging에만 존재한다. 운영 `app.py`, `templates/`, `static/`, 실제 DB와 메뉴 데이터는 변경하지 않았다.
- 다음 단계는 Staging diff 검토 후 운영 통합 승인과 별도 임시 DB 통합 시험이다.
