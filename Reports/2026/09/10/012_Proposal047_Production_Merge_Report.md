---
artifact_id: REPORT-20260910-012
work_id: WORK-20260910-LINEUP-NODE-MANAGEMENT
created_at: 2026-09-10T18:40:06.684+09:00
related_artifacts:
  - ../../../../Tasks/2026/09/10/005_Proposal047_Production_Merge_Task.md
  - ../../../../Reports/2026/09/10/011_Proposal047_Production_Review_Report.md
---
# 제안 047 운영 소스 반영 결과

상태: 운영 소스 반영 완료. Linux 서비스 적용·브라우저 확인 미수행. commit·push 미수행.

## 반영

- app.py: 기존 node POST/PUT/DELETE를 Blueprint로 교체, 관리자 페이지 및 멱등 메뉴 migration 연결. 관리자 메뉴 순서 9, 기존 메뉴 순서 유지.
- utils/lineup_node_service.py: 생성·수정·삭제·관리자 목록 서비스. 정수 입력, JSON 객체, 승인 상태, 중복, 순환, 부모 조합, 최대 깊이, 자손 깊이 보정, 사용 중 삭제 제한.
- utils/lineup_routes.py: 로그인·관리자·CSRF 적용. BEGIN IMMEDIATE 이후 중복 검사와 변경을 수행하고 감사 로그도 같은 DB 연결에서 기록하여 별도 연결 잠금 충돌 방지.
- templates/index.html 및 static/js/lineup_registration.js: 빈 분류/기존 노드 아래 추가 패널, 생성 후 경로 재선택, 노드 생성 중 장비 저장 차단, 필터 변경 시 이전 옵션 초기화. 부모 노드에 옵션과 자식이 공존해도 기존 옵션을 선택 가능.
- templates/lineup_management.html: 상태·사용량·트리 관리, 승인 대기 편집/삭제 제한, 순환/고립 노드 표시 보호.

## 검증

- 운영 서비스 모듈 대상 메모리 SQLite 시험 13건 통과. 새 검증은 소수·bool ID, JSON 비객체, PENDING 변경 제한, 실패 이동의 기존 데이터 보존 포함.
- 운영 등록 템플릿 IIFE를 메모리 DOM에서 실행하는 상태 전이 시험 3건 통과. 빈 루트 생성 진입, 생성 노드 재선택·옵션 귀속·busy 잠금, 자식 있는 부모의 옵션 선택·분류 변경 초기화 확인.
- Python 구문 검사(app.py 및 두 모듈), JavaScript 구문 검사 통과.
- Staging 초기 단위 9건·정적 계약 3건도 보완 시 통과했으며, 운영 회귀 테스트는 tests/test_proposal047_nodes.py 및 tests/test_proposal047_registration.mjs에 보존.
- 실제 Flask 서버·운영 DB·Linux 서비스는 실행하거나 변경하지 않았음. 메모리 DOM 검증은 실브라우저 시험을 대체하지 않음.

## 보존 및 후속

해당 047 Staging 소스는 운영 파일과 영구 tests로 옮긴 후 정리했다. 통합 명세는 docs/proposal047-operation.md에 보존했다. 다른 Staging 작업과 기존 Antigravity 변경은 유지했다.

047은 제안·로드맵 원장 및 미구현 목록에서 '운영 소스 반영 완료 / Linux 서비스 적용·사용자 확인 대기'로 유지한다. 013 상태·시험은 변경하지 않았다. 기존 옵션 승인 정책·임시저장 fallback·마스터 삭제 문제는 010 보고서의 별도 후속 항목으로 유지한다.

복귀는 이번 운영 소스 변경을 한 단위로 역패치한다. 메뉴 추가는 기존 레코드를 덮어쓰지 않으며 DB 스키마·기존 데이터 삭제가 없다. Linux 배포 이후에는 서버의 승인 commit 일치와 서비스 상태 확인이 필요하다.
