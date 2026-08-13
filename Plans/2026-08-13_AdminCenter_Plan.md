# [제안-035] 관리자 전용 메뉴 허브(Admin Center) 및 계층형 권한 시스템 영구 기획서 (2026-08-13_AdminCenter_Plan.md)

## 1. 개요 및 배경
본 문서는 제안-035 '관리자 전용 메뉴 허브(Admin Center) 및 계층형 권한 시스템' 기능의 영구 보존용 기획서입니다. (Rule.md 제7-2조 및 제7-3조 준수)

## 2. 핵심 요구사항 및 아키텍처
1. **N-Depth 계층형 메뉴 데이터베이스 스키마**:
   - `menus` 테이블에 `ParentMenuCode` 및 `SortOrder` 추가.
   - 포털 메뉴(`ParentMenuCode IS NULL`)와 서브 메뉴(예: `ParentMenuCode = 'admin_center'`)의 계층적 연관관계 구축.
2. **백엔드 무결성 조상 검증 로직 (Recursive Ancestor Validation)**:
   - 프론트엔드가 조작되거나 해킹된 악의적 POST 패킷 유입 시, 하위 메뉴는 켜져 있는데 상위 부모 메뉴가 꺼져 있는 무순서/불법 상태를 재귀 스캔하여 400 Bad Request 리턴.
   - `@csrf_required` 데코레이터 필수 적용.
3. **프론트엔드 상태(State) 기반 재귀 렌더링**:
   - 체크박스 DOM 직접 수정을 배제하고 원본 데이터 배열(`currentPermissions`)을 상태로 관리.
   - 자식 노드 활성화 시 모든 상위 조상 노드 자동 켜짐(`togglePermission`).
   - 하위 자식이 켜져 있는 상위 노드는 체크 해제 불가(`disabled=true`, `hasAllowedDescendant`).
   - `renderTree` 재귀 함수로 N-Depth 트리를 무한 계층으로 시각적 렌더링.
4. **관리자 센터 분리 페이지 (`/admin_center`)**:
   - 포털 화면에는 상위 노드 `admin_center` 카드가 표시되며, 기존 4개 관리자 메뉴(`permissions`, `audit_logs`, `users_management`, `master_management`)는 포털에서 숨김.
   - 관리자 센터 클릭 시 `/admin_center`로 이동하여 자식 메뉴들을 동적 렌더링.

## 3. 구현 내역 스니펫 상세
(기획서 implementation_plan.md 및 Staging 소스 코드 참조)
