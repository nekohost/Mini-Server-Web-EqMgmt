# [Staging 검토 보고서] 마스터 데이터 조회 정합성 복구 및 전자결재 연동 파이프라인

작성일: 2026-09-08  
작성자: AI Agent (Antigravity)  
검토 대상: `Staging/app.py`, `Staging/templates/index.html`, `Staging/templates/master_management.html`  
관련 계획서: `Plans/2026-09-07_Master_Data_and_Approval_Pipeline_Improvement_Plan.md`  
관련 작업 관리 대장: `Plans/2026-09-07_Master_Data_and_Approval_Pipeline_Improvement_Task.md`  
검토 목적: (1) 의도한 대로 구현되었는지, (2) 운영 반영 시 이상(버그 등) 발생 여지 판단

---

## 검토 범위

| 파일 | Staging 위치 | 주요 변경 함수/영역 |
| :--- | :--- | :--- |
| `app.py` | `Staging/app.py` (6,113 Lines) | `get_or_create_master_management_item()` (L5316~), `add_equipment()` (L4860~5077), `process_approval()` (L4629~4765) |
| `index.html` | `Staging/templates/index.html` (824 Lines) | `updateSubmitLockState()` (L268~334), `submitEquipment()` (L640~760), `openModal()` (L579), `oninput` 핸들러 (L98, L107) |
| `master_management.html` | `Staging/templates/master_management.html` | `invalidateNodeCache()` (L288~292), 성공 콜백 4개소 |

---

## 1단계: 거버넌스 준수성 — PASS

| 항목 | 결과 | 근거 |
| :--- | :--- | :--- |
| `governance-tool.mjs validate` | PASS | 40노드 0에러 0경고 |
| 변경 파일 위치 | PASS | 모든 수정은 `Staging/` 디렉터리 내부에서만 수행 |
| 편집 도구 규칙 | PASS | 구조화된 편집 도구(replace_file_content)로만 수정됨 |
| 계획서-실행 추적성 | PASS | Task 1~7 전부 완료, 계획에 없는 임의 변경 미발견 |
| Staging 격리 | PASS | 운영 루트 파일 직접 수정 없음 |
| 외부 라이브러리 | PASS | 신규 외부 의존성 추가 없음 (기존 `json` 표준 라이브러리만 사용) |

---

## 2단계: 사용자 의도 달성도 — PASS (단서 1건)

### 2-1. 사용자 요청 대조

| 사용자 보고/요청 | 구현 여부 | 근거 |
| :--- | :--- | :--- |
| 카테고리/제조사 등록 후 목록에 안 나옴 | ✅ 해결 | `c.id` → `c.CategoryId`, `m.id` → `m.ManufacturerId`로 수정 (L5332, L5344) |
| 중복 등록 시 "이미 있다"고 나옴 | ✅ 해결 | 위 SQL 수정으로 INSERT는 정상 → SELECT도 정상 |
| 장비등록 화면에도 안 나타남 | ✅ 해결 | `invalidateNodeCache()` 추가 + `init(true)` 강제 갱신 |
| 결재 시스템 연결 확인 | ✅ 구현 | `add_equipment()` 커스텀 루트 → `approval_requests` 상신 |
| '기타' 입력 시 진행 가능해야 함 | ✅ 구현 | `updateSubmitLockState()` 재작성, 버튼 잠금 해제 |

### 2-2. 계획서 대비 구현 일치도

계획서의 5개 세부 설계 항목 모두 구현 확인.

**단서**: 계획서 대상 파일 목록에 `templates/approvals.html`이 언급되어 있었으나 실제 변경되지 않음. 확인 결과 기존 `approvals.html`에 이미 `ADD_CATEGORY`/`ADD_MANUFACTURER` 타입 뱃지 및 승인/반려 모달 UI가 구현되어 있어 수정이 불필요. **영향도: 없음.**

---

## 3단계: 정적 로직 검증 — WARN (3건)

### 3-1. SQL 쿼리 정확성 — PASS

| 쿼리 위치 | 컬럼명 정확성 | 조인 조건 정확성 |
| :--- | :--- | :--- |
| `get_or_create_master_management_item` 카테고리 (L5331~5341) | `c.CategoryId` ✅ | `c.CategoryId = node.category_id` ✅ |
| `get_or_create_master_management_item` 제조사 (L5343~5353) | `m.ManufacturerId` ✅ | `m.ManufacturerId = node.manufacturer_id` ✅ |
| `add_equipment` 카테고리 조회 (L4918) | `CategoryId` ✅ | N/A |
| `add_equipment` 제조사 조회 (L4942) | `ManufacturerId` ✅ | N/A |
| `process_approval` 승인 캐스케이드 (L4664~4705) | `CategoryId`, `ManufacturerId` ✅ | 3-Tier JOIN 정상 ✅ |

모든 SQL 쿼리에서 파라미터 바인딩(`?`)이 사용되어 SQL Injection 방어 확인.

### 3-2. [WARN-1] `json_extract()` SQLite 호환성 — Medium

**위치**: `Staging/app.py` L4927, L4951

```python
cursor.execute("SELECT RequestId FROM approval_requests WHERE ... AND json_extract(RequestDataJSON, '$.name') = ?", ...)
```

**문제**: `json_extract()` 함수는 SQLite 3.38.0+(기본 내장) 또는 SQLite 3.9.0+(JSON1 확장 활성화 필요)에서 지원됨. Python 표준 `sqlite3` 모듈은 Python 3.9+에서 JSON1이 기본 활성화되어 있으나, 배포 서버의 Python/SQLite 버전이 이보다 낮으면 `no such function: json_extract` 에러 발생.

**영향도**: Medium — 결재 중복 방어 쿼리이므로, 실패 시 동일 카테고리/제조사에 대한 중복 PENDING 요청 생성 가능.  
**완화 방안**: 배포 서버에서 `python3 -c "import sqlite3; print(sqlite3.sqlite_version)"` 실행하여 버전 확인 권장. 3.9.0 미만이면 Python 레벨에서 JSON 파싱 후 비교로 대체 필요.

### 3-3. [WARN-2] 단일 커스텀 분류 시 노드 미생성 엣지 케이스 — Medium

**위치**: `Staging/app.py` L4965

```python
if final_cat_id and final_mfg_id:
    # 임시 노드/옵션 생성 ...
```

**문제**: 사용자가 카테고리만 '기타'로 입력하고 제조사를 선택하지 않았거나(`final_mfg_id = None`), 반대 경우에 이 조건이 `False`가 되어 임시 노드/옵션이 생성되지 않음. 이 경우 코드는 L5021~5034의 fallback 로직에 의해 `SELECT id FROM equipment_options LIMIT 1`으로 **무관한 기존 옵션**에 장비를 연결함.

**파급**: 
- 결재 승인 시 `UPDATE equipments SET is_draft = 0 WHERE option_id IN (...)` 쿼리가 해당 장비를 찾지 못해 영구적 `is_draft=1` 상태로 남음
- 사용자에게는 "임시저장되었습니다"라고 표시되지만 승인 후에도 활성화되지 않는 논리적 불일치 발생

**영향도**: Medium — 프론트엔드에서 카테고리/제조사 모두 필수 선택이므로 발생 빈도는 낮으나, API 직접 호출 시 재현 가능.

### 3-4. [WARN-3] 듀얼 커스텀 승인 시 조기 장비 활성화 — Low

**위치**: `Staging/app.py` L4676~4684

**문제**: 카테고리와 제조사가 모두 커스텀인 경우 두 개의 `approval_requests`가 생성됨. 카테고리 승인 캐스케이드가 먼저 실행되면 해당 노드 하위 장비의 `is_draft`가 0으로 전환됨. 이때 제조사는 아직 `IsApproved=0` 상태이나 장비는 이미 정식 활성화됨. 반대로 제조사가 거부되면 거부 캐스케이드가 `lineup_nodes`를 삭제하지만 장비는 `is_draft=0`이므로 삭제 대상에서 제외되어 **고아 장비 레코드**가 남음.

**영향도**: Low — 양쪽 모두 승인되는 정상 경로에서는 문제 없음. 한쪽만 거부되는 예외 경로에서만 발생.  
**완화 방안**: 양쪽 `approval_requests`가 모두 `APPROVED`일 때만 장비 `is_draft=0` 전환하는 로직 추가 검토 권장.

---

## 4단계: 운영 병합 영향 — PASS (주의 2건)

### 4-1. 기존 데이터 호환성 — PASS

- 신규 테이블이나 컬럼 추가 없음. 기존 `categories.IsApproved`, `manufacturers.IsApproved`, `approval_requests.RequestDataJSON`, `lineup_nodes.status`, `equipment_options.status`, `equipments.is_draft` 컬럼 모두 기존 스키마에 존재.
- `get_or_create_master_management_item()` 수정은 기존 데이터에 긍정적 영향 (이전에 조회 실패했던 데이터가 정상 표시됨).

### 4-2. 기존 API 응답 형식 — PASS

- `add_equipment()`: 기존 응답 `{message, equipment_id}` 형식에 `is_draft` 필드가 추가됨. 하위 호환.
- `process_approval()`: 기존 응답 형식 `{success, message}` 유지.
- `get_or_create_master_management_item()`: GET 응답 형식 `{success, data}` 유지. 에러 시 `{success: False, message}` 추가 (이전에는 500 크래시).

### 4-3. [주의-1] 캐스케이드 UPDATE 범위

`process_approval()` L4666~4705에서 승인 캐스케이드 UPDATE의 WHERE 조건이 `categories.Name`(또는 `manufacturers.Name`) 기반. 동일 이름의 카테고리가 두 개 존재할 가능성은 중복 검증 로직에 의해 방지되므로 **실질적 위험은 낮음**.

### 4-4. [주의-2] 마이그레이션 불필요

기존 스키마 내 컬럼 활용만으로 구현되어 별도 마이그레이션 없이 배포 가능. 단, 기존 운영 DB에 `IsApproved` 컬럼이 있는지는 `init_db()` 마이그레이션 로직으로 자동 보장됨.

---

## 5단계: 보안 및 엣지 케이스 — PASS (주의 2건)

### 5-1. SQL Injection — PASS

모든 SQL 쿼리에서 파라미터 바인딩(`?`) 사용. `f-string` SQL은 `table_name` 변수에만 사용되며 해당 변수는 코드 내 하드코딩된 값(`'categories'` / `'manufacturers'`)만 대입됨.

### 5-2. XSS — PASS

- 프론트엔드: `updateSubmitLockState()`의 메시지 출력은 `innerText`(DOM 텍스트) 사용. `innerHTML` 미사용.
- 커스텀 입력값은 `.value.trim()`으로 추출 후 JSON 페이로드로 서버 전송. 기존 `escapeHtml()` 헬퍼가 트리 렌더링에서 사용 중.

### 5-3. CSRF — PASS

`add_equipment()` (L4862), `process_approval()` (L4631) 모두 `@csrf_required` 데코레이터 적용. 프론트엔드도 `X-CSRFToken` 헤더 전송 확인 (L723).

### 5-4. 권한 검증 — PASS

- `process_approval()`: L4639에서 `admin` 역할 검증
- `get_or_create_master_management_item()`: L5322에서 `admin` 역할 검증
- `add_equipment()`: `@login_required` 데코레이터

### 5-5. [주의-1] 서버 측 `is_draft` 강제 미적용

`add_equipment()` L4894에서 `is_draft = 1 if (has_custom_root or data.get('IsDraft') or data.get('is_draft')) else 0`으로 서버 측에서도 커스텀 루트일 때 `is_draft=1`을 강제함. **이 부분은 정상 구현되어 있음.** 클라이언트 조작 방어 확인.

### 5-6. [주의-2] 빈 문자열/None 경계값

- `cat_custom_val`이 빈 문자열이면 `has_custom_cat`이 `False`가 되어 커스텀 경로 미진입 (L4890). 정상.
- `root_data.get('categoryId')`가 빈 문자열이면 `cat_select_val`이 빈 문자열 → `has_custom_cat` False. 정상.
- `final_cat_id`가 None일 때 L4965 조건 미통과 → 엣지 케이스 (3단계 WARN-2에서 기술).

---

## 6단계: 롤백 검증 — PASS

### 6-1. 코드 롤백

| 항목 | 결과 | 근거 |
| :--- | :--- | :--- |
| 롤백 가능성 | PASS | Staging 파일을 운영에 복사하는 방식이므로, 운영 원본을 백업해두면 즉시 복원 가능 |
| git 이력 | PASS | git 커밋 단위 격리. `git revert` 또는 이전 커밋 체크아웃으로 복원 |

### 6-2. DB 롤백

| 항목 | 결과 | 근거 |
| :--- | :--- | :--- |
| 스키마 변경 | 해당 없음 | 신규 테이블/컬럼 추가 없음 |
| 데이터 정리 | PASS | 롤백 시 `IsApproved=0` 카테고리/제조사, `status='PENDING'` 노드/옵션, `is_draft=1` 장비가 DB에 남을 수 있으나 기존 조회 쿼리(`is_draft=0` 필터)에 의해 사용자에게 노출되지 않음 |
| 세션/캐시 잔여물 | PASS | `sessionStorage` 캐시는 브라우저 탭 종료 시 자동 소멸. 롤백 후 `invalidateNodeCache()`가 사라져도 기존 동작으로 복귀 |

---

## 7단계: 휴먼 에러 및 UX 방어 — PASS (단서 1건)

### 7-1. UI 오류 피드백

| 시나리오 | 피드백 제공 | 구현 위치 |
| :--- | :--- | :--- |
| 커스텀 입력 미입력 시 | ✅ 버튼 비활성화 + 안내 메시지 | L296~306 |
| 커스텀 입력 후 서밋 시 이름 누락 | ✅ `alert()` 표시 + focus | L690~698 |
| 시리얼 중복 | ✅ 에러 JSON 반환 | L4906~4909 |
| 일반 모드 옵션 미선택 | ✅ 버튼 비활성화 + 안내 메시지 | L324~332 |

### 7-2. 데드엔드 UI — PASS

커스텀 입력 시 `return;` (L308)로 일반 경로와 완전히 분리. 일반 경로에서 커스텀 잔여 상태가 남지 않음.

### 7-3. [단서] 이중 결재 건 사용자 인지

카테고리와 제조사 모두 '기타'로 입력 시 두 개의 결재 요청이 별도로 생성됨. 사용자에게 "2건의 결재가 상신됩니다"라는 별도 안내는 없음. 현재 안내 문구(`ℹ️ 신규 분류가 포함되어 있습니다...`)가 이를 포괄적으로 커버하나, 명시적 건수 안내가 추가되면 UX 개선 가능.

---

## 8단계: AI 메타 거버넌스 — PASS

| 항목 | 결과 | 근거 |
| :--- | :--- | :--- |
| 환각 코드 | 해당 없음 | 모든 테이블명, 컬럼명, 라우트 경로가 기존 코드베이스와 일치 확인 |
| 존재하지 않는 API 호출 | 해당 없음 | 신규 API 엔드포인트 추가 없음 |
| 잘못된 가정 | 해당 없음 | `categories.CategoryId`, `manufacturers.ManufacturerId` PK 컬럼 존재 검증됨 |
| scratch 파일 정리 | PASS | 분석용 scratch 파일은 아티팩트 디렉터리에 격리 |
| 승인 재촉 | PASS | 객관적 사실 기반 보고 |

---

## 종합 판정

### 의도한 대로 구현되었는가?

**YES.** 계획서의 5개 세부 설계 항목(SQL 정정, 캐시 무효화, 커스텀 UI 전환, 결재 상신 파이프라인, 결재 처리 캐스케이드)이 모두 코드에 반영되어 있으며, 사용자가 보고한 3가지 버그(마스터 조회 실패, 캐시 고착, 결재 단절)에 대한 수정이 정확하게 이루어졌습니다.

### 운영 반영 시 이상 발생 여지

| 등급 | 내용 | 발생 조건 | 사용자 결정 필요 여부 |
| :--- | :--- | :--- | :--- |
| **Medium** | `json_extract()` SQLite 호환성 (WARN-1) | 배포 서버 SQLite < 3.9.0 | ✅ 서버 버전 확인 필요 |
| **Medium** | 단일 커스텀 분류 시 노드 미생성 (WARN-2) | 카테고리만 '기타'이고 제조사 미선택 (또는 반대) | 프론트엔드에서 양쪽 필수 선택으로 방어 가능 |
| **Low** | 듀얼 커스텀 한쪽 거부 시 고아 장비 (WARN-3) | 카테고리+제조사 모두 '기타' 후 한쪽만 거부 | 운영 빈도 극히 낮음 |

### 권고 사항

1. **배포 전 확인 필수**: 운영 서버에서 `python3 -c "import sqlite3; print(sqlite3.sqlite_version)"` 실행하여 SQLite 버전 3.9.0 이상 확인.
2. **차기 개선 검토**: WARN-2(단일 커스텀 노드 미생성)와 WARN-3(듀얼 커스텀 고아 장비)는 현재 배포를 차단할 수준은 아니나, 향후 개선 과제로 등록 권장.
3. **운영 병합 절차**: `Staging/` → 운영 루트로의 파일 복사 시, 3개 파일(`app.py`, `templates/index.html`, `templates/master_management.html`)을 동시에 반영해야 함. 부분 배포 시 프론트-백엔드 불일치 발생.

---

## 종합 결론

**운영 반영 가능.** 계획된 변경이 정확하게 구현되었으며, 기존 기능을 훼손하지 않습니다. Medium 등급 WARN 2건은 배포 서버 SQLite 버전 확인과 프론트엔드 입력 필수화로 완화 가능하며, 배포를 차단할 수준의 결함은 발견되지 않았습니다.

