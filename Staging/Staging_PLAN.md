# 스마트 동적 네비게이션(이전 화면 / 포털 복귀) UX 개선 계획서

본 문서는 사용자가 메인 포털에서 특정 메뉴(예: 대시보드, 장비 관리)로 이동한 후, 상단 '내 정보'(`/mypage`) 등 서브 유틸리티 화면으로 진입했을 때 상단 뒤로가기 버튼이 항상 메인 포털(`/portal`)로만 이동하여 부자연스러웠던 UX 이동 동선을 개선하기 위한 기술적 검토 및 구현 계획서입니다.

---

## 1. 개요 및 문제 진단

### 1.1 현재 상황 (Current Behavior)
- `miniserver_frame.html`에 상단 뒤로가기 버튼이 `<a href="/portal">← 포털로</a>` 형태로 고정 하드코딩되어 있습니다.
- **이동 시나리오 비교**:
  - `포털` ➡️ `대시보드` ➡️ `← 포털로` 클릭 ➡️ `포털` 도착 (**자연스러움**)
  - `포털` ➡️ `대시보드` ➡️ `내 정보(마이페이지)` ➡️ `← 포털로` 클릭 ➡️ `포털` 도착 (**부자연스러움**: 직전에 작업하던 `대시보드`로 돌아가지 못하고 포털로 튕겨 나감)

### 1.2 개선 목표 (Goal)
- 사용자가 어디에서 `내 정보` 또는 기타 유틸리티 페이지에 진입했는지 맥락(Context)을 인지하여, 직전 메뉴가 있을 경우 **"← 이전으로" (직전 메뉴 복귀)**, 직전 메뉴가 없거나 포털인 경우 **"← 포털로" (포털 복귀)**가 동적으로 유연하게 동작하도록 개선합니다.

---

## 2. 기술적 대안 검토 (Alternatives Analysis)

### 🟢 대안 A: `document.referrer` 및 `history.back()` 기반 동적 처리
- **동작**: 브라우저의 DOM `document.referrer` 또는 `window.history.back()`을 활용하여 뒤로가기 수행.
- **장점**: 별도의 백엔드 수정이나 URL 쿼리 파라미터 전달 없이 프론트엔드 JS 단에서 즉시 적용 가능.
- **단점**: 사용자가 주소창에 URL을 직접 입력해 진입했거나, 새로고침을 수행했거나, 외부 페이지에서 진입한 경우 `referrer`가 소실되거나 올바르지 않을 수 있음.

### 🟢 대안 B: URL Query Parameter (`?from=...`) 기반 명시적 이전 경로 전달
- **동작**: `miniserver_frame.html` 내 '내 정보' 링크를 `href="/mypage"` 대신 JS로 현재 페이지 경로(`location.pathname`)를 포함하여 `/mypage?from=/dashboard` 형태로 생성.
- **장점**: 100% 신뢰할 수 있는 이전 경로가 명시적으로 전달되므로 새로고침을 하더라도 직전 메뉴 복귀 경로가 유지됨.
- **단점**: 마이페이지 진입 URL에 쿼리 스트링이 노출됨.

### 🟢 대안 C: 템플릿 Block 오버라이딩 + JS Hybrid 연동 (최고 권장안)
- **동작**: 
  1. `miniserver_frame.html` 기본 버튼을 스마트 뒤로가기 컴포넌트로 구성.
  2. `document.referrer`가 존재하고 동일 도메인이며 포털(`/portal`)이 아닌 경우 ➡️ **"← 이전으로"** 표출 및 `history.back()` 수행.
  3. 그 외(포털에서 직접 들어왔거나 referrer 없음) ➡️ **"← 포털로"** 표출 및 `/portal` 이동.
  4. 필요 시 특정 페이지에서 `{% block back_to_portal_link %}`로 개별 제어 가능.

---

## 3. 상세 구현 계획 (Proposed Changes)

### 3.1 `miniserver_frame.html` 수정
- 상단 뒤로가기 버튼 영역을 스마트 동적 버튼으로 변경:
```html
{% block back_to_portal_link %}
<a id="smart-back-btn" href="/portal" class="text-xs sm:text-sm font-medium text-slate-600 dark:text-slate-300 hover:text-brand-500 dark:hover:text-brand-400 transition flex items-center gap-1 mr-1 sm:mr-2">
    <i id="smart-back-icon" class="fa-solid fa-arrow-left text-xs"></i>
    <span id="smart-back-text" class="hidden sm:inline">포털로</span>
</a>
{% endblock %}
```

- `session_timer.js` 또는 `miniserver_frame.html` 하단에 스마트 버튼 바인딩 스크립트 추가:
```javascript
document.addEventListener('DOMContentLoaded', () => {
    const backBtn = document.getElementById('smart-back-btn');
    const backText = document.getElementById('smart-back-text');
    
    if (backBtn && backText) {
        const ref = document.referrer;
        const currentHost = window.location.host;
        
        // 동일 도메인에서 왔고, 직전 페이지가 포털(/portal)이나 자기자신이 아닌 경우
        if (ref && ref.includes(currentHost) && !ref.endsWith('/portal') && !ref.endsWith(window.location.pathname)) {
            backText.textContent = '이전으로';
            backBtn.addEventListener('click', (e) => {
                e.preventDefault();
                window.history.back();
            });
        }
    }
});
```

---

## 4. 검증 및 테스트 계획 (Verification Plan)

1. **시나리오 1**: `포털` ➡️ `대시보드` ➡️ `포털로` 클릭 ➡️ `포털` 이동 확인.
2. **시나리오 2**: `포털` ➡️ `대시보드` ➡️ `내 정보` ➡️ `이전으로` 클릭 ➡️ `대시보드` 복귀 확인.
3. **시나리오 3**: `포털` ➡️ `장비 관리` ➡️ `권한 관리` ➡️ `내 정보` ➡️ `이전으로` 클릭 ➡️ `권한 관리` 복귀 확인.
4. **시나리오 4**: 주소창에 `/mypage` 직접 입력 진입 ➡️ `포털로` 표출 및 `/portal` 이동 확인.
