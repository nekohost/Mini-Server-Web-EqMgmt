# [개선계획 보고서] 마스터 데이터 조회 정합성 복구 및 전자결재 연동 파이프라인 구축

작성일: 2026-09-07  
상태: 검토 완료, 승인 대기  
대상: `app.py` (마스터 관리 API, 장비 등록 API, 전자결재 처리 API), `templates/master_management.html`, `templates/index.html`, `templates/approvals.html`

---

## 1. 현행 확인 및 문제 정의

현재 시스템에서 마스터 데이터(카테고리/제조사) 관리와 장비 등록, 전자결재 시스템 사이에 세 가지 중대한 단절 및 결함이 확인되었습니다.

### 1) 마스터 데이터 관리 화면 조회 버그 (`c.id`, `m.id` 부재)
- **증상**: 관리자 센터의 [마스터 데이터 관리] 화면에서 신규 카테고리나 제조사를 등록하면 추가는 성공(DB에 저장)하지만, 목록에는 "등록된 데이터가 없습니다"로 표시됩니다. 동일 명칭으로 재등록을 시도하면 중복 에러가 발생합니다.
- **원인**: `app.py`의 `get_or_create_master_management_item()` (`GET /api/master/manage/<target_type>`) 쿼리에서 `c.id`, `m.id`를 조회하고 조인합니다. 그러나 실제 DB 테이블(`categories`, `manufacturers`)의 기본키는 `CategoryId`, `ManufacturerId`이므로, `no such column: c.id` SQL 에러가 발생하여 조회가 실패합니다.

### 2) 장비 등록 화면 세션 캐시 고착화
- **증상**: 마스터 데이터가 추가되어도 장비 등록 화면(`index.html`)의 카테고리/제조사 드롭다운에 즉시 반영되지 않습니다.
- **원인**: `templates/index.html`에서 브라우저의 `sessionStorage('nodeCache_v2')`에 카탈로그 트리를 영구 캐싱하며, 마스터 데이터 변경 시 이를 무효화하는 트리거가 없습니다.

### 3) 장비 등록 화면 '기타' 입력 시 전자결재 파이프라인 단절
- **증상**: 장비 등록 모달에서 `➕ 기타 (직접 입력...)`를 선택하고 신규 분류명을 입력해도 결재 시스템으로 넘어가지 않고 [저장하기] 버튼이 잠겨(disabled) 진행할 수 없습니다.
- **원인**:
  1. UI 레벨: 3-Tier 가변 카탈로그 노드 및 옵션이 선택되지 않았다는 이유로 `updateSubmitLockState()`가 [저장하기] 버튼을 강제 잠금 처리합니다. 결재 상신 버튼도 없습니다.
  2. 백엔드 레벨: `POST /api/equipment` (`add_equipment()`)에 프론트엔드가 보낸 `RootData`(`__custom__`)를 읽어 `approval_requests` 테이블에 결재 요청을 등록하는 코드가 전혀 존재하지 않습니다. 제안-027(구 텍스트 기반 결재)에서 제안-036(3-Tier 트리)으로 개편되는 과정에서 파이프라인이 유실되었습니다.

---

## 2. 개선 목표

1. **마스터 데이터 관리 조회 정상화**: 올바른 PK 컬럼(`CategoryId`, `ManufacturerId`)으로 쿼리를 정정하여 등록된 카테고리/제조사 목록과 연결 장비 수를 정확히 표출합니다.
2. **장비 등록 화면 캐시 실시간 동기화**: 마스터 변경 발생 시 캐시를 즉시 무효화하고, 장비 등록 모달 진입 시 최신 데이터를 보장합니다.
3. **'기타 입력 → 전자결재 상신' 원스톱 파이프라인 구축**: 사용자가 장비 등록 시 신규 카테고리/제조사를 '기타'로 직접 입력하면, 장비는 임시저장(`is_draft = 1`)되고 분류 등록 건은 전자결재함(`approval_requests`)에 자동 상신되는 통합 플로우를 완성합니다.

---

## 3. 세부 설계 및 구현 내용

### 1단계: 마스터 데이터 관리 API 스키마 정합성 복구 (`app.py`)

- `get_or_create_master_management_item(target_type)`의 `GET` 쿼리 수정:
  ```sql
  -- 카테고리 조회
  SELECT c.CategoryId as CategoryId, c.CategoryId as id, c.Name as Name, c.NameKo as NameKo, c.NameEn as NameEn, 
         c.IsApproved as IsApproved, c.CreatedAt as CreatedAt,
         COUNT(e.id) as UsageCount
  FROM categories c
  LEFT JOIN lineup_nodes node ON c.CategoryId = node.category_id
  LEFT JOIN equipment_options opt ON node.id = opt.lineup_node_id
  LEFT JOIN equipments e ON opt.id = e.option_id
  GROUP BY c.CategoryId
  ORDER BY c.CategoryId DESC

  -- 제조사 조회
  SELECT m.ManufacturerId as ManufacturerId, m.ManufacturerId as id, m.Name as Name, m.NameKo as NameKo, m.NameEn as NameEn, 
         m.IsApproved as IsApproved, m.CreatedAt as CreatedAt,
         COUNT(e.id) as UsageCount
  FROM manufacturers m
  LEFT JOIN lineup_nodes node ON m.ManufacturerId = node.manufacturer_id
  LEFT JOIN equipment_options opt ON node.id = opt.lineup_node_id
  LEFT JOIN equipments e ON opt.id = e.option_id
  GROUP BY m.ManufacturerId
  ORDER BY m.ManufacturerId DESC
  ```
- `try-except` 예외 블록을 보강하여 DB 오류 시 명확한 에러 JSON(`{"success": False, "message": "..."}`)을 반환하도록 보호합니다.

### 2단계: 장비 등록 화면 캐시 무효화 및 카탈로그 자동 연계 (`index.html`, `master_management.html`)

1. **캐시 무효화 트리거**:
   - `templates/master_management.html`에서 항목 추가/수정/통폐합/삭제 성공 시 `sessionStorage.removeItem('nodeCache_v2')`를 실행합니다.
2. **장비 등록 모달 캐시 갱신 보장**:
   - `templates/index.html`에서 신규 장비 등록 모달(`openAddModal`)을 열 때 `window.LineupApp.init(true)`(강제 새로고침)을 호출하여 항상 최신 마스터 데이터를 반영합니다.

### 3단계: '기타' 입력 시 임시 장비 저장 및 전자결재 자동 상신 파이프라인 (`index.html`, `app.py`)

1. **프론트엔드 UI 상태 전환 (`index.html`)**:
   - 사용자가 `CategorySelect` 또는 `ManufacturerSelect`에서 `__custom__`을 선택하고 직접 입력창에 텍스트를 입력한 경우:
   - `updateSubmitLockState()`에서 잠금을 해제하고, [저장하기] 버튼 문구를 **[신규 분류 승인 요청 및 임시등록]**으로 변경합니다.
   - 안내 문구를 `ℹ️ 신규 분류가 포함되어 있습니다. 등록 시 전자결재 승인 요청이 함께 상신되며, 관리자 승인 전까지 임시저장 상태로 보관됩니다.`로 표시합니다.
2. **백엔드 장비 등록 파이프라인 (`app.py` `add_equipment`)**:
   - `RootData.categoryId === '__custom__'` 또는 `RootData.manufacturerId === '__custom__'` 감지 시:
     1. `categories` / `manufacturers` 테이블에 해당 명칭을 `IsApproved = 0` (미승인 상태)으로 삽입.
     2. 해당 미승인 분류 하위에 기본 라인업 노드(`lineup_nodes`, `status = 'PENDING'`) 및 기본 옵션(`equipment_options`, `status = 'PENDING'`) 자동 연계 생성.
     3. `approval_requests` 테이블에 `RequestType = 'ADD_CATEGORY'` (또는 `ADD_MANUFACTURER`) 결재 상신 레코드 자동 적재 (`RequesterId`, `RequestDataJSON`, `Status = 'PENDING'`).
     4. 장비 레코드는 `equipments` 테이블에 `is_draft = 1` (임시저장 상태)로 저장.
     5. 응답 메시지로 `신규 분류 등록 요청이 전자결재함에 상신되었으며, 장비는 임시저장되었습니다. 관리자 승인 후 정식 활성화됩니다.` 반환.
3. **관리자 전자결재 처리 연동 (`app.py` `process_approval`, `approvals.html`)**:
   - 관리자가 전자결재함에서 해당 건을 **[승인]** 시:
     - 카테고리/제조사 `IsApproved = 1` 업데이트
     - 하위 라인업 노드 및 옵션 `status = 'APPROVED'` 업데이트
     - 연결된 임시 장비 `is_draft = 0` 정식 전환
   - 관리자가 **[반려]** 시:
     - 대체 분류 지정 여부에 따라 장비 연결 분류를 기존 승인 항목으로 변경하거나 반려 상태 유지.

---

## 4. 변경 대상 파일 매트릭스

| 파일 | 변경 위치 | 변경 목적 |
| :--- | :--- | :--- |
| `app.py` | L4158~4186 (`get_or_create_master_management_item`) | PK 컬럼명(`CategoryId`, `ManufacturerId`) 정정 및 `try-except` 보강 |
| `app.py` | L3790~3880 (`add_equipment`) | `RootData` 커스텀 명칭 감지 시 `approval_requests` 상신 및 임시 노드/장비 생성 로직 추가 |
| `app.py` | L3644~3694 (`process_approval`) | 승인 시 연계된 `lineup_nodes`, `equipment_options`, `equipments.is_draft` 일괄 승인 처리 동기화 |
| `templates/master_management.html` | L170~280 (JS 함수부) | 마스터 데이터 변경 시 `sessionStorage` 캐시 무효화 코드 추가 |
| `templates/index.html` | L268~308, L620~650 (JS 함수부) | 커스텀 분류 입력 시 잠금 해제, [승인요청 및 임시등록] 버튼 전환 및 모달 열기 시 캐시 강제 새로고침 |

---

## 5. 단계별 검증 계획 (Validation 1~8단계)

1. **거버넌스 검증**: `governance-tool.mjs validate` 40노드 무결성 유지.
2. **사용자 의도 달성도**:
   - 마스터 관리 화면에서 추가한 카테고리/제조사가 목록에 즉시 나타나는가?
   - 장비 등록 모달에 방금 추가한 카테고리/제조사가 드롭다운에 즉시 반영되는가?
   - '기타' 입력 후 등록 시 [전자결재함]에 정확히 결재 문서가 생성되는가?
3. **정적 논리 검증**: SQL 문법 검증, Node.js 기반 JS 구문 검증, SQLite 트랜잭션 원자성 확인.
4. **운영 영향도**: 기존 정규 카탈로그 등록 프로세스(`isNew=false`)에 부작용이 없는지 확인.
5. **보안 및 엣지 케이스**: 권한 없는 사용자의 승인 API 호출 차단, 악의적 긴 문자열 입력 방어.
6. **롤백 전략**: Git 커밋 단위 격리 및 DB 역마이그레이션 불필요(기존 스키마 내 컬럼 및 상태 플래그 활용).
7. **휴먼 에러 방지**: 승인 전 장비가 일반 공개(`is_public=1`)되지 않도록 `is_draft=1` 강제 락 처리.
8. **AI 메타 거버넌스**: Staging 브랜치/환경에서 우선 검증 후 운영 반영.

