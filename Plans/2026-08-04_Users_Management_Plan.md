# 계정 삭제 후 화면 자동 갱신 미동작 버그 수정 계획서

본 문서는 관리자 사용자 관리 화면(`/users_management`)에서 계정 삭제(단일 삭제 및 다중 선택 삭제) 성공 후, 화면이 자동으로 갱신되지 않고 수동 새로고침(F5)을 해야만 삭제 결과가 반영되던 버그에 대한 원인 분석 및 개선 계획서입니다.

---

## 1. 현상 및 원인 분석 (Diagnostic Root Cause)

### 🔴 문제 현상
- 계정 삭제 버튼을 누르고 알림 확인(Confirm) 및 성공 메시지(Alert)를 받아도 테이블 목록에 삭제된 사용자가 그대로 남아있음.
- 사용자가 브라우저를 수동으로 새로고침(F5)해야만 비로소 목록에서 삭제된 계정이 사라짐.

### 🔍 근본 원인 (Root Cause)
1. **HTTP GET API 응답 캐싱 (Browser Cache / 304 Not Modified)**:
   - 기존 `fetchUsers()` 함수는 `fetch('/api/users')`로 단순 GET 요청을 수행합니다.
   - 브라우저에 따라 서버의 `/api/users` 응답을 캐싱하여, 삭제 API(`POST /api/users/delete_selected`)가 DB에서 성공적으로 레코드를 삭제했음에도 불구하고 `fetchUsers()` 호출 시 이전 캐시 데이터를 그대로 반환하는 현상이 발생합니다.
2. **UI 상태(체크박스 및 파기/삭제 버튼) 비동기 동기화 누락**:
   - `fetchUsers()`만 호출할 경우 `selectAllCheckbox` 및 선택된 유저 수 카운트 버튼(`btnDeleteSelected`, `btnForceSelected`)의 가시성 상태가 깔끔하게 리셋되지 않아 DOM 상태 불일치가 발생할 수 있습니다.

---

## 2. 개선 및 해결 방안 (Proposed Fix)

1. **캐시 방지(Cache-Busting) 파라미터 적용**:
   - `fetchUsers()` 호출 시 URL 뒤에 실시간 타임스탬프(`?_t=${Date.now()}`)를 부여하여 브라우저 캐시를 원천 차단하고 서버로부터 항상 최신 사용자 데이터 목록을 응답받도록 보완합니다.

2. **명시적 UI 상태 리셋 및 `location.reload()` 적용 (Flash 모델 제안)**:
   - `deleteSelectedUsers()` 및 `deleteSingleUser()` 삭제 성공 후, `location.reload()`를 호출하여 테이블, 체크박스, 선택 버튼 상태 전체를 100% 깨끗하고 안전하게 즉시 자동 새로고침(Refresh) 처리합니다.

---

## 3. [Gemini 3.1 Pro 리뷰] 개선안 검토 및 수정 지침

1. **캐시 방지(Cache-Busting) 파라미터 적용 (적절성: 최상 🟢)**:
   - `fetch('/api/users?_t=' + Date.now())` 기법은 브라우저의 HTTP 304 Not Modified 반환이나 메모리 캐싱을 완벽하게 차단하는 가장 훌륭하고 교과서적인 해결책입니다.
2. **`location.reload()` 사용 (적절성: 낮음 🔴)**:
   - **문제점**: 삭제 시마다 브라우저 전체가 새로고침되어 화면 깜빡임(FOUC)이 발생하고 서버에 CSS/JS/HTML을 재요청하므로, 모던 웹의 부드러운 UX(Single Page Application 방식)를 저해합니다.
   - **수정 지침**: 이미 캐시 방지(1번)가 적용되어 `fetchUsers()`가 무조건 최신 데이터를 가져오므로, 무식한 `location.reload()` 대신 **기존의 부드러운 DOM 상태 리셋 로직(`selectAllCheckbox.checked = false`, `toggleAllCheckboxes`, `fetchUsers()`)을 그대로 유지**하는 것이 훨씬 세련되고 성능상 유리합니다.

---

## 4. 수정 대상 파일 및 변경 사항 (Target Files)

- `Staging/Staging_users_management.html` (운영 대상: `templates/users_management.html`)
  - `fetchUsers()` 내 캐시 방지 타임스탬프 추가 (`?_t=${Date.now()}`)
  - 삭제 처리 후 `location.reload()` 대신 부드러운 비동기 DOM 리셋(`fetchUsers()`) 유지

---

*본 계획서 및 스테이징 소스는 사용자 검토 후 승인 시 운영 프로덕션 소스코드에 합병(Merge)됩니다.*
